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
from typing import Iterable, Tuple
from someipy._internal.someip_header import SomeIpHeader
from .transport_layer_protocol import TransportLayerProtocol
from .someip_sd_header import (
    SD_BYTE_LENGTH_IP4ENDPOINT_OPTION,
    SD_SINGLE_ENTRY_LENGTH_BYTES,
    SdService,
    SomeIpSdHeader,
    SdEntry,
    SdEntryType,
    SdServiceEntry,
    SdOptionCommon,
    SD_IPV4ENDPOINT_OPTION_LENGTH_VALUE,
    SdOptionType,
    SdIPV4EndpointOption,
    SdEventGroupEntry,
)


def build_offer_service_sd_header(
    services_to_offer: Iterable[SdService], session_id: int, reboot_flag: bool
) -> SomeIpSdHeader:
    # Remove duplicates
    services_to_offer = list(set(services_to_offer))

    # Collect all endpoints and create an option for each unique endpoint
    options = []
    for service in services_to_offer:

        # Check if endpoint is already contained in options
        if any(
            option.ipv4_address == service.endpoint[0]
            and option.port == service.endpoint[1]
            and option.protocol == service.protocol
            for option in options
        ):
            continue

        option_entry_common = SdOptionCommon(
            length=SD_IPV4ENDPOINT_OPTION_LENGTH_VALUE,
            type=SdOptionType.IPV4_ENDPOINT,
            discardable_flag=False,
        )
        sd_option_entry = SdIPV4EndpointOption(
            sd_option_common=option_entry_common,
            ipv4_address=service.endpoint[0],
            protocol=service.protocol,
            port=service.endpoint[1],
        )
        options.append(sd_option_entry)

    # Build the entries that reference the options
    entries = []
    for service in services_to_offer:
        for i in range(len(options)):
            if (
                options[i].ipv4_address == service.endpoint[0]
                and options[i].port == service.endpoint[1]
                and options[i].protocol == service.protocol
            ):
                sd_entry = SdEntry(
                    SdEntryType.OFFER_SERVICE,
                    i,  # index_first_option
                    0,  # index_second_option
                    1,  # num_options_1
                    0,  # num_options_2
                    service.service_id,
                    service.instance_id,
                    service.major_version,
                    service.ttl,
                )
                service_entry = SdServiceEntry(
                    sd_entry=sd_entry, minor_version=service.minor_version
                )
                entries.append(service_entry)

    # Pack together all entries and options into a single SD message

    # 20 bytes for header and length values of entries and options
    # + length of entries array
    # + length of options array
    total_length = (
        20
        + (len(entries) * SD_SINGLE_ENTRY_LENGTH_BYTES)
        + (len(options) * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION)
    )
    someip_header = SomeIpHeader.generate_sd_header(
        length=total_length, session_id=session_id
    )

    return SomeIpSdHeader(
        someip_header=someip_header,
        reboot_flag=reboot_flag,
        unicast_flag=True,
        length_entries=(len(entries) * SD_SINGLE_ENTRY_LENGTH_BYTES),
        length_options=(len(options) * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION),
        service_entries=entries,
        options=options,
    )


def build_stop_offer_service_sd_header(
    services: Iterable[SdService], session_id: int, reboot_flag: bool
) -> SomeIpSdHeader:
    header = build_offer_service_sd_header(services, session_id, reboot_flag)
    for entry in header.service_entries:
        entry.sd_entry.entry_type = SdEntryType.STOP_OFFER_SERVICE
        entry.sd_entry.ttl = 0
    return header


def build_subscribe_eventgroup_ack_entry(
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


def build_subscribe_eventgroup_ack_sd_header(
    entry: SdEventGroupEntry, session_id: int, reboot_flag: bool
) -> SomeIpSdHeader:
    # 20 bytes for header and length values of entries and options
    # + length of entries array (1 entry)
    total_length = 20 + (1 * SD_SINGLE_ENTRY_LENGTH_BYTES)
    someip_header = SomeIpHeader.generate_sd_header(
        length=total_length, session_id=session_id
    )

    return SomeIpSdHeader(
        someip_header=someip_header,
        reboot_flag=reboot_flag,
        unicast_flag=True,
        length_entries=(1 * SD_SINGLE_ENTRY_LENGTH_BYTES),
        length_options=0,
        service_entries=[entry],
        options=[],
    )


def build_subscribe_eventgroup_sd_header(
    service_id: int,
    instance_id: int,
    major_version: int,
    ttl: int,
    event_group_id: int,
    session_id: int,
    reboot_flag: bool,
    endpoint: Tuple[ipaddress.IPv4Address, int],
    protocol: TransportLayerProtocol,
) -> SomeIpSdHeader:
    sd_entry: SdEntry = SdEntry(
        SdEntryType.SUBSCRIBE_EVENT_GROUP,
        0,  # index_first_option
        0,  # index_second_option
        1,  # num_options_1
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

    option_entry_common = SdOptionCommon(
        length=SD_IPV4ENDPOINT_OPTION_LENGTH_VALUE,
        type=SdOptionType.IPV4_ENDPOINT,
        discardable_flag=False,
    )
    sd_option_entry = SdIPV4EndpointOption(
        sd_option_common=option_entry_common,
        ipv4_address=endpoint[0],
        protocol=protocol,
        port=endpoint[1],
    )

    # 20 bytes for header and length values of entries and options
    # + length of entries array (1 entry)
    # + length of options array (1 option)
    total_length = (
        20
        + (1 * SD_SINGLE_ENTRY_LENGTH_BYTES)
        + (1 * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION)
    )
    someip_header = SomeIpHeader.generate_sd_header(
        length=total_length, session_id=session_id
    )

    return SomeIpSdHeader(
        someip_header=someip_header,
        reboot_flag=reboot_flag,
        unicast_flag=True,
        length_entries=(1 * SD_SINGLE_ENTRY_LENGTH_BYTES),
        length_options=(1 * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION),
        service_entries=[entry],
        options=[sd_option_entry],
    )


def build_find_service_sd_header(
    service_id: int,
    instance_id: int = 0xFFFF,
    major_version: int = 0xFF,
    minor_version: int = 0xFFFFFFFF,
    session_id: int = 0,
    reboot_flag: bool = False,
) -> SomeIpSdHeader:
    sd_entry: SdEntry = SdEntry(
        SdEntryType.FIND_SERVICE,
        0,  # index_first_option
        0,  # index_second_option
        0,  # num_options_1
        0,  # num_options_2
        service_id,
        instance_id,
        major_version,
        0,  # TTL can be set to an arbitrary value
    )

    sd_service_entry = SdServiceEntry(sd_entry=sd_entry, minor_version=minor_version)

    # 20 bytes for header and length values of entries and options
    # + length of entries array (1 entry)
    # + length of options array (1 option)
    total_length = (
        20
        + (1 * SD_SINGLE_ENTRY_LENGTH_BYTES)
        + (1 * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION)
    )
    someip_header = SomeIpHeader.generate_sd_header(
        length=total_length, session_id=session_id
    )

    return SomeIpSdHeader(
        someip_header=someip_header,
        reboot_flag=reboot_flag,
        unicast_flag=True,
        length_entries=(1 * SD_SINGLE_ENTRY_LENGTH_BYTES),
        length_options=(1 * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION),
        service_entries=[sd_service_entry],
        options=[],
    )
