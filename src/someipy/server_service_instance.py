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
from typing import Tuple

from someipy._internal.someip_message import SomeIpMessage
from someipy.service import Service

from someipy._internal.tcp_client_manager import TcpClientManager, TcpClientProtocol
from someipy._internal.message_types import MessageType
from someipy._internal.return_codes import ReturnCode
from someipy._internal.someip_sd_builder import (
    build_stop_offer_service_sd_header,
    build_subscribe_eventgroup_ack_entry,
    build_offer_service_sd_header,
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
from someipy._internal.simple_timer import SimplePeriodicTimer
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


class ServerServiceInstance(ServiceDiscoveryObserver):
    _service: Service
    _instance_id: int
    _endpoint: EndpointType
    _protocol: TransportLayerProtocol
    _someip_endpoint: SomeipEndpoint
    _ttl: int
    _sd_sender: ServiceDiscoverySender
    _cyclic_offer_delay_ms: int

    _subscribers: Subscribers
    _offer_timer: SimplePeriodicTimer

    def __init__(
        self,
        service: Service,
        instance_id: int,
        endpoint: EndpointType,
        protocol: TransportLayerProtocol,
        someip_endpoint: SomeipEndpoint,
        ttl: int = 0,  # TTL used for SD Offer entries
        sd_sender=None,
        cyclic_offer_delay_ms=2000,
    ):
        self._service = service
        self._instance_id = instance_id
        self._endpoint = endpoint
        self._protocol = protocol
        self._someip_endpoint = someip_endpoint
        self._ttl = ttl
        self._sd_sender = sd_sender
        self._cyclic_offer_delay_ms = cyclic_offer_delay_ms

        self._subscribers = Subscribers()
        self._offer_timer = None

    def send_event(self, event_group_id: int, event_id: int, payload: bytes) -> None:
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

        self._subscribers.update()

        length = 8 + len(payload)
        someip_header = SomeIpHeader(
            service_id=self._service.id,
            method_id=event_id,
            length=length,
            client_id=0x00,  # TODO
            session_id=0x01,  # TODO
            protocol_version=1,  # TODO
            interface_version=1,  # TODO
            message_type=MessageType.NOTIFICATION.value,
            return_code=0x00,
        )

        for sub in self._subscribers.subscribers:
            # Check if the subscriber wants to receive the event group id
            if sub.eventgroup_id == event_group_id:
                get_logger(_logger_name).debug(
                    f"Send event for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X} to {sub.endpoint[0]}:{sub.endpoint[1]}"
                )
                self._someip_endpoint.sendto(
                    someip_header.to_buffer() + payload,
                    endpoint_to_str_int_tuple(sub.endpoint),
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

        if header.method_id not in self._service.methods.keys():
            get_logger(_logger_name).warning(
                f"Unknown method ID received from {addr}: ID 0x{header.method_id:04X}"
            )
            header_to_return.message_type = MessageType.RESPONSE.value
            header_to_return.return_code = ReturnCode.E_UNKNOWN_METHOD.value
            send_response()
            return

        # TODO: Test for protocol and interface version

        if (
            header.message_type == MessageType.REQUEST.value
            and header.return_code == 0x00
        ):
            method_handler = self._service.methods[header.method_id].method_handler
            result = method_handler(message.payload, addr)

            header_to_return.message_type = result.message_type.value
            header_to_return.return_code = result.return_code.value
            payload_to_return = result.payload
            send_response()

        else:
            get_logger(_logger_name).warning(
                f"Unknown message type received from {addr}: Type 0x{header.message_type:04X}"
            )

    def handle_find_service(self):
        """
        Handle an SD find service entry. Not implemented yet.

        Args:
            None
        Returns:
            None
        """
        # TODO: implement SD behaviour and send back offer
        pass

    def handle_offer_service(self, _: SdService):
        """
        React on an SD offer entry. In a server instance no reaction is needed.

        Parameters:
            _ (SdService): The service update that was offered.

        Returns:
            None
        """
        # No reaction in a server instance needed
        pass

    def handle_stop_offer_service(self, _: SdService) -> None:
        # No reaction in a server instance needed
        pass

    def handle_subscribe_eventgroup(
        self,
        sd_event_group: SdEventGroupEntry,
        ipv4_endpoint_option: SdIPV4EndpointOption,
    ) -> None:
        """
        React on an SD subscribe eventgroup entry.

        Parameters:
            sd_event_group (SdEventGroupEntry): The subscribe eventgroup entry.
            ipv4_endpoint_option (SdIPV4EndpointOption): The IPv4 endpoint option.

        Returns:
            None

        """

        # From SD specification:
        # [PRS_SOMEIPSD_00829] When receiving a SubscribeEventgroupAck or Sub-
        # scribeEventgroupNack the Service ID, Instance ID, Eventgroup ID, and Major Ver-
        # sion shall match exactly to the corresponding SubscribeEventgroup Entry to identify
        # an Eventgroup of a Service Instance.
        # TODO: Enable major version check
        if sd_event_group.sd_entry.service_id != self._service.id:
            return
        if sd_event_group.sd_entry.instance_id != self._instance_id:
            return
        if sd_event_group.eventgroup_id not in self._service.eventgroupids:
            return

        if ipv4_endpoint_option.protocol != self._protocol:
            get_logger(_logger_name).warn(
                f"Subscribing a different protocol (TCP/UDP) than offered is not supported. Received subscribe for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X} "
                "from {ipv4_endpoint_option.ipv4_address}/{ipv4_endpoint_option.port} with wrong protocol"
            )
            return

        (
            session_id,
            reboot_flag,
        ) = self._sd_sender.get_unicast_session_handler().update_session()

        get_logger(_logger_name).debug(
            f"Send Subscribe ACK for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X}, TTL: {sd_event_group.sd_entry.ttl}"
        )
        ack_entry = build_subscribe_eventgroup_ack_entry(
            service_id=sd_event_group.sd_entry.service_id,
            instance_id=sd_event_group.sd_entry.instance_id,
            major_version=sd_event_group.sd_entry.major_version,
            ttl=sd_event_group.sd_entry.ttl,
            event_group_id=sd_event_group.eventgroup_id,
        )
        header_output = build_subscribe_eventgroup_ack_sd_header(
            entry=ack_entry, session_id=session_id, reboot_flag=reboot_flag
        )

        self._sd_sender.send_unicast(
            buffer=header_output.to_buffer(),
            dest_ip=ipv4_endpoint_option.ipv4_address,
        )

        self._subscribers.add_subscriber(
            EventGroupSubscriber(
                eventgroup_id=sd_event_group.eventgroup_id,
                endpoint=(
                    ipv4_endpoint_option.ipv4_address,
                    ipv4_endpoint_option.port,
                ),
                ttl=sd_event_group.sd_entry.ttl,
            )
        )

    def handle_subscribe_ack_eventgroup(self, _: SdEventGroupEntry) -> None:
        """
        React on an SD subscribe ACK event group entry. Shall not be received in a server instance. No reaction is needed in a server service instance.

        Args:
            _ (SdEventGroupEntry): The subscription ACK event group entry.

        Returns:
            None: This function does not return anything.
        """
        # Not needed for server instance
        pass

    def offer_timer_callback(self):
        """
        Callback function for the periodic offer timer.

        Parameters:
            None

        Returns:
            None
        """
        get_logger(_logger_name).debug(
            f"Offer service for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X}, TTL: {self._ttl}, version: {self._service.major_version}.{self._service.minor_version}"
        )

        service_to_offer = SdService(
            service_id=self._service.id,
            instance_id=self._instance_id,
            major_version=1,
            minor_version=0,
            ttl=self._ttl,
            endpoint=self._endpoint,
            protocol=self._protocol,
        )
        self._sd_sender.offer_service(service_to_offer)

    def start_offer(self):
        """
        Starts sending periodic service discovery offer entries for the instance.

        This method creates a new `SimplePeriodicTimer` instance with the specified delay in seconds and assigns it to the `_offer_timer` attribute. The timer is then started by calling its `start` method.

        Parameters:
            None

        Returns:
            None
        """
        if self._offer_timer is None:
            self._offer_timer = SimplePeriodicTimer(
                self._cyclic_offer_delay_ms / 1000.0, self.offer_timer_callback
            )
            self._offer_timer.start()

    async def stop_offer(self):
        """
        Stop the offer for the service instance.  Stops the periodic send offer timer and sends out an SD message with a stop offer entry.

        Parameters:
            None

        Returns:
            None
        """
        get_logger(_logger_name).debug(
            f"Stop offer for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X}"
        )

        self._subscribers.clear()

        if self._offer_timer is not None:
            self._offer_timer.stop()
            await self._offer_timer.task

        service_to_stop = SdService(
            service_id=self._service.id,
            instance_id=self._instance_id,
            major_version=1,
            minor_version=0,
            ttl=self._ttl,
            endpoint=self._endpoint,
            protocol=self._protocol,
        )
        (
            session_id,
            reboot_flag,
        ) = self._sd_sender.get_multicast_session_handler().update_session()
        sd_header = build_stop_offer_service_sd_header(
            [service_to_stop], session_id, reboot_flag
        )
        self._sd_sender.send_multicast(sd_header.to_buffer())


async def construct_server_service_instance(
    service: Service,
    instance_id: int,
    endpoint: EndpointType,
    ttl,
    sd_sender: ServiceDiscoverySender,
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
        sd_sender (Any, optional): The service discovery sender.
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
            sd_sender,
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
            sd_sender,
            cyclic_offer_delay_ms,
        )

        tcp_someip_endpoint.set_someip_callback(server_instance.someip_message_received)

        return server_instance
