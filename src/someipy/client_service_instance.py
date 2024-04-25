import asyncio
from typing import Tuple, Callable, Set, List

from someipy import Service
from someipy._internal.someip_sd_header import (
    SdService,
    TransportLayerProtocol,
    SdEventGroupEntry,
)
from someipy._internal.someip_sd_builder import build_subscribe_eventgroup_entry
from someipy._internal.service_discovery_abcs import (
    ServiceDiscoveryObserver,
    ServiceDiscoverySender,
)
from someipy._internal.tcp_client_manager import TcpClientManager, TcpClientProtocol
from someipy._internal.utils import create_udp_socket, EndpointType
from someipy._internal.logging import get_logger
from someipy._internal.message_types import MessageType
from someipy._internal.someip_endpoint import (
    SomeipEndpoint,
    TCPSomeipEndpoint,
    UDPSomeipEndpoint,
    SomeIpMessage,
)

_logger = get_logger("client_service_instance")


class ExpectedAck:
    def __init__(self, eventgroup_id: int) -> None:
        self.eventgroup_id = eventgroup_id


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

    def register_callback(self, callback: Callable[[SomeIpMessage], None]) -> None:
        self._callback = callback

    def someip_message_received(
        self, someip_message: SomeIpMessage, addr: Tuple[str, int]
    ) -> None:
        print(someip_message.header)
        if (
            someip_message.header.client_id == 0x00
            and someip_message.header.message_type == MessageType.NOTIFICATION.value
            and someip_message.header.return_code == 0x00
        ):
            if self._callback is not None:
                self._callback(someip_message)

    def subscribe_eventgroup(self, eventgroup_id: int):
        if eventgroup_id in self._eventgroups_to_subscribe:
            _logger.debug(
                f"Eventgroup ID {eventgroup_id} is already in subscription list."
            )
        self._eventgroups_to_subscribe.add(eventgroup_id)

    def stop_subscribe_eventgroup(self, eventgroup_id: int):
        # TODO: Implement StopSubscribe
        raise NotImplementedError

    def find_service_update(self):
        # Not needed in client service instance
        pass

    def offer_service_update(self, offered_service: SdService):
        if len(self._eventgroups_to_subscribe) == 0:
            return

        if self._service.id != offered_service.service_id:
            return
        if self._instance_id != offered_service.instance_id:
            return

        if (
            offered_service.service_id == self._service.id
            and offered_service.instance_id == self._instance_id
        ):
            for eventgroup_to_subscribe in self._eventgroups_to_subscribe:
                (
                    session_id,
                    reboot_flag,
                ) = self._sd_sender.get_unicast_session_handler().update_session()

                # Improvement: Pack all entries into a single SD message
                subscribe_sd_header = build_subscribe_eventgroup_entry(
                    service_id=self._service.id,
                    instance_id=self._instance_id,
                    major_version=self._service.major_version,
                    ttl=self._ttl,
                    event_group_id=eventgroup_to_subscribe,
                    session_id=session_id,
                    reboot_flag=reboot_flag,
                    endpoint=self._endpoint,
                    protocol=TransportLayerProtocol.UDP,
                )

                _logger.debug(
                    f"Send subscribe for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X}, "
                    f"eventgroup ID: {eventgroup_to_subscribe} TTL: {self._ttl}, version: "
                    f"session ID: {session_id}"
                )

                self._expected_acks.append(ExpectedAck(eventgroup_to_subscribe))
                self._sd_sender.send_unicast(
                    buffer=subscribe_sd_header.to_buffer(),
                    dest_ip=offered_service.endpoint[0],
                )

    def subscribe_eventgroup_update(self, _, __) -> None:
        # Not needed for client instance
        pass

    def subscribe_ack_eventgroup_update(
        self, event_group_entry: SdEventGroupEntry
    ) -> None:
        new_acks: List[ExpectedAck] = []
        ack_found = False
        for expected_ack in self._expected_acks:
            if expected_ack.eventgroup_id == event_group_entry.eventgroup_id:
                ack_found = True
                _logger.debug(
                    f"Received expected subscribe ACK for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
                )
            else:
                new_acks.append(expected_ack)

        self._expected_acks = new_acks
        if not ack_found:
            _logger.warn(
                f"Received unexpected subscribe ACK for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
            )


async def construct_client_service_instance(
    service: Service,
    instance_id: int,
    endpoint: EndpointType,
    ttl: int = 0,
    sd_sender=None,
    protocol=TransportLayerProtocol.UDP,
) -> ClientServiceInstance:
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
        tcp_client_manager = TcpClientManager()
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: TcpClientProtocol(client_manager=tcp_client_manager),
            str(endpoint[0]),
            endpoint[1],
        )

        tcp_someip_endpoint = TCPSomeipEndpoint(server, tcp_client_manager)

        server_instance = ClientServiceInstance(
            service,
            instance_id,
            endpoint,
            TransportLayerProtocol.TCP,
            tcp_someip_endpoint,
            ttl,
            sd_sender,
        )
        return server_instance

    client_instance = ClientServiceInstance(service, instance_id, ttl, sd_sender)

    return client_instance
