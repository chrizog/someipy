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

import ipaddress
from abc import ABC, abstractmethod
from someipy._internal.someip_sd_header import (
    SdService,
    SdEventGroupEntry,
    SdIPV4EndpointOption,
)
from someipy._internal.session_handler import SessionHandler


class ServiceDiscoveryObserver(ABC):
    @abstractmethod
    def handle_offer_service(self, offered_service: SdService) -> None:
        pass

    @abstractmethod
    def handle_stop_offer_service(self, offered_service: SdService) -> None:
        pass

    @abstractmethod
    def handle_find_service(self) -> None:
        pass

    @abstractmethod
    def handle_subscribe_eventgroup(
        self,
        sd_event_group: SdEventGroupEntry,
        ip4_endpoint_option: SdIPV4EndpointOption,
    ) -> None:
        pass

    @abstractmethod
    def handle_subscribe_ack_eventgroup(
        self, sd_event_group: SdEventGroupEntry
    ) -> None:
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
    def offer_service(self, service: SdService) -> None:
        pass

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
