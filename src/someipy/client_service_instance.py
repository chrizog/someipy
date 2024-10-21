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

import asyncio
from enum import Enum
import struct
from typing import Iterable, Tuple, Callable, Set, List

from someipy import Service
from someipy._internal.method_result import MethodResult
from someipy._internal.someip_data_processor import SomeipDataProcessor
from someipy._internal.someip_sd_header import (
    SdService,
    TransportLayerProtocol,
    SdEventGroupEntry,
)
from someipy._internal.someip_header import (
    SomeIpHeader,
)
from someipy._internal.someip_sd_builder import build_subscribe_eventgroup_sd_header
from someipy._internal.service_discovery_abcs import (
    ServiceDiscoveryObserver,
    ServiceDiscoverySender,
)
from someipy._internal.utils import (
    create_udp_socket,
    EndpointType,
    endpoint_to_str_int_tuple,
)
from someipy._internal.logging import get_logger
from someipy._internal.message_types import MessageType
from someipy._internal.return_codes import ReturnCode
from someipy._internal.someip_endpoint import (
    SomeipEndpoint,
    UDPSomeipEndpoint,
    SomeIpMessage,
)
from someipy._internal.tcp_connection import TcpConnection

_logger_name = "client_service_instance"


class ExpectedAck:
    def __init__(self, eventgroup_id: int) -> None:
        self.eventgroup_id = eventgroup_id

    def __eq__(self, value: object) -> bool:
        return self.eventgroup_id == value.eventgroup_id


class FoundService:
    service: SdService

    def __init__(self, service: SdService) -> None:
        self.service = service

    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, FoundService):
            return self.service == __value.service


