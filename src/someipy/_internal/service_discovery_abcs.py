from abc import ABC, abstractmethod
from someipy._internal.someip_sd_header import *
from someipy._internal.session_handler import SessionHandler


class ServiceDiscoveryObserver(ABC):
    @abstractmethod
    def offer_service_update(self, offered_service: SdService) -> None:
        pass

    @abstractmethod
    def find_service_update(self) -> None:
        pass

    @abstractmethod
    def subscribe_eventgroup_update(self, sd_event_group: SdEventGroupEntry, ip4_endpoint_option: SdIPV4EndpointOption) -> None:
        pass

    @abstractmethod
    def subscribe_ack_eventgroup_update(self, sd_event_group: SdEventGroupEntry) -> None:
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