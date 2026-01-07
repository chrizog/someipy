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


from enum import Enum, unique


@unique
class SdEntryType(Enum):
    FIND_SERVICE = 0
    OFFER_SERVICE = 1
    STOP_OFFER_SERVICE = 2
    SUBSCRIBE_EVENT_GROUP = 3
    STOP_SUBSCRIBE_EVENT_GROUP = 4
    SUBSCRIBE_EVENT_GROUP_ACK = 5
    SUBSCRIBE_EVENT_GROUP_NACK = 6


class SdEntry:
    def __init__(self, entry_type: SdEntryType):
        self._entry_type = entry_type

    @property
    def type(self) -> SdEntryType:
        return self._entry_type
