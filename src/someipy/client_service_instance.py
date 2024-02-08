import asyncio
from typing import Tuple, Union, Any, Callable

from someipy._internal.someip_sd_header import (
    SdService,
    TransportLayerProtocol,
    SdEventGroupEntry,
)
from someipy._internal.someip_sd_builder import build_subscribe_eventgroup_entry
from someipy._internal.someip_header import (
    get_payload_from_someip_message,
    SomeIpHeader,
)
from someipy._internal.service_discovery_abcs import (
    ServiceDiscoveryObserver,
    ServiceDiscoverySender,
)
from someipy._internal.utils import create_udp_socket, EndpointType, DatagramAdapter
from someipy._internal.logging import get_logger


_logger = get_logger("client_service_instance")


class ClientServiceInstance(ServiceDiscoveryObserver):
    service_id: int
    instance_id: int
    major_version: int
    minor_version: int
    endpoint: EndpointType
    ttl: int
    sd_sender: ServiceDiscoverySender

    eventgroup_to_subscribe: int
    expect_ack: bool

    callback: Callable[[bytes], None]

    def __init__(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        minor_version: int,
        endpoint: EndpointType,
        ttl: int = 0,
        sd_sender=None,
    ):
        self.service_id = service_id
        self.instance_id = instance_id
        self.major_version = major_version
        self.minor_version = minor_version
        self.endpoint = endpoint
        self.ttl = ttl
        self.sd_sender = sd_sender

        self.eventgroup_to_subscribe = -1
        self.expect_ack = False

        self.unicast_transport = None

        self.callback = None

    def register_callback(self, callback: Callable[[bytes], None]) -> None:
        self.callback = callback

    def datagram_received(self, data: bytes, addr: Tuple[Union[str, Any], int]) -> None:
        # TODO: Test if there is a subscription active for the received data
        if self.callback is not None:
            header = SomeIpHeader.from_buffer(data)
            payload = get_payload_from_someip_message(header, data)
            self.callback(payload)

    def connection_lost(self, exc: Exception) -> None:
        pass

    def subscribe_eventgroup(self, eventgroup_id: int):
        # TODO: Currently only one eventgroup per service is supported
        self.eventgroup_to_subscribe = eventgroup_id

    def stop_subscribe_eventgroup(self, eventgroup_id: int):
        # TODO: Implement StopSubscribe
        raise NotImplementedError

    def find_service_update(self):
        # Not needed in client service instance
        pass

    def offer_service_update(self, offered_service: SdService):
        if (
            self.eventgroup_to_subscribe != -1
            and offered_service.service_id == self.service_id
            and offered_service.instance_id == self.instance_id
        ):
            (
                session_id,
                reboot_flag,
            ) = self.sd_sender.get_unicast_session_handler().update_session()

            subscribe_sd_header = build_subscribe_eventgroup_entry(
                service_id=self.service_id,
                instance_id=self.instance_id,
                major_version=self.major_version,
                ttl=self.ttl,
                event_group_id=self.eventgroup_to_subscribe,
                session_id=session_id,
                reboot_flag=reboot_flag,
                endpoint=self.endpoint,
                protocol=TransportLayerProtocol.UDP,
            )

            # TODO: Subscription shall be only active when ACK is received
            self.expect_ack = True

            _logger.debug(
                f"Send subscribe for instance 0x{self.instance_id:04X}, service: 0x{self.service_id:04X}, evengroup ID: {self.eventgroup_to_subscribe} TTL: {self.ttl}, version: {self.major_version}.{self.minor_version}, session ID: {session_id}"
            )

            self.sd_sender.send_unicast(
                buffer=subscribe_sd_header.to_buffer(),
                dest_ip=offered_service.endpoint[0],
            )

    def subscribe_eventgroup_update(self, _, __) -> None:
        # Not needed for client instance
        pass

    def subscribe_ack_eventgroup_update(
        self, event_group_entry: SdEventGroupEntry
    ) -> None:
        if self.expect_ack:
            self.expect_ack = False
            _logger.debug(
                f"Received subscribe ACK for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
            )


async def construct_client_service_instance(
    service_id: int,
    instance_id: int,
    major_version: int,
    minor_version: int,
    endpoint: EndpointType,
    ttl: int = 0,
    sd_sender=None,
) -> ClientServiceInstance:
    client_instance = ClientServiceInstance(
        service_id, instance_id, major_version, minor_version, endpoint, ttl, sd_sender
    )

    loop = asyncio.get_running_loop()
    rcv_socket = create_udp_socket(str(endpoint[0]), endpoint[1])

    unicast_transport, _ = await loop.create_datagram_endpoint(
        lambda: DatagramAdapter(target=client_instance), sock=rcv_socket
    )
    client_instance.unicast_transport = unicast_transport

    return client_instance
