import asyncio
from typing import Tuple

from someipy.service import Service

from someipy._internal.tcp_client_manager import TcpClientManager, TcpClientProtocol
from someipy._internal.message_types import MessageType, ReturnCode
from someipy._internal.someip_sd_builder import (
    build_subscribe_eventgroup_ack_entry,
    build_offer_service_sd_header,
    build_subscribe_eventgroup_ack_sd_header,
)
from someipy._internal.someip_header import (
    SomeIpHeader,
    get_payload_from_someip_message,
)
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

_logger = get_logger("server_service_instance")


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
            if sub.eventgroup_id == event_group_id:
                _logger.debug(
                    f"Send event for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X} to {sub.endpoint[0]}:{sub.endpoint[1]}"
                )
                self._someip_endpoint.sendto(
                    someip_header.to_buffer() + payload,
                    endpoint_to_str_int_tuple(sub.endpoint),
                )

    def someip_message_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        header = SomeIpHeader.from_buffer(data)
        payload_to_return = bytes()
        header_to_return = header

        def send_response():
            self.unicast_transport.sendto(
                header_to_return.to_buffer() + payload_to_return, addr
            )

        if header.service_id != self.service_id:
            _logger.warn(
                f"Unknown service ID received from {addr}: ID 0x{header.service_id:04X}"
            )
            header_to_return.message_type = MessageType.RESPONSE.value
            header_to_return.return_code = ReturnCode.E_UNKNOWN_SERVICE.value
            send_response()
            return

        if header.method_id not in self.methods.keys():
            _logger.warn(
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
            payload_in = get_payload_from_someip_message(header, data)
            (success, payload_to_return) = self.methods[
                header.method_id
            ].method_handler(payload_in)

            if not success:
                _logger.debug(
                    f"Return ERROR message type to {addr} for service and instance ID: 0x{self.service_id:04X} / 0x{self._instance_id:04X}"
                )
                header_to_return.message_type = MessageType.ERROR.value
            else:
                _logger.debug(
                    f"Return RESPONSE message type to {addr} for service and instance ID: 0x{self.service_id:04X} / 0x{self._instance_id:04X}"
                )
                header_to_return.message_type = MessageType.RESPONSE.value

            send_response()
        else:
            _logger.warn(
                f"Unknown message type received from {addr}: Type 0x{header.message_type:04X}"
            )

    def find_service_update(self):
        # TODO: implement SD behaviour and send back offer
        pass

    def offer_service_update(self, _: SdService):
        # No reaction in a server instance needed
        pass

    def subscribe_eventgroup_update(
        self,
        sd_event_group: SdEventGroupEntry,
        ipv4_endpoint_option: SdIPV4EndpointOption,
    ) -> None:
        # [PRS_SOMEIPSD_00829] When receiving a SubscribeEventgroupAck or Sub-
        # scribeEventgroupNack the Service ID, Instance ID, Eventgroup ID, and Major Ver-
        # sion shall match exactly to the corresponding SubscribeEventgroup Entry to identify
        # an Eventgroup of a Service Instance.
        # TODO: enable major version check
        if sd_event_group.sd_entry.service_id != self._service.id:
            return
        if sd_event_group.sd_entry.instance_id != self._instance_id:
            return
        if sd_event_group.eventgroup_id not in self._service.eventgroupids:
            return

        if ipv4_endpoint_option.protocol != self._protocol:
            _logger.warn(
                f"Subscribing a different protocol (TCP/UDP) than offered is not supported. Received subscribe for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X} "
                "from {ipv4_endpoint_option.ipv4_address}/{ipv4_endpoint_option.port} with wrong protocol"
            )
            return

        (
            session_id,
            reboot_flag,
        ) = self._sd_sender.get_unicast_session_handler().update_session()

        _logger.debug(
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

    def subscribe_ack_eventgroup_update(self, _: SdEventGroupEntry) -> None:
        # Not needed for server instance
        pass

    def offer_timer_callback(self):
        (
            session_id,
            reboot_flag,
        ) = self._sd_sender.get_multicast_session_handler().update_session()

        _logger.debug(
            f"Offer service for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X}, TTL: {self._ttl}, version: {self._service.major_version}.{self._service.minor_version}, session ID: {session_id}"
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
        sd_header = build_offer_service_sd_header(
            service_to_offer, session_id, reboot_flag
        )
        self._sd_sender.send_multicast(sd_header.to_buffer())

    def start_offer(self):
        self._offer_timer = SimplePeriodicTimer(
            self._cyclic_offer_delay_ms / 1000.0, self.offer_timer_callback
        )
        self._offer_timer.start()

    async def stop_offer(self):
        _logger.debug(
            f"Stop offer for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X}"
        )

        if self._offer_timer is not None:
            self._offer_timer.stop()
            await self._offer_timer.task
        # TODO: send out a stop offer sd message before stopping the timer


async def construct_server_service_instance(
    service: Service,
    instance_id: int,
    endpoint: EndpointType,
    ttl: int = 0,
    sd_sender=None,
    cyclic_offer_delay_ms=2000,
    protocol=TransportLayerProtocol.UDP,
) -> ServerServiceInstance:
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
        return server_instance

    elif protocol == TransportLayerProtocol.TCP:
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
        return server_instance
