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


import socket
import struct

from someipy._internal._sd.options.endpoint import (
    IpV4EndpointOption,
    IpV6EndpointOption,
)
from someipy._internal._sd.entries.sd_entry import SdEntryType
from someipy._internal.utils import set_bit_at_position
from someipy._internal._sd.sd_message import SdMessage

SERVICE_ID_SD = 0xFFFF
METHOD_ID_SD = 0x8100
CLIENT_ID_SD = 0x0000
PROTOCOL_VERSION_SD = 0x01
INTERFACE_VERSION_SD = 0x01
MESSAGE_TYPE_SD = 0x02
RETURN_CODE_SD = 0x00

MINIMAL_HEADER_SIZE = 16


def entry_type_to_on_wire(entry_type: SdEntryType) -> int:
    lookup = {
        SdEntryType.FIND_SERVICE: 0x00,
        SdEntryType.OFFER_SERVICE: 0x01,
        SdEntryType.STOP_OFFER_SERVICE: 0x01,  # with TTL to 0x000000
        SdEntryType.SUBSCRIBE_EVENT_GROUP: 0x06,
        SdEntryType.STOP_SUBSCRIBE_EVENT_GROUP: 0x06,  # with TTL to 0x000000
        SdEntryType.SUBSCRIBE_EVENT_GROUP_ACK: 0x07,
        SdEntryType.SUBSCRIBE_EVENT_GROUP_NACK: 0x07,
    }
    if entry_type not in lookup:
        raise ValueError(f"Unsupported SdEntryType: {entry_type}")

    return lookup[entry_type]


def serialize_ipv4_endpoint_option(option: IpV4EndpointOption) -> bytes:
    output = bytes()
    LENGTH = 0x0009
    TYPE = 0x04

    discardable_flag_value = set_bit_at_position(0, 7, False)
    output += struct.pack(">HBB", LENGTH, TYPE, discardable_flag_value)
    output += struct.pack(
        ">IBBH", int(option.address), 0, option.protocol.value, option.port
    )
    return output


def serialize_ipv6_endpoint_option(option: IpV6EndpointOption) -> bytes:
    output = bytes()
    LENGTH = 0x0015
    TYPE = 0x06

    ipv6_str = str(option.address)
    packed_ip = socket.inet_pton(socket.AF_INET6, ipv6_str)

    discardable_flag_value = set_bit_at_position(0, 7, False)
    output += struct.pack(">HBB", LENGTH, TYPE, discardable_flag_value)
    output += packed_ip
    output += struct.pack(">BBH", 0, option.protocol.value, option.port)
    return output


