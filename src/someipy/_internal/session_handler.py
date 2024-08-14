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

from typing import Tuple

class SessionHandler:
    session_id: int
    reboot_flag: bool

    def __init__(self, initial_value=0):
        self.session_id = initial_value
        self.reboot_flag = True

    def update_session(self) -> Tuple[int, bool]:
        self.session_id += 1
        if self.session_id > 0xFFFF:
            self.session_id = 1
            self.reboot_flag = False

        return self.session_id, self.reboot_flag