import asyncio
import json
import struct
from typing import List

from someipy.service_discovery import SdService


async def connect_to_someipy_daemon(config: dict = None):
    daemon_client = SomeIpDaemonClient(config)
    await daemon_client._connect_to_daemon()
    return daemon_client


class SomeIpDaemonClient:

    def __init__(self, config: dict = None):
        self.config = config

        if self.config == None or "socket_path" not in self.config:
            self.socket_path = "/tmp/someipyd.sock"
        else:
            self.socket_path = self.config["socket_path"]

    def _prepare_request(self, message: dict):
        payload = json.dumps(message).encode("utf-8")
        return struct.pack("<I", len(payload)) + bytes(256 - 4) + payload

    async def _connect_to_daemon(self):
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path), timeout=1
            )
        except asyncio.TimeoutError:
            raise Exception("Failed to connect to daemon: Timeout")
        except Exception as e:
            raise Exception(f"Failed to connect to daemon: {e}")

    async def disconnect_from_daemon(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            self.writer = None

    async def _read_next_message(self, timeout=None) -> str:
        wait_for_header = True
        header_buffer = b""
        message_buffer = b""
        message_length = 0

        while True:
            if wait_for_header:
                try:
                    if timeout is not None:
                        data = await asyncio.wait_for(
                            self.reader.read(256 - len(header_buffer)), timeout
                        )
                    else:
                        data = await self.reader.read(256 - len(header_buffer))
                    if not data:
                        break
                except asyncio.TimeoutError:
                    raise Exception("Failed to read header: Timeout")
                except Exception as e:
                    raise Exception(f"Failed to read header: {e}")

                header_buffer += data

                if len(header_buffer) == 256:
                    try:
                        message_length = struct.unpack("<I", header_buffer[:4])[0]
                        wait_for_header = False
                    except struct.error:
                        print(f"Client sent invalid message length.")
                        break

            else:
                try:
                    if timeout is not None:
                        data = await asyncio.wait_for(
                            self.reader.read(message_length - len(message_buffer)),
                            timeout,
                        )
                    else:
                        data = await self.reader.read(
                            message_length - len(message_buffer)
                        )
                    if not data:
                        break
                except asyncio.TimeoutError:
                    raise Exception("Failed to read message: Timeout")
                except Exception as e:
                    raise Exception(f"Failed to read message: {e}")

                message_buffer += data

                if len(message_buffer) == message_length:
                    return message_buffer.decode("utf-8")

    async def _get_offered_services(self) -> List[SdService]:
        request = {
            "type": "get_offered_services_req",
        }
        request_bytes = self._prepare_request(request)
        self.writer.write(request_bytes)
        await self.writer.drain()

        response = await self._read_next_message(timeout=1)
        response_dict = json.loads(response)

        if response_dict["type"] != "get_offered_services_res":
            raise Exception(
                f"Invalid response from daemon. Expected get_offered_services_res and got {response['type']}"
            )

        services = [
            SdService.from_json(service) for service in response_dict["services"]
        ]

        return services

    async def _find_service(self, service: SdService):
        request = {
            "type": "find_service_req",
            "service": service.to_dict(),
        }
        request_bytes = self._prepare_request(request)
        self.writer.write(request_bytes)
        await self.writer.drain()

        response = await self._read_next_message(timeout=1)
        if response["type"] != "find_service_res":
            raise Exception(
                f"Invalid response from daemon. Expected find_service_res and got {response['type']}"
            )

        return response["service"]

    async def _subscribe_to_eventgroup(self, service: SdService, eventgroup_id: int):
        pass

    async def _unsubscribe_from_eventgroup(
        self, service: SdService, eventgroup_id: int
    ):
        pass