class ClientServiceInstance(ServiceDiscoveryObserver):
    _service: Service
    _instance_id: int
    _endpoint: EndpointType
    _protocol: TransportLayerProtocol
    _someip_endpoint: SomeipEndpoint
    _ttl: int
    _sd_sender: ServiceDiscoverySender

    _eventgroups_to_subscribe: Set[int]
    _expected_acks: List[ExpectedAck]

    _callback: Callable[[bytes], None]
    _found_services: Iterable[FoundService]
    _subscription_active: bool
    _method_call_future: asyncio.Future

    def __init__(
        self,
        service: Service,
        instance_id: int,
        endpoint: EndpointType,
        protocol: TransportLayerProtocol,
        someip_endpoint: SomeipEndpoint,
        ttl: int = 0,
        sd_sender=None,
    ):
        self._service = service
        self._instance_id = instance_id
        self._endpoint = endpoint
        self._protocol = protocol
        self._someip_endpoint = someip_endpoint
        self._ttl = ttl
        self._sd_sender = sd_sender

        self._eventgroups_to_subscribe = set()
        self._expected_acks = []
        self._callback = None

        self._tcp_connection: TcpConnection = None

        self._tcp_connect_lock = asyncio.Lock()
        self._tcp_task = None
        self._tcp_connection_established_event = asyncio.Event()
        self._shutdown_requested = False

        self._found_services = []
        self._subscription_active = False
        self._method_call_future = None

    def register_callback(self, callback: Callable[[SomeIpMessage], None]) -> None:
        """
        Register a callback function to be called when a SOME/IP event is received.

        Args:
            callback (Callable[[SomeIpMessage], None]): The callback function to be registered.
                This function should take a SomeIpMessage object as its only argument and return None.

        Returns:
            None
        """
        self._callback = callback

    def service_found(self) -> bool:
        """
        Returns whether the service instance represented by the ClientServiceInstance has been offered by a server and was found.
        """
        has_service = False
        for s in self._found_services:
            if (
                s.service.service_id == self._service.id
                and s.service.instance_id == self._instance_id
            ):
                has_service = True
                break
        return has_service

    async def call_method(self, method_id: int, payload: bytes) -> MethodResult:
        """
        Calls a method on the service instance represented by the ClientServiceInstance.

        Args:
            method_id (int): The ID of the method to call.
            payload (bytes): The payload to send with the method call.

        Returns:
            MethodResult: The result of the method call which can contain an error or a successfull result including the response payload.

        Raises:
            RuntimeError: If the TCP connection to the server cannot be established or if the server service has not been found yet.
            asyncio.TimeoutError: If the method call times out, i.e. the server does not send back a response within one second.
        """

        get_logger(_logger_name).debug(f"Try to call method 0x{method_id:04X}")

        if not self.service_found():
            get_logger(_logger_name).warning(
                f"Method 0x{method_id:04x} called, but service 0x{self._service.id:04X} with instance 0x{self._instance_id:04X} not found yet."
            )
            raise RuntimeError(
                f"Method 0x{method_id:04x} called, but service 0x{self._service.id:04X} with instance 0x{self._instance_id:04X} not found yet."
            )

        header = SomeIpHeader(
            service_id=self._service.id,
            method_id=method_id,
            client_id=0x00,
            session_id=0x00,
            protocol_version=0x01,
            interface_version=0x00,
            message_type=MessageType.REQUEST.value,
            return_code=0x00,
            length=len(payload) + 8,
        )
        someip_message = SomeIpMessage(header, payload)

        self._method_call_future = asyncio.get_running_loop().create_future()

        dst_address = str(self._found_services[0].service.endpoint[0])
        dst_port = self._found_services[0].service.endpoint[1]

        if self._protocol == TransportLayerProtocol.TCP:
            # In case of TCP, first try to connect to the TCP server
            # [PRS_SOMEIP_00708] The TCP connection shall be opened by the client, when the
            # first method call shall be transported or the client tries to receive the first notifications
            if self._tcp_task is None:
                get_logger(_logger_name).debug(
                    f"Create new TCP task for client of 0x{self._instance_id:04X}, 0x{self._service.id:04X}"
                )
                self._tcp_task = asyncio.create_task(
                    self.setup_tcp_connection(
                        str(self._endpoint[0]), self._endpoint[1], dst_address, dst_port
                    )
                )

            try:
                # Wait for two seconds until the connection is established, otherwise return an error
                await asyncio.wait_for(self._tcp_connection_established_event.wait(), 2)
            except asyncio.TimeoutError:
                get_logger(_logger_name).error(
                    f"Cannot establish TCP connection to {dst_address}:{dst_port}."
                )
                raise RuntimeError(
                    f"Cannot establish TCP connection to {dst_address}:{dst_port}."
                )

            if self._tcp_connection.is_open():
                self._tcp_connection.writer.write(someip_message.serialize())
            else:
                get_logger(_logger_name).error(
                    f"TCP connection to {dst_address}:{dst_port} is not opened."
                )
                raise RuntimeError(
                    f"TCP connection to {dst_address}:{dst_port} is not opened."
                )

        else:
            # In case of UDP, just send out the datagram and wait for the response
            self._someip_endpoint.sendto(
                someip_message.serialize(),
                endpoint_to_str_int_tuple(self._found_services[0].service.endpoint),
            )

        # After sending the method call wait for maximum one second
        try:
            await asyncio.wait_for(self._method_call_future, 1.0)
        except asyncio.TimeoutError:
            get_logger(_logger_name).error(
                f"Waiting on response for method call 0x{method_id:04X} timed out."
            )
            raise

        return self._method_call_future.result()

    def someip_message_received(
        self, someip_message: SomeIpMessage, addr: Tuple[str, int]
    ) -> None:
        if (
            someip_message.header.client_id == 0x00
            and someip_message.header.message_type == MessageType.NOTIFICATION.value
            and someip_message.header.return_code == ReturnCode.E_OK.value
        ):
            if self._callback is not None and self._subscription_active:
                self._callback(someip_message)
                return

        if (
            someip_message.header.message_type == MessageType.RESPONSE.value
            or someip_message.header.message_type == MessageType.ERROR.value
        ):
            if self._method_call_future is not None:
                result = MethodResult()
                result.message_type = MessageType(someip_message.header.message_type)
                result.return_code = ReturnCode(someip_message.header.return_code)
                result.payload = someip_message.payload
                self._method_call_future.set_result(result)
                return

    def subscribe_eventgroup(self, eventgroup_id: int):
        """
        Adds an event group to the list of event groups to subscribe to.

        Args:
            eventgroup_id (int): The ID of the event group to subscribe to.

        Returns:
            None

        Raises:
            None

        Notes:
            - If the event group ID is already in the subscription list, a debug log message is printed.
        """
        if eventgroup_id in self._eventgroups_to_subscribe:
            get_logger(_logger_name).debug(
                f"Eventgroup ID {eventgroup_id} is already in subscription list."
            )
        self._eventgroups_to_subscribe.add(eventgroup_id)

    def stop_subscribe_eventgroup(self, eventgroup_id: int):
        """
        Stops subscribing to an event group. Not implemented yet.

        Args:
            eventgroup_id (int): The ID of the event group to stop subscribing to.

        Raises:
            NotImplementedError: This method is not yet implemented.

        Notes:
            - This method is currently not implemented and raises a `NotImplementedError`.
        """
        # TODO: Implement StopSubscribe
        raise NotImplementedError

    def handle_find_service(self):
        # Not needed in client service instance
        pass

    def handle_offer_service(self, offered_service: SdService):
        if self._service.id != offered_service.service_id:
            return
        if self._instance_id != offered_service.instance_id:
            return

        if (
            offered_service.service_id == self._service.id
            and offered_service.instance_id == self._instance_id
        ):
            if FoundService(offered_service) not in self._found_services:
                self._found_services.append(FoundService(offered_service))

            if len(self._eventgroups_to_subscribe) == 0:
                return

            # Try to subscribe to requested event groups
            for eventgroup_to_subscribe in self._eventgroups_to_subscribe:
                (
                    session_id,
                    reboot_flag,
                ) = self._sd_sender.get_unicast_session_handler().update_session()

                # Improvement: Pack all entries into a single SD message
                subscribe_sd_header = build_subscribe_eventgroup_sd_header(
                    service_id=self._service.id,
                    instance_id=self._instance_id,
                    major_version=self._service.major_version,
                    ttl=self._ttl,
                    event_group_id=eventgroup_to_subscribe,
                    session_id=session_id,
                    reboot_flag=reboot_flag,
                    endpoint=self._endpoint,
                    protocol=self._protocol,
                )

                get_logger(_logger_name).debug(
                    f"Send subscribe for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X}, "
                    f"eventgroup ID: {eventgroup_to_subscribe} TTL: {self._ttl}, version: "
                    f"session ID: {session_id}"
                )

                if self._protocol == TransportLayerProtocol.TCP:
                    if self._tcp_task is None:
                        get_logger(_logger_name).debug(
                            f"Create new TCP task for client of 0x{self._instance_id:04X}, 0x{self._service.id:04X}"
                        )
                        self._tcp_task = asyncio.create_task(
                            self.setup_tcp_connection(
                                str(self._endpoint[0]),
                                self._endpoint[1],
                                str(offered_service.endpoint[0]),
                                offered_service.endpoint[1],
                            )
                        )

                self._expected_acks.append(ExpectedAck(eventgroup_to_subscribe))
                self._sd_sender.send_unicast(
                    buffer=subscribe_sd_header.to_buffer(),
                    dest_ip=offered_service.endpoint[0],
                )

    def handle_stop_offer_service(self, offered_service: SdService) -> None:
        if self._service.id != offered_service.service_id:
            return
        if self._instance_id != offered_service.instance_id:
            return

        # Remove the service from the found services
        self._found_services = [
            f for f in self._found_services if f.service != offered_service
        ]

        self._expected_acks = []
        self._subscription_active = False

    async def setup_tcp_connection(
        self, src_ip: str, src_port: int, dst_ip: str, dst_port: int
    ):
        try:
            while True:

                get_logger(_logger_name).debug(
                    f"Try to open TCP connection to ({dst_ip}, {dst_port})"
                )
                self._tcp_connection = TcpConnection(dst_ip, dst_port)

                # Reset the event before the first await call
                self._tcp_connection_established_event.clear()
                try:
                    await self._tcp_connection.connect(src_ip, src_port)
                except OSError:
                    get_logger(_logger_name).debug(
                        f"Connection refused to ({dst_ip}, {dst_port}). Try to reconnect in 1 second"
                    )
                    # Wait a second before trying to connect again
                    await asyncio.sleep(1.0)
                    continue

                # Notify other tasks waiting on the event, so the other task could send a method call
                if self._tcp_connection.is_open():
                    self._tcp_connection_established_event.set()

                get_logger(_logger_name).debug(f"Start reading on port {src_port}")

                someip_processor = SomeipDataProcessor()

                while self._tcp_connection.is_open():
                    try:
                        new_data = await asyncio.wait_for(
                            self._tcp_connection.reader.read(
                                someip_processor.expected_bytes
                            ),
                            3.0,
                        )

                        if someip_processor.process_data(new_data):
                            self.someip_message_received(
                                someip_processor.someip_message, (dst_ip, dst_port)
                            )

                    except asyncio.TimeoutError:
                        get_logger(_logger_name).debug(
                            f"Timeout reading from TCP connection ({src_ip}, {src_port})"
                        )

                # Clear the event to avoid that a method call would be sent
                self._tcp_connection_established_event.clear()
                await self._tcp_connection.close()

        except asyncio.CancelledError:
            if self._tcp_connection.is_open():
                await self._tcp_connection.close()
            get_logger(_logger_name).debug("TCP task is cancelled. Raise again.")
            raise

    def handle_subscribe_eventgroup(self, _, __) -> None:
        # Not needed for client instance
        pass

    def handle_subscribe_ack_eventgroup(
        self, event_group_entry: SdEventGroupEntry
    ) -> None:
        new_acks: List[ExpectedAck] = []
        ack_found = False
        for expected_ack in self._expected_acks:
            if expected_ack.eventgroup_id == event_group_entry.eventgroup_id:
                ack_found = True
                self._subscription_active = True
                get_logger(_logger_name).debug(
                    f"Received expected subscribe ACK for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
                )
            else:
                new_acks.append(expected_ack)

        self._expected_acks = new_acks
        if not ack_found:
            get_logger(_logger_name).warning(
                f"Received unexpected subscribe ACK for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
            )

    async def close(self):
        self._shutdown_requested = True
        if self._tcp_task is not None:
            self._tcp_task.cancel()
            try:
                await self._tcp_task
            except asyncio.CancelledError:
                get_logger(_logger_name).debug("TCP task is cancelled.")


