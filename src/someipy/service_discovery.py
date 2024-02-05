import asyncio
import ipaddress
from typing import Any, Union, Tuple, List

from someipy._internal.someip_header import SomeIpHeader
from someipy._internal.someip_sd_header import *
from someipy._internal.someip_sd_extractors import *
from someipy._internal.session_handler import SessionHandler
from someipy._internal.utils import (
    create_rcv_multicast_socket,
    create_udp_socket,
    DatagramAdapter,
)
from someipy._internal.service_discovery_abcs import *
from someipy._internal.logging import get_logger

_logger = get_logger("service_discovery")


class ServiceDiscoveryProtocol(ServiceDiscoverySubject, ServiceDiscoverySender):
    attached_observers: List[ServiceDiscoveryObserver]

    def __init__(self, multicast_ip: str, interface_ip: str, sd_port: int):
        self.interface_ip = interface_ip
        self.multicast_ip = multicast_ip
        self.sd_port = sd_port

        self.sender_socket = create_udp_socket(interface_ip, sd_port)

        self.attached_observers = []
        self.mcast_transport = None
        self.unicast_transport = None

        self.mcast_session_handler = SessionHandler()
        self.unicast_session_handler = SessionHandler()

    def get_multicast_session_handler(self) -> SessionHandler:
        return self.mcast_session_handler

    def get_unicast_session_handler(self) -> SessionHandler:
        return self.unicast_session_handler

    def close(self):
        if self.mcast_transport is not None:
            self.mcast_transport.close()
        if self.unicast_transport is not None:
            self.unicast_transport.close()

    def detach(self, service_instance: ServiceDiscoveryObserver) -> None:
        # TODO
        raise NotImplementedError

    def attach(self, service_instance: ServiceDiscoveryObserver) -> None:
        self.attached_observers.append(service_instance)

    def datagram_received(self, data: bytes, addr: Tuple[Union[str, Any], int]) -> None:
        # If the data was sent by the app itself ignore it and return
        if addr[0] == self.interface_ip:
            return

        # Test if destination port of the packet is the SD port. Otherwise ignore it and return
        if addr[1] != self.sd_port:
            return

        someip_header = SomeIpHeader.from_buffer(data)
        if not someip_header.is_sd_header():
            return

        someip_sd_header = SomeIpSdHeader.from_buffer(data)

        for offered_service in extract_offered_services(someip_sd_header):
            _logger.debug(
                f"Received offer for instance 0x{offered_service.instance_id:04X}, service 0x{offered_service.service_id:04X}"
            )
            for o in self.attached_observers:
                o.offer_service_update(offered_service)

        for (
            event_group_entry,
            ipv4_endpoint_option,
        ) in extract_subscribe_eventgroup_entries(someip_sd_header):
            _logger.debug(
                f"Received subscribe for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
            )
            for o in self.attached_observers:
                o.subscribe_eventgroup_update(event_group_entry, ipv4_endpoint_option)

        for event_group_entry in extract_subscribe_ack_eventgroup_entries(someip_sd_header):
            _logger.debug(
                f"Received subscribe ACK for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
            )
            #for o in self.attached_observers:
            #    o.sub

    def connection_lost(self, exc: Exception) -> None:
        pass

    def send_multicast(self, buffer: bytes) -> None:
        self.sender_socket.sendto(buffer, (self.multicast_ip, self.sd_port))

    def send_unicast(self, buffer: bytes, dest_ip: ipaddress.IPv4Address) -> None:
        self.sender_socket.sendto(buffer, (str(dest_ip), self.sd_port))


async def construct_service_discovery(
    multicast_group, multicast_port, unicast_ip
) -> ServiceDiscoveryProtocol:
    sd = ServiceDiscoveryProtocol(multicast_group, unicast_ip, multicast_port)

    multicast_sock = create_rcv_multicast_socket(multicast_group, multicast_port)
    loop = asyncio.get_running_loop()

    mcast_transport, _ = await loop.create_datagram_endpoint(
        lambda: DatagramAdapter(target=sd),
        sock=multicast_sock,
    )

    unicast_sock = create_udp_socket(unicast_ip, multicast_port)

    unicast_transport, _ = await loop.create_datagram_endpoint(
        lambda: DatagramAdapter(target=sd), sock=unicast_sock
    )

    sd.mcast_transport = mcast_transport
    sd.unicast_transport = unicast_transport
    return sd
