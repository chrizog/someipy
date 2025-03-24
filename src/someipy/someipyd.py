import asyncio
import argparse
import json
import logging
import os
import struct
import sys
from typing import Any, Tuple, Union

from someipy._internal.someip_header import SomeIpHeader
from someipy._internal.someip_sd_extractors import (
    extract_offered_services,
)
from someipy._internal.someip_sd_header import SdService, SomeIpSdHeader
from someipy._internal.store_with_timeout import StoreWithTimeout
from someipy._internal.utils import (
    DatagramAdapter,
    create_rcv_multicast_socket,
    create_udp_socket,
)


DEFAULT_SOCKET_PATH = "/tmp/someipyd.sock"
DEFAULT_CONFIG_FILE = "someipyd.json"
DEFAULT_SD_ADDRESS = "224.224.224.245"
DEFAULT_INTERFACE_IP = "127.0.0.1"
DEFAULT_SD_PORT = 30490


class SomeipDaemon:
    def __init__(self, config_file=None):
        self.logger = self._configure_logging()
        self.config = self._load_config(config_file)
        self.socket_path = self.config.get("socket_path", DEFAULT_SOCKET_PATH)
        self.sd_address = self.config.get("sd_address", DEFAULT_SD_ADDRESS)
        self.sd_port = self.config.get("sd_port", DEFAULT_SD_PORT)
        self.interface = self.config.get("interface", DEFAULT_INTERFACE_IP)
        self.clients = set()
        self.sd_socket_mcast = None
        self.sd_socket_ucast = None
        self.mcast_transport = None
        self.ucast_transport = None
        self.queue = asyncio.Queue()
        self.transmission_timer_running = False
        self._offered_services = StoreWithTimeout()

    def _configure_logging(self):
        logger = logging.getLogger(f"someipyd")
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d %(name)s [%(levelname)s]: %(message)s",
            datefmt="%Y-%m-%d,%H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        logger.setLevel(logging.DEBUG)
        return logger

    def _load_config(self, config_file):
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                self.logger.error(f"Error loading config file: {e}. Using defaults.")
                return {}
        elif os.path.exists(DEFAULT_CONFIG_FILE):
            try:
                with open(DEFAULT_CONFIG_FILE, "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                self.logger.error(f"Error loading config file: {e}. Using defaults.")
                return {}
        else:
            return {}

    async def handle_client(self, reader, writer):
        self.clients.add(writer)
        addr = writer.get_extra_info("peername")
        self.logger.info(f"Client connected: {addr}")

        try:
            wait_for_header = True
            header_buffer = b""
            message_buffer = b""
            message_length = 0

            while True:
                if wait_for_header:
                    data = await reader.read(256 - len(header_buffer))
                    if not data:
                        break  # Client disconnected

                    header_buffer += data

                    if len(header_buffer) == 256:
                        try:
                            message_length = struct.unpack("<I", header_buffer[:4])[
                                0
                            ]  # read the first 4 bytes as unsigned int little endian.
                        except struct.error:
                            self.logger.error(
                                f"Client {addr} sent invalid message length."
                            )
                            break

                        wait_for_header = False
                        message_buffer = b""  # reset the message buffer
                    elif len(header_buffer) > 256:
                        self.logger.error(f"Client {addr} sent too much header data.")
                        break

                else:
                    data = await reader.read(message_length - len(message_buffer))
                    if not data:
                        break  # Client disconnected

                    message_buffer += data

                    if len(message_buffer) == message_length:

                        self.logger.debug(
                            f"Client {addr} sent message: {message_buffer}"
                        )
                        json_message = json.loads(message_buffer.decode("utf-8"))
                        await self.handle_client_message(json_message, writer)

                        wait_for_header = True
                        header_buffer = b""  # reset header buffer
                        message_buffer = b""  # reset message buffer
                        message_length = 0  # reset message length
                    elif len(message_buffer) > message_length:
                        self.logger.error(f"Client {addr} sent too much message data.")
                        break
        except ConnectionResetError:
            self.logger.error(f"Client {addr} disconnected abruptly.")
        except Exception as e:
            self.logger.error(f"Error handling client {addr}: {e}")
        finally:
            self.logger.debug(f"Client disconnected: {addr}")
            writer.close()
            await writer.wait_closed()
            self.clients.remove(writer)

    async def handle_client_message(self, message: dict, writer: asyncio.StreamWriter):
        message_type = message.get("type")
        self.logger.debug(f"Received message type: {message_type}")
        if message_type == "get_offered_services_req":
            services = [v.value.to_json() for v in self._offered_services.values]
            answer = {"type": "get_offered_services_res", "services": services}
            self.logger.debug(
                f"Sending offered services to client {writer.get_extra_info('peername')}: {answer}"
            )
            writer.write(self.prepare_message(answer))
            await writer.drain()

        elif message_type == "find_service_req":
            pass
            # self.handle_find_service_req(message)

    def prepare_message(self, message: dict):
        payload = json.dumps(message).encode("utf-8")
        return struct.pack("<I", len(payload)) + bytes(256 - 4) + payload

    async def send_to_all_clients(self, message):
        for writer in self.clients:
            try:
                writer.write(message)
                await writer.drain()
            except ConnectionError:
                self.logger.error("Error sending message to client.")
                self.clients.remove(writer)
                writer.close()
                await writer.wait_closed()

    async def start_server(self):
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        server = await asyncio.start_unix_server(
            self.handle_client, path=self.socket_path
        )
        self.logger.info(f"Unix domain socket server started at {self.socket_path}")

        try:
            await self.start_sd_listening()
            async with server:
                await server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            if self.mcast_transport:
                self.mcast_transport.close()
            if self.ucast_transport:
                self.ucast_transport.close()
            self.logger.info("UDS server stopped.")

    def _timeout_of_offered_service(self, offered_service: SdService):
        self.logger.info(
            f"Offered service timed out: service id 0x{offered_service.service_id:04x}, instance id 0x{offered_service.instance_id:04x}"
        )

    def handle_offered_service(self, offered_service: SdService):
        self.logger.info(f"Received offered service: {offered_service}")
        asyncio.create_task(
            self._offered_services.add(
                offered_service, self._timeout_of_offered_service
            )
        )

    def datagram_received_mcast(
        self, data: bytes, addr: Tuple[Union[str, Any], int]
    ) -> None:
        # print(f"Received SD message from {addr}: {data}")

        someip_header = SomeIpHeader.from_buffer(data)
        if not someip_header.is_sd_header():
            return

        someip_sd_header = SomeIpSdHeader.from_buffer(data)

        for offered_service in extract_offered_services(someip_sd_header):
            self.handle_offered_service(offered_service)

        """
        for (
            event_group_entry,
            ipv4_endpoint_option,
        ) in extract_subscribe_eventgroup_entries(someip_sd_header):
            self._handle_subscribe_eventgroup_entry(
                event_group_entry, ipv4_endpoint_option
            )

        for event_group_entry in extract_subscribe_ack_eventgroup_entries(
            someip_sd_header
        ):
            self._handle_subscribe_ack_eventgroup_entry(event_group_entry)
        """

    def connection_lost_mcast(self, exc: Exception) -> None:
        pass

    def datagram_received_ucast(
        self, data: bytes, addr: Tuple[Union[str, Any], int]
    ) -> None:
        self.logger.debug(f"Received SD message from {addr}: {data}")

    def connection_lost_ucast(self, exc: Exception) -> None:
        pass

    async def start_sd_listening(self):
        self.sd_socket_mcast = create_rcv_multicast_socket(
            self.sd_address, self.sd_port, DEFAULT_INTERFACE_IP
        )

        loop = asyncio.get_running_loop()
        self.mcast_transport, _ = await loop.create_datagram_endpoint(
            lambda: DatagramAdapter(
                target=None,
                datagram_received_callback=self.datagram_received_mcast,
                connection_lost_callback=self.connection_lost_mcast,
            ),
            sock=self.sd_socket_mcast,
        )

        self.sd_socket_ucast = create_udp_socket(self.interface, self.sd_port)
        self.ucast_transport, _ = await loop.create_datagram_endpoint(
            lambda: DatagramAdapter(
                target=None,
                datagram_received_callback=self.datagram_received_ucast,
                connection_lost_callback=self.connection_lost_ucast,
            ),
            sock=self.sd_socket_ucast,
        )

    async def start_transmission_timer(self):
        self.transmission_timer_running = True
        await asyncio.sleep(0.1)  # 100ms
        self.transmission_timer_running = False
        await self.send_sd_offer()

    async def send_sd_offer(self):
        queue_data = []
        while not self.queue.empty():
            queue_data.append(await self.queue.get())
        if queue_data:
            offer_message = pack_someip_sd_offer(queue_data)
            try:
                self.sd_socket_mcast.sendto(
                    offer_message, (self.sd_address, self.sd_port)
                )
                self.logger.debug(f"Sent SD offer: {offer_message}")
            except Exception as e:
                self.logger.error(f"Error sending SD offer: {e}")


async def main():
    parser = argparse.ArgumentParser(description="SOME/IP Daemon")
    parser.add_argument("--config", help="Path to configuration file")
    args = parser.parse_args()

    daemon = SomeipDaemon(args.config)
    await daemon.start_server()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Daemon stopped.")
