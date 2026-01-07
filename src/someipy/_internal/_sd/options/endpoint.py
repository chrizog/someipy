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
import ipaddress

from someipy._internal.transport_layer_protocol import TransportLayerProtocol


@dataclass(eq=True, frozen=True)
class IpV4EndpointOption:
    address: ipaddress.IPv4Address
    protocol: TransportLayerProtocol
    port: int


@dataclass(eq=True, frozen=True)
class IpV6EndpointOption:
    address: ipaddress.IPv6Address
    protocol: TransportLayerProtocol
    port: int
