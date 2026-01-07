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

import asyncio
import logging
import os
from someipy._internal._common.event import Event
from someipy._internal._daemon.daemon_server_client import DaemonServerClient


class ClientConnectedEventArgs:
    def __init__(self, client: DaemonServerClient):
        self.client = client


class DaemonServer:

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self.client_connected: Event[ClientConnectedEventArgs] = Event()
        self.client_disconnected: Event[ClientConnectedEventArgs] = Event()

    async def _handle_client(self, reader, writer):
        writer_id = id(writer)
        self._logger.info(f"New client connected: {writer_id}")

        client = DaemonServerClient(reader, writer, writer_id, self._logger)
        await self.client_connected.invoke(self, ClientConnectedEventArgs(client))

        while True:
            message = await client.read_next_message()
            if message is None:
                break  # Client disconnected

        await self.client_disconnected.invoke(self, ClientConnectedEventArgs(client))

    async def start(
        self,
        use_tcp: bool = False,
        socket_path: str | None = None,
        tcp_port: int | None = None,
        host: str = "127.0.0.1",
    ):
        if not use_tcp:
            if os.path.exists(socket_path):
                os.unlink(socket_path)

            self._server = await asyncio.start_unix_server(
                self._handle_client, path=socket_path
            )
            self._logger.info(f"Unix domain socket server started at {socket_path}")
        else:
            self._server = await asyncio.start_server(
                self._handle_client,
                host=host,
                port=tcp_port,
                reuse_port=True,
            )
            self._logger.info(f"TCP server started at {host}:{tcp_port}")

    async def serve_forever(self):
        async with self._server:
            await self._server.serve_forever()
