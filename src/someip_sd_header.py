import struct
import ipaddress
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, TypeVar, Generator, Union

from src.someip_header import (
    SomeIpHeader,
    SERVICE_ID_SD,
    METHOD_ID_SD,
    CLIENT_ID_SD,
    PROTOCOL_VERSION_SD,
    INTERFACE_VERSION_SD,
    MESSAGE_TYPE_SD,
    RETURN_CODE_SD,
)

_SD_IP4ENDPOINT_OPTION_LENGTH = 9

_SD_POSITION_ENTRY_LENGTH = 20
_SD_START_POSITION_ENTRIES = 24

_SD_SINGLE_ENTRY_LENGTH_BYTES = 16

_T = TypeVar("_T")


def set_bit_at_position(number: int, position: int, value: bool) -> int:
    """Set the bit at the specified position to the given boolean value."""
    if value:
        # Set the bit to 1
        return number | (1 << position)
    else:
        # Set the bit to 0
        return number & ~(1 << position)


def is_bit_set(number: int, bit_position: int) -> bool:
    """
    Checks if the bit at the specified position is set in the given number.

    Parameters:
    - number: The integer to check.
    - bit_position: The position of the bit to check (0-based index).

    Returns:
    - True if the bit is set, False otherwise.
    """
    # Left shift 1 to the bit position and perform bitwise AND with the number
    # If the result is non-zero, the bit is set; otherwise, it's not set.
    return (number & (1 << bit_position)) != 0


class SdEntryType(Enum):
    FIND_SERVICE = 0x00
    OFFER_SERVICE = 0x01
    STOP_OFFER_SERVICE = 0x01 # with TTL to 0x000000
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
    def from_buffer(cls, buf: bytes):
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
    def from_buffer(cls, buf: bytes):
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
    def from_buffer(cls, buf: bytes):
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
    def from_buffer(cls, buf: bytes):
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
    def from_buffer(cls, buf: bytes):
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
class SdOfferedService:
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


    def extract_offered_services(self) -> List[SdOfferedService]:
        result = []
        service_offers = [
            o
            for o in self.service_entries
            if o.sd_entry.type == SdEntryType.OFFER_SERVICE
        ]
        for e in service_offers:
            endpoint = (
                self.options[e.sd_entry.index_first_option].ipv4_address,
                self.options[e.sd_entry.index_first_option].port,
            )
            protocol = self.options[e.sd_entry.index_first_option].protocol

            sd_offered_service = SdOfferedService(
                service_id=e.sd_entry.service_id,
                instance_id=e.sd_entry.instance_id,
                major_version=e.sd_entry.major_version,
                minor_version=e.minor_version,
                ttl=e.sd_entry.ttl,
                endpoint=endpoint,
                protocol=protocol,
            )
            result.append(sd_offered_service)
        return result

    @classmethod
    def from_buffer(cls, buf: bytes):
        someip_header = SomeIpHeader.from_buffer(buf)

        (flags,) = struct.unpack(">B", buf[16:17])
        reboot_flag = is_bit_set(flags, 7)
        unicast_flag = is_bit_set(flags, 6)

        (length_entries,) = struct.unpack(
            ">I", buf[_SD_POSITION_ENTRY_LENGTH : _SD_POSITION_ENTRY_LENGTH + 4]
        )
        number_of_entries = int(length_entries / _SD_SINGLE_ENTRY_LENGTH_BYTES)

        entries = []
        for i in range(number_of_entries):
            start_entry = _SD_START_POSITION_ENTRIES + i * _SD_SINGLE_ENTRY_LENGTH_BYTES
            end_entry = start_entry + _SD_SINGLE_ENTRY_LENGTH_BYTES

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

        pos_length_options = _SD_POSITION_ENTRY_LENGTH + 4 + length_entries
        (length_options,) = struct.unpack(
            ">I", buf[pos_length_options : pos_length_options + 4]
        )
        pos_start_options = pos_length_options + 4

        current_pos_option = pos_start_options
        bytes_options_left = length_options

        options = []
        while bytes_options_left > 0:
            sd_option_common = SdOptionCommon.from_buffer(
                buf[current_pos_option : current_pos_option + 8]
            )

            if sd_option_common.type == SdOptionType.IPV4_ENDPOINT:
                sd_option = SdIPV4EndpointOption.from_buffer(
                    buf[
                        current_pos_option : current_pos_option
                        + sd_option_common.length
                        + 3
                    ]
                )
                options.append(sd_option)

            # Subtract 3 bytes first for length and type
            bytes_options_left -= 3
            current_pos_option += 3
            bytes_options_left -= sd_option_common.length
            current_pos_option += sd_option_common.length

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

        out += struct.pack(">I", flags)  # flags + 24 reserved bits
        out += struct.pack(">I", self.length_entries)
        for entry in self.service_entries:
            out += entry.to_buffer()
        out += struct.pack(">I", self.length_options)
        for option in self.options:
            out += option.to_buffer()
        return out


