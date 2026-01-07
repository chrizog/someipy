# Copyright (C) 2025 Christian H.
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

from someipy._internal._common.endpoint import Endpoint
from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy.service import EventGroup


class Subscription:
    def __init__(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        eventgroup: EventGroup,
        ttl_seconds: int,
        client_endpoint: Endpoint,
        server_endpoint: Endpoint,
        protocols: frozenset[TransportLayerProtocol],
        timestamp_last_update: float = 0.0,
    ):
        self.service_id = service_id
        self.instance_id = instance_id
        self.major_version = major_version
        self.eventgroup = eventgroup
        self.ttl_seconds = ttl_seconds

        self.client_endpoint = client_endpoint
        self.server_endpoint = server_endpoint
        self.protocols = protocols
        self.timestamp_last_update = timestamp_last_update

    def __eq__(self, value: "Subscription") -> bool:
        return (
            self.service_id == value.service_id
            and self.instance_id == value.instance_id
            and self.major_version == value.major_version
            and self.eventgroup == value.eventgroup
            and self.client_endpoint == value.client_endpoint
            and self.server_endpoint == value.server_endpoint
            and self.protocols == value.protocols
        )

    def __hash__(self) -> int:
        # Do not include the timestamp and ttl in the hash calculation
        return hash(
            (
                self.service_id,
                self.instance_id,
                self.major_version,
                self.eventgroup,
                self.client_endpoint,
                self.server_endpoint,
                self.protocols,
            )
        )
