# Copyright (C) 2024 Christian H.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


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

import someipy
from someipy._internal._common.endpoint import Endpoint
from someipy._internal._daemon.daemon_server_client import (
    ClientMessageEventArgs,
    DaemonServerClient,
)
from someipy._internal._daemon.subscription import Subscription
from someipy._internal._daemon.subscription_storage import SubscriptionStorage
from someipy._internal._sd.deserialization.sd_deserialization import (
    deserialize_sd_message,
    is_sd_message,
)
from someipy._internal._sd.deserialization.sd_serialization import serialize_sd_message
from someipy._internal._sd.entries.offer_service_entry import OfferServiceEntry
from someipy._internal._sd.entries.stop_subscribe_eventgroup_entry import (
    StopSubscribeEventGroupEntry,
)
from someipy._internal._sd.entries.subscribe_eventgroup_entry import (
    SubscribeEventGroupEntry,
)
from someipy._internal._sd.options.endpoint import IpV4EndpointOption
from someipy._internal._sd.sd_message import SdMessage
from someipy._internal._sd.sd_message_creator import (
    create_offer_service_message,
    create_stop_offer_service_message,
)
from someipy._internal._sd.service_instance import ServiceInstance
from someipy._internal.message_types import MessageType
from someipy._internal.someip_endpoint import (
    TCPClientSomeipEndpoint,
    TCPSomeipEndpoint,
)
from someipy._internal.someip_endpoint_factory import SomeipEndpointFactory
from someipy._internal.someip_endpoint_storage import SomeipEndpointStorage
from someipy._internal.someip_message import SomeIpMessage
from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy._internal.session_handler import SessionHandler
from someipy._internal.simple_timer import SimplePeriodicTimer
from someipy._internal.someip_header import SomeIpHeader
from someipy._internal.someip_sd_builder import (
    build_subscribe_eventgroup_ack_entry,
    build_subscribe_eventgroup_ack_sd_header,
)
from someipy._internal.someip_sd_extractors import (
    extract_subscribe_ack_eventgroup_entries,
    extract_subscribe_entries,
    extract_subscribe_nack_eventgroup_entries,
)
from someipy._internal.someip_sd_header import (
    SdEntryType,
    SdEventGroupEntry,
    SdService,
    SdService2,
    SdServiceWithTimestamp,
    SdSubscription,
    SomeIpSdHeader,
)
from someipy._internal.subscribers import EventGroupSubscriber, Subscribers
from someipy._internal._daemon.uds_messages import (
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
    create_rcv_broadcast_socket,
    create_udp_socket,
)
from someipy._internal._daemon.offer_service_storage import (
    OfferServiceStorage,
    ServiceToOffer,
)
from someipy.service import Event, Method, EventGroup
from someipy._internal._daemon.daemon_server import (
    ClientConnectedEventArgs,
    DaemonServer,
)


