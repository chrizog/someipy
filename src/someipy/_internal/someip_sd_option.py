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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar
import ipaddress
import struct

from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy._internal.utils import is_bit_set, set_bit_at_position

_T = TypeVar("_T")


class SdOptionType(Enum):
    CONFIGURATION = 0x01  # TODO: not implemented
    LOAD_BALANCING = 0x02  # TODO: not implemented
    IPV4_ENDPOINT = 0x04
    IPV6_ENDPOINT = 0x06  # TODO: not implemented
    IPV4_MULTICAST = 0x14  # TODO: not implemented
    IPV6_MULTICAST = 0x16  # TODO: not implemented
    IPV4_SD_ENDPOINT = 0x24  # TODO: not implemented
    IPV6_SD_ENDPOINT = 0x26  # TODO: not implemented

class SdOptionInterface(ABC):
    
    @abstractmethod
    def get_sd_option_type(self):
        pass

@dataclass
class SdOptionCommon(SdOptionInterface):
    """This class represents the common part of all SD options
    including the length of the option in bytes, the type of the option (uint8)
    and a discardable flag (bool)"""

    length: int
    type: SdOptionType
    discardable_flag: bool

    @classmethod
    def from_buffer(cls: _T, buf: bytes) -> _T:
        option_length, option_type, discardable_flag_value = struct.unpack(
            ">HBB", buf[0:4]
        )
        option_type = SdOptionType(option_type)
        discardable_flag = is_bit_set(discardable_flag_value, 7)
        return cls(option_length, option_type, discardable_flag)

    def to_buffer(self) -> bytes:
        discardable_flag_value = set_bit_at_position(0, 7, self.discardable_flag)
        return struct.pack(">HBB", self.length, self.type.value, discardable_flag_value)

    def get_sd_option_type(self) -> SdOptionType:
        return self.type

@dataclass
class SdIPV4EndpointOption(SdOptionInterface):
    sd_option_common: SdOptionCommon
    ipv4_address: ipaddress.IPv4Address
    protocol: TransportLayerProtocol
    port: int

    @classmethod
    def from_buffer(cls: _T, buf: bytes) -> _T:
        sd_option_common = SdOptionCommon.from_buffer(buf)
        ip1, ip2, ip3, ip4, _, protocol_value, port = struct.unpack(
            ">BBBBBBH", buf[4:12]
        )
        protocol = TransportLayerProtocol(protocol_value)
        return cls(
            sd_option_common,
            ipaddress.IPv4Address(f"{ip1}.{ip2}.{ip3}.{ip4}"),
            protocol,
            port,
        )

    def to_buffer(self) -> bytes:
        return self.sd_option_common.to_buffer() + struct.pack(
            ">IBBH", int(self.ipv4_address), 0, self.protocol.value, self.port
        )
    
    def get_sd_option_type(self) -> SdOptionType:
        return self.sd_option_common.type