async def construct_client_service_instance(
    service: Service,
    instance_id: int,
    endpoint: EndpointType,
    ttl: int = 0,
    sd_sender=None,
    protocol=TransportLayerProtocol.UDP,
) -> ClientServiceInstance:
    """
    Asynchronously constructs a ClientServerInstance. Based on the given transport protocol, proper endpoints are setup before constructing the actual ServerServiceInstance.

    Args:
        service (Service): The service associated with the instance.
        instance_id (int): The ID of the instance.
        endpoint (EndpointType): The endpoint of the client instance containing IP address and port.
        ttl (int, optional): The time-to-live for the instance used for service discovery subscribe entries. A value of 0 means that subscriptions are valid for infinite time.
        sd_sender (Any, optional): The service discovery sender.
        protocol (TransportLayerProtocol, optional): The transport layer protocol for the instance. Defaults to TransportLayerProtocol.UDP.

    Returns:
        ClientServerInstance: The constructed ClientServerInstance.

    Raises:
        None
    """
    if protocol == TransportLayerProtocol.UDP:
        loop = asyncio.get_running_loop()
        rcv_socket = create_udp_socket(str(endpoint[0]), endpoint[1])

        _, udp_endpoint = await loop.create_datagram_endpoint(
            lambda: UDPSomeipEndpoint(), sock=rcv_socket
        )

        client_instance = ClientServiceInstance(
            service,
            instance_id,
            endpoint,
            TransportLayerProtocol.UDP,
            udp_endpoint,
            ttl,
            sd_sender,
        )

        udp_endpoint.set_someip_callback(client_instance.someip_message_received)

        return client_instance

    elif protocol == TransportLayerProtocol.TCP:

        client_instance = ClientServiceInstance(
            service,
            instance_id,
            endpoint,
            TransportLayerProtocol.TCP,
            None,
            ttl,
            sd_sender,
        )

        return client_instance

    client_instance = ClientServiceInstance(service, instance_id, ttl, sd_sender)

    return client_instance
