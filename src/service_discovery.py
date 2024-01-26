import asyncio
import ipaddress
from abc import ABC, abstractmethod
from typing import Any, Union, Tuple, List
from src.someip_header import SomeIpHeader
from src.someip_sd_header import *
from src.session_handler import SessionHandler
from src.utils import create_rcv_multicast_socket, create_udp_socket

class ServiceDiscoveryObserver(ABC):
    @abstractmethod
    def offer_service_update(self, offered_service: SdOfferedService) -> None:
        pass

    @abstractmethod
    def find_service_update(self) -> None:
        pass

    @abstractmethod
    def subscribe_eventgroup_update(self, sd_event_group: SdEventGroupEntry, ip4_endpoint_option: SdIPV4EndpointOption) -> None:
        pass

class ServiceDiscoverySubject(ABC):
    @abstractmethod
    def attach(self, service_instance: ServiceDiscoveryObserver) -> None:
        pass

    @abstractmethod
    def detach(self, service_instance: ServiceDiscoveryObserver) -> None:
        pass

class ServiceDiscoverySender(ABC):
    @abstractmethod
    def send_multicast(self, buffer: bytes) -> None:
        pass

    @abstractmethod
    def send_unicast(self, buffer: bytes, dest_ip: ipaddress.IPv4Address) -> None:
        pass

    @abstractmethod
    def get_multicast_session_handler(self) -> SessionHandler:
        pass

    @abstractmethod
    def get_unicast_session_handler(self) -> SessionHandler:
        pass




class DatagramAdapter(asyncio.DatagramProtocol):
    def __init__(self, target):
        self.target = target

    def datagram_received(self, data: bytes, addr: Tuple[Union[str, Any], int]) -> None:
        self.target.datagram_received(data, addr)

    def connection_lost(self, exc: Exception) -> None:
        self.target.connection_lost(exc)


class ServiceDiscoveryProtocol(ServiceDiscoverySubject, ServiceDiscoverySender):

    attached_observers: List[ServiceDiscoveryObserver]

    def __init__(self, multicast_ip: str, interface_ip: str, sd_port: int):
        self.sender_socket = create_udp_socket(interface_ip, sd_port)
        
        self.multicast_ip = multicast_ip
        self.sd_port = sd_port

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
        # TODO close transports
        if self.mcast_transport is not None:
            self.mcast_transport.close()
        if self.unicast_transport is not None:
            self.unicast_transport.close()

    def detach(self, service_instance: ServiceDiscoveryObserver) -> None:
        # TODO
        pass

    def attach(self, service_instance: ServiceDiscoveryObserver) -> None:
        self.attached_observers.append(service_instance)

    def datagram_received(self, data: bytes, addr: Tuple[Union[str, Any], int]) -> None:
        print(f"Received data from: {addr}")
        someip_header = SomeIpHeader.from_buffer(data)

        # Test if dst port is the SD port
        if addr[1] != self.sd_port:
            return

        if someip_header.is_sd_header():
            someip_sd_header = SomeIpSdHeader.from_buffer(data)
            # print(someip_sd_header)

            for offered_service in someip_sd_header.extract_offered_services():
                for o in self.attached_observers:
                    o.offer_service_update(offered_service)

            for event_group_entry, ipv4_endpoint_option in extract_subscribe_eventgroup_entries(someip_sd_header):
                for o in self.attached_observers:
                    print(event_group_entry, ipv4_endpoint_option)
                    o.subscribe_eventgroup_update(event_group_entry, ipv4_endpoint_option)


    def connection_lost(self, exc: Exception) -> None:
        pass

    def send_multicast(self, buffer: bytes) -> None:
        self.sender_socket.sendto(buffer, (self.multicast_ip, self.sd_port))

    def send_unicast(self, buffer: bytes, dest_ip: ipaddress.IPv4Address) -> None:
        self.sender_socket.sendto(buffer, (str(dest_ip), self.sd_port))


async def construct_service_discovery(multicast_group, multicast_port, unicast_ip) -> ServiceDiscoveryProtocol:
    sd = ServiceDiscoveryProtocol(multicast_group, unicast_ip, multicast_port)

    multicast_sock = create_rcv_multicast_socket(multicast_group, multicast_port)
    loop = asyncio.get_running_loop()

    mcast_transport, _ = await loop.create_datagram_endpoint(
        lambda: DatagramAdapter(target=sd),
        sock=multicast_sock,
    )

    unicast_sock = create_udp_socket(unicast_ip, multicast_port)

    unicast_transport, _ = await loop.create_datagram_endpoint(
        lambda: DatagramAdapter(target=sd),
        sock=unicast_sock
    )

    sd.mcast_transport = mcast_transport
    sd.unicast_transport = unicast_transport
    return sd
