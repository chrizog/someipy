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
from enum import Enum
import ipaddress
import socket
import struct


from someipy._internal._sd.entries.find_service_entry import FindServiceEntry
from someipy._internal._sd.entries.offer_service_entry import OfferServiceEntry
from someipy._internal._sd.entries.stop_offer_service_entry import StopOfferServiceEntry
from someipy._internal._sd.entries.stop_subscribe_eventgroup_entry import (
    StopSubscribeEventGroupEntry,
)
from someipy._internal._sd.entries.subscribe_ack_entry import (
    SubscribeAckEventGroupEntry,
)
from someipy._internal._sd.entries.subscribe_eventgroup_entry import (
    SubscribeEventGroupEntry,
)
from someipy._internal._sd.entries.subscribe_eventgroup_nack import (
    SubscribeEventGroupNackEntry,
)
from someipy._internal._sd.options.configuration_option import ConfigurationOption
from someipy._internal._sd.options.endpoint import (
    IpV4EndpointOption,
    IpV6EndpointOption,
)
from someipy._internal._sd.options.load_balancing import LoadBalancingOption
from someipy._internal._sd.options.multicast import (
    IpV4MulticastOption,
    IpV6MulticastOption,
)
from someipy._internal._sd.options.sd_endpoint import (
    IpV4SdEndpointOption,
    IpV6SdEndpointOption,
)
from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy._internal.utils import is_bit_set
from someipy._internal._sd.sd_message import SdMessage

SERVICE_ID_SD = 0xFFFF
METHOD_ID_SD = 0x8100
CLIENT_ID_SD = 0x0000
PROTOCOL_VERSION_SD = 0x01
INTERFACE_VERSION_SD = 0x01
MESSAGE_TYPE_SD = 0x02
RETURN_CODE_SD = 0x00

MINIMAL_HEADER_SIZE = 16


class SdOptionOnWireType(Enum):
    CONFIGURATION = 0x01
    LOAD_BALANCING = 0x02
    IPV4_ENDPOINT = 0x04
    IPV6_ENDPOINT = 0x06
    IPV4_MULTICAST = 0x14
    IPV6_MULTICAST = 0x16
    IPV4_SD_ENDPOINT = 0x24
    IPV6_SD_ENDPOINT = 0x26


class SdEntryOnWireType(Enum):
    FIND_SERVICE = 0x00
    OFFER_SERVICE = 0x01
    STOP_OFFER_SERVICE = 0x01  # with TTL to 0x000000
    SUBSCRIBE_EVENT_GROUP = 0x06
    STOP_SUBSCRIBE_EVENT_GROUP = 0x06  # with TTL to 0x000000
    SUBSCRIBE_EVENT_GROUP_ACK = 0x07
    SUBSCRIBE_EVENT_GROUP_NACK = 0x07  # with TTL to 0x000000


def is_sd_message(data: bytes) -> bool:
    if len(data) < MINIMAL_HEADER_SIZE:
        return False

    service_id, method_id, length = struct.unpack(">HHI", data[0:8])

    if length < 12:
        return False

    if length > len(data) - 8:
        return False

    (
        client_id,
        session_id,
        protocol_version,
        interface_version,
        message_type,
        return_code,
    ) = struct.unpack(">HHBBBB", data[8:16])

    return (
        service_id == SERVICE_ID_SD
        and method_id == METHOD_ID_SD
        and client_id == CLIENT_ID_SD
        and protocol_version == PROTOCOL_VERSION_SD
        and interface_version == INTERFACE_VERSION_SD
        and message_type == MESSAGE_TYPE_SD
        and return_code == RETURN_CODE_SD
        and session_id != 0
    )


@dataclass
class CommonEntryData:
    type_field_value: int
    index_first_option: int
    index_second_option: int
    num_options_1: int
    num_options_2: int
    service_id: int
    instance_id: int
    major_version: int
    ttl: int


@dataclass
class CommonOptionData:
    option_length: int
    option_type: SdOptionOnWireType
    discardable_flag: bool


