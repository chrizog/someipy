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
from typing import List

from someipy._internal._sd.entries.sd_entry import SdEntry, SdEntryType
from someipy._internal._sd.options.endpoint import (
    IpV4EndpointOption,
    IpV6EndpointOption,
)


@dataclass
class SubscribeEventGroupEntry(SdEntry):
    service_id: int
    instance_id: int
    major_version: int
    ttl: int
    eventgroup_id: int
    counter: int
    ip_v4_endpoints: List[IpV4EndpointOption]
    ip_v6_endpoints: List[IpV6EndpointOption]

    def __init__(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        ttl: int,
        eventgroup_id: int,
        counter: int,
        ip_v4_endpoints: List[IpV4EndpointOption],
        ip_v6_endpoints: List[IpV6EndpointOption],
    ):
        super().__init__(SdEntryType.SUBSCRIBE_EVENT_GROUP)
        self.service_id = service_id
        self.instance_id = instance_id
        self.major_version = major_version
        self.ttl = ttl
        self.eventgroup_id = eventgroup_id
        self.counter = counter
        self.ip_v4_endpoints = ip_v4_endpoints
        self.ip_v6_endpoints = ip_v6_endpoints
