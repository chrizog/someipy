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
from typing import Set, Tuple

from someipy._internal.someip_message import SomeIpMessage
from someipy._internal.someipy_daemon_client import SomeIpDaemonClient
from someipy.service import Service

from someipy._internal.tcp_client_manager import TcpClientManager, TcpClientProtocol
from someipy._internal.message_types import MessageType
from someipy._internal.return_codes import ReturnCode
from someipy._internal.someip_sd_builder import (
    build_subscribe_eventgroup_ack_entry,
    build_subscribe_eventgroup_ack_sd_header,
)
from someipy._internal.someip_header import SomeIpHeader
from someipy._internal.someip_sd_header import (
    SdService,
    TransportLayerProtocol,
    SdEventGroupEntry,
    SdIPV4EndpointOption,
)
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
from someipy._internal.subscribers import Subscribers, EventGroupSubscriber
from someipy._internal.someip_endpoint import (
    SomeipEndpoint,
    TCPSomeipEndpoint,
    UDPSomeipEndpoint,
)

_logger_name = "server_service_instance"


class ServerServiceInstance:

    def __init__(
        self,
        service: Service,
        instance_id: int,
        endpoint: EndpointType,
        protocol: TransportLayerProtocol,
        someip_endpoint: SomeipEndpoint,
        ttl: int = 0,  # TTL used for SD Offer entries
        daemon: SomeIpDaemonClient = None,
        cyclic_offer_delay_ms=2000,
    ):
        self._service = service
        self._instance_id = instance_id
        self._endpoint = endpoint
        self._protocol = protocol
        self._someip_endpoint = someip_endpoint
        self._ttl = ttl
        self._daemon = daemon
        self._cyclic_offer_delay_ms = cyclic_offer_delay_ms

        self._subscribers = Subscribers()

        self._handler_tasks = set()
        self._is_running = True
        self._session_id = 0  # Starts from 1 to 0xFFFF

    async def send_event(
        self, event_group_id: int, event_id: int, payload: bytes
    ) -> None:
        """
        Sends an event to subscribers with the given event group ID, event ID, and payload.

        Args:
            event_group_id (int): The ID of the event group.
            event_id (int): The ID of the event.
            payload (bytes): The payload of the event. Can be manually crafter or serialized using someipy serialization.

        Returns:
            None: This function does not return anything.

        Note:
            - The client id and session id are set to 0x00 and 0x01 respectively.
            - The protocol version and interface version are set to 1.
        """

        # Get the subscribers from the daemon
        subscribers = await self._daemon._get_subscribers(
            SdService(
                service_id=self._service.id,
                instance_id=self._instance_id,
                major_version=self._service.major_version,
                minor_version=self._service.minor_version,
                ttl=self._ttl,
                endpoint=self._endpoint,
                protocol=self._protocol,
            ),
            event_group_id,
        )

        if len(subscribers) == 0:
            return

        # Session ID is a 16-bit value and should be incremented for each method call starting from 1
        self._session_id = (self._session_id + 1) % 0xFFFF

        length = 8 + len(payload)
        someip_header = SomeIpHeader(
            service_id=self._service.id,
            method_id=event_id,
            length=length,
            client_id=0x00,
            session_id=self._session_id,
            protocol_version=1,
            interface_version=self._service.major_version,
            message_type=MessageType.NOTIFICATION.value,
            return_code=0x00,
        )

        for sub in subscribers:
            get_logger(_logger_name).debug(
                f"Send event for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X} to {sub[0]}:{sub[1]}"
            )
            self._someip_endpoint.sendto(
                someip_header.to_buffer() + payload,
                endpoint_to_str_int_tuple(sub),
            )

    async def _handle_method_call(self, method_handler, dst_addr, header_to_return):
        try:
            result = await method_handler
            header_to_return.message_type = result.message_type.value
            header_to_return.return_code = result.return_code.value
            payload_to_return = result.payload

            # Update length in header to the correct length
            header_to_return.length = 8 + len(payload_to_return)
            self._someip_endpoint.sendto(
                header_to_return.to_buffer() + payload_to_return, dst_addr
            )
        except asyncio.CancelledError:
            get_logger(_logger_name).debug(
                f"Method call for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X} was canceled"
            )

    def someip_message_received(
        self, message: SomeIpMessage, addr: Tuple[str, int]
    ) -> None:
        """
        Handle a received Some/IP message, typically when a client uses an offered service.

        Args:
            message (SomeIpMessage): The received someip message.
            addr (Tuple[str, int]): The address of the sender consisting of IP address and source port.

        Returns:
            None: This function does not return anything.

        Raises:
            None: This function does not raise any exceptions.

        Note:
            - The protocol and interface version are not checked yet.
            - If the message type in the received header is not a request, a warning is logged.
        """

        if not self._is_running:
            return

        header = message.header
        payload_to_return = bytes()
        header_to_return = header

        def send_response():
            """Helper function to send out the buffer"""

            # Update length in header to the correct length
            header_to_return.length = 8 + len(payload_to_return)
            self._someip_endpoint.sendto(
                header_to_return.to_buffer() + payload_to_return, addr
            )

        if header.service_id != self._service.id:
            get_logger(_logger_name).warning(
                f"Unknown service ID received from {addr}: ID 0x{header.service_id:04X}"
            )
            header_to_return.message_type = MessageType.RESPONSE.value
            header_to_return.return_code = ReturnCode.E_UNKNOWN_SERVICE.value
            send_response()
            return

        # TODO: Rework this check. The interface version is part of the interface defintion and not the major version.
        # if header.interface_version != self._service.major_version:
        if False:
            get_logger(_logger_name).warning(
                f"Unknown interface version received from {addr}: Version {header.interface_version}"
            )
            header_to_return.message_type = MessageType.RESPONSE.value
            header_to_return.return_code = ReturnCode.E_WRONG_INTERFACE_VERSION.value
            send_response()
            return

        if header.method_id not in self._service.methods.keys():
            get_logger(_logger_name).warning(
                f"Unknown method ID received from {addr}: ID 0x{header.method_id:04X}"
            )
            header_to_return.message_type = MessageType.RESPONSE.value
            header_to_return.return_code = ReturnCode.E_UNKNOWN_METHOD.value
            send_response()
            return

        if header.message_type != MessageType.REQUEST.value:
            get_logger(_logger_name).warning(
                f"Unknown message type received from {addr}: Type 0x{header.message_type:04X}"
            )
            header_to_return.message_type = MessageType.RESPONSE.value
            header_to_return.return_code = ReturnCode.E_WRONG_MESSAGE_TYPE.value
            send_response()
            return

        if header.return_code == 0x00:
            method_handler = self._service.methods[header.method_id].method_handler
            coro = method_handler(message.payload, addr)

            # If a method is called, do it in a separate task to allow for asynchronous processing inside
            # method handlers
            new_task = asyncio.create_task(
                self._handle_method_call(coro, addr, header_to_return)
            )
            self._handler_tasks.add(new_task)
            new_task.add_done_callback(self._handler_tasks.discard)

        else:
            get_logger(_logger_name).warning(
                f"Wrong return type received from {addr}: Type 0x{header.return_code:02X}"
            )

    async def start_offer(self):
        """
        Starts sending periodic service discovery offer entries for the instance.

        Parameters:
            None

        Returns:
            None
        """

        service_to_offer = SdService(
            service_id=self._service.id,
            instance_id=self._instance_id,
            major_version=1,
            minor_version=0,
            ttl=self._ttl,
            endpoint=self._endpoint,
            protocol=self._protocol,
        )

        await self._daemon._offer_service(
            service_to_offer,
            self._cyclic_offer_delay_ms,
            list(self._service.eventgroups.keys()),
        )

    async def stop_offer(self):
        """
        Stop the offer for the service instance. Stops the periodic send offer message and sends out an SD message with a stop offer entry.

        Parameters:
            None

        Returns:
            None
        """

        service_to_offer = SdService(
            service_id=self._service.id,
            instance_id=self._instance_id,
            major_version=1,
            minor_version=0,
            ttl=self._ttl,
            endpoint=self._endpoint,
            protocol=self._protocol,
        )

        await self._daemon._stop_offer_service(service_to_offer)


