import argparse
import asyncio
import base64
import functools
import json
import logging
import os
import struct
import sys
import ipaddress
from typing import Any, Dict, List, Tuple, Union

from someipy._internal.message_types import MessageType
from someipy._internal.someip_endpoint import (
    SomeipEndpoint,
    TCPSomeipEndpoint,
    UDPSomeipEndpoint,
)
from someipy._internal.someip_endpoint_storage import SomeipEndpointStorage
from someipy._internal.someip_message import SomeIpMessage
from someipy._internal.tcp_client_manager import TcpClientManager, TcpClientProtocol
from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy._internal.session_handler import SessionHandler
from someipy._internal.simple_timer import SimplePeriodicTimer
from someipy._internal.someip_header import SomeIpHeader
from someipy._internal.someip_sd_builder import (
    build_offer_service_sd_header,
    build_stop_offer_service_sd_header,
    build_subscribe_eventgroup_ack_entry,
    build_subscribe_eventgroup_ack_sd_header,
    build_subscribe_eventgroup_sd_header,
)
from someipy._internal.someip_sd_extractors import (
    extract_offered_services,
    extract_subscribe_ack_eventgroup_entries,
    extract_subscribe_entries,
    extract_subscribe_nack_eventgroup_entries,
)
from someipy._internal.someip_sd_header import (
    SdEventGroupEntry,
    SdService,
    SdSubscription,
    SomeIpSdHeader,
)
from someipy._internal.store_with_timeout import StoreWithTimeout
from someipy._internal.subscribers import EventGroupSubscriber, Subscribers
from someipy._internal.uds_messages import (
    CallMethodRequest,
    CallMethodResponse,
    OfferServiceRequest,
    StopOfferServiceRequest,
    SubscribeEventgroupReadyRequest,
    SubscribeEventgroupReadyResponse,
    create_uds_message,
)
from someipy._internal.utils import (
    DatagramAdapter,
    create_rcv_multicast_socket,
    create_udp_socket,
)
from someipy._internal.offer_service_storage import OfferServiceStorage, ServiceToOffer
from someipy.service import Method


DEFAULT_SOCKET_PATH = "/tmp/someipyd.sock"
DEFAULT_CONFIG_FILE = "someipyd.json"
DEFAULT_SD_ADDRESS = "224.224.224.245"
DEFAULT_INTERFACE_IP = "127.0.0.2"
DEFAULT_SD_PORT = 30490


class RequestedSubscription:
    def __init__(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        client_endpoint_ip: str,
        client_endpoint_port: int,
        protocol: TransportLayerProtocol,
        eventgroup_id: int,
        ttl_subscription: int,
    ):
        self.service_id = service_id
        self.instance_id = instance_id
        self.major_version = major_version
        self.client_endpoint_ip = client_endpoint_ip
        self.client_endpoint_port = client_endpoint_port
        self.protocol = protocol
        self.eventgroup_id = eventgroup_id
        self.ttl = ttl_subscription

    def __eq__(self, other: "RequestedSubscription") -> bool:
        return (
            self.service_id == other.service_id
            and self.instance_id == other.instance_id
            and self.major_version == other.major_version
            and self.protocol == other.protocol
            and self.eventgroup_id == other.eventgroup_id
            and self.client_endpoint_ip == other.client_endpoint_ip
            and self.client_endpoint_port == other.client_endpoint_port
            and self.ttl == other.ttl
        )


class RequestedSubscriptionStore:

    def __init__(self):
        self._subscriptions_by_client: Dict[int, List[RequestedSubscription]] = {}

    def add_subscription(self, writer_id: int, subscription: RequestedSubscription):
        if writer_id not in self._subscriptions_by_client:
            self._subscriptions_by_client[writer_id] = []
            self._subscriptions_by_client[writer_id].append(subscription)

        else:
            if subscription not in self._subscriptions_by_client[writer_id]:
                self._subscriptions_by_client[writer_id].append(subscription)

    def remove_subscription(self, writer_id: int, subscription: RequestedSubscription):
        if writer_id in self._subscriptions_by_client:
            if subscription in self._subscriptions_by_client[writer_id]:
                self._subscriptions_by_client[writer_id].remove(subscription)

                if len(self._subscriptions_by_client[writer_id]) == 0:
                    del self._subscriptions_by_client[writer_id]

    def has_subscriptions(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        protocol: TransportLayerProtocol,
    ) -> List[Tuple[RequestedSubscription, int]]:
        """
        Check if there are any subscriptions for the given service id, instance id, major version and protocol.
        Returns a list of tuples containing the subscription and the writer id (UDS client).
        """
        subscriptions_to_return = []
        for writer_id, subscriptions in self._subscriptions_by_client.items():
            for subscription in subscriptions:
                if (
                    subscription.service_id == service_id
                    and subscription.instance_id == instance_id
                    and subscription.major_version == major_version
                    and subscription.protocol == protocol
                ):
                    subscriptions_to_return.append((subscription, writer_id))

        return subscriptions_to_return

    def remove_client(self, writer_id: int):
        if writer_id in self._subscriptions_by_client:
            del self._subscriptions_by_client[writer_id]


