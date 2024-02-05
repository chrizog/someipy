import ipaddress
import struct
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, TypeVar, Union

from someipy._internal.utils import set_bit_at_position, is_bit_set
from someipy._internal.someip_header import SomeIpHeader

# Constants for byte positions inside the SD header
SD_POSITION_ENTRY_LENGTH = 20
SD_START_POSITION_ENTRIES = 24

# Constants for length of sections in the SD header
SD_SINGLE_ENTRY_LENGTH_BYTES = 16

SD_IPV4ENDPOINT_OPTION_LENGTH_VALUE = 9
SD_BYTE_LENGTH_IP4ENDPOINT_OPTION = 12

_T = TypeVar("_T")


class SdEntryType(Enum):
    FIND_SERVICE = 0x00
    OFFER_SERVICE = 0x01
    STOP_OFFER_SERVICE = 0x01  # with TTL to 0x000000
    SUBSCRIBE_EVENT_GROUP = 0x06
    STOP_SUBSCRIBE_EVENT_GROUP = 0x06  # with TTL to 0x000000
    SUBSCRIBE_EVENT_GROUP_ACK = 0x07
    SUBSCRIBE_EVENT_GROUP_NACK = 0x07  # with TTL to 0x000000


class SdOptionType(Enum):
    CONFIGURATION = 0x01  # TODO: not implemented
    LOAD_BALANCING = 0x02  # TODO: not implemented
    IPV4_ENDPOINT = 0x04
    IPV6_ENDPOINT = 0x06  # TODO: not implemented
    IPV4_MULTICAST = 0x14  # TODO: not implemented
    IPV6_MULTICAST = 0x16  # TODO: not implemented


class TransportLayerProtocol(Enum):
    TCP = 0x06
    UDP = 0x11


@dataclass
class SdEntry:
    type: SdEntryType
    index_first_option: int
    index_second_option: int
    num_options_1: int
    num_options_2: int
    service_id: int
    instance_id: int
    major_version: int
    ttl: int

    @classmethod
    def from_buffer(cls: _T, buf: bytes) -> _T:
        type_field_value, index_first_option, index_second_option = struct.unpack(
            ">BBB", buf[0:3]
        )

        num_options_1 = struct.unpack(">B", buf[3:4])[0]  # higher 4 bits
        num_options_1 = (num_options_1 >> 4) & 0x0F

        num_options_2 = struct.unpack(">B", buf[3:4])[0]  # lower 4 bits
        num_options_2 = num_options_2 & 0x0F

        service_id, instance_id, major_version = struct.unpack(">HHB", buf[4:9])
        (ttl,) = struct.unpack(">I", buf[8:12])
        ttl = ttl & 0xFFFFFF

        if (
            type_field_value == SdEntryType.STOP_SUBSCRIBE_EVENT_GROUP.value
            and ttl == 0
        ):
            type_field = SdEntryType.STOP_SUBSCRIBE_EVENT_GROUP
        elif (
            type_field_value == SdEntryType.STOP_SUBSCRIBE_EVENT_GROUP.value
            and ttl != 0
        ):
            type_field = SdEntryType.SUBSCRIBE_EVENT_GROUP
        elif (
            type_field_value == SdEntryType.SUBSCRIBE_EVENT_GROUP_NACK.value
            and ttl == 0
        ):
            type_field = SdEntryType.SUBSCRIBE_EVENT_GROUP_NACK
        elif (
            type_field_value == SdEntryType.SUBSCRIBE_EVENT_GROUP_ACK.value and ttl != 0
        ):
            type_field = SdEntryType.SUBSCRIBE_EVENT_GROUP_ACK
        else:
            type_field = SdEntryType(type_field_value)

        return cls(
            type_field,
            index_first_option,
            index_second_option,
            num_options_1,
            num_options_2,
            service_id,
            instance_id,
            major_version,
            ttl,
        )

    def to_buffer(self) -> bytes:
        num_options = (self.num_options_1 << 4) | self.num_options_2
        ttl_high = (self.ttl & 0xFF0000) >> 16
        ttl_low = self.ttl & 0xFFFF
        return struct.pack(
            ">BBBBHHBBH",
            self.type.value,
            self.index_first_option,
            self.index_second_option,
            num_options,
            self.service_id,
            self.instance_id,
            self.major_version,
            ttl_high,
            ttl_low,
        )


@dataclass
class SdEventGroupEntry:
    sd_entry: SdEntry
    initial_data_requested_flag: int
    counter: int
    eventgroup_id: int

    @classmethod
    def from_buffer(cls: _T, buf: bytes) -> _T:
        sd_entry = SdEntry.from_buffer(buf)
        initial_data_requested_flag_counter_value, eventgroup_id = struct.unpack(
            ">BH", buf[13:16]
        )
        initial_data_requested_flag = is_bit_set(
            initial_data_requested_flag_counter_value, 7
        )
        counter = initial_data_requested_flag_counter_value & 0xF
        return cls(sd_entry, initial_data_requested_flag, counter, eventgroup_id)

    def to_buffer(self) -> bytes:
        initial_data_requested_flag_counter_value = set_bit_at_position(0, 7, True)
        initial_data_requested_flag_counter_value = (
            initial_data_requested_flag_counter_value | (self.counter & 0xF)
        )
        return self.sd_entry.to_buffer() + struct.pack(
            ">BBH", 0, initial_data_requested_flag_counter_value, self.eventgroup_id
        )