def deserialize_common_entry_data(data: bytes) -> CommonEntryData:
    type_field_value, index_first_option, index_second_option = struct.unpack(
        ">BBB", data[0:3]
    )

    num_options_1 = struct.unpack(">B", data[3:4])[0]  # higher 4 bits
    num_options_1 = (num_options_1 >> 4) & 0x0F

    num_options_2 = struct.unpack(">B", data[3:4])[0]  # lower 4 bits
    num_options_2 = num_options_2 & 0x0F

    service_id, instance_id, major_version = struct.unpack(">HHB", data[4:9])
    (ttl,) = struct.unpack(">I", data[8:12])
    ttl = ttl & 0xFFFFFF

    return CommonEntryData(
        type_field_value,
        index_first_option,
        index_second_option,
        num_options_1,
        num_options_2,
        service_id,
        instance_id,
        major_version,
        ttl,
    )


def deserialize_common_option_data(data: bytes) -> CommonOptionData:
    option_length, option_type, discardable_flag_value = struct.unpack(
        ">HBB", data[0:4]
    )
    option_type = SdOptionOnWireType(option_type)
    discardable_flag = is_bit_set(discardable_flag_value, 7)
    return CommonOptionData(option_length, option_type, discardable_flag)


def deserialize_ipv4_endpoint_option(data: bytes) -> IpV4EndpointOption:
    ip1, ip2, ip3, ip4, _, protocol_value, port = struct.unpack(">BBBBBBH", data[0:8])
    address = ipaddress.IPv4Address(f"{ip1}.{ip2}.{ip3}.{ip4}")
    protocol = TransportLayerProtocol(protocol_value)
    return IpV4EndpointOption(address=address, protocol=protocol, port=port)


def deserialize_ipv6_endpoint_option(data: bytes) -> IpV6EndpointOption:
    packed = data[0:16]
    ipv6_str = socket.inet_ntop(socket.AF_INET6, packed)
    address = ipaddress.IPv6Address(ipv6_str)
    _, protocol_value, port = struct.unpack(">BBH", data[16:20])
    protocol = TransportLayerProtocol(protocol_value)
    return IpV6EndpointOption(address=address, protocol=protocol, port=port)


def deserialize_ipv4_multicast_option(data: bytes) -> IpV4MulticastOption:
    ip1, ip2, ip3, ip4, _, protocol_value, port = struct.unpack(">BBBBBBH", data[0:8])
    address = ipaddress.IPv4Address(f"{ip1}.{ip2}.{ip3}.{ip4}")
    protocol = TransportLayerProtocol(protocol_value)
    return IpV4MulticastOption(address=address, protocol=protocol, port=port)


def deserialize_ipv6_multicast_option(data: bytes) -> IpV6MulticastOption:
    packed = data[0:16]
    ipv6_str = socket.inet_ntop(socket.AF_INET6, packed)
    address = ipaddress.IPv6Address(ipv6_str)
    _, protocol_value, port = struct.unpack(">BBH", data[16:20])
    protocol = TransportLayerProtocol(protocol_value)
    return IpV6MulticastOption(address=address, protocol=protocol, port=port)


def deserialize_ipv4_sd_endpoint_option(data: bytes) -> IpV4SdEndpointOption:
    ip1, ip2, ip3, ip4, _, _, port = struct.unpack(">BBBBBBH", data[0:8])
    address = ipaddress.IPv4Address(f"{ip1}.{ip2}.{ip3}.{ip4}")
    return IpV4SdEndpointOption(address=address, port=port)


def deserialize_ipv6_sd_endpoint_option(data: bytes) -> IpV6SdEndpointOption:
    packed = data[0:16]
    ipv6_str = socket.inet_ntop(socket.AF_INET6, packed)
    address = ipaddress.IPv6Address(ipv6_str)
    _, _, port = struct.unpack(">BBH", data[16:20])
    return IpV6SdEndpointOption(address=address, port=port)


def deserialize_load_balancing_option(data: bytes) -> LoadBalancingOption:
    priority, weight = struct.unpack(">HH", data[0:4])
    return LoadBalancingOption(priority=priority, weight=weight)


