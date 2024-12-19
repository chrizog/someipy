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

from typing import List, Tuple, Iterable, Union
from .someip_sd_header import (
    SomeIpSdHeader,
    SdService,
    SdEntryType,
    SdEventGroupEntry,
    SdServiceEntry,
)
from .someip_sd_option import SdIPV4EndpointOption, SdOptionType, SdOptionInterface


def option_runs(
    entry: Union[SdServiceEntry, SdEventGroupEntry], sd_message: SomeIpSdHeader
) -> Iterable[SdOptionInterface]:
    """This function performs the option runs for SD entries. It uses the
    start index and the number of options to iterate over the options in two runs"""

    # First option run
    start_index = entry.sd_entry.index_first_option
    for i in range(entry.sd_entry.num_options_1):
        yield sd_message.options[start_index + i]

    # Second option run
    start_index = entry.sd_entry.index_second_option
    for i in range(entry.sd_entry.num_options_2):
        yield sd_message.options[start_index + i]


def extract_offered_services(someip_sd_header: SomeIpSdHeader) -> List[SdService]:
    result: List[SdService] = []
    service_offers = [
        o
        for o in someip_sd_header.service_entries
        if o.sd_entry.type == SdEntryType.OFFER_SERVICE
    ]
    for e in service_offers:

        options = option_runs(e, someip_sd_header)
        for option in options:
            if option.get_sd_option_type() == SdOptionType.IPV4_ENDPOINT:
                endpoint = (
                    option.ipv4_address,
                    option.port,
                )
                protocol = option.protocol
                sd_offered_service = SdService(
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


def extract_subscribe_eventgroup_entries(
    someip_sd_header: SomeIpSdHeader,
) -> List[Tuple[SdEventGroupEntry, SdIPV4EndpointOption]]:
    result = []

    for entry in someip_sd_header.service_entries:
        if entry.sd_entry.type == SdEntryType.SUBSCRIBE_EVENT_GROUP:
            # Check TTL in order to distinguish between subscribe and stop subscribe
            # SUBSCRIBE_EVENT_GROUP = 0x06
            # STOP_SUBSCRIBE_EVENT_GROUP = 0x06 but with TTL set to 0x00
            if entry.sd_entry.ttl != 0x00:

                options = option_runs(entry, someip_sd_header)
                for current_option in options:
                    if (
                        current_option.sd_option_common.type
                        == SdOptionType.IPV4_ENDPOINT
                    ):
                        result.append((entry, current_option))
    return result


def extract_subscribe_ack_eventgroup_entries(
    someip_sd_header: SomeIpSdHeader,
) -> List[SdEventGroupEntry]:
    result = []

    for entry in someip_sd_header.service_entries:
        if entry.sd_entry.type == SdEntryType.SUBSCRIBE_EVENT_GROUP_ACK:
            # Check TTL in order to distinguish between subscribe ack and nack
            # SUBSCRIBE_EVENT_GROUP_ACK = 0x07
            # SUBSCRIBE_EVENT_GROUP_NACK = 0x07  # with TTL set to 0x00
            if entry.sd_entry.ttl != 0x00:
                result.append(entry)
    return result