def extract_subscribe_eventgroup_entries(
    someip_sd_header: SomeIpSdHeader,
) -> List[Tuple[SdEventGroupEntry, SdIPV4EndpointOption]]:
    result = []

    for entry in someip_sd_header.service_entries:
        if entry.sd_entry.type == SdEntryType.SUBSCRIBE_EVENT_GROUP:
            # Check TTL in order to distinguish between subscribe and stop subscribe
            # SUBSCRIBE_EVENT_GROUP = 0x06
            # STOP_SUBSCRIBE_EVENT_GROUP = 0x06  # with TTL to 0x000000
            if entry.sd_entry.ttl != 0x00:
                if entry.sd_entry.num_options_1 > 0:
                    option = someip_sd_header.options[entry.sd_entry.index_first_option]
                    result.append((entry, option))

    return result


def construct_offer_service_sd_header(
    service_to_offer: SdOfferedService, session_id: int, reboot_flag: bool
):
    sd_entry: SdEntry = SdEntry(
        SdEntryType.OFFER_SERVICE,
        0,  # index_first_option
        0,  # index_second_option
        1,  # num_options_1
        0,  # num_options_2
        service_to_offer.service_id,
        service_to_offer.instance_id,
        service_to_offer.major_version,
        service_to_offer.ttl,
    )

    service_entry = SdServiceEntry(
        sd_entry=sd_entry, minor_version=service_to_offer.minor_version
    )
    option_entry_common = SdOptionCommon(
        length=_SD_IP4ENDPOINT_OPTION_LENGTH,
        type=SdOptionType.IPV4_ENDPOINT,
        discardable_flag=False,
    )
    sd_option_entry = SdIPV4EndpointOption(
        sd_option_common=option_entry_common,
        ipv4_address=service_to_offer.endpoint[0],
        protocol=service_to_offer.protocol,
        port=service_to_offer.endpoint[1],
    )

    LENGTH_SERVICE_ENTRY = 16
    LENGTH_IP4ENDPOINT_OPTION = 12

    # 20 bytes for header and length values of entries and options
    # + length of entries array
    # + length of options array
    total_length = 20 + 1 * LENGTH_SERVICE_ENTRY + 1 * LENGTH_IP4ENDPOINT_OPTION
    someip_header = SomeIpHeader.generate_sd_header(
        length=total_length, session_id=session_id
    )

    return SomeIpSdHeader(
        someip_header=someip_header,
        reboot_flag=reboot_flag,
        unicast_flag=True,
        length_entries=1 * LENGTH_SERVICE_ENTRY,
        length_options=1 * LENGTH_IP4ENDPOINT_OPTION,
        service_entries=[service_entry],
        options=[sd_option_entry],
    )


def construct_subscribe_eventgroup_ack_entry(
    service_id: int, instance_id: int, major_version: int, ttl: int, event_group_id: int
) -> SdEventGroupEntry:
    sd_entry: SdEntry = SdEntry(
        SdEntryType.SUBSCRIBE_EVENT_GROUP_ACK,
        0,  # index_first_option
        0,  # index_second_option
        0,  # num_options_1
        0,  # num_options_2
        service_id,
        instance_id,
        major_version,
        ttl,
    )

    entry = SdEventGroupEntry(
        sd_entry=sd_entry,
        initial_data_requested_flag=False,
        counter=0,
        eventgroup_id=event_group_id,
    )
    return entry


def construct_subscribe_eventgroup_ack_sd_header(
    entry: SdEventGroupEntry, session_id: int, reboot_flag: bool
) -> SomeIpSdHeader:
    total_length = 20 + 1 * _SD_SINGLE_ENTRY_LENGTH_BYTES
    someip_header = SomeIpHeader.generate_sd_header(
        length=total_length, session_id=session_id
    )

    return SomeIpSdHeader(
        someip_header=someip_header,
        reboot_flag=reboot_flag,
        unicast_flag=True,
        length_entries=_SD_SINGLE_ENTRY_LENGTH_BYTES,
        length_options=0,
        service_entries=[entry],
        options=[],
    )
