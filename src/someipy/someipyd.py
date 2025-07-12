import argparse
import asyncio
import base64
from dataclasses import dataclass
import functools
import json
import logging
import os
import struct
import sys
import ipaddress
import time
from typing import Any, Dict, List, Set, Tuple, Union

from someipy._internal.message_types import MessageType
from someipy._internal.someip_endpoint import (
    SomeipEndpoint,
    TCPClientSomeipEndpoint,
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
    SdEntry,
    SdEntryType,
    SdEventGroupEntry,
    SdService,
    SdService2,
    SdServiceWithTimestamp,
    SdSubscription,
    SomeIpSdHeader,
)
from someipy._internal.store_with_timeout import StoreWithTimeout
from someipy._internal.subscribers import EventGroupSubscriber, Subscribers
from someipy._internal.uds_messages import (
    InboundCallMethodRequest,
    InboundCallMethodResponse,
    FindServiceRequest,
    FindServiceResponse,
    OfferServiceRequest,
    OutboundCallMethodRequest,
    OutboundCallMethodResponse,
    ReceivedEvent,
    SendEventRequest,
    StopOfferServiceRequest,
    StopSubscribeEventGroupRequest,
    SubscribeEventGroupRequest,
    create_uds_message,
)
from someipy._internal.utils import (
    DatagramAdapter,
    create_rcv_multicast_socket,
    create_udp_socket,
)
from someipy._internal.offer_service_storage import OfferServiceStorage, ServiceToOffer
from someipy.service import Event, Method, EventGroup


DEFAULT_SOCKET_PATH = "/tmp/someipyd.sock"
DEFAULT_CONFIG_FILE = "someipyd.json"
DEFAULT_SD_ADDRESS = "224.224.224.245"
DEFAULT_INTERFACE_IP = "127.0.0.2"
DEFAULT_SD_PORT = 30490


class Subscription:
    def __init__(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        eventgroup: EventGroup,
        ttl_seconds: int,
        client_endpoint_ip: str,
        client_endpoint_port: int,
        server_endpoint_ip: str,
        server_endpoint_port: int,
        timestamp: float = time.time(),
    ):
        self.service_id = service_id
        self.instance_id = instance_id
        self.major_version = major_version
        self.eventgroup = eventgroup
        self.ttl_seconds = ttl_seconds

        self.client_endpoint_ip = client_endpoint_ip
        self.client_endpoint_port = client_endpoint_port
        self.server_endpoint_ip = server_endpoint_ip
        self.server_endpoint_port = server_endpoint_port
        self.timestamp = timestamp

    def __eq__(self, value: "Subscription") -> bool:
        return (
            self.service_id == value.service_id
            and self.instance_id == value.instance_id
            and self.major_version == value.major_version
            and self.eventgroup == value.eventgroup
            and self.client_endpoint_ip == value.client_endpoint_ip
            and self.client_endpoint_port == value.client_endpoint_port
            and self.server_endpoint_ip == value.server_endpoint_ip
            and self.server_endpoint_port == value.server_endpoint_port
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.service_id,
                self.instance_id,
                self.major_version,
                self.eventgroup,
                self.client_endpoint_ip,
                self.client_endpoint_port,
                self.server_endpoint_ip,
                self.server_endpoint_port,
            )
        )


