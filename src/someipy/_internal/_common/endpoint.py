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

import ipaddress
from typing import NamedTuple, Union


class Endpoint(NamedTuple):
    """Represents a network endpoint with IP address and port."""

    ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
    port: int

    @property
    def is_ipv4(self):
        return isinstance(self.ip, ipaddress.IPv4Address)

    def __str__(self):
        if isinstance(self.ip, ipaddress.IPv6Address):
            return f"[{self.ip}]:{self.port}"
        return f"{self.ip}:{self.port}"
