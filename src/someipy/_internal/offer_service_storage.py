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

from typing import List
from someipy.service import Event, EventGroup, Method
from someipy._internal.transport_layer_protocol import TransportLayerProtocol


class ServiceToOffer:
    def __init__(
        self,
        client_writer_id: int,
        instance_id: int,
        service_id: int,
        major_version: int,
        minor_version: int,
        offer_ttl_seconds: int,
        cyclic_offer_delay_ms: int,
        endpoint_ip: str,
        endpoint_port: int,
        methods: List[Method],
        eventgroups: List[EventGroup],
    ):
        self.client_writer_id = client_writer_id
        self.instance_id = instance_id
        self.service_id = service_id
        self.major_version = major_version
        self.minor_version = minor_version
        self.offer_ttl_seconds = offer_ttl_seconds
        self.cyclic_offer_delay_ms = cyclic_offer_delay_ms
        self.endpoint_ip = endpoint_ip
        self.endpoint_port = endpoint_port
        self.methods = methods
        self.eventgroups = eventgroups
        self.last_offer_time = None  # Placeholder for last offer time

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ServiceToOffer):
            return False
        return (
            self.client_writer_id == other.client_writer_id
            and self.instance_id == other.instance_id
            and self.service_id == other.service_id
            and self.major_version == other.major_version
            and self.minor_version == other.minor_version
            and self.offer_ttl_seconds == other.offer_ttl_seconds
            and self.cyclic_offer_delay_ms == other.cyclic_offer_delay_ms
            and self.endpoint_ip == other.endpoint_ip
            and self.endpoint_port == other.endpoint_port
            and self.methods == other.methods
            and self.eventgroups == other.eventgroups
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.client_writer_id,
                self.instance_id,
                self.service_id,
                self.major_version,
                self.minor_version,
                self.offer_ttl_seconds,
                self.cyclic_offer_delay_ms,
                self.endpoint_ip,
                self.endpoint_port,
                tuple(self.methods),  # Convert list to tuple for hashing
                tuple(self.eventgroups),  # Convert list to tuple for hashing
            )
        )

    @property
    def has_udp(self) -> bool:
        has_method_udp = any(
            method.protocol == TransportLayerProtocol.UDP for method in self.methods
        )

        events = [event for eg in self.eventgroups for event in eg.events]
        has_event_udp = any(
            event.protocol == TransportLayerProtocol.UDP for event in events
        )
        return has_method_udp or has_event_udp

    @property
    def has_tcp(self) -> bool:
        has_method_tcp = any(
            method.protocol == TransportLayerProtocol.TCP for method in self.methods
        )

        events = [event for eg in self.eventgroups for event in eg.events]
        has_event_tcp = any(
            event.protocol == TransportLayerProtocol.TCP for event in events
        )
        return has_method_tcp or has_event_tcp

    @property
    def eventgroup_ids(self) -> List[int]:
        """Returns a list of all eventgroup IDs from the stored eventgroups"""
        return [eventgroup.id for eventgroup in self.eventgroups]

    @property
    def protocols(self) -> frozenset[TransportLayerProtocol]:
        result = set()
        if self.has_udp:
            result.add(TransportLayerProtocol.UDP)
        if self.has_tcp:
            result.add(TransportLayerProtocol.TCP)
        return frozenset(result)


class OfferServiceStorage:
    def __init__(self):
        self._services: List[ServiceToOffer] = []

    def add_service(self, service: ServiceToOffer) -> bool:
        """Add a new ServiceToOffer to the storage if it doesn't already exist.
        Returns True if the service was added, False if it was a duplicate."""
        if service in self._services:
            return False
        self._services.append(service)
        return True

    def remove_service(self, service: ServiceToOffer) -> bool:
        """Remove a specific ServiceToOffer from the storage.
        Returns True if the service was found and removed, False otherwise."""
        try:
            self._services.remove(service)
            return True
        except ValueError:
            return False

    def remove_client(self, client_writer_id: int) -> int:
        """Remove all services with the given client_writer_id.
        Returns the number of services removed."""
        initial_count = len(self._services)
        self._services = [
            service
            for service in self._services
            if service.client_writer_id != client_writer_id
        ]
        return initial_count - len(self._services)

    def services_by_cyclic_offer_delay(
        self, cyclic_offer_delay_ms: int
    ) -> List[ServiceToOffer]:
        """Return all services with the specified cyclic_offer_delay_ms"""
        return [
            service
            for service in self._services
            if service.cyclic_offer_delay_ms == cyclic_offer_delay_ms
        ]

    def get_all_services(self) -> List[ServiceToOffer]:
        """Return all services in the storage"""
        return self._services.copy()

    def clear(self) -> None:
        """Remove all services from the storage"""
        self._services.clear()

    @property
    def cyclic_offer_delays(self) -> List[int]:
        """Returns a list of all unique cyclic_offer_delay_ms values from stored services"""
        return sorted({service.cyclic_offer_delay_ms for service in self._services})
