import asyncio
import json
import logging
import struct
from typing import Optional

from someipy._internal._common.event import Event


class DaemonServerClient:

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        client_id: int,
        logger: logging.Logger = None,
    ):
        self._reader = reader
        self._writer = writer
        self._id = client_id
        self._logger = logger
        self.message_received: Event[ClientMessageEventArgs] = Event()

    async def read_next_message(self) -> Optional[dict]:
        wait_for_header = True
        header_buffer = b""
        message_buffer = b""
        message_length = 0

        while True:
            if wait_for_header:
                data = await self._reader.read(256 - len(header_buffer))
                if not data:
                    self._logger.debug(
                        f"Reading data returned none. Client disconnected."
                    )
                    break  # Client disconnected

                header_buffer += data

                if len(header_buffer) == 256:
                    try:
                        message_length = struct.unpack("<I", header_buffer[:4])[
                            0
                        ]  # read the first 4 bytes as unsigned int little endian.
                    except struct.error:
                        self._logger.error(f"Client sent invalid message length.")
                        break

                    wait_for_header = False
                    message_buffer = b""  # reset the message buffer
                elif len(header_buffer) > 256:
                    self._logger.error(f"Client sent too much header data.")
                    break

            else:
                data = await self._reader.read(message_length - len(message_buffer))
                if not data:
                    self._logger.debug(
                        f"Reading data returned none. Client disconnected."
                    )
                    break  # Client disconnected

                message_buffer += data

                if len(message_buffer) == message_length:
                    self._logger.debug(
                        f"Client {self.id} sent message: {message_buffer}"
                    )
                    json_message = json.loads(message_buffer.decode("utf-8"))
                    await self.message_received.invoke(
                        self, ClientMessageEventArgs(self, json_message)
                    )
                    return json_message

                elif len(message_buffer) > message_length:
                    self._logger.error(f"Client sent too much message data.")
                    raise Exception("Client sent too much message data.")
        return None

    async def send(self, data: bytes):
        self._writer.write(data)
        await self._writer.drain()

    async def close(self):
        self._writer.close()
        await self._writer.wait_closed()

    @property
    def id(self) -> int:
        return self._id


class ClientMessageEventArgs:
    def __init__(self, client: DaemonServerClient, message: dict):
        self.client = client
        self.message = message