class RequestedSubscription:
    def __init__(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        client_endpoint_ip: str,
        client_endpoint_port: int,
        protocols: frozenset[TransportLayerProtocol],
        eventgroup: EventGroup,
        ttl_subscription: int,
    ):
        self.service_id = service_id
        self.instance_id = instance_id
        self.major_version = major_version
        self.client_endpoint_ip = client_endpoint_ip
        self.client_endpoint_port = client_endpoint_port
        self.protocols = protocols
        self.eventgroup = eventgroup
        self.ttl = ttl_subscription

    def __eq__(self, other: "RequestedSubscription") -> bool:
        return (
            self.service_id == other.service_id
            and self.instance_id == other.instance_id
            and self.major_version == other.major_version
            and self.protocols == other.protocols
            and self.eventgroup == other.eventgroup
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

    @property
    def subscriptions(self) -> List[RequestedSubscription]:
        """
        Get all subscriptions from all clients.
        """
        subscriptions = []
        for client_subscriptions in self._subscriptions_by_client.values():
            subscriptions.extend(client_subscriptions)
        return subscriptions

    def get_client_ids(self, subscription: RequestedSubscription) -> List[int]:
        """
        Get all client ids (writer ids) that have the given subscription.
        """
        client_ids = []
        for writer_id, subscriptions in self._subscriptions_by_client.items():
            if subscription in subscriptions:
                client_ids.append(writer_id)
        return client_ids

    def has_subscriptions(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
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
                ):
                    subscriptions_to_return.append((subscription, writer_id))

        return subscriptions_to_return

    def remove_client(self, writer_id: int):
        if writer_id in self._subscriptions_by_client:
            del self._subscriptions_by_client[writer_id]


@dataclass
class MethodCall:
    service_id: int
    method_id: int
    client_id: int
    session_id: int
    src_ip: str
    src_port: int

    def __hash__(self):
        return hash(
            (
                self.service_id,
                self.method_id,
                self.client_id,
                self.session_id,
                self.src_ip,
                self.src_port,
            )
        )


class SomeipDaemon:

    def __init__(self, config_file=None, log_path=None):
        self.config = self._load_config(config_file)
        self.socket_path = self.config.get("socket_path", DEFAULT_SOCKET_PATH)
        self.sd_address = self.config.get("sd_address", DEFAULT_SD_ADDRESS)
        self.sd_port = self.config.get("sd_port", DEFAULT_SD_PORT)
        self.interface = self.config.get("interface", DEFAULT_INTERFACE_IP)
        log_level = self.config.get("log_level", "DEBUG")
        self.log_path = log_path if log_path else self.config.get("log_path")

        self.logger = self._configure_logging(
            log_level=log_level, log_path=self.log_path
        )

        self.logger.info(
            f"Starting SOME/IP Daemon with config:\n"
            f"Socket path: {self.socket_path}\n"
            f"SD address: {self.sd_address}\n"
            f"SD port: {self.sd_port}\n"
            f"Interface: {self.interface}\n"
            f"Loglevel: {log_level}\n"
            f"Log path: {self.log_path if self.log_path else 'Console'}\n"
        )

        log_level_mapping = {
            "DEBUG": logging.DEBUG,
            "ERROR": logging.ERROR,
            "INFO": logging.INFO,
            "FATAL": logging.FATAL,
        }

        if log_level in log_level_mapping:
            self.logger.setLevel(log_level_mapping[log_level])

        self._sd_socket_mcast = None
        self._sd_socket_ucast = None
        self._mcast_transport = None
        self._ucast_transport = None

        # Services offered by other ECUs
        self._found_services: List[SdServiceWithTimestamp] = []

        # Services offered by this daemon
        self._services_to_offer = OfferServiceStorage()
        self._offer_timers: Dict[int, SimplePeriodicTimer] = {}

        # Active subscriptions to services offered by this daemon
        self._service_subscribers: Dict[ServiceToOffer, Subscribers] = {}

        # Subscriptions requested by local clients
        self._requested_subscriptions = RequestedSubscriptionStore()

        self._pending_subscriptions: Set[Subscription] = set()
        self._active_subscriptions: Set[Subscription] = set()

        self._mcast_session_handler = SessionHandler()
        self._unicast_session_handler = SessionHandler()

        # Qeueues and tasks stored by id of asyncio.StreamWriter
        self._tx_queues: Dict[int, asyncio.Queue] = {}
        self._tx_tasks: Dict[int, asyncio.Task] = {}
        self._rx_queues: Dict[int, asyncio.Queue] = {}

        self._someip_server_endpoints = SomeipEndpointStorage()
        self._someip_client_endpoints = SomeipEndpointStorage()

        self._ttl_task = asyncio.create_task(self._check_services_ttl_task())

        self._issued_method_calls: Dict[MethodCall, int] = {}

    def _configure_logging(self, log_level=logging.DEBUG, log_path=None):
        logger = logging.getLogger(f"someipyd")
        logger.setLevel(log_level)

        # Remove any existing handlers to prevent duplicate logs
        if logger.hasHandlers():
            logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d %(name)s [%(levelname)s]: %(message)s",
            datefmt="%Y-%m-%d,%H:%M:%S",
        )

        if log_path:
            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        else:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
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

    async def _check_services_ttl_task(self):
        try:
            while True:
                await asyncio.sleep(0.1)

                self._cleanup_obsolete_pending_subscriptions()
                self._cleanup_active_subscriptions()

                count_before = len(self._found_services)

                current_time = time.time()

                # self.logger.debug(f"Current time: {current_time}, checking services...")

                # for service in self._found_services:
                #    self.logger.debug(
                #        f"Checking service {service.service_id}, timestamp: {service.timestamp}, ttl: {service.ttl}"
                #    )

                # Process timeouts and filter services in one operation
                self._found_services = [
                    service
                    for service in self._found_services
                    if not (current_time - service.timestamp > service.service.ttl)
                ]

                count_after = len(self._found_services)
                if count_before != count_after:
                    self.logger.info(
                        f"Removed {count_before - count_after} timed out services. Remaining: {count_after}"
                    )

        except asyncio.CancelledError:
            # Task was cancelled - exit cleanly
            self.logger.debug("Service TTL checker task cancelled")
        except Exception as e:
            self.logger.error(f"Error in service TTL checker task: {e}")
        pass

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

                            call_method_request = create_uds_message(
                                InboundCallMethodRequest,
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

        elif MessageType(header.message_type) == MessageType.RESPONSE:
            issued_call = MethodCall(
                service_id=header.service_id,
                method_id=header.method_id,
                client_id=header.client_id,
                session_id=header.session_id,
                src_ip=dst_addr[0],
                src_port=dst_addr[1],
            )

            if not issued_call in self._issued_method_calls:
                self.logger.debug(f"Received response for unknown method call.")
                return

            writer_id = self._issued_method_calls[issued_call]
            del self._issued_method_calls[issued_call]
            payload_encoded = base64.b64encode(message.payload).decode("utf-8")

            message = create_uds_message(
                OutboundCallMethodResponse,
                service_id=header.service_id,
                method_id=header.method_id,
                client_id=header.client_id,
                session_id=header.session_id,
                return_code=header.return_code,
                dst_endpoint_ip=dst_addr[0],
                dst_endpoint_port=dst_addr[1],
                payload=payload_encoded,
            )

            self._tx_queues[writer_id].put_nowait(self.prepare_message(message))

        elif MessageType(header.message_type) == MessageType.NOTIFICATION:
            if header.return_code == 0x00 and header.client_id == 0x00:
                self.logger.debug(
                    f"Received notification for service {header.service_id}, event {header.method_id}"
                )

                event_id = header.method_id

                event_msg = create_uds_message(
                    ReceivedEvent,
                    service_id=header.service_id,
                    event_id=event_id,
                    src_endpoint_ip=src_addr[0],
                    src_endpoint_port=src_addr[1],
                    payload=base64.b64encode(message.payload).decode("utf-8"),
                )

                for active_subscription in self._active_subscriptions:
                    event_ids = [i.id for i in active_subscription.eventgroup.events]
                    self.logger.debug("check event ids: %s", event_ids)
                    if (
                        event_id in event_ids
                        and active_subscription.server_endpoint_ip == src_addr[0]
                        and active_subscription.server_endpoint_port == src_addr[1]
                        and active_subscription.service_id == header.service_id
                    ):
                        self.logger.debug(
                            f"Found active subscription for service {header.service_id}, "
                            f"instance {active_subscription.instance_id}, "
                            f"eventgroup {active_subscription.eventgroup.id}, "
                        )

                        for (
                            requested_subscription
                        ) in self._requested_subscriptions.subscriptions:
                            if (
                                requested_subscription.service_id
                                == active_subscription.service_id
                                and requested_subscription.instance_id
                                == active_subscription.instance_id
                                and requested_subscription.major_version
                                == active_subscription.major_version
                                and requested_subscription.eventgroup
                                == active_subscription.eventgroup
                                and requested_subscription.client_endpoint_ip
                                == active_subscription.client_endpoint_ip
                                and requested_subscription.client_endpoint_port
                                == active_subscription.client_endpoint_port
                            ):

                                writer_ids = (
                                    self._requested_subscriptions.get_client_ids(
                                        requested_subscription
                                    )
                                )

                                for writer_id in writer_ids:
                                    tx_queue = self._tx_queues.get(writer_id)
                                    if tx_queue:
                                        tx_queue.put_nowait(
                                            self.prepare_message(event_msg)
                                        )

    def _cleanup_active_subscriptions(self):
        current_time = time.time()
        subscriptions_to_remove = []
        for subscription in self._active_subscriptions:
            if current_time - subscription.timestamp > subscription.ttl_seconds:
                subscriptions_to_remove.append(subscription)

        for subscription in subscriptions_to_remove:
            self._active_subscriptions.remove(subscription)
            self.logger.debug(
                f"Removed active subscription for service {subscription.service_id}, "
                f"instance {subscription.instance_id}, eventgroup {subscription.eventgroup_id}"
            )

    def _cleanup_obsolete_pending_subscriptions(self):
        current_time = time.time()
        subscriptions_to_remove = []
        for subscription in self._pending_subscriptions:
            if current_time - subscription.timestamp > 10.0:
                subscriptions_to_remove.append(subscription)

        for subscription in subscriptions_to_remove:
            self._pending_subscriptions.remove(subscription)

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
        for endpoint in self._someip_server_endpoints:
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
        writer_id = id(writer)
        self.logger.info(f"New client connected: {writer_id}")

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

            client_endpoints = self._someip_server_endpoints.get_endpoints(writer_id)
            if client_endpoints is not None:
                for endpoint in client_endpoints:
                    self.logger.debug(
                        f"Closing endpoint {endpoint.dst_ip()}:{endpoint.dst_port()} for client {writer_id}"
                    )
                    endpoint.shutdown()
                    self._someip_server_endpoints.remove_endpoint(writer_id, endpoint)

            self.logger.debug(f"Client disconnected")

    async def handle_client_message(self, message: dict, writer: asyncio.StreamWriter):
        writer_id = id(writer)
        message_type = message.get("type")
        self.logger.debug(f"Received message type: {message_type}")

        message_handlers = {
            OfferServiceRequest.__name__: self._handle_offer_service_request,
            StopOfferServiceRequest.__name__: self._handle_stop_offer_service_request,
            InboundCallMethodResponse.__name__: self._handle_inbound_call_method_response,
            FindServiceRequest.__name__: self._handle_find_service_request,
            OutboundCallMethodRequest.__name__: self._handle_outbound_call_method_request,
            SendEventRequest.__name__: self._handle_send_event_request,
            SubscribeEventGroupRequest.__name__: self._handle_subscribe_eventgroup_request,
            StopSubscribeEventGroupRequest.__name__: self._handle_stop_subscribe_eventgroup_request,
        }

        if message_type in message_handlers:
            handler = message_handlers[message_type]

            if asyncio.iscoroutinefunction(handler):
                await handler(message, writer_id)
                return
            else:
                handler(message, writer_id)
                return
        else:
            self.logger.warning(
                f"Received unknown message type: {message_type}. Message: {message}"
            )

    async def _handle_subscribe_eventgroup_request(
        self, message: SubscribeEventGroupRequest, writer_id: int
    ):

        protocols = []
        if message["udp"]:
            protocols.append(TransportLayerProtocol.UDP)

            if not self._someip_client_endpoints.has_endpoint(
                message["client_endpoint_ip"],
                message["client_endpoint_port"],
                TransportLayerProtocol.UDP,
            ):
                self.logger.debug(
                    f"Creating new UDP endpoint for {message['client_endpoint_ip']}:{message['client_endpoint_port']}"
                )

                udp_endpoint = await self._create_server_endpoint(
                    message["client_endpoint_ip"],
                    message["client_endpoint_port"],
                    TransportLayerProtocol.UDP,
                )

                udp_endpoint.set_someip_callback(self._someip_message_callback)

                self._someip_client_endpoints.add_endpoint(writer_id, udp_endpoint)

        if message["tcp"]:
            protocols.append(TransportLayerProtocol.TCP)

        event_group = EventGroup.from_json(message["eventgroup"])

        new_subscription = RequestedSubscription(
            service_id=message["service_id"],
            instance_id=message["instance_id"],
            major_version=message["major_version"],
            client_endpoint_ip=message["client_endpoint_ip"],
            client_endpoint_port=message["client_endpoint_port"],
            protocols=frozenset(protocols),
            eventgroup=event_group,
            ttl_subscription=message["ttl_subscription"],
        )

        self._requested_subscriptions.add_subscription(writer_id, new_subscription)

    def _handle_stop_subscribe_eventgroup_request(
        self, message: StopSubscribeEventGroupRequest, writer_id: int
    ):
        # TODO: Remove from self._requested_subscriptions
        # Check if there is an active subscription. If yes, send out a stop subscribe message
        pass

    async def _handle_offer_service_request(
        self, message: OfferServiceRequest, writer_id: int
    ):
        method_strs = message.get("method_list", [])
        methods = [Method.from_json(m) for m in method_strs]

        eventgroup_strs = message.get("eventgroup_list", [])
        eventgroups = [EventGroup.from_json(e) for e in eventgroup_strs]

        """
        - Store offered service including events
        - Subscribe received with service id, instance id, major version, ttl, eventgroup id. References an endpoint with ip and port option
        - If service is offered and found, send back an acknowledge and store the subscription with:
            - endpoint ip and port of the client where the events shall be sent to
            - service id, instance id, major version, eventgroup id,
        
        """

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
            eventgroups=eventgroups,
        )

        self._services_to_offer.add_service(service_to_add)

        # Check if there is already an endpoint for the ip and port, if not, open a new endpoint
        if service_to_add.has_udp:
            if not self._someip_server_endpoints.has_endpoint(
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
                self._someip_server_endpoints.add_endpoint(writer_id, udp_endpoint)

        if service_to_add.has_tcp:
            if not self._someip_server_endpoints.has_endpoint(
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
                self._someip_server_endpoints.add_endpoint(writer_id, tcp_endpoint)

        cyclic_offer_delay_ms = message["cyclic_offer_delay_ms"]

        # If there is no timer running for the interval yet, create a new timer task
        if cyclic_offer_delay_ms not in self._offer_timers:
            self.logger.debug(f"Starting new offer timer for {cyclic_offer_delay_ms}ms")
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

        eventgroup_strs = message.get("eventgroup_list", [])
        eventgroups = [EventGroup.from_json(e) for e in eventgroup_strs]

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
            eventgroups=eventgroups,
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
        if self._ucast_transport:
            self.logger.debug(
                f"Send stop offer message for service 0x{service_to_stop.service_id:04x}, instance 0x{service_to_stop.instance_id:04x} to {self.sd_address}:{self.sd_port}"
            )
            self._ucast_transport.sendto(buffer, (self.sd_address, self.sd_port))

        if service_to_stop.has_udp:
            try:
                udp_endpoint = self._someip_server_endpoints.get_endpoint(
                    writer_id, TransportLayerProtocol.UDP
                )
                if udp_endpoint:
                    self.logger.debug(
                        f"Closing UDP endpoint for {service_to_stop.endpoint_ip}:{service_to_stop.endpoint_port}"
                    )
                    udp_endpoint.shutdown()
                    self._someip_server_endpoints.remove_endpoint(
                        writer_id, udp_endpoint
                    )
            except Exception as e:
                self.logger.error(
                    f"Error closing UDP endpoint for {service_to_stop.endpoint_ip}:{service_to_stop.endpoint_port}: {e}"
                )

        if service_to_stop.has_tcp:
            try:
                tcp_endpoint = self._someip_server_endpoints.get_endpoint(
                    writer_id, TransportLayerProtocol.TCP
                )
                if tcp_endpoint:
                    self.logger.debug(
                        f"Closing TCP endpoint for {service_to_stop.endpoint_ip}:{service_to_stop.endpoint_port}"
                    )
                    tcp_endpoint.shutdown()
                    self._someip_server_endpoints.remove_endpoint(
                        writer_id, tcp_endpoint
                    )
            except Exception as e:
                self.logger.error(
                    f"Error closing TCP endpoint for {service_to_stop.endpoint_ip}:{service_to_stop.endpoint_port}: {e}"
                )

    def _handle_inbound_call_method_response(
        self, message: InboundCallMethodResponse, writer_id: int
    ):
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

        endpoint = self._someip_server_endpoints.get_endpoint(
            writer_id, TransportLayerProtocol(message["protocol"])
        )
        self.logger.debug(
            f"Sending CallMethodResponse to {message['src_endpoint_ip']}:{message['src_endpoint_port']}"
        )

        if endpoint:
            endpoint.sendto(
                header.to_buffer() + payload_decoded,
                (message["src_endpoint_ip"], message["src_endpoint_port"]),
            )

    async def _handle_outbound_call_method_request(
        self, message: OutboundCallMethodRequest, writer_id: int
    ):
        endpoint = None
        if TransportLayerProtocol(message["protocol"]) == TransportLayerProtocol.UDP:
            if not self._someip_client_endpoints.has_endpoint(
                message["src_endpoint_ip"],
                message["src_endpoint_port"],
                TransportLayerProtocol.UDP,
            ):
                self.logger.debug(
                    f"Creating new UDP endpoint for {message['src_endpoint_ip']}:{message['src_endpoint_port']}"
                )

                udp_endpoint = await self._create_server_endpoint(
                    message["src_endpoint_ip"],
                    message["src_endpoint_port"],
                    TransportLayerProtocol.UDP,
                )

                udp_endpoint.set_someip_callback(self._someip_message_callback)

                self._someip_client_endpoints.add_endpoint(writer_id, udp_endpoint)
                endpoint = udp_endpoint
            else:
                endpoint = self._someip_client_endpoints.get_endpoint_by_ip_port(
                    message["src_endpoint_ip"],
                    message["src_endpoint_port"],
                    TransportLayerProtocol.UDP,
                )

        elif TransportLayerProtocol(message["protocol"]) == TransportLayerProtocol.TCP:

            if not self._someip_client_endpoints.has_tcp_endpoint(
                message["src_endpoint_ip"],
                message["src_endpoint_port"],
                message["dst_endpoint_ip"],
                message["dst_endpoint_port"],
            ):
                self.logger.debug(
                    f"Creating new TCP endpoint for {message['src_endpoint_ip']}:{message['src_endpoint_port']}"
                )

                tcp_endpoint = TCPClientSomeipEndpoint(
                    message["dst_endpoint_ip"],
                    message["dst_endpoint_port"],
                    message["src_endpoint_ip"],
                    message["src_endpoint_port"],
                    self.logger,
                )

                tcp_endpoint.set_someip_callback(self._someip_message_callback)

                self._someip_client_endpoints.add_endpoint(writer_id, tcp_endpoint)
                endpoint: TCPClientSomeipEndpoint = tcp_endpoint
            else:
                endpoint: TCPClientSomeipEndpoint = (
                    self._someip_client_endpoints.get_end_point_by_src_and_dst_ip_port(
                        message["src_endpoint_ip"],
                        message["src_endpoint_port"],
                        message["dst_endpoint_ip"],
                        message["dst_endpoint_port"],
                        TransportLayerProtocol.TCP,
                    )
                )

            # TODO: This shall not block the handle_client function. A new task shall be created
            # For TCP wait for the connection to be established
            while not endpoint.is_connected():
                # self.logger.debug(
                #    f"Waiting for TCP connection to {message['dst_endpoint_ip']}:{message['dst_endpoint_port']}"
                # )
                await asyncio.sleep(0.2)

        # Build the request message
        self.logger.debug(
            f"Sending OutboundCallMethodRequest to {message['dst_endpoint_ip']}:{message['dst_endpoint_port']}"
        )

        decoded_payload = base64.b64decode(message["payload"])

        header = SomeIpHeader(
            service_id=message["service_id"],
            method_id=message["method_id"],
            client_id=message["client_id"],
            session_id=message["session_id"],
            protocol_version=0x01,
            interface_version=message["major_version"],
            message_type=MessageType.REQUEST.value,
            return_code=0x00,
            length=len(decoded_payload) + 8,
        )
        someip_message = SomeIpMessage(header, decoded_payload)

        new_call = MethodCall(
            service_id=message["service_id"],
            method_id=message["method_id"],
            client_id=message["client_id"],
            session_id=message["session_id"],
            src_ip=message["src_endpoint_ip"],
            src_port=message["src_endpoint_port"],
        )

        if new_call in self._issued_method_calls:
            self.logger.warning(
                f"Method call {new_call} already issued. Overwriting writer_id."
            )

        self._issued_method_calls[new_call] = writer_id

        endpoint.sendto(
            someip_message.serialize(),
            (message["dst_endpoint_ip"], message["dst_endpoint_port"]),
        )

    def _handle_find_service_request(self, message: FindServiceRequest, writer_id: int):

        service_found = False
        all_services = [s for s in self._found_services]

        for service in self._services_to_offer.get_all_services():
            protocols_to_add = set()
            if service.has_udp:
                protocols_to_add.add(TransportLayerProtocol.UDP)
            if service.has_tcp:
                protocols_to_add.add(TransportLayerProtocol.TCP)

            service_to_add = SdService2(
                service_id=service.service_id,
                instance_id=service.instance_id,
                major_version=service.major_version,
                minor_version=service.minor_version,
                ttl=0,
                endpoint=(
                    ipaddress.IPv4Address(service.endpoint_ip),
                    service.endpoint_port,
                ),
                protocols=frozenset(protocols_to_add),
            )

            service_to_add = SdServiceWithTimestamp(service_to_add, 0.0)
            all_services.append(service_to_add)

        for found_service in all_services:
            """
            • Instance ID shall be set to 0xFFFF, if all service instances shall be returned. It
            shall be set to the Instance ID of a specific service instance, if just a single service
            instance shall be returned.
            • Major Version shall be set to 0xFF, that means that services with any version shall
            be returned. If set to value different than 0xFF, services with this specific major
            version shall be returned only.
            • Minor Version shall be set to 0xFFFF FFFF, that means that services with any
            version shall be returned. If set to a value different to 0xFFFF FFFF, services
            with this specific minor version shall be returned only
            """

            if (
                (message["service_id"] == found_service.service.service_id)
                and (
                    message["instance_id"] == found_service.service.instance_id
                    or message["instance_id"] == 0xFFFF
                )
                and (
                    message["major_version"] == found_service.service.major_version
                    or message["major_version"] == 0xFF
                )
                and (
                    message["minor_version"] == found_service.service.minor_version
                    or message["minor_version"] == 0xFFFFFFFF
                )
            ):
                service_found = True
                response = create_uds_message(
                    FindServiceResponse,
                    success=True,
                    service_id=found_service.service.service_id,
                    instance_id=found_service.service.instance_id,
                    major_version=found_service.service.major_version,
                    minor_version=found_service.service.minor_version,
                    endpoint_ip=str(found_service.service.endpoint[0]),
                    endpoint_port=found_service.service.endpoint[1],
                )

                tx_queue = self._tx_queues.get(writer_id)
                if tx_queue:
                    tx_queue.put_nowait(self.prepare_message(response))

                break

        if not service_found:
            response = create_uds_message(
                FindServiceResponse,
                success=False,
                service_id=message["service_id"],
                instance_id=message["instance_id"],
                major_version=message["major_version"],
                minor_version=message["minor_version"],
                endpoint_ip="empty",
                endpoint_port=0,
            )

            tx_queue = self._tx_queues.get(writer_id)
            if tx_queue:
                tx_queue.put_nowait(self.prepare_message(response))

    def _handle_send_event_request(self, message: SendEventRequest, writer_id: int):
        for sub in self._service_subscribers.values():
            sub.update()

        deserialized_event = Event.from_json(message["event"])
        payload_decoded = base64.b64decode(message["payload"])

        for offered_service in self._service_subscribers.keys():
            if (
                offered_service.service_id == message["service_id"]
                and offered_service.instance_id == message["instance_id"]
                and message["eventgroup_id"] in offered_service.eventgroup_ids
            ):

                if self._service_subscribers[offered_service].has_subscribers:
                    for subscriber in self._service_subscribers[
                        offered_service
                    ].subscribers:
                        self.logger.debug(
                            f"Sending event to subscriber {subscriber.endpoint[0]}:{subscriber.endpoint[1]}"
                        )

                        if deserialized_event.protocol == TransportLayerProtocol.UDP:
                            endpoint = (
                                self._someip_server_endpoints.get_endpoint_by_ip_port(
                                    message["src_endpoint_ip"],
                                    message["src_endpoint_port"],
                                    TransportLayerProtocol.UDP,
                                )
                            )

                            if endpoint:
                                someip_header = SomeIpHeader(
                                    service_id=offered_service.service_id,
                                    method_id=deserialized_event.id,
                                    length=len(payload_decoded) + 8,
                                    client_id=message["client_id"],
                                    session_id=message["session_id"],
                                    protocol_version=1,
                                    interface_version=offered_service.major_version,
                                    message_type=MessageType.NOTIFICATION.value,
                                    return_code=0x00,
                                )

                                someip_message = SomeIpMessage(
                                    someip_header, payload_decoded
                                )
                                endpoint.sendto(
                                    someip_message.serialize(), subscriber.endpoint
                                )

                        elif deserialized_event.protocol == TransportLayerProtocol.TCP:

                            endpoint: TCPSomeipEndpoint = (
                                self._someip_server_endpoints.get_endpoint_by_ip_port(
                                    message["src_endpoint_ip"],
                                    message["src_endpoint_port"],
                                    TransportLayerProtocol.TCP,
                                )
                            )

                            if endpoint:
                                someip_header = SomeIpHeader(
                                    service_id=offered_service.service_id,
                                    method_id=deserialized_event.id,
                                    length=len(payload_decoded) + 8,
                                    client_id=message["client_id"],
                                    session_id=message["session_id"],
                                    protocol_version=1,
                                    interface_version=offered_service.major_version,
                                    message_type=MessageType.NOTIFICATION.value,
                                    return_code=0x00,
                                )

                                someip_message = SomeIpMessage(
                                    someip_header, payload_decoded
                                )
                                endpoint.sendto(
                                    someip_message.serialize(), subscriber.endpoint
                                )

        # Handle internal subscriptions (UDS clients)
        for requested_subscription in self._requested_subscriptions.subscriptions:
            if (
                requested_subscription.service_id == message["service_id"]
                and requested_subscription.instance_id == message["instance_id"]
                and requested_subscription.eventgroup.id == message["eventgroup_id"]
                and requested_subscription.major_version == message["major_version"]
            ):
                self.logger.debug(
                    f"Found internal subscription for service {message['service_id']}, "
                    f"instance {message['instance_id']}, eventgroup {message['eventgroup_id']}"
                )

                event_msg = create_uds_message(
                    ReceivedEvent,
                    service_id=message["service_id"],
                    event_id=deserialized_event.id,
                    src_endpoint_ip=message["src_endpoint_ip"],
                    src_endpoint_port=message["src_endpoint_port"],
                    payload=message["payload"],
                )

                writer_ids = self._requested_subscriptions.get_client_ids(
                    requested_subscription
                )

                for writer_id in writer_ids:
                    tx_queue = self._tx_queues.get(writer_id)
                    if tx_queue:
                        tx_queue.put_nowait(self.prepare_message(event_msg))

    def offer_timer_callback(self, cyclic_offer_delay_ms: int):
        self.logger.debug(f"Offer timer callback for {cyclic_offer_delay_ms}ms")

        services_to_offer: List[ServiceToOffer] = (
            self._services_to_offer.services_by_cyclic_offer_delay(
                cyclic_offer_delay_ms
            )
        )

        for service in services_to_offer:
            service.last_offer_time = time.time()

        if len(services_to_offer) > 0:
            (
                session_id,
                reboot_flag,
            ) = self._mcast_session_handler.update_session()

            sd_message = build_offer_service_sd_header(
                services_to_offer, session_id, reboot_flag
            )
            buffer = sd_message.to_buffer()

            if self._ucast_transport:
                self._ucast_transport.sendto(buffer, (self.sd_address, self.sd_port))

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
            self.logger.info("UDS server cancelled.")
            pass
        finally:
            if self._mcast_transport:
                self._mcast_transport.close()
            if self._ucast_transport:
                self._ucast_transport.close()
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

    def _handle_offered_service(self, offered_service: SdService2):
        self.logger.info(f"Received offered service: {offered_service}")

        new_service = SdServiceWithTimestamp(offered_service, time.time())

        if new_service not in self._found_services:
            self._found_services.append(new_service)
        else:
            # Update the timestamp if the service is already in the list
            index = self._found_services.index(new_service)
            self._found_services[index].timestamp = time.time()

        # Check if there is a requested subscription for this service
        for requested_subscription in self._requested_subscriptions.has_subscriptions(
            offered_service.service_id,
            offered_service.instance_id,
            offered_service.major_version,
        ):
            requested_protocols: Set[TransportLayerProtocol] = set()
            for protocol in offered_service.protocols:
                if protocol in requested_subscription[0].protocols:
                    requested_protocols.add(protocol)

            if TransportLayerProtocol.TCP in requested_protocols:
                if not self._someip_client_endpoints.has_tcp_endpoint(
                    requested_subscription[0].client_endpoint_ip,
                    requested_subscription[0].client_endpoint_port,
                    str(offered_service.endpoint[0]),
                    offered_service.endpoint[1],
                ):
                    self.logger.debug(
                        f"Creating new TCP endpoint for {requested_subscription[0].client_endpoint_ip}:{requested_subscription[0].client_endpoint_port}"
                    )

                    tcp_endpoint = TCPClientSomeipEndpoint(
                        str(offered_service.endpoint[0]),
                        offered_service.endpoint[1],
                        requested_subscription[0].client_endpoint_ip,
                        requested_subscription[0].client_endpoint_port,
                        self.logger,
                    )

                    tcp_endpoint.set_someip_callback(self._someip_message_callback)
                    self._someip_client_endpoints.add_endpoint(
                        requested_subscription[1], tcp_endpoint
                    )
                    # TODO: This shall not block the handle_client function. A new task shall be created
                    # For TCP wait for the connection to be established
                    # while not tcp_endpoint.is_connected():
                    #    await asyncio.sleep(0.2)

            (
                session_id,
                reboot_flag,
            ) = self._unicast_session_handler.update_session()

            # Improvement: Pack all entries into a single SD message
            subscribe_sd_header = build_subscribe_eventgroup_sd_header(
                service_id=offered_service.service_id,
                instance_id=offered_service.instance_id,
                major_version=offered_service.major_version,
                ttl=int(requested_subscription[0].ttl),
                event_group_id=requested_subscription[0].eventgroup.id,
                session_id=session_id,
                reboot_flag=reboot_flag,
                endpoint=(
                    ipaddress.IPv4Address(requested_subscription[0].client_endpoint_ip),
                    requested_subscription[0].client_endpoint_port,
                ),
                protocols=requested_protocols,
            )

            pending_subscription = Subscription(
                service_id=offered_service.service_id,
                instance_id=offered_service.instance_id,
                major_version=offered_service.major_version,
                eventgroup=requested_subscription[0].eventgroup,
                ttl_seconds=requested_subscription[0].ttl,
                client_endpoint_ip=requested_subscription[0].client_endpoint_ip,
                client_endpoint_port=requested_subscription[0].client_endpoint_port,
                server_endpoint_ip=str(offered_service.endpoint[0]),
                server_endpoint_port=offered_service.endpoint[1],
                timestamp=time.time(),
            )
            self._pending_subscriptions.add(pending_subscription)

            if self._ucast_transport:
                self._ucast_transport.sendto(
                    subscribe_sd_header.to_buffer(),
                    (str(offered_service.endpoint[0]), self.sd_port),
                )

    def _handle_subscription(
        self,
        sd_subscription: SdSubscription,
    ):
        # TODO: Send back a nack message if no service is found
        self.logger.info(f"Received subscription: {sd_subscription}")

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
        for offered_service in self._services_to_offer.get_all_services():
            # [PRS_SOMEIPSD_00828] When receiving a SubscribeEventgroup or StopSubscribeEventgroup the Service ID,
            # Instance ID, Eventgroup ID, and Major Version shall
            # match exactly to the configured values to identify an Eventgroup of a Service Instance.
            if (
                offered_service.service_id == sd_subscription.service_id
                and offered_service.instance_id == sd_subscription.instance_id
                and sd_subscription.eventgroup_id in offered_service.eventgroup_ids
                and offered_service.major_version == sd_subscription.major_version
            ):

                self.logger.info(
                    f"Subscription to eventgroup 0x{sd_subscription.eventgroup_id:04X} of service 0x{offered_service.service_id:04X}, instance 0x{offered_service.instance_id:04X} requested."
                )

                (
                    session_id,
                    reboot_flag,
                ) = self._unicast_session_handler.update_session()

                ack_entry = build_subscribe_eventgroup_ack_entry(
                    service_id=offered_service.service_id,
                    instance_id=offered_service.instance_id,
                    major_version=offered_service.major_version,
                    ttl=sd_subscription.ttl,
                    event_group_id=sd_subscription.eventgroup_id,
                )

                header_output = build_subscribe_eventgroup_ack_sd_header(
                    entry=ack_entry,
                    session_id=session_id,
                    reboot_flag=reboot_flag,
                )

                self.logger.info(
                    f"Sending subscribe ack for eventgroup 0x{sd_subscription.eventgroup_id:04X} of service 0x{offered_service.service_id:04X} instance 0x{offered_service.instance_id:04X} to {sd_subscription.ipv4_address}:{sd_subscription.port}"
                )

                new_subscriber = EventGroupSubscriber(
                    sd_subscription.eventgroup_id,
                    (sd_subscription.ipv4_address, sd_subscription.port),
                    sd_subscription.ttl,
                )

                if offered_service not in self._service_subscribers:
                    self._service_subscribers[offered_service] = Subscribers()

                self._service_subscribers[offered_service].add_subscriber(
                    new_subscriber
                )

                if self._ucast_transport:
                    self._ucast_transport.sendto(
                        data=header_output.to_buffer(),
                        addr=(
                            str(sd_subscription.ipv4_address),
                            self.sd_port,
                        ),
                    )

    def _handle_sd_subscribe_ack_eventgroup_entry(
        self, event_group_entry: SdEventGroupEntry
    ):
        self.logger.info(
            f"Received subscribe ack eventgroup entry: {event_group_entry}"
        )
        pending_subscription = None

        for pending_subscription_tmp in self._pending_subscriptions:
            self.logger.debug(
                f"Checking pending subscription: {pending_subscription_tmp} with values \
                service_id={pending_subscription_tmp.service_id}, \
                instance_id={pending_subscription_tmp.instance_id}, \
                major_version={pending_subscription_tmp.major_version}, \
                eventgroup_id={pending_subscription_tmp.eventgroup.id}"
            )

            self.logger.debug(
                f"Event group entry values: \
                service_id={event_group_entry.sd_entry.service_id}, \
                instance_id={event_group_entry.sd_entry.instance_id}, \
                major_version={event_group_entry.sd_entry.major_version}, \
                eventgroup_id={event_group_entry.eventgroup_id}"
            )

            if (
                pending_subscription_tmp.service_id
                == event_group_entry.sd_entry.service_id
                and pending_subscription_tmp.instance_id
                == event_group_entry.sd_entry.instance_id
                and pending_subscription_tmp.major_version
                == event_group_entry.sd_entry.major_version
                and pending_subscription_tmp.eventgroup.id
                == event_group_entry.eventgroup_id
            ):
                self.logger.debug(
                    f"Found matching pending subscription: {pending_subscription_tmp}"
                )
                pending_subscription = pending_subscription_tmp
                break

        if pending_subscription is not None:
            pending_subscription.timestamp = time.time()
            self._active_subscriptions.discard(pending_subscription)
            self._active_subscriptions.add(pending_subscription)

            self.logger.info(f"Subscription acknowledged: {pending_subscription}")
            self._pending_subscriptions.discard(pending_subscription)

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
            self._handle_offered_service(offered_service)

        for subscription in extract_subscribe_entries(someip_sd_header):
            self._handle_subscription(subscription)

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
            self._handle_subscription(subscription)

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
        self._sd_socket_mcast = create_rcv_multicast_socket(
            self.sd_address, self.sd_port, DEFAULT_INTERFACE_IP
        )

        loop = asyncio.get_running_loop()
        self._mcast_transport, _ = await loop.create_datagram_endpoint(
            lambda: DatagramAdapter(
                target=None,
                datagram_received_callback=self.datagram_received_mcast,
                connection_lost_callback=self.connection_lost_mcast,
            ),
            sock=self._sd_socket_mcast,
        )

        self._sd_socket_ucast = create_udp_socket(self.interface, self.sd_port)
        self._ucast_transport, _ = await loop.create_datagram_endpoint(
            lambda: DatagramAdapter(
                target=None,
                datagram_received_callback=self.datagram_received_ucast,
                connection_lost_callback=self.connection_lost_ucast,
            ),
            sock=self._sd_socket_ucast,
        )


async def async_main():
    parser = argparse.ArgumentParser(description="SOME/IP Daemon")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--log-path", help="Path to log file")
    args = parser.parse_args()

    daemon = SomeipDaemon(args.config, args.log_path)
    await daemon.start_server()


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