async def construct_server_service_instance(
    service: Service,
    instance_id: int,
    endpoint: EndpointType,
    ttl,
    daemon: SomeIpDaemonClient,
    cyclic_offer_delay_ms=2000,
    protocol=TransportLayerProtocol.UDP,
) -> ServerServiceInstance:
    """
    Asynchronously constructs a ServerServiceInstance. Based on the given transport protocol, proper endpoints are setup before constructing the actual ServerServiceInstance.

    Args:
        service (Service): The service associated with the instance.
        instance_id (int): The ID of the instance.
        endpoint (EndpointType): The endpoint for the instance containing IP address and port.
        ttl (int, optional): The time-to-live for the instance used for service discovery offer entries. A value of 0 means that offer entries are valid for infinite time.
        daemon (SomeIpDaemonClient, optional): The daemon client.
        cyclic_offer_delay_ms (int, optional): The delay in milliseconds for cyclic offers. Defaults to 2000.
        protocol (TransportLayerProtocol, optional): The transport layer protocol for the instance. Defaults to TransportLayerProtocol.UDP.

    Returns:
        ServerServiceInstance: The constructed ServerServiceInstance.

    Raises:
        None
    """

    if protocol == TransportLayerProtocol.UDP:
        loop = asyncio.get_running_loop()
        rcv_socket = create_udp_socket(str(endpoint[0]), endpoint[1])

        _, udp_endpoint = await loop.create_datagram_endpoint(
            lambda: UDPSomeipEndpoint(), sock=rcv_socket
        )

        server_instance = ServerServiceInstance(
            service,
            instance_id,
            endpoint,
            TransportLayerProtocol.UDP,
            udp_endpoint,
            ttl,
            daemon,
            cyclic_offer_delay_ms,
        )

        udp_endpoint.set_someip_callback(server_instance.someip_message_received)

        return server_instance

    elif protocol == TransportLayerProtocol.TCP:

        # Create a TcpClientManager, a TcpClientProtocol and a TCP server
        # The TcpClientProtocol handles incoming (or lost) connections and will (de)register them
        # in the TcpClientManager. The TcpClientProtocol also handles incoming data and will trigger
        # the callback in the TcpClientManager which will forward the callback to the ClientServiceInstance.
        tcp_client_manager = TcpClientManager()
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: TcpClientProtocol(client_manager=tcp_client_manager),
            str(endpoint[0]),
            endpoint[1],
        )

        tcp_someip_endpoint = TCPSomeipEndpoint(server, tcp_client_manager)

        server_instance = ServerServiceInstance(
            service,
            instance_id,
            endpoint,
            TransportLayerProtocol.TCP,
            tcp_someip_endpoint,
            ttl,
            daemon,
            cyclic_offer_delay_ms,
        )

        tcp_someip_endpoint.set_someip_callback(server_instance.someip_message_received)

        return server_instance