class SomeipDaemon:

    def __init__(self, config_file=None):
        self.logger = self._configure_logging()
        self.config = self._load_config(config_file)
        self.socket_path = self.config.get("socket_path", DEFAULT_SOCKET_PATH)
        self.sd_address = self.config.get("sd_address", DEFAULT_SD_ADDRESS)
        self.sd_port = self.config.get("sd_port", DEFAULT_SD_PORT)
        self.interface = self.config.get("interface", DEFAULT_INTERFACE_IP)

        self.logger.info(
            f"Starting SOME/IP Daemon with config:\n"
            f"Socket path: {self.socket_path}\n"
            f"SD address: {self.sd_address}\n"
            f"SD port: {self.sd_port}\n"
            f"Interface: {self.interface}\n"
        )

        self.sd_socket_mcast = None
        self.sd_socket_ucast = None
        self.mcast_transport = None
        self.ucast_transport = None

        # Services offered by other ECUs
        self._offered_services = StoreWithTimeout()

        # Services offered by this daemon
        self._services_to_offer = OfferServiceStorage()
        self._offer_timers: Dict[int, SimplePeriodicTimer] = {}

        # Active subscriptions to services offered by this daemon
        self._service_subscribers: Dict[SdService, Subscribers] = {}

        # Subscriptions requested by local clients
        self._requested_subscriptions = RequestedSubscriptionStore()

        self._mcast_session_handler = SessionHandler()
        self._unicast_session_handler = SessionHandler()

        # Qeueues and tasks stored by id of asyncio.StreamWriter
        self._tx_queues: Dict[int, asyncio.Queue] = {}
        self._tx_tasks: Dict[int, asyncio.Task] = {}
        self._rx_queues: Dict[int, asyncio.Queue] = {}

        self._someip_endpoints = SomeipEndpointStorage()

    def _configure_logging(self):
        logger = logging.getLogger(f"someipyd")
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d %(name)s [%(levelname)s]: %(message)s",
            datefmt="%Y-%m-%d,%H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        logger.setLevel(logging.DEBUG)
        return logger

    def _load_config(self, config_file):
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                self.logger.error(f"Error loading config file: {e}. Using defaults.")
                return {}
        elif os.path.exists(DEFAULT_CONFIG_FILE):
            try:
                with open(DEFAULT_CONFIG_FILE, "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                self.logger.error(f"Error loading config file: {e}. Using defaults.")
                return {}
        else:
            return {}

    async def _create_server_endpoint(
        self, ip: str, port: int, protocol: TransportLayerProtocol
    ) -> SomeipEndpoint:

        if protocol == TransportLayerProtocol.UDP:
            loop = asyncio.get_running_loop()
            rcv_socket = create_udp_socket(ip, port)

            _, udp_endpoint = await loop.create_datagram_endpoint(
                lambda: UDPSomeipEndpoint(ip, port), sock=rcv_socket
            )

            udp_endpoint.set_someip_callback(self._someip_message_callback)

            return udp_endpoint
        else:
            tcp_client_manager = TcpClientManager(ip, port)
            loop = asyncio.get_running_loop()
            server = await loop.create_server(
                lambda: TcpClientProtocol(client_manager=tcp_client_manager),
                ip,
                port,
            )
            tcp_someip_endpoint = TCPSomeipEndpoint(
                server, tcp_client_manager, ip, port
            )

            tcp_someip_endpoint.set_someip_callback(self._someip_message_callback)

            return tcp_someip_endpoint

    def _someip_message_callback(
        self,
        message: SomeIpMessage,
        src_addr: Tuple[str, int],
        dst_addr: Tuple[str, int],
        protocol: TransportLayerProtocol,
    ) -> None:
        self.logger.debug(
            f"Received SOME/IP message from {src_addr} to {dst_addr} with protocol {protocol}"
        )

        header = message.header
        print(f"message_type {header.message_type}")
        if MessageType(header.message_type) == MessageType.REQUEST:
            service_id = header.service_id
            method_id = header.method_id

            for service in self._services_to_offer.get_all_services():

                if (
                    service.service_id == service_id
                    and service.endpoint_ip == dst_addr[0]
                    and service.endpoint_port == dst_addr[1]
                ):
                    self.logger.debug(f"Found matching service {service.service_id}")
                    for method in service.methods:
                        if method.id == method_id:
                            self.logger.debug(
                                f"Found matching method id {method.id} for service {service_id}"
                            )

                            payload_encoded = base64.b64encode(message.payload).decode(
                                "utf-8"
                            )

                            print(header)

                            call_method_request = create_uds_message(
                                CallMethodRequest,
                                service_id=service_id,
                                instance_id=service.instance_id,
                                method_id=method_id,
                                client_id=header.client_id,
                                session_id=header.session_id,
                                protocol_version=header.protocol_version,
                                interface_version=header.interface_version,
                                major_version=service.major_version,
                                minor_version=service.minor_version,
                                message_type=header.message_type,
                                src_endpoint_ip=src_addr[0],
                                src_endpoint_port=src_addr[1],
                                protocol=protocol.value,
                                payload=payload_encoded,
                            )

                            tx_queue = self._tx_queues.get(service.client_writer_id)
                            if tx_queue:
                                tx_queue.put_nowait(
                                    self.prepare_message(call_method_request)
                                )

    def _cleanup_unused_timers(self):
        timers_to_stop = []
        for interval in self._offer_timers.keys():
            if (
                len(self._services_to_offer.services_by_cyclic_offer_delay(interval))
                == 0
            ):
                timers_to_stop.append(interval)
        for interval in timers_to_stop:
            self.logger.debug(f"Stopping offer timer for {interval}ms")
            self._offer_timers[interval].stop()
            del self._offer_timers[interval]

    def _close_unused_endpoints(self):
        endpoints_to_close = []

        # Loop through all endpoints. For each endpoint loop through offered services and check if the endpoint is used by any service
        for endpoint in self._someip_endpoints:
            endpoint_used = False
            for service in self._services_to_offer.services:
                if (
                    service.endpoint_ip == endpoint.ip()
                    and service.endpoint_port == endpoint.port()
                ):
                    endpoint_used = True
                    break

            if not endpoint_used:
                endpoints_to_close.append(endpoint)

    async def tx_task(self, writer: asyncio.StreamWriter):
        tx_queue = self._tx_queues[id(writer)]

        try:
            while True:
                try:
                    # Wait on queue with timeout
                    data = await asyncio.wait_for(tx_queue.get(), timeout=0.2)

                    try:
                        # Send the data
                        writer.write(data)
                        await writer.drain()
                        tx_queue.task_done()
                    except ConnectionError as e:
                        self.logger.error(f"Error sending data in tx task: {e}")
                        break

                except asyncio.TimeoutError:
                    # Periodic timeout for cancellation check
                    continue

        except asyncio.CancelledError:
            self.logger.debug(f"TX task for writer {id(writer)} cancelled")
            # Perform cleanup here
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                self.logger.error(f"Error closing writer: {e}")
        finally:
            # Always clean up the queue
            self._tx_queues.pop(id(writer), None)
            self.logger.debug(f"TX task for writer {id(writer)} finished")

    async def handle_client(self, reader, writer):
        self.logger.info(f"Client connected")
        writer_id = id(writer)

        # Create the tx_queue and tx_task for the client using the writers id
        self._tx_queues[writer_id] = asyncio.Queue()
        self._tx_tasks[writer_id] = asyncio.create_task(self.tx_task(writer))
        self._rx_queues[writer_id] = asyncio.Queue()

        try:
            wait_for_header = True
            header_buffer = b""
            message_buffer = b""
            message_length = 0

            while True:
                if wait_for_header:
                    data = await reader.read(256 - len(header_buffer))
                    if not data:
                        self.logger.debug(f"Data is none. Client disconnected.")
                        break  # Client disconnected

                    header_buffer += data

                    if len(header_buffer) == 256:
                        try:
                            message_length = struct.unpack("<I", header_buffer[:4])[
                                0
                            ]  # read the first 4 bytes as unsigned int little endian.
                        except struct.error:
                            self.logger.error(f"Client sent invalid message length.")
                            break

                        wait_for_header = False
                        message_buffer = b""  # reset the message buffer
                    elif len(header_buffer) > 256:
                        self.logger.error(f"Client sent too much header data.")
                        break

                else:
                    data = await reader.read(message_length - len(message_buffer))
                    if not data:
                        self.logger.debug(f"Data is none. Client disconnected.")
                        break  # Client disconnected

                    message_buffer += data

                    if len(message_buffer) == message_length:

                        self.logger.debug(f"Client sent message: {message_buffer}")
                        json_message = json.loads(message_buffer.decode("utf-8"))
                        await self.handle_client_message(json_message, writer)

                        wait_for_header = True
                        header_buffer = b""  # reset header buffer
                        message_buffer = b""  # reset message buffer
                        message_length = 0  # reset message length
                    elif len(message_buffer) > message_length:
                        self.logger.error(f"Client sent too much message data.")
                        break
        except ConnectionResetError:
            self.logger.error(f"Client disconnected abruptly.")
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
        finally:

            # Remove all subscriptions for the client
            self._requested_subscriptions.remove_client(writer_id)

            # Clean up the transmission task for the client. This will also clean up the transmission queue
            tx_task = self._tx_tasks.get(writer_id)
            if tx_task and not tx_task.cancelled():
                tx_task.cancel()
                try:
                    await tx_task
                except asyncio.CancelledError:
                    pass

            self._rx_queues.pop(writer_id, None)

            self._services_to_offer.remove_client(writer_id)
            self._cleanup_unused_timers()

            client_endpoints = self._someip_endpoints.get_endpoints(writer_id)
            if client_endpoints is not None:
                for endpoint in client_endpoints:
                    self.logger.debug(
                        f"Closing endpoint {endpoint.ip()}:{endpoint.port()} for client {writer_id}"
                    )
                    endpoint.shutdown()
                    self._someip_endpoints.remove_endpoint(writer_id, endpoint)

            self.logger.debug(f"Client disconnected")

    async def handle_client_message(self, message: dict, writer: asyncio.StreamWriter):
        writer_id = id(writer)

        message_type = message.get("type")
        self.logger.debug(f"Received message type: {message_type}")

        message_handlers = {
            OfferServiceRequest.__name__: self._handle_offer_service_request,
            StopOfferServiceRequest.__name__: self._handle_stop_offer_service_request,
            CallMethodResponse.__name__: self._handle_call_method_response,
        }

        if message_type in message_handlers:
            handler = message_handlers[message_type]

            if asyncio.iscoroutinefunction(handler):
                await handler(message, writer_id)
                return
            else:
                handler(message, writer_id)
                return

        elif message_type == "get_eventgroup_subscriptions_req":
            for sub in self._service_subscribers.values():
                sub.update()

            service = SdService.from_json(message["service"])
            eventgroup_id = message["eventgroup_id"]
            answer = {"type": "get_eventgroup_subscriptions_res", "subscriptions": []}

            if service in self._service_subscribers:
                for subscriber in self._service_subscribers[service].subscribers:
                    if subscriber.eventgroup_id == eventgroup_id:
                        answer["subscriptions"].append(
                            {
                                "endpoint_ip": str(subscriber.endpoint[0]),
                                "endpoint_port": subscriber.endpoint[1],
                            }
                        )

            tx_queue = self._tx_queues[writer_id]
            tx_queue.put_nowait(self.prepare_message(answer))

        elif message_type == "subscribe_eventgroup_req":

            service_id = int(message["service_id"])
            instance_id = int(message["instance_id"])
            major_version = int(message["major_version"])
            client_endpoint_ip = message["client_endpoint_ip"]
            client_endpoint_port = int(message["client_endpoint_port"])
            eventgroup_id = int(message["eventgroup_id"])
            ttl_subscription = int(message["ttl_subscription"])
            protocol = TransportLayerProtocol(message["protocol"])

            self._requested_subscriptions.add_subscription(
                id(writer),
                RequestedSubscription(
                    service_id,
                    instance_id,
                    major_version,
                    client_endpoint_ip,
                    client_endpoint_port,
                    protocol,
                    eventgroup_id,
                    ttl_subscription,
                ),
            )

        else:
            self.logger.warning(
                f"Received unknown message type: {message_type}. Message: {message}"
            )

    def _handle_client_message_subscribe_eventgroup_ready_res(
        self, message: SubscribeEventgroupReadyResponse
    ):
        if message["success"] == True:
            # Build a subscribe message and send it via unicast UDP
            (
                session_id,
                reboot_flag,
            ) = self._unicast_session_handler.update_session()

            client_endpoint_ip = message["client_endpoint_ip"]
            client_endpoint_port = message["client_endpoint_port"]

            service_id = message["service_id"]
            instance_id = message["instance_id"]
            ttl_subscription = message["ttl_subscription"]
            major_version = message["major_version"]
            protocol = TransportLayerProtocol(message["protocol"])
            eventgroup_id = message["eventgroup_id"]
            service_endpoint_ip = message["service_endpoint_ip"]

            # Build Subscribe header and send it out
            subscribe_sd_header = build_subscribe_eventgroup_sd_header(
                service_id=service_id,
                instance_id=instance_id,
                major_version=major_version,
                ttl=ttl_subscription,
                event_group_id=eventgroup_id,
                session_id=session_id,
                reboot_flag=reboot_flag,
                endpoint=(
                    ipaddress.IPv4Address(client_endpoint_ip),
                    client_endpoint_port,
                ),
                protocol=protocol,
            )
            if self.ucast_transport:

                self.logger.debug(
                    f"Send subscribe message for service 0x{service_id:04x}, instance 0x{instance_id:04x} to {service_endpoint_ip}:{self.sd_port}"
                )
                self.ucast_transport.sendto(
                    subscribe_sd_header.to_buffer(),
                    (service_endpoint_ip, self.sd_port),
                )

    async def _handle_offer_service_request(
        self, message: OfferServiceRequest, writer_id: int
    ):
        method_strs = message.get("method_list", [])
        methods = [Method.from_json(m) for m in method_strs]

        service_to_add = ServiceToOffer(
            client_writer_id=writer_id,
            instance_id=message["instance_id"],
            service_id=message["service_id"],
            major_version=message["major_version"],
            minor_version=message["minor_version"],
            offer_ttl_seconds=message["ttl"],
            cyclic_offer_delay_ms=message["cyclic_offer_delay_ms"],
            endpoint_ip=message["endpoint_ip"],
            endpoint_port=message["endpoint_port"],
            methods=methods,
        )

        self._services_to_offer.add_service(service_to_add)

        # Check if there is already an endpoint for the ip and port, if not, open a new endpoint
        if service_to_add.has_udp:
            if not self._someip_endpoints.has_endpoint(
                service_to_add.endpoint_ip,
                service_to_add.endpoint_port,
                TransportLayerProtocol.UDP,
            ):
                self.logger.debug(
                    f"Creating new UDP endpoint for {service_to_add.endpoint_ip}:{service_to_add.endpoint_port}"
                )

                udp_endpoint = await self._create_server_endpoint(
                    service_to_add.endpoint_ip,
                    service_to_add.endpoint_port,
                    TransportLayerProtocol.UDP,
                )
                self._someip_endpoints.add_endpoint(writer_id, udp_endpoint)

        if service_to_add.has_tcp:
            if not self._someip_endpoints.has_endpoint(
                service_to_add.endpoint_ip,
                service_to_add.endpoint_port,
                TransportLayerProtocol.TCP,
            ):
                self.logger.debug(
                    f"Creating new TCP endpoint for {service_to_add.endpoint_ip}:{service_to_add.endpoint_port}"
                )

                tcp_endpoint = await self._create_server_endpoint(
                    service_to_add.endpoint_ip,
                    service_to_add.endpoint_port,
                    TransportLayerProtocol.TCP,
                )
                self._someip_endpoints.add_endpoint(writer_id, tcp_endpoint)

        cyclic_offer_delay_ms = message["cyclic_offer_delay_ms"]

        # If there is no timer running for the interval yet, create a new timer task
        if cyclic_offer_delay_ms not in self._offer_timers:
            self.logger.debug(f"Starting offer timer for {cyclic_offer_delay_ms}ms")
            self._offer_timers[cyclic_offer_delay_ms] = SimplePeriodicTimer(
                cyclic_offer_delay_ms / 1000.0,
                functools.partial(self.offer_timer_callback, cyclic_offer_delay_ms),
            )
            self._offer_timers[cyclic_offer_delay_ms].start()

    def _handle_stop_offer_service_request(
        self, message: StopOfferServiceRequest, writer_id: int
    ):
        method_strs = message.get("method_list", [])
        methods = [Method.from_json(m) for m in method_strs]

        service_to_stop = ServiceToOffer(
            client_writer_id=writer_id,
            instance_id=message["instance_id"],
            service_id=message["service_id"],
            major_version=message["major_version"],
            minor_version=message["minor_version"],
            offer_ttl_seconds=message["ttl"],
            cyclic_offer_delay_ms=message["cyclic_offer_delay_ms"],
            endpoint_ip=message["endpoint_ip"],
            endpoint_port=message["endpoint_port"],
            methods=methods,
        )

        # Remove the service from the storage
        self._services_to_offer.remove_service(service_to_stop)
        self._cleanup_unused_timers()

        (
            session_id,
            reboot_flag,
        ) = self._mcast_session_handler.update_session()

        sd_header = build_stop_offer_service_sd_header(
            [service_to_stop], session_id, reboot_flag
        )
        buffer = sd_header.to_buffer()
        if self.ucast_transport:
            self.logger.debug(
                f"Send stop offer message for service 0x{service_to_stop.service_id:04x}, instance 0x{service_to_stop.instance_id:04x} to {self.sd_address}:{self.sd_port}"
            )
            self.ucast_transport.sendto(buffer, (self.sd_address, self.sd_port))

        if service_to_stop.has_udp:
            try:
                udp_endpoint = self._someip_endpoints.get_endpoint(
                    writer_id, TransportLayerProtocol.UDP
                )
                if udp_endpoint:
                    self.logger.debug(
                        f"Closing UDP endpoint for {service_to_stop.endpoint_ip}:{service_to_stop.endpoint_port}"
                    )
                    udp_endpoint.shutdown()
                    self._someip_endpoints.remove_endpoint(writer_id, udp_endpoint)
            except Exception as e:
                self.logger.error(
                    f"Error closing UDP endpoint for {service_to_stop.endpoint_ip}:{service_to_stop.endpoint_port}: {e}"
                )

        if service_to_stop.has_tcp:
            try:
                tcp_endpoint = self._someip_endpoints.get_endpoint(
                    writer_id, TransportLayerProtocol.TCP
                )
                if tcp_endpoint:
                    self.logger.debug(
                        f"Closing TCP endpoint for {service_to_stop.endpoint_ip}:{service_to_stop.endpoint_port}"
                    )
                    tcp_endpoint.shutdown()
                    self._someip_endpoints.remove_endpoint(writer_id, tcp_endpoint)
            except Exception as e:
                self.logger.error(
                    f"Error closing TCP endpoint for {service_to_stop.endpoint_ip}:{service_to_stop.endpoint_port}: {e}"
                )

    def _handle_call_method_response(self, message: CallMethodResponse, writer_id: int):
        self.logger.debug(f"Received CallMethodResponse: {message}")

        header = SomeIpHeader(
            service_id=message["service_id"],
            method_id=message["method_id"],
            length=0,
            client_id=message["client_id"],
            session_id=message["session_id"],
            protocol_version=message["protocol_version"],
            interface_version=message["interface_version"],
            message_type=message["message_type"],
            return_code=message["return_code"],
        )

        payload_decoded = base64.b64decode(message["payload"])
        header.length = 8 + len(payload_decoded)

        endpoint = self._someip_endpoints.get_endpoint(
            writer_id, TransportLayerProtocol(message["protocol"])
        )
        self.logger.debug(
            f"Sending CallMethodResponse to {message['src_endpoint_ip']}:{message['src_endpoint_port']}"
        )

        print(header)
        if endpoint:
            endpoint.sendto(
                header.to_buffer() + payload_decoded,
                (message["src_endpoint_ip"], message["src_endpoint_port"]),
            )

    def offer_timer_callback(self, cyclic_offer_delay_ms: int):
        self.logger.debug(f"Offer timer callback for {cyclic_offer_delay_ms}ms")

        services_to_offer: List[ServiceToOffer] = (
            self._services_to_offer.services_by_cyclic_offer_delay(
                cyclic_offer_delay_ms
            )
        )
        if len(services_to_offer) > 0:
            (
                session_id,
                reboot_flag,
            ) = self._mcast_session_handler.update_session()

            sd_message = build_offer_service_sd_header(
                services_to_offer, session_id, reboot_flag
            )
            buffer = sd_message.to_buffer()

            if self.ucast_transport:
                self.ucast_transport.sendto(buffer, (self.sd_address, self.sd_port))

    def prepare_message(self, message: dict):
        payload = json.dumps(message).encode("utf-8")
        return struct.pack("<I", len(payload)) + bytes(256 - 4) + payload

    async def send_to_all_clients(self, message):
        for writer in self.clients:
            try:
                writer.write(message)
                await writer.drain()
            except ConnectionError:
                self.logger.error("Error sending message to client.")
                self.clients.remove(writer)
                writer.close()
                await writer.wait_closed()

    async def start_server(self):
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        server = await asyncio.start_unix_server(
            self.handle_client, path=self.socket_path
        )
        self.logger.info(f"Unix domain socket server started at {self.socket_path}")

        try:
            await self.start_sd_listening()
            async with server:
                await server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            if self.mcast_transport:
                self.mcast_transport.close()
            if self.ucast_transport:
                self.ucast_transport.close()
            self.logger.info("UDS server stopped.")

    def _timeout_of_offered_service(self, offered_service: SdService):
        self.logger.info(
            f"Offered service timed out: service id 0x{offered_service.service_id:04x}, instance id 0x{offered_service.instance_id:04x}"
        )

        # TODO: If clients subscribed to this service, remove all subscriptions

    async def wait_for_message_in_rx_queue(
        self, rx_queue: asyncio.Queue, msg_type: str, timeout: int = 1.0
    ) -> dict:

        messages_to_keep = []
        found_message = None
        message_found = False

        while not message_found:
            try:
                msg = await asyncio.wait_for(rx_queue.get(), timeout=timeout)

                if msg.get("type") == msg_type:
                    found_message = msg
                    message_found = True
                else:
                    messages_to_keep.append(msg)
            except asyncio.TimeoutError:
                # Put all non-target messages back in the queue
                for msg in messages_to_keep:
                    await rx_queue.put(msg)
                return None

        # Put all non-target messages back in the queue
        for msg in messages_to_keep:
            await rx_queue.put(msg)

        return found_message

    def handle_offered_service(self, offered_service: SdService):
        self.logger.info(f"Received offered service: {offered_service}")
        t = asyncio.create_task(
            self._offered_services.add(
                offered_service, self._timeout_of_offered_service
            )
        )

        requested_subscriptions = self._requested_subscriptions.has_subscriptions(
            offered_service.service_id,
            offered_service.instance_id,
            offered_service.major_version,
            offered_service.protocol,
        )

        if len(requested_subscriptions) > 0:
            for subscription, writer_id in requested_subscriptions:
                message = create_uds_message(
                    SubscribeEventgroupReadyRequest,
                    service_id=offered_service.service_id,
                    instance_id=offered_service.instance_id,
                    major_version=offered_service.major_version,
                    client_endpoint_ip=subscription.client_endpoint_ip,
                    client_endpoint_port=subscription.client_endpoint_port,
                    eventgroup_id=subscription.eventgroup_id,
                    ttl_subscription=subscription.ttl,
                    protocol=subscription.protocol.value,
                    service_endpoint_ip=str(offered_service.endpoint[0]),
                    service_endpoint_port=offered_service.endpoint[1],
                )

                tx_queue = self._tx_queues[writer_id]
                tx_queue.put_nowait(self.prepare_message(message))

    def handle_subscription(
        self,
        sd_subscription: SdSubscription,
    ):
        # TODO: Send back a nack message if no service is found

        self.logger.info(f"Received subscription: {SdSubscription}")

        for sub in self._service_subscribers.values():
            sub.update()

        # From SD specification:
        # [PRS_SOMEIPSD_00829] When receiving a SubscribeEventgroupAck or Sub-
        # scribeEventgroupNack the Service ID, Instance ID, Eventgroup ID, and Major Ver-
        # sion shall match exactly to the corresponding SubscribeEventgroup Entry to identify
        # an Eventgroup of a Service Instance.
        # Check if the service id, the instance and the major version is in the list of offered services
        # If yes, check if the eventgroup id is in the list of eventgroup ids
        # If yes, subscribe to the eventgroup
        for service_wrapper in self._services_to_offer.service_wrappers:
            service = service_wrapper.sd_service
            if (
                service.service_id == sd_subscription.service_id
                and service.instance_id == sd_subscription.instance_id
                and sd_subscription.eventgroup_id in service_wrapper.eventgroup_ids
                and sd_subscription.protocol == service.protocol
            ):
                self.logger.info(
                    f"Subscription to eventgroup 0x{sd_subscription.eventgroup_id:04X} of service 0x{service.service_id:04X}, instance 0x{service.instance_id:04X} requested."
                )
                (
                    session_id,
                    reboot_flag,
                ) = self._unicast_session_handler.update_session()
                ack_entry = build_subscribe_eventgroup_ack_entry(
                    service_id=service.service_id,
                    instance_id=service.instance_id,
                    major_version=service.major_version,
                    ttl=service.ttl,
                    event_group_id=sd_subscription.eventgroup_id,
                )
                header_output = build_subscribe_eventgroup_ack_sd_header(
                    entry=ack_entry,
                    session_id=session_id,
                    reboot_flag=reboot_flag,
                )
                self.logger.info(
                    f"Sending subscribe ack for eventgroup 0x{sd_subscription.eventgroup_id:04X} of service 0x{service.service_id:04X} instance 0x{service.instance_id:04X} to {sd_subscription.ipv4_address}:{sd_subscription.port}"
                )
                if self.ucast_transport:
                    self.ucast_transport.sendto(
                        data=header_output.to_buffer(),
                        addr=(
                            str(sd_subscription.ipv4_address),
                            self.sd_port,
                        ),
                    )
                    if service not in self._service_subscribers:
                        self._service_subscribers[service] = Subscribers()
                    self._service_subscribers[service].add_subscriber(
                        EventGroupSubscriber(
                            eventgroup_id=sd_subscription.eventgroup_id,
                            endpoint=(
                                sd_subscription.ipv4_address,
                                sd_subscription.port,
                            ),
                            ttl=sd_subscription.ttl,
                        )
                    )

    def _handle_sd_subscribe_ack_eventgroup_entry(
        self, event_group_entry: SdEventGroupEntry
    ):
        self.logger.info(
            f"Received subscribe ack eventgroup entry: {event_group_entry}"
        )

    def _handle_sd_subscribe_nack_eventgroup_entry(
        self, event_group_entry: SdEventGroupEntry
    ):
        self.logger.info(
            f"Received subscribe nack eventgroup entry: {event_group_entry}"
        )

    def datagram_received_mcast(
        self, data: bytes, addr: Tuple[Union[str, Any], int]
    ) -> None:

        # Ignore messages from the same interface and port
        if addr[0] == self.interface and addr[1] == self.sd_port:
            return

        someip_header = SomeIpHeader.from_buffer(data)
        if not someip_header.is_sd_header():
            return

        someip_sd_header = SomeIpSdHeader.from_buffer(data)

        for offered_service in extract_offered_services(someip_sd_header):
            self.handle_offered_service(offered_service)

        for subscription in extract_subscribe_entries(someip_sd_header):
            self.handle_subscription(subscription)

        for event_group_entry in extract_subscribe_ack_eventgroup_entries(
            someip_sd_header
        ):
            self._handle_sd_subscribe_ack_eventgroup_entry(event_group_entry)

    def connection_lost_mcast(self, exc: Exception) -> None:
        pass

    def datagram_received_ucast(
        self, data: bytes, addr: Tuple[Union[str, Any], int]
    ) -> None:
        self.logger.debug(f"Received SD message from {addr}: {data}")

        # Ignore messages from the same interface and port
        if addr[0] == self.interface and addr[1] == self.sd_port:
            return

        someip_header = SomeIpHeader.from_buffer(data)
        if not someip_header.is_sd_header():
            return

        someip_sd_header = SomeIpSdHeader.from_buffer(data)

        for subscription in extract_subscribe_entries(someip_sd_header):
            self.handle_subscription(subscription)

        for event_group_entry in extract_subscribe_ack_eventgroup_entries(
            someip_sd_header
        ):
            self._handle_sd_subscribe_ack_eventgroup_entry(event_group_entry)

        for event_group_entry in extract_subscribe_nack_eventgroup_entries(
            someip_sd_header
        ):
            self._handle_sd_subscribe_nack_eventgroup_entry(event_group_entry)

    def connection_lost_ucast(self, exc: Exception) -> None:
        pass

    async def start_sd_listening(self):
        self.sd_socket_mcast = create_rcv_multicast_socket(
            self.sd_address, self.sd_port, DEFAULT_INTERFACE_IP
        )

        loop = asyncio.get_running_loop()
        self.mcast_transport, _ = await loop.create_datagram_endpoint(
            lambda: DatagramAdapter(
                target=None,
                datagram_received_callback=self.datagram_received_mcast,
                connection_lost_callback=self.connection_lost_mcast,
            ),
            sock=self.sd_socket_mcast,
        )

        self.sd_socket_ucast = create_udp_socket(self.interface, self.sd_port)
        self.ucast_transport, _ = await loop.create_datagram_endpoint(
            lambda: DatagramAdapter(
                target=None,
                datagram_received_callback=self.datagram_received_ucast,
                connection_lost_callback=self.connection_lost_ucast,
            ),
            sock=self.sd_socket_ucast,
        )


async def main():
    parser = argparse.ArgumentParser(description="SOME/IP Daemon")
    parser.add_argument("--config", help="Path to configuration file")
    args = parser.parse_args()

    daemon = SomeipDaemon(args.config)
    await daemon.start_server()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Daemon stopped.")