def serialize_sd_message(sd_message: SdMessage) -> bytes:

    output = bytes()

    SERVICE_ID_SD = 0xFFFF
    METHOD_ID_SD = 0x8100
    CLIENT_ID_SD = 0x0000
    PROTOCOL_VERSION_SD = 0x01
    INTERFACE_VERSION_SD = 0x01
    MESSAGE_TYPE_SD = 0x02
    RETURN_CODE_SD = 0x00

    output += struct.pack(
        ">HHIHHBBBB",
        SERVICE_ID_SD,
        METHOD_ID_SD,
        0,
        CLIENT_ID_SD,
        sd_message.session_id,
        PROTOCOL_VERSION_SD,
        INTERFACE_VERSION_SD,
        MESSAGE_TYPE_SD,
        RETURN_CODE_SD,
    )

    # TODO: Set the reboot flag properly
    reboot_flag = False
    unicast_flag = True

    flags = 0
    flags = set_bit_at_position(flags, 31, reboot_flag)
    flags = set_bit_at_position(flags, 30, unicast_flag)

    output += struct.pack(">I", flags)  # 8 bit flags + 24 reserved bits

    options = []
    option_set = set()

    for entry in sd_message.entries:
        if entry.type in [
            SdEntryType.OFFER_SERVICE,
            SdEntryType.STOP_OFFER_SERVICE,
            SdEntryType.SUBSCRIBE_EVENT_GROUP,
            SdEntryType.STOP_SUBSCRIBE_EVENT_GROUP,
        ]:
            for endpoint in entry.ip_v4_endpoints:
                if endpoint not in option_set:
                    option_set.add(endpoint)
                    options.append(endpoint)
            for endpoint in entry.ip_v6_endpoints:
                if endpoint not in option_set:
                    option_set.add(endpoint)
                    options.append(endpoint)

    # Length of the entries array
    SD_SINGLE_ENTRY_LENGTH_BYTES = 16
    length_entries_array = len(sd_message.entries) * SD_SINGLE_ENTRY_LENGTH_BYTES
    output += struct.pack(">I", length_entries_array)

    for entry in sd_message.entries:
        if entry.type in [
            SdEntryType.OFFER_SERVICE,
            SdEntryType.STOP_OFFER_SERVICE,
            SdEntryType.FIND_SERVICE,
        ]:
            if entry.type == SdEntryType.OFFER_SERVICE:
                ttl = entry.ttl
            else:
                ttl = 0

            ttl_high = (ttl & 0xFF0000) >> 16
            ttl_low = ttl & 0xFFFF

            index_first_option = 0

            if entry.type == SdEntryType.FIND_SERVICE:
                num_options_1 = 0
                index_first_option = 0
            else:
                num_options_1 = len(entry.ip_v4_endpoints) + len(entry.ip_v6_endpoints)
                if num_options_1 > 2:
                    raise ValueError("Too many options for entry configured.")

                entry_options = set(entry.ip_v4_endpoints + entry.ip_v6_endpoints)

                for i in range(len(options)):
                    if options[i] in entry_options:
                        index_first_option = i
                        break

            num_options_2 = 0  # No second option in this implementation
            num_options = (num_options_1 << 4) | num_options_2

            index_second_option = 0  # No second option in this implementation

            output += struct.pack(
                ">BBBBHHBBH",
                entry_type_to_on_wire(entry.type),
                index_first_option,
                index_second_option,
                num_options,
                entry.service_id,
                entry.instance_id,
                entry.major_version,
                ttl_high,
                ttl_low,
            )

            output += struct.pack(">I", entry.minor_version)

        else:
            if entry.type in [
                SdEntryType.STOP_SUBSCRIBE_EVENT_GROUP,
                SdEntryType.SUBSCRIBE_EVENT_GROUP_NACK,
            ]:
                ttl = 0
            else:
                ttl = entry.ttl

            ttl_high = (ttl & 0xFF0000) >> 16
            ttl_low = ttl & 0xFFFF

            if entry.type in [
                SdEntryType.SUBSCRIBE_EVENT_GROUP,
                SdEntryType.STOP_SUBSCRIBE_EVENT_GROUP,
            ]:
                num_options_1 = len(entry.ip_v4_endpoints) + len(entry.ip_v6_endpoints)
                if num_options_1 > 2:
                    raise ValueError("Too many options for entry configured.")

                entry_options = set(entry.ip_v4_endpoints + entry.ip_v6_endpoints)

                for i in range(len(options)):
                    if options[i] in entry_options:
                        index_first_option = i
                        break
            else:
                num_options_1 = 0
                index_first_option = 0

            num_options_2 = 0  # No second option in this implementation
            num_options = (num_options_1 << 4) | num_options_2

            index_second_option = 0  # No second option in this implementation

            output += struct.pack(
                ">BBBBHHBBH",
                entry_type_to_on_wire(entry.type),
                index_first_option,
                index_second_option,
                num_options,
                entry.service_id,
                entry.instance_id,
                entry.major_version,
                ttl_high,
                ttl_low,
            )

            initial_data_requested_flag_counter_value = set_bit_at_position(0, 7, True)
            initial_data_requested_flag_counter_value = (
                initial_data_requested_flag_counter_value | (entry.counter & 0xF)
            )
            output += struct.pack(
                ">BBH",
                0,
                initial_data_requested_flag_counter_value,
                entry.eventgroup_id,
            )

    length_of_options = 0

    for option in options:
        if isinstance(option, IpV4EndpointOption):
            length_of_options += 12
        elif isinstance(option, IpV6EndpointOption):
            length_of_options += 24

    output += struct.pack(">I", length_of_options)

    for option in options:
        if isinstance(option, IpV4EndpointOption):
            output += serialize_ipv4_endpoint_option(option)
        elif isinstance(option, IpV6EndpointOption):
            output += serialize_ipv6_endpoint_option(option)

    total_length = len(output) - 8
    total_length_bytes = struct.pack(">I", total_length)

    output = output[:4] + total_length_bytes + output[8:]

    return output
