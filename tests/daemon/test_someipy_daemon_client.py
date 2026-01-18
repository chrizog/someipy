# Copyright (C) 2026 Christian H.
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

import json
import pytest

from someipy._internal._daemon.someipy_daemon_client import SomeIpDaemonClient


@pytest.mark.asyncio
async def test_read_next_message_reads_message():

    client = SomeIpDaemonClient()

    data = {"test": "data"}

    data_bytes = json.dumps(data).encode("utf-8")
    length_bytes = len(data_bytes).to_bytes(4, byteorder="little")
    header_bytes = length_bytes + bytes(252)

    message_bytes = header_bytes + data_bytes

    class StubReader:
        def __init__(self):
            self.pos = 0

        async def read(self, n: int) -> bytes:
            new_pos = self.pos + n
            result = message_bytes[self.pos : new_pos]
            self.pos = new_pos
            return result

    message = await client._read_next_message(StubReader())
    assert message == data
