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

import asyncio
from someipy._internal.logging import get_logger

_logger_name = "tcp_connection"


class TcpConnection:
    def __init__(self, remote_ip: str, remote_port: int):
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.reader = None
        self.writer = None

    async def connect(self, src_ip: str, src_port: int):
        local_addr = (src_ip, src_port)
        self.reader, self.writer = await asyncio.open_connection(
            self.remote_ip, self.remote_port, local_addr=local_addr
        )
        get_logger(_logger_name).debug(
            f"Connected to {self.remote_ip}:{self.remote_port}"
        )

    def is_open(self):
        if self.writer is None or self.writer.is_closing():
            return False
        return not self.reader.at_eof()

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            self.writer = None
            get_logger(_logger_name).debug(
                f"Connection to {self.remote_ip}:{self.remote_port} closed"
            )
