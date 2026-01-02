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


from dataclasses import dataclass

from someipy._internal._common.endpoint import Endpoint
from someipy._internal.transport_layer_protocol import TransportLayerProtocol


@dataclass
class ServiceInstance:
    """This class aggregates data from entries and options and provides a compact interface instead of loose SD entries and options"""

    service_id: int
    instance_id: int
    major_version: int
    minor_version: int
    ttl: int
    endpoint: Endpoint
    protocols: frozenset[TransportLayerProtocol]
    timestamp: float

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ServiceInstance):
            return False

        # Ignore the timestamp in equality comparison
        return (
            self.service_id == other.service_id
            and self.instance_id == other.instance_id
            and self.major_version == other.major_version
            and self.minor_version == other.minor_version
            and self.ttl == other.ttl
            and self.endpoint == other.endpoint
            and self.protocols == other.protocols
        )
