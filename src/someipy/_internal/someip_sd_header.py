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
import json
from dataclasses import dataclass
from typing import Tuple, TypeVar

from someipy._internal.transport_layer_protocol import TransportLayerProtocol

# Constants for byte positions inside the SD header
SD_POSITION_ENTRY_LENGTH = 20
SD_START_POSITION_ENTRIES = 24

# Constants for length of sections in the SD header
SD_SINGLE_ENTRY_LENGTH_BYTES = 16

SD_IPV4ENDPOINT_OPTION_LENGTH_VALUE = 9
SD_BYTE_LENGTH_IP4ENDPOINT_OPTION = 12

_T = TypeVar("_T")


@dataclass
class SdService:
    """This class aggregates data from entries and options and provides a compact interface instead of loose SD entries and options"""

    service_id: int
    instance_id: int
    major_version: int
    minor_version: int
    ttl: int
    endpoint: Tuple[ipaddress.IPv4Address, int]
    protocol: TransportLayerProtocol

    def __hash__(self) -> int:
        return hash(
            (
                self.service_id,
                self.instance_id,
                self.major_version,
                self.minor_version,
                self.ttl,
                self.endpoint,
                self.protocol,
            )
        )

    def to_json(self):
        output_dict = {
            "service_id": self.service_id,
            "instance_id": self.instance_id,
            "major_version": self.major_version,
            "minor_version": self.minor_version,
            "ttl": self.ttl,
            "endpoint_ip": str(self.endpoint[0]),
            "endpoint_port": self.endpoint[1],
            "protocol": self.protocol.value,
        }
        return json.dumps(output_dict)

    @classmethod
    def from_json(cls: _T, json_str: str) -> _T:
        json_dict = json.loads(json_str)
        o = cls(
            int(json_dict["service_id"]),
            int(json_dict["instance_id"]),
            int(json_dict["major_version"]),
            int(json_dict["minor_version"]),
            int(json_dict["ttl"]),
            (
                ipaddress.IPv4Address(json_dict["endpoint_ip"]),
                json_dict["endpoint_port"],
            ),
            TransportLayerProtocol(json_dict["protocol"]),
        )
        return o
