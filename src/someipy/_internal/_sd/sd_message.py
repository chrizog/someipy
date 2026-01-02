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


from typing import List
from someipy._internal._sd.entries.sd_entry import SdEntry


class SdMessage:

    def __init__(self):
        self.source: str = ""
        self.source_port: int = 0
        self.multicast: bool = True
        self.timestamp: float = 0.0

        self.session_id: int = 0
        self.reboot_flag: bool = False
        self.entries: List[SdEntry] = []
