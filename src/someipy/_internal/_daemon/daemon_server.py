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
        use_uds: bool = True,
        socket_path: str | None = None,
        tcp_port: int | None = None,
        host: str = "127.0.0.1",
    ):
        if use_uds:
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