@dataclass
class SdServiceEntry:
    sd_entry: SdEntry
    minor_version: int

    @classmethod
    def from_buffer(cls: _T, buf: bytes) -> _T:
        sd_entry = SdEntry.from_buffer(buf)
        (minor_version,) = struct.unpack(">I", buf[12:16])
        return cls(sd_entry, minor_version)

    def to_buffer(self) -> bytes:
        return self.sd_entry.to_buffer() + struct.pack(">I", self.minor_version)


@dataclass
class SdOptionCommon:
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


@dataclass
class SdIPV4EndpointOption:
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


@dataclass
class SomeIpSdHeader:
    someip_header: SomeIpHeader
    reboot_flag: bool
    unicast_flag: bool
    length_entries: int
    length_options: int
    service_entries: List[Union[SdServiceEntry, SdEventGroupEntry]]
    options: List[SdIPV4EndpointOption]

    @classmethod
    def from_buffer(cls: _T, buf: bytes) -> _T:
        someip_header = SomeIpHeader.from_buffer(buf)

        (flags,) = struct.unpack(">B", buf[16:17])
        reboot_flag = is_bit_set(flags, 7)
        unicast_flag = is_bit_set(flags, 6)

        (length_entries,) = struct.unpack(
            ">I", buf[SD_POSITION_ENTRY_LENGTH : SD_POSITION_ENTRY_LENGTH + 4]
        )
        number_of_entries = int(length_entries / SD_SINGLE_ENTRY_LENGTH_BYTES)

        # Read in all Service and Event Group entries
        entries = []
        for i in range(number_of_entries):
            start_entry = SD_START_POSITION_ENTRIES + (i * SD_SINGLE_ENTRY_LENGTH_BYTES)
            end_entry = start_entry + SD_SINGLE_ENTRY_LENGTH_BYTES

            sd_entry = SdEntry.from_buffer(buf[start_entry:end_entry])

            if sd_entry.type in [
                SdEntryType.FIND_SERVICE,
                SdEntryType.OFFER_SERVICE,
                SdEntryType.STOP_OFFER_SERVICE,
            ]:
                entries.append(SdServiceEntry.from_buffer(buf[start_entry:end_entry]))

            elif sd_entry.type in [
                SdEntryType.SUBSCRIBE_EVENT_GROUP,
                SdEntryType.SUBSCRIBE_EVENT_GROUP_ACK,
                SdEntryType.SUBSCRIBE_EVENT_GROUP_NACK,
                SdEntryType.STOP_SUBSCRIBE_EVENT_GROUP,
            ]:
                entries.append(
                    SdEventGroupEntry.from_buffer(buf[start_entry:end_entry])
                )

        # Read in all options
        # The length of the positions is stored after all entries. Therefore the length entry (4 bytes)
        # and the total length of the entries is added to the position of the entries length
        pos_length_options = SD_POSITION_ENTRY_LENGTH + 4 + length_entries
        (length_options,) = struct.unpack(
            ">I", buf[pos_length_options : pos_length_options + 4]
        )
        pos_start_options = pos_length_options + 4

        current_pos_option = pos_start_options
        bytes_options_left = length_options

        options = []
        while bytes_options_left > 0:
            sd_option_common = SdOptionCommon.from_buffer(
                buf[current_pos_option : current_pos_option + 4]
            )

            if sd_option_common.type == SdOptionType.IPV4_ENDPOINT:
                sd_option = SdIPV4EndpointOption.from_buffer(
                    buf[
                        current_pos_option : (
                            current_pos_option + SD_BYTE_LENGTH_IP4ENDPOINT_OPTION
                        )
                    ]
                )
                options.append(sd_option)

            # Subtract 3 bytes first for length and type
            bytes_options_left -= sd_option_common.length + 3
            current_pos_option += sd_option_common.length + 3

        return cls(
            someip_header,
            reboot_flag,
            unicast_flag,
            length_entries,
            length_options,
            service_entries=entries,
            options=options,
        )

    def to_buffer(self) -> bytes:
        out = self.someip_header.to_buffer()
        flags = 0
        flags = set_bit_at_position(flags, 31, self.reboot_flag)
        flags = set_bit_at_position(flags, 30, self.unicast_flag)

        out += struct.pack(">I", flags)  # 8 bit flags + 24 reserved bits
        out += struct.pack(">I", self.length_entries)
        for entry in self.service_entries:
            out += entry.to_buffer()
        out += struct.pack(">I", self.length_options)
        for option in self.options:
            out += option.to_buffer()
        return out