DEFAULT_SOCKET_PATH = "/tmp/someipyd.sock"
DEFAULT_CONFIG_FILE = "someipyd.json"
DEFAULT_SD_ADDRESS = "224.224.224.245"
DEFAULT_INTERFACE_IP = "127.0.0.1"
DEFAULT_SD_PORT = 30490
DEFAULT_TCP_PORT = 30500


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

    def __init__(
        self,
        server: DaemonServer,
        endpoint_factory: SomeipEndpointFactory,
        config: dict = None,
        logger: logging.Logger = None,
    ):

        self.config = config
        self.logger = logger
        self._endpoint_factory = endpoint_factory

        self.sd_address = self.config.get("sd_address", DEFAULT_SD_ADDRESS)
        self.sd_port = self.config.get("sd_port", DEFAULT_SD_PORT)
        self.interface = self.config.get("interface", DEFAULT_INTERFACE_IP)

        self._server = server

        self._sd_socket_mcast = None
        self._sd_socket_ucast = None
        self._mcast_transport = None
        self._ucast_transport = None

        # Services offered by other ECUs
        self._found_services: List[ServiceInstance] = []

        # Services offered by this daemon
        self._services_to_offer = OfferServiceStorage()
        self._offer_timers: Dict[int, SimplePeriodicTimer] = {}

        # Active subscriptions to services offered by this daemon
        self._service_subscribers: Dict[ServiceToOffer, Subscribers] = {}

        # Subscriptions requested by local clients
        self._requested_subscriptions = SubscriptionStorage()

        self._pending_subscriptions: Set[Subscription] = set()
        self._active_subscriptions: Set[Subscription] = set()

        self._mcast_session_handler = SessionHandler()
        self._unicast_session_handler = SessionHandler()

        # Qeueues and tasks stored by id of asyncio.StreamWriter
        self._tx_queues: Dict[int, asyncio.Queue] = {}
        self._tx_tasks: Dict[int, asyncio.Task] = {}

        self._someip_server_endpoints = SomeipEndpointStorage()
        self._someip_client_endpoints = SomeipEndpointStorage()

        self._ttl_task: asyncio.Task = None

        self._issued_method_calls: Dict[MethodCall, int] = {}

    async def new_client_connected(
        self, sender: object, event_args: ClientConnectedEventArgs
    ):
        self.logger.info(f"New client connected: {event_args.client.id}")

        # Create the tx_queue and tx_task for the client using the writers id
        self._tx_queues[event_args.client.id] = asyncio.Queue()
        self._tx_tasks[event_args.client.id] = asyncio.create_task(
            self.tx_task(event_args.client)
        )

        event_args.client.message_received += self.handle_client_message

    async def client_disconnected(
        self, sender: object, event_args: ClientConnectedEventArgs
    ):
        self.logger.info(f"Client disconnected: {event_args.client.id}")

        client_id = event_args.client.id

        event_args.client.message_received -= self.handle_client_message

        # Remove all subscriptions for the client
        self._requested_subscriptions.remove_client(client_id)

        # Clean up the transmission task for the client. This will also clean up the transmission queue
        tx_task = self._tx_tasks.pop(client_id, None)
        if tx_task and not tx_task.cancelled():
            tx_task.cancel()
            try:
                await tx_task
            except asyncio.CancelledError:
                pass

        self._services_to_offer.remove_client(client_id)
        self._cleanup_unused_timers()

        client_endpoints = self._someip_server_endpoints.get_endpoints(client_id)
        if client_endpoints is not None:
            for endpoint in client_endpoints:
                self.logger.debug(
                    f"Closing endpoint {endpoint.dst_ip()}:{endpoint.dst_port()} for client {client_id}"
                )
                endpoint.shutdown()
                self._someip_server_endpoints.remove_endpoint(client_id, endpoint)

        self.logger.debug(f"Client disconnected")

    async def _check_services_ttl_task(self):
        try:
            while True:
                await asyncio.sleep(0.1)
                self._check_service_ttl_task_impl()

        except asyncio.CancelledError:
            # Task was cancelled - exit cleanly
            self.logger.debug("Service TTL checker task cancelled")
        except Exception as e:
            self.logger.error(f"Error in service TTL checker task: {e}")
        pass

    def _check_service_ttl_task_impl(self):

        self._cleanup_obsolete_pending_subscriptions()
        self._cleanup_active_subscriptions()

        count_before = len(self._found_services)

        current_time = time.time()

        # Process timeouts and filter services in one operation
        self._found_services = [
            service
            for service in self._found_services
            if not (current_time - service.timestamp > service.ttl)
        ]

        count_after = len(self._found_services)
        if count_before != count_after:
            self.logger.info(
                f"Removed {count_before - count_after} timed out services. Remaining: {count_after}"
            )

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
                    and str(service.endpoint.ip) == dst_addr[0]
                    and service.endpoint.port == dst_addr[1]
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
                        and str(active_subscription.server_endpoint.ip) == src_addr[0]
                        and active_subscription.server_endpoint.port == src_addr[1]
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
                                and requested_subscription.client_endpoint.ip
                                == active_subscription.client_endpoint.ip
                                and requested_subscription.client_endpoint.port
                                == active_subscription.client_endpoint.port
                            ):

                                client_ids = (
                                    self._requested_subscriptions.get_client_ids(
                                        requested_subscription
                                    )
                                )

                                for client_id in client_ids:
                                    tx_queue = self._tx_queues.get(client_id)
                                    if tx_queue:
                                        tx_queue.put_nowait(
                                            self.prepare_message(event_msg)
                                        )

    def _cleanup_active_subscriptions(self):
        current_time = time.time()
        subscriptions_to_remove = []
        for subscription in self._active_subscriptions:
            if (
                current_time - subscription.timestamp_last_update
                > subscription.ttl_seconds
            ):
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
            if current_time - subscription.timestamp_last_update > 10.0:
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
                    service.endpoint.ip == endpoint.ip()
                    and service.endpoint_port == endpoint.port()
                ):
                    endpoint_used = True
                    break

            if not endpoint_used:
                endpoints_to_close.append(endpoint)

    async def tx_task(self, client: DaemonServerClient):
        tx_queue = self._tx_queues[client.id]
        try:
            while True:
                try:
                    # Wait on queue with timeout
                    data = await asyncio.wait_for(tx_queue.get(), timeout=0.2)

                    try:
                        # Send the data
                        await client.send(data)
                        tx_queue.task_done()
                    except ConnectionError as e:
                        self.logger.error(f"Error sending data in tx task: {e}")
                        break

                except asyncio.TimeoutError:
                    # Periodic timeout for cancellation check
                    continue

        except asyncio.CancelledError:
            self.logger.debug(f"TX task for writer {client.id} cancelled")
            # Perform cleanup here
            try:
                await client.close()
            except Exception as e:
                self.logger.error(f"Error closing writer: {e}")
        finally:
            # Always clean up the queue
            self._tx_queues.pop(client.id, None)
            self.logger.debug(f"TX task for writer {client.id} finished")

    async def handle_client_message(
        self, sender: object, event_args: ClientMessageEventArgs
    ):
        client_id = event_args.client.id

        message = event_args.message
        message_type = event_args.message.get("type")
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
                await handler(message, client_id)
                return
            else:
                handler(message, client_id)
                return
        else:
            self.logger.warning(
                f"Received unknown message type: {message_type}. Message: {message}"
            )

    async def _handle_subscribe_eventgroup_request(
        self, message: SubscribeEventGroupRequest, client_id: int
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

                udp_endpoint = await self._endpoint_factory.create_server_endpoint(
                    Endpoint(
                        ip=ipaddress.IPv4Address(message["client_endpoint_ip"]),
                        port=message["client_endpoint_port"],
                    ),
                    TransportLayerProtocol.UDP,
                    self._someip_message_callback,
                )

                self._someip_client_endpoints.add_endpoint(client_id, udp_endpoint)

        if message["tcp"]:
            protocols.append(TransportLayerProtocol.TCP)

        event_group = EventGroup.from_json(message["eventgroup"])

        client_address = ipaddress.IPv4Address(message["client_endpoint_ip"])
        client_endpoint = Endpoint(
            ip=client_address, port=message["client_endpoint_port"]
        )

        new_subscription = Subscription(
            service_id=message["service_id"],
            instance_id=message["instance_id"],
            major_version=message["major_version"],
            client_endpoint=client_endpoint,
            server_endpoint=None,
            protocols=frozenset(protocols),
            eventgroup=event_group,
            ttl_seconds=message["ttl_subscription"],
        )

        if new_subscription in self._requested_subscriptions.subscriptions:
            self.logger.warning(
                f"The requested subscription received by client {client_id} is already requested."
            )

        self.logger.debug(f"Add subscription to storage with id {client_id}")
        self._requested_subscriptions.add_subscription(client_id, new_subscription)

    def _handle_stop_subscribe_eventgroup_request(
        self, message: StopSubscribeEventGroupRequest, client_id: int
    ):
        client_endpoint = Endpoint(
            ip=ipaddress.IPv4Address(message["client_endpoint_ip"]),
            port=message["client_endpoint_port"],
        )

        event_group = EventGroup.from_json(message["eventgroup"])

        protocols = [
            protocol
            for flag, protocol in (
                (message["udp"], TransportLayerProtocol.UDP),
                (message["tcp"], TransportLayerProtocol.TCP),
            )
            if flag
        ]

        subscription_to_remove = Subscription(
            service_id=message["service_id"],
            instance_id=message["instance_id"],
            major_version=message["major_version"],
            client_endpoint=client_endpoint,
            server_endpoint=None,
            protocols=frozenset(protocols),
            eventgroup=event_group,
            ttl_seconds=0,  # TTL is not relevant for removal
        )

        self._requested_subscriptions.remove_subscription(
            client_id, subscription_to_remove
        )

        if (
            len(self._requested_subscriptions.get_client_ids(subscription_to_remove))
            == 0
        ):

            for pending_subscription in list(self._pending_subscriptions):
                if (
                    pending_subscription.service_id == subscription_to_remove.service_id
                    and pending_subscription.instance_id
                    == subscription_to_remove.instance_id
                    and pending_subscription.major_version
                    == subscription_to_remove.major_version
                    and pending_subscription.eventgroup.id
                    == subscription_to_remove.eventgroup.id
                    and pending_subscription.client_endpoint
                    == subscription_to_remove.client_endpoint
                ):
                    self._pending_subscriptions.remove(pending_subscription)

            for active_subscription in list(self._active_subscriptions):
                if (
                    active_subscription.service_id == subscription_to_remove.service_id
                    and active_subscription.instance_id
                    == subscription_to_remove.instance_id
                    and active_subscription.major_version
                    == subscription_to_remove.major_version
                    and active_subscription.eventgroup.id
                    == subscription_to_remove.eventgroup.id
                    and active_subscription.client_endpoint
                    == subscription_to_remove.client_endpoint
                ):
                    self._active_subscriptions.remove(active_subscription)

                    (
                        session_id,
                        reboot_flag,
                    ) = self._unicast_session_handler.update_session()

                    # Build subscribe message
                    sd_message = SdMessage()
                    sd_message.session_id = session_id
                    sd_message.reboot_flag = reboot_flag

                    options = []
                    for protocol in active_subscription.protocols:
                        options.append(
                            IpV4EndpointOption(
                                address=active_subscription.client_endpoint.ip,
                                protocol=protocol,
                                port=active_subscription.client_endpoint.port,
                            )
                        )

                    entry = StopSubscribeEventGroupEntry(
                        service_id=active_subscription.service_id,
                        instance_id=active_subscription.instance_id,
                        major_version=active_subscription.major_version,
                        eventgroup_id=active_subscription.eventgroup.id,
                        counter=0,
                        ip_v4_endpoints=options,
                        ip_v6_endpoints=[],
                    )
                    sd_message.entries.append(entry)

                    # Send to server
                    if self._ucast_transport:
                        self._ucast_transport.sendto(
                            serialize_sd_message(sd_message),
                            (
                                str(active_subscription.server_endpoint.ip),
                                self.sd_port,
                            ),
                        )

    async def _handle_offer_service_request(
        self, message: OfferServiceRequest, client_id: int
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
            client_writer_id=client_id,
            instance_id=message["instance_id"],
            service_id=message["service_id"],
            major_version=message["major_version"],
            minor_version=message["minor_version"],
            offer_ttl_seconds=message["ttl"],
            cyclic_offer_delay_ms=message["cyclic_offer_delay_ms"],
            endpoint=Endpoint(
                ipaddress.IPv4Address(message["endpoint_ip"]), message["endpoint_port"]
            ),
            methods=methods,
            eventgroups=eventgroups,
        )

        self._services_to_offer.add_service(service_to_add)

        # Check if there is already an endpoint for the ip and port, if not, open a new endpoint
        if service_to_add.has_udp:
            if not self._someip_server_endpoints.has_endpoint(
                str(service_to_add.endpoint.ip),
                service_to_add.endpoint.port,
                TransportLayerProtocol.UDP,
            ):
                self.logger.debug(
                    f"Creating new UDP endpoint for {service_to_add.endpoint}"
                )

                udp_endpoint = await self._endpoint_factory.create_server_endpoint(
                    service_to_add.endpoint,
                    TransportLayerProtocol.UDP,
                    self._someip_message_callback,
                )

                self._someip_server_endpoints.add_endpoint(client_id, udp_endpoint)

        if service_to_add.has_tcp:
            if not self._someip_server_endpoints.has_endpoint(
                str(service_to_add.endpoint.ip),
                service_to_add.endpoint.port,
                TransportLayerProtocol.TCP,
            ):
                self.logger.debug(
                    f"Creating new TCP endpoint for {service_to_add.endpoint}"
                )

                tcp_endpoint = await self._endpoint_factory.create_server_endpoint(
                    service_to_add.endpoint,
                    TransportLayerProtocol.TCP,
                    self._someip_message_callback,
                )

                self._someip_server_endpoints.add_endpoint(client_id, tcp_endpoint)

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
            endpoint=Endpoint(
                ipaddress.IPv4Address(message["endpoint_ip"]), message["endpoint_port"]
            ),
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

        sd_message = create_stop_offer_service_message(
            services_to_stop=[service_to_stop],
            session_id=session_id,
            reboot_flag=reboot_flag,
        )

        if self._ucast_transport:
            self.logger.debug(
                f"Send stop offer message for service 0x{service_to_stop.service_id:04x}, instance 0x{service_to_stop.instance_id:04x} to {self.sd_address}:{self.sd_port}"
            )
            self._ucast_transport.sendto(
                serialize_sd_message(sd_message), (self.sd_address, self.sd_port)
            )

        if service_to_stop.has_udp:
            try:
                udp_endpoint = self._someip_server_endpoints.get_endpoint(
                    writer_id, TransportLayerProtocol.UDP
                )
                if udp_endpoint:
                    self.logger.debug(
                        f"Closing UDP endpoint for {service_to_stop.endpoint}"
                    )
                    udp_endpoint.shutdown()
                    self._someip_server_endpoints.remove_endpoint(
                        writer_id, udp_endpoint
                    )
            except Exception as e:
                self.logger.error(
                    f"Error closing UDP endpoint for {service_to_stop.endpoint}: {e}"
                )

        if service_to_stop.has_tcp:
            try:
                tcp_endpoint = self._someip_server_endpoints.get_endpoint(
                    writer_id, TransportLayerProtocol.TCP
                )
                if tcp_endpoint:
                    self.logger.debug(
                        f"Closing TCP endpoint for {service_to_stop.endpoint}"
                    )
                    tcp_endpoint.shutdown()
                    self._someip_server_endpoints.remove_endpoint(
                        writer_id, tcp_endpoint
                    )
            except Exception as e:
                self.logger.error(
                    f"Error closing TCP endpoint for {service_to_stop.endpoint}: {e}"
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
        self, message: OutboundCallMethodRequest, client_id: int
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

                dst_endpoint = Endpoint(
                    ip=ipaddress.IPv4Address(message["dst_endpoint_ip"]),
                    port=message["dst_endpoint_port"],
                )
                src_endpoint = Endpoint(
                    ip=ipaddress.IPv4Address(message["src_endpoint_ip"]),
                    port=message["src_endpoint_port"],
                )

                udp_endpoint = await self._endpoint_factory.create_udp_client_endpoint(
                    dst_endpoint,
                    src_endpoint,
                    self._someip_message_callback,
                    self.logger,
                )
                self._someip_client_endpoints.add_endpoint(client_id, udp_endpoint)

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

                tcp_endpoint = self._endpoint_factory.create_tcp_client_endpoint(
                    Endpoint(
                        ip=ipaddress.IPv4Address(message["dst_endpoint_ip"]),
                        port=message["dst_endpoint_port"],
                    ),
                    Endpoint(
                        ip=ipaddress.IPv4Address(message["src_endpoint_ip"]),
                        port=message["src_endpoint_port"],
                    ),
                    self._someip_message_callback,
                    self.logger,
                )

                self._someip_client_endpoints.add_endpoint(client_id, tcp_endpoint)
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

        self._issued_method_calls[new_call] = client_id

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

            service_to_add = ServiceInstance(
                service_id=service.service_id,
                instance_id=service.instance_id,
                major_version=service.major_version,
                minor_version=service.minor_version,
                ttl=service.offer_ttl_seconds,
                endpoint=service.endpoint,
                protocols=frozenset(protocols_to_add),
                timestamp=0.0,
            )

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
                (message["service_id"] == found_service.service_id)
                and (
                    message["instance_id"] == found_service.instance_id
                    or message["instance_id"] == 0xFFFF
                )
                and (
                    message["major_version"] == found_service.major_version
                    or message["major_version"] == 0xFF
                )
                and (
                    message["minor_version"] == found_service.minor_version
                    or message["minor_version"] == 0xFFFFFFFF
                )
            ):
                service_found = True
                response = create_uds_message(
                    FindServiceResponse,
                    success=True,
                    service_id=found_service.service_id,
                    instance_id=found_service.instance_id,
                    major_version=found_service.major_version,
                    minor_version=found_service.minor_version,
                    endpoint_ip=str(found_service.endpoint.ip),
                    endpoint_port=found_service.endpoint.port,
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
                    f"Internal subscription for service {message['service_id']:04x}, "
                    f"instance {message['instance_id']:04x}, eventgroup {message['eventgroup_id']:04x}"
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

            sd_message = create_offer_service_message(
                services_to_offer=services_to_offer,
                session_id=session_id,
                reboot_flag=reboot_flag,
            )

            if self._ucast_transport:
                self._ucast_transport.sendto(
                    serialize_sd_message(sd_message), (self.sd_address, self.sd_port)
                )

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
        try:
            if self._ttl_task is None or self._ttl_task.done():
                self._ttl_task = asyncio.create_task(self._check_services_ttl_task())
            await self.start_sd_listening()
            await self._server.serve_forever()
        except asyncio.CancelledError:
            self.logger.info(f"Server cancelled.")
        finally:
            if self._mcast_transport:
                self._mcast_transport.close()
            if self._ucast_transport:
                self._ucast_transport.close()

            self.logger.info(f"Server stopped.")

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

    def _handle_offered_service(self, offered_service: ServiceInstance):
        self.logger.info(f"Received offered service: {offered_service}")

        if offered_service not in self._found_services:
            self._found_services.append(offered_service)
        else:
            # Update the timestamp if the service is already in the list
            index = self._found_services.index(offered_service)
            self._found_services[index].timestamp = offered_service.timestamp

        # Check if there is a requested subscription for this service
        for (
            requested_subscription,
            client_id,
        ) in self._requested_subscriptions.has_subscriptions(
            offered_service.service_id,
            offered_service.instance_id,
            offered_service.major_version,
        ):

            requested_protocols: Set[TransportLayerProtocol] = (
                offered_service.protocols & requested_subscription.protocols
            )

            if TransportLayerProtocol.TCP in requested_protocols:
                if not self._someip_client_endpoints.has_tcp_endpoint(
                    str(requested_subscription.client_endpoint.ip),
                    requested_subscription.client_endpoint.port,
                    str(offered_service.endpoint.ip),
                    offered_service.endpoint.port,
                ):
                    self.logger.debug(
                        f"Creating new TCP endpoint for {requested_subscription.client_endpoint}"
                    )

                    tcp_endpoint = self._endpoint_factory.create_tcp_client_endpoint(
                        offered_service.endpoint,
                        requested_subscription.client_endpoint,
                        self._someip_message_callback,
                        self.logger,
                    )

                    self._someip_client_endpoints.add_endpoint(client_id, tcp_endpoint)

                    # TODO: This shall not block the handle_client function. A new task shall be created
                    # For TCP wait for the connection to be established
                    # while not tcp_endpoint.is_connected():
                    #    await asyncio.sleep(0.2)

            (
                session_id,
                reboot_flag,
            ) = self._unicast_session_handler.update_session()

            # Build subscribe message
            sd_message = SdMessage()
            sd_message.session_id = session_id
            sd_message.reboot_flag = reboot_flag

            options = []
            for protocol in requested_protocols:
                options.append(
                    IpV4EndpointOption(
                        address=requested_subscription.client_endpoint.ip,
                        protocol=protocol,
                        port=requested_subscription.client_endpoint.port,
                    )
                )

            entry = SubscribeEventGroupEntry(
                service_id=offered_service.service_id,
                instance_id=offered_service.instance_id,
                major_version=offered_service.major_version,
                ttl=requested_subscription.ttl_seconds,
                eventgroup_id=requested_subscription.eventgroup.id,
                counter=0,
                ip_v4_endpoints=options,
                ip_v6_endpoints=[],
            )
            sd_message.entries.append(entry)

            client_endpoint = requested_subscription.client_endpoint
            server_endpoint = offered_service.endpoint

            pending_subscription = Subscription(
                service_id=offered_service.service_id,
                instance_id=offered_service.instance_id,
                major_version=offered_service.major_version,
                eventgroup=requested_subscription.eventgroup,
                ttl_seconds=requested_subscription.ttl_seconds,
                client_endpoint=client_endpoint,
                server_endpoint=server_endpoint,
                protocols=frozenset(requested_protocols),
                timestamp_last_update=time.time(),
            )
            self._pending_subscriptions.add(pending_subscription)

            if self._ucast_transport:
                self._ucast_transport.sendto(
                    serialize_sd_message(sd_message),
                    (str(offered_service.endpoint.ip), self.sd_port),
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
            pending_subscription.timestamp_last_update = time.time()
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

        if not is_sd_message(data):
            return

        sd_message = deserialize_sd_message(data, addr[0], addr[1], multicast=True)
        sd_message.timestamp = time.time()

        for offer_service_entry in [
            o
            for o in sd_message.entries
            if o.type
            == someipy._internal._sd.entries.sd_entry.SdEntryType.OFFER_SERVICE
        ]:
            entry: OfferServiceEntry = offer_service_entry

            protocols = set()
            for ep in entry.ip_v4_endpoints:
                protocols.add(ep.protocol)
            for ep in entry.ip_v6_endpoints:
                protocols.add(ep.protocol)

            endpoint = Endpoint(
                ip=entry.ip_v4_endpoints[0].address,
                port=entry.ip_v4_endpoints[0].port,
            )

            service_instance = ServiceInstance(
                service_id=entry.service_id,
                instance_id=entry.instance_id,
                major_version=entry.major_version,
                minor_version=entry.minor_version,
                ttl=entry.ttl,
                endpoint=endpoint,
                protocols=frozenset(protocols),
                timestamp=sd_message.timestamp,
            )
            self._handle_offered_service(service_instance)

        someip_sd_header = SomeIpSdHeader.from_buffer(data)

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
        if self.sd_address.startswith("224"):
            self._sd_socket_mcast = create_rcv_multicast_socket(
                self.sd_address, self.sd_port, self.interface
            )
        else:
            self._sd_socket_mcast = create_rcv_broadcast_socket(
                self.sd_address, self.sd_port, self.interface
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


def _configure_logging(log_level=logging.DEBUG, log_path=None) -> logging.Logger:
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


def _load_config(config_file: str) -> dict:
    if config_file and os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading config file: {e}. Using defaults.")
            return {}
    elif os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading config file: {e}. Using defaults.")
            return {}
    else:
        return {}


async def async_main():
    parser = argparse.ArgumentParser(description="SOME/IP Daemon")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--log-path", help="Path to log file")
    args = parser.parse_args()

    # Load configuration
    config = _load_config(args.config)

    # Logging
    log_path = args.log_path if args.log_path else config.get("log_path", None)
    log_level = config.get("log_level", "INFO")

    log_level_mapping = {
        "DEBUG": logging.DEBUG,
        "ERROR": logging.ERROR,
        "INFO": logging.INFO,
        "FATAL": logging.FATAL,
    }

    if log_level in log_level_mapping:
        log_level = log_level_mapping[log_level]

    logger = _configure_logging(log_level=log_level, log_path=log_path)

    logger.info(
        f"Starting SOME/IP daemon with config:\n"
        f"Socket path: {config.get('socket_path', DEFAULT_SOCKET_PATH)}\n"
        f"SD address: {config.get('sd_address', DEFAULT_SD_ADDRESS)}\n"
        f"SD port: {config.get('sd_port', DEFAULT_SD_PORT)}\n"
        f"Interface: {config.get('interface', DEFAULT_INTERFACE_IP)}\n"
        f"Loglevel: {log_level}\n"
        f"Log path: {log_path if log_path else 'Console'}\n"
        f"Use tcp: {config.get('use_tcp', False)}\n"
        f"Tcp port: {config.get('tcp_port', None)}\n"
        f"Tcp host: {config.get('tcp_host', '127.0.0.1')}\n"
    )

    daemon_server = DaemonServer(logger)

    daemon = SomeipDaemon(daemon_server, SomeipEndpointFactory(), config, logger)

    daemon_server.client_connected += daemon.new_client_connected
    daemon_server.client_disconnected += daemon.client_disconnected

    await daemon_server.start(
        use_tcp=config.get("use_tcp", False),
        socket_path=config.get("socket_path", DEFAULT_SOCKET_PATH),
        tcp_port=config.get("tcp_port", 30500),
        host=config.get("tcp_host", "127.0.0.1"),
    )

    await daemon.start_server()


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