def deserialize_sd_message(
    data: bytes, source: str, port: int, multicast: bool
) -> SdMessage:

    if not is_sd_message(data):
        raise ValueError("The provided data is not a valid SOME/IP-SD message.")

    service_id, method_id, length = struct.unpack(">HHI", data[0:8])
    if length <= 0:
        raise ValueError(f"Length in SOME/IP header is <=0 ({length})")

    if length < 8:
        raise ValueError(f"Length in SOME/IP header is <8 ({length})")

    (
        client_id,
        session_id,
        protocol_version,
        interface_version,
        message_type,
        return_code,
    ) = struct.unpack(">HHBBBB", data[8:16])

    (flags,) = struct.unpack(">B", data[16:17])
    reboot_flag = is_bit_set(flags, 7)
    unicast_flag = is_bit_set(flags, 6)

    # Constants for byte positions inside the SD header
    SD_POSITION_ENTRY_LENGTH = 20
    SD_START_POSITION_ENTRIES = 24

    # Constants for length of sections in the SD header
    SD_SINGLE_ENTRY_LENGTH_BYTES = 16

    (length_entries,) = struct.unpack(
        ">I", data[SD_POSITION_ENTRY_LENGTH : SD_POSITION_ENTRY_LENGTH + 4]
    )

    number_of_entries = int(length_entries / SD_SINGLE_ENTRY_LENGTH_BYTES)

    pos_length_options = SD_POSITION_ENTRY_LENGTH + 4 + length_entries
    (length_options,) = struct.unpack(
        ">I", data[pos_length_options : pos_length_options + 4]
    )
    pos_start_options = pos_length_options + 4

    current_pos_option = pos_start_options
    bytes_options_left = length_options

    options = []
    while bytes_options_left > 0:

        common_option_data = deserialize_common_option_data(
            data[current_pos_option : current_pos_option + 4]
        )

        option_type = common_option_data.option_type

        if option_type == SdOptionOnWireType.IPV4_ENDPOINT:
            sd_option = deserialize_ipv4_endpoint_option(
                data[current_pos_option + 4 : current_pos_option + 12]
            )
            options.append(sd_option)

        elif option_type == SdOptionOnWireType.IPV6_ENDPOINT:
            sd_option = deserialize_ipv6_endpoint_option(
                data[current_pos_option + 4 : current_pos_option + 24]
            )
            options.append(sd_option)
        elif option_type == SdOptionOnWireType.IPV4_MULTICAST:
            sd_option = deserialize_ipv4_multicast_option(
                data[current_pos_option + 4 : current_pos_option + 12]
            )
            options.append(sd_option)
        elif option_type == SdOptionOnWireType.IPV6_MULTICAST:
            sd_option = deserialize_ipv6_multicast_option(
                data[current_pos_option + 4 : current_pos_option + 24]
            )
            options.append(sd_option)
        elif option_type == SdOptionOnWireType.IPV4_SD_ENDPOINT:
            sd_option = deserialize_ipv4_sd_endpoint_option(
                data[current_pos_option + 4 : current_pos_option + 12]
            )
            options.append(sd_option)
        elif option_type == SdOptionOnWireType.IPV6_SD_ENDPOINT:
            sd_option = deserialize_ipv6_sd_endpoint_option(
                data[current_pos_option + 4 : current_pos_option + 24]
            )
            options.append(sd_option)
        elif option_type == SdOptionOnWireType.CONFIGURATION:
            dummy_config_option = ConfigurationOption()
            options.append(dummy_config_option)
        elif option_type == SdOptionOnWireType.LOAD_BALANCING:
            sd_option = deserialize_load_balancing_option(
                data[current_pos_option + 4 : current_pos_option + 8]
            )
            options.append(sd_option)

        # Subtract 3 bytes first for length and type
        bytes_options_left -= common_option_data.option_length + 3
        current_pos_option += common_option_data.option_length + 3

    # Read in all Service and Event Group entries
    entries = []
    for i in range(number_of_entries):
        start_entry = SD_START_POSITION_ENTRIES + (i * SD_SINGLE_ENTRY_LENGTH_BYTES)
        end_entry = start_entry + SD_SINGLE_ENTRY_LENGTH_BYTES

        common_entry_data = deserialize_common_entry_data(
            data[start_entry : start_entry + 12]
        )

        if (
            common_entry_data.type_field_value == SdEntryOnWireType.OFFER_SERVICE.value
            and common_entry_data.ttl != 0
        ):
            (minor_version,) = struct.unpack(
                ">I", data[start_entry + 12 : start_entry + 16]
            )

            applicable_options = []
            for j in range(common_entry_data.num_options_1):
                applicable_options.append(
                    options[common_entry_data.index_first_option + j]
                )
            for j in range(common_entry_data.num_options_2):
                applicable_options.append(
                    options[common_entry_data.index_second_option + j]
                )

            offer_service_entry = OfferServiceEntry(
                service_id=common_entry_data.service_id,
                instance_id=common_entry_data.instance_id,
                major_version=common_entry_data.major_version,
                minor_version=minor_version,
                ttl=common_entry_data.ttl,
                ip_v4_endpoints=[
                    o for o in applicable_options if isinstance(o, IpV4EndpointOption)
                ],
                ip_v6_endpoints=[
                    o for o in applicable_options if isinstance(o, IpV6EndpointOption)
                ],
            )
            entries.append(offer_service_entry)

        elif (
            common_entry_data.type_field_value
            == SdEntryOnWireType.STOP_OFFER_SERVICE.value
            and common_entry_data.ttl == 0
        ):
            (minor_version,) = struct.unpack(
                ">I", data[start_entry + 12 : start_entry + 16]
            )

            applicable_options = []
            for j in range(common_entry_data.num_options_1):
                applicable_options.append(
                    options[common_entry_data.index_first_option + j]
                )
            for j in range(common_entry_data.num_options_2):
                applicable_options.append(
                    options[common_entry_data.index_second_option + j]
                )

            stop_offer_service_entry = StopOfferServiceEntry(
                service_id=common_entry_data.service_id,
                instance_id=common_entry_data.instance_id,
                major_version=common_entry_data.major_version,
                minor_version=minor_version,
                ip_v4_endpoints=[
                    o for o in applicable_options if isinstance(o, IpV4EndpointOption)
                ],
                ip_v6_endpoints=[
                    o for o in applicable_options if isinstance(o, IpV6EndpointOption)
                ],
            )
            entries.append(stop_offer_service_entry)

        elif common_entry_data.type_field_value == SdEntryOnWireType.FIND_SERVICE.value:
            (minor_version,) = struct.unpack(
                ">I", data[start_entry + 12 : start_entry + 16]
            )

            find_service_entry = FindServiceEntry(
                service_id=common_entry_data.service_id,
                instance_id=common_entry_data.instance_id,
                major_version=common_entry_data.major_version,
                minor_version=minor_version,
            )
            entries.append(find_service_entry)

        elif (
            common_entry_data.type_field_value
            == SdEntryOnWireType.SUBSCRIBE_EVENT_GROUP.value
            and common_entry_data.ttl != 0
        ):
            initial_data_requested_flag_counter_value, eventgroup_id = struct.unpack(
                ">BH", data[start_entry + 13 : start_entry + 16]
            )
            initial_data_requested_flag = is_bit_set(
                initial_data_requested_flag_counter_value, 7
            )
            counter = initial_data_requested_flag_counter_value & 0xF

            applicable_options = []
            for j in range(common_entry_data.num_options_1):
                applicable_options.append(
                    options[common_entry_data.index_first_option + j]
                )
            for j in range(common_entry_data.num_options_2):
                applicable_options.append(
                    options[common_entry_data.index_second_option + j]
                )

            subscribe_eventgroup_entry = SubscribeEventGroupEntry(
                service_id=common_entry_data.service_id,
                instance_id=common_entry_data.instance_id,
                major_version=common_entry_data.major_version,
                minor_version=minor_version,
                ttl=common_entry_data.ttl,
                eventgroup_id=eventgroup_id,
                counter=counter,
                ip_v4_endpoints=[
                    o for o in applicable_options if isinstance(o, IpV4EndpointOption)
                ],
                ip_v6_endpoints=[
                    o for o in applicable_options if isinstance(o, IpV6EndpointOption)
                ],
            )
            entries.append(subscribe_eventgroup_entry)

        elif (
            common_entry_data.type_field_value
            == SdEntryOnWireType.STOP_SUBSCRIBE_EVENT_GROUP.value
            and common_entry_data.ttl == 0
        ):
            initial_data_requested_flag_counter_value, eventgroup_id = struct.unpack(
                ">BH", data[start_entry + 13 : start_entry + 16]
            )
            initial_data_requested_flag = is_bit_set(
                initial_data_requested_flag_counter_value, 7
            )
            counter = initial_data_requested_flag_counter_value & 0xF

            applicable_options = []
            for j in range(common_entry_data.num_options_1):
                applicable_options.append(
                    options[common_entry_data.index_first_option + j]
                )
            for j in range(common_entry_data.num_options_2):
                applicable_options.append(
                    options[common_entry_data.index_second_option + j]
                )

            stop_subscribe_eventgroup_entry = StopSubscribeEventGroupEntry(
                service_id=common_entry_data.service_id,
                instance_id=common_entry_data.instance_id,
                major_version=common_entry_data.major_version,
                minor_version=minor_version,
                ttl=common_entry_data.ttl,
                ip_v4_endpoints=[
                    o for o in applicable_options if isinstance(o, IpV4EndpointOption)
                ],
                ip_v6_endpoints=[
                    o for o in applicable_options if isinstance(o, IpV6EndpointOption)
                ],
            )
            entries.append(stop_subscribe_eventgroup_entry)

        elif (
            common_entry_data.type_field_value
            == SdEntryOnWireType.SUBSCRIBE_EVENT_GROUP_ACK.value
            and common_entry_data.ttl != 0
        ):
            initial_data_requested_flag_counter_value, eventgroup_id = struct.unpack(
                ">BH", data[start_entry + 13 : start_entry + 16]
            )
            initial_data_requested_flag = is_bit_set(
                initial_data_requested_flag_counter_value, 7
            )
            counter = initial_data_requested_flag_counter_value & 0xF

            applicable_options = []
            for j in range(common_entry_data.num_options_1):
                applicable_options.append(
                    options[common_entry_data.index_first_option + j]
                )
            for j in range(common_entry_data.num_options_2):
                applicable_options.append(
                    options[common_entry_data.index_second_option + j]
                )

            subscribe_ack_eventgroup_entry = SubscribeAckEventGroupEntry(
                service_id=common_entry_data.service_id,
                instance_id=common_entry_data.instance_id,
                major_version=common_entry_data.major_version,
                minor_version=minor_version,
                ttl=common_entry_data.ttl,
                eventgroup_id=eventgroup_id,
                counter=counter,
                ip_v4_endpoints=[
                    o for o in applicable_options if isinstance(o, IpV4EndpointOption)
                ],
                ip_v6_endpoints=[
                    o for o in applicable_options if isinstance(o, IpV6EndpointOption)
                ],
            )
            entries.append(subscribe_ack_eventgroup_entry)

        elif (
            common_entry_data.type_field_value
            == SdEntryOnWireType.SUBSCRIBE_EVENT_GROUP_NACK.value
            and common_entry_data.ttl == 0
        ):
            initial_data_requested_flag_counter_value, eventgroup_id = struct.unpack(
                ">BH", data[start_entry + 13 : start_entry + 16]
            )
            initial_data_requested_flag = is_bit_set(
                initial_data_requested_flag_counter_value, 7
            )
            counter = initial_data_requested_flag_counter_value & 0xF

            applicable_options = []
            for j in range(common_entry_data.num_options_1):
                applicable_options.append(
                    options[common_entry_data.index_first_option + j]
                )
            for j in range(common_entry_data.num_options_2):
                applicable_options.append(
                    options[common_entry_data.index_second_option + j]
                )

            subscribe_ack_eventgroup_entry = SubscribeEventGroupNackEntry(
                service_id=common_entry_data.service_id,
                instance_id=common_entry_data.instance_id,
                major_version=common_entry_data.major_version,
                minor_version=minor_version,
                eventgroup_id=eventgroup_id,
                counter=counter,
            )
            entries.append(subscribe_ack_eventgroup_entry)

    sd_message = SdMessage()
    sd_message.source = source
    sd_message.source_port = port
    sd_message.multicast = multicast
    sd_message.session_id = session_id
    sd_message.reboot_flag = reboot_flag
    sd_message.entries = entries
    return sd_message
