import asyncio
import ipaddress
import json
import struct
from typing import Dict, List, TypedDict

from someipy._internal.daemon_client_abcs import ClientInstanceInterface
from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy._internal.utils import EndpointType
from someipy.service_discovery import SdService


async def connect_to_someipy_daemon(config: dict = None):
    daemon_client = SomeIpDaemonClient(config)
    await daemon_client._connect_to_daemon()
    return daemon_client


class DaemonMessage(TypedDict):
    type: str


class SomeIpDaemonClient:

    def __init__(self, config: dict = None):
        self._config = config

        if self._config == None or "socket_path" not in self._config:
            self._socket_path = "/tmp/someipyd.sock"
        else:
            self._socket_path = self._config["socket_path"]

        self._rx_message_queue: asyncio.Queue[DaemonMessage] = asyncio.Queue()
        self._rx_task: asyncio.Task = None

        self._tx_queue: asyncio.Queue = asyncio.Queue()
        self._tx_task: asyncio.Task = None

        self._client_service_instances: Dict[int, ClientInstanceInterface] = {}

    def _prepare_request(self, message: dict):
        payload = json.dumps(message).encode("utf-8")
        return struct.pack("<I", len(payload)) + bytes(256 - 4) + payload

    async def _connect_to_daemon(self):
        try:
            while not self._rx_message_queue.empty():
                try:
                    self._rx_message_queue.get_nowait()
                    self._rx_message_queue.task_done()
                except asyncio.QueueEmpty:
                    break

            self._rx_message_queue = asyncio.Queue()
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self._socket_path), timeout=1
            )

            self._rx_task = asyncio.create_task(self.receive_data())
            self._tx_task = asyncio.create_task(self.transmit_data_task(self.writer))

        except asyncio.TimeoutError:
            raise Exception("Failed to connect to daemon: Timeout")
        except Exception as e:
            raise Exception(f"Failed to connect to daemon: {e}")

    async def disconnect_from_daemon(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            self.writer = None

        if self._rx_task:
            try:
                self._rx_task.cancel()
                await self._rx_task
            except asyncio.CancelledError:
                pass
            finally:
                self._rx_task = None

        if self._tx_task:
            try:
                self._tx_task.cancel()
                await self._tx_task
            except asyncio.CancelledError:
                pass
            finally:
                self._tx_task = None

    async def transmit_data_task(self, writer: asyncio.StreamWriter):
        try:
            while True:
                try:
                    # Wait on queue with timeout
                    data = await asyncio.wait_for(self._tx_queue.get(), timeout=0.2)

                    try:
                        # Send the data
                        writer.write(data)
                        await writer.drain()
                    except ConnectionError as e:
                        print(f"Connection error: {e}")
                        break

                except asyncio.TimeoutError:
                    # Periodic timeout for cancellation check
                    continue

        except asyncio.CancelledError:
            print("TX task cancelled, cleaning up...")
            # Perform cleanup here
            try:
                print("Closing writer...")
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                print(f"Error closing writer: {e}")
        finally:
            print("TX task finished")

    def transmit_message_to_daemon(self, message: dict):
        request_bytes = self._prepare_request(message)
        self._tx_queue.put_nowait(request_bytes)

    async def receive_data(self):
        while True:
            try:
                message = await self._read_next_message()
                print(f"Received message: {message}")
                if message:
                    if message["type"] == "SubscribeEventgroupReadyRequest":
                        # Multiple client service instances can be connected to the daemon
                        for client in self._client_service_instances.values():
                            client.subscribe_ready_request(message)

                    else:
                        self._rx_message_queue.put_nowait(message)
                else:
                    break
            except Exception as e:
                print(f"Error receiving data: {e}")
                break

        if self._tx_task:
            try:
                self._tx_task.cancel()
                await self._tx_task
            except asyncio.CancelledError:
                pass

    async def _read_next_message(self, timeout=None) -> dict:
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
                except asyncio.TimeoutError as e:
                    print("Failed to read header: Timeout")
                    raise e
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
                except asyncio.TimeoutError as e:
                    print("Failed to read message: Timeout")
                    raise e
                except Exception as e:
                    raise Exception(f"Failed to read message: {e}")

                message_buffer += data

                if len(message_buffer) == message_length:
                    return json.loads(message_buffer.decode("utf-8"))
        return None

    async def _get_offered_services(self) -> List[SdService]:
        request = {
            "type": "get_offered_services_req",
        }
        request_bytes = self._prepare_request(request)
        self._tx_queue.put_nowait(request_bytes)

        response = await self._rx_message_queue.get()

        if response["type"] != "get_offered_services_res":
            self._rx_message_queue.task_done()
            raise Exception(
                f"Invalid response from daemon. Expected get_offered_services_res and got {response['type']}"
            )

        services = [SdService.from_json(service) for service in response["services"]]
        self._rx_message_queue.task_done()
        return services

    async def _find_service(self, service: SdService):
        request = {
            "type": "find_service_req",
            "service": service.to_dict(),
        }
        request_bytes = self._prepare_request(request)
        self._tx_queue.put_nowait(request_bytes)

        response = await self._rx_message_queue.get()

        if response["type"] != "find_service_res":
            self._rx_message_queue.task_done()
            raise Exception(
                f"Invalid response from daemon. Expected find_service_res and got {response['type']}"
            )

        self._rx_message_queue.task_done()
        return response["service"]

    async def _offer_service(
        self,
        service: SdService,
        cyclic_offer_delay_ms: int,
        eventgroup_ids: List[int] = [],
    ):
        request = {
            "type": "offer_service_req",
            "service": service.to_json(),
            "cyclic_offer_delay_ms": cyclic_offer_delay_ms,
            "eventgroup_ids": eventgroup_ids,
        }
        request_bytes = self._prepare_request(request)
        self._tx_queue.put_nowait(request_bytes)

    async def _stop_offer_service(self, service: SdService):
        request = {
            "type": "stop_offer_service_req",
            "service": service.to_json(),
        }
        request_bytes = self._prepare_request(request)
        self._tx_queue.put_nowait(request_bytes)

    async def _get_subscribers(
        self, service: SdService, eventgroup_id: int
    ) -> List[EndpointType]:
        request = {
            "type": "get_eventgroup_subscriptions_req",
            "service": service.to_json(),
            "eventgroup_id": eventgroup_id,
        }
        request_bytes = self._prepare_request(request)
        self._tx_queue.put_nowait(request_bytes)

        response = await self._rx_message_queue.get()

        if response["type"] != "get_eventgroup_subscriptions_res":
            self._rx_message_queue.task_done()
            raise Exception(
                f"Invalid response from daemon. Expected get_subscribers_res and got {response['type']}"
            )

        subscriptions = []
        for subscription in response["subscriptions"]:
            subscriptions.append(
                (
                    ipaddress.IPv4Address(subscription["endpoint_ip"]),
                    subscription["endpoint_port"],
                )
            )

        self._rx_message_queue.task_done()
        return subscriptions

    def _subscribe_to_eventgroup(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        client_endpoint_ip: str,
        client_endpoint_port: int,
        protocol: TransportLayerProtocol,
        eventgroup_id: int,
        ttl_subscription: int,
    ):
        request = {
            "type": "subscribe_eventgroup_req",
            "service_id": service_id,
            "instance_id": instance_id,
            "major_version": major_version,
            "client_endpoint_ip": client_endpoint_ip,
            "client_endpoint_port": client_endpoint_port,
            "eventgroup_id": eventgroup_id,
            "ttl_subscription": ttl_subscription,
            "protocol": protocol.value,
        }
        request_bytes = self._prepare_request(request)
        self._tx_queue.put_nowait(request_bytes)

    def _unsubscribe_from_eventgroup(self, service: SdService, eventgroup_id: int):
        request = {
            "type": "stop_subscribe_eventgroup_req",
            "service": service.to_json(),
            "eventgroup_id": eventgroup_id,
        }
        request_bytes = self._prepare_request(request)
        self._tx_queue.put_nowait(request_bytes)
