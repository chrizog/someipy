import asyncio
import base64
import ipaddress
import json
import struct
from typing import Dict, List, TypedDict, cast

from someipy._internal.daemon_client_abcs import (
    ClientInstanceInterface,
    ServerInstanceInterface,
)
from someipy._internal.logging import get_logger
from someipy._internal.someip_sd_header import SdService
from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy._internal.uds_messages import (
    BaseMessage,
    InboundCallMethodRequest,
    InboundCallMethodResponse,
    FindServiceRequest,
    FindServiceResponse,
    OfferServiceRequest,
    OutboundCallMethodResponse,
    ReceivedEvent,
    StopOfferServiceRequest,
    create_uds_message,
)
from someipy.service import EventGroup, Method

_logger_name = "someipyd_client"


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

        self._server_service_instances: List[ServerInstanceInterface] = []
        self._client_service_instances: List[ClientInstanceInterface] = []

        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None

    def _prepare_request(self, message: dict):
        payload = json.dumps(message).encode("utf-8")
        return struct.pack("<I", len(payload)) + bytes(256 - 4) + payload

    async def _connected_to_daemon(self):
        pass

    async def _disconnected_from_daemon(self):
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                get_logger(_logger_name).error(f"Error closing writer: {e}")
            finally:
                self.writer = None

        if self._rx_task and not self._rx_task.done() and not self._rx_task.cancelled():
            try:
                self._rx_task.cancel()
                await self._rx_task
            except asyncio.CancelledError:
                pass
            finally:
                self._rx_task = None

        if self._tx_task and not self._tx_task.done() and not self._tx_task.cancelled():
            try:
                self._tx_task.cancel()
                await self._tx_task
            except asyncio.CancelledError:
                pass
            finally:
                self._tx_task = None

        self._clear_rx_queue()

    def _clear_rx_queue(self):
        if self._rx_message_queue is None:
            return
        while not self._rx_message_queue.empty():
            try:
                self._rx_message_queue.get_nowait()
                self._rx_message_queue.task_done()
            except asyncio.QueueEmpty:
                break

    async def _connect_to_daemon(self):
        num_retries = 3
        success = False

        while num_retries > 0:
            num_retries -= 1
            try:
                self._clear_rx_queue()
                self._rx_message_queue = asyncio.Queue()

                self.reader, self.writer = await asyncio.open_unix_connection(
                    self._socket_path
                )
                success = True
                break

            except Exception as e:
                get_logger(_logger_name).error(
                    f"Failed to connect to daemon: {e}. Retries left: {num_retries}"
                )
                await asyncio.sleep(1.0)

        if not success:
            raise Exception(f"Failed to connect to daemon after retries")
        else:
            self._rx_task = asyncio.create_task(self.receive_data_task(self.reader))
            self._tx_task = asyncio.create_task(self.transmit_data_task(self.writer))

    async def _wait_until_tx_queue_empty(self):
        while not self._tx_queue.empty():
            await asyncio.sleep(0.1)

    async def disconnect_from_daemon(self):
        await asyncio.wait_for(self._wait_until_tx_queue_empty(), 0.5)
        await self._disconnected_from_daemon()

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

                        self._tx_queue.task_done()

                    except ConnectionError as e:
                        get_logger(_logger_name).error(f"Connection error: {e}")
                        break

                except asyncio.TimeoutError:
                    # Periodic timeout for cancellation check
                    continue

        except asyncio.CancelledError:
            get_logger(_logger_name).debug("Daemon client TX task cancelled")
        finally:
            get_logger(_logger_name).debug("Daemon client TX task finished")

    def transmit_message_to_daemon(self, message: dict):
        get_logger(_logger_name).debug(f"Transmitting message: {message}")
        request_bytes = self._prepare_request(message)
        self._tx_queue.put_nowait(request_bytes)

    async def handle_single_method_call(
        self, method_request: InboundCallMethodRequest, method: Method
    ):

        payload_decoded = base64.b64decode(method_request["payload"])

        # check if the method handler is a coroutine function
        if asyncio.iscoroutinefunction(method.method_handler):
            # Call the method handler as a coroutine
            result = await method.method_handler(
                payload_decoded,
                (
                    method_request["src_endpoint_ip"],
                    method_request["src_endpoint_port"],
                ),
            )
        else:
            # Call the method handler as a regular function
            result = method.method_handler(
                payload_decoded,
                (
                    method_request["src_endpoint_ip"],
                    method_request["src_endpoint_port"],
                ),
            )

        encoded_result = base64.b64encode(result.payload).decode("utf-8")
        call_method_response = create_uds_message(
            InboundCallMethodResponse,
            service_id=method_request["service_id"],
            instance_id=method_request["instance_id"],
            method_id=method_request["method_id"],
            client_id=method_request["client_id"],
            session_id=method_request["session_id"],
            protocol_version=method_request["protocol_version"],
            interface_version=method_request["interface_version"],
            major_version=method_request["major_version"],
            minor_version=method_request["minor_version"],
            message_type=result.message_type.value,
            src_endpoint_ip=method_request["src_endpoint_ip"],
            src_endpoint_port=method_request["src_endpoint_port"],
            protocol=method_request["protocol"],
            payload=encoded_result,
            return_code=result.return_code.value,
        )

        self.transmit_message_to_daemon(call_method_response)

    async def _handle_message(self, message: BaseMessage):

        if message["type"] == InboundCallMethodRequest.__name__:

            get_logger(_logger_name).debug(f"Received CallMethodRequest: {message}")

            message = cast(InboundCallMethodRequest, message)

            # Find the right method and call the method handler
            service_id = message["service_id"]
            instance_id = message["instance_id"]
            major_version = message["major_version"]
            minor_version = message["minor_version"]
            method_id = message["method_id"]
            protocol = message["protocol"]

            for service_instance in self._server_service_instances:
                if (
                    service_instance.service.id == service_id
                    and service_instance.instance_id == instance_id
                    and service_instance.service.major_version == major_version
                ):
                    method = service_instance.service.methods.get(method_id, None)
                    if method:
                        get_logger(_logger_name).debug(
                            f"Calling method {method_id} on service {service_id}"
                        )
                        # Call the method handler, eventually call it in a separate task
                        # to avoid blocking the event loop

                        asyncio.create_task(
                            self.handle_single_method_call(message, method)
                        )

        elif message["type"] == OutboundCallMethodResponse.__name__:
            get_logger(_logger_name).debug(
                f"Received OutboundCallMethodResponse: {message}"
            )

            message = cast(OutboundCallMethodResponse, message)

            for service_instance in self._client_service_instances:
                if (
                    service_instance.service.id == message["service_id"]
                    and message["method_id"]
                    in [m for m in service_instance.service.methods.keys()]
                    and service_instance.endpoint[1] == message["dst_endpoint_port"]
                    and service_instance.endpoint[0] == message["dst_endpoint_ip"]
                ):
                    service_instance._method_call_data_received(message)

        elif message["type"] == ReceivedEvent.__name__:
            get_logger(_logger_name).debug(f"Received ReceivedEvent: {message}")
            for service_instance in self._client_service_instances:
                service_instance._event_data_received(cast(ReceivedEvent, message))

        else:
            self._rx_message_queue.put_nowait(message)

    async def receive_data_task(self, reader: asyncio.StreamReader):
        while True:
            try:
                message = await self._read_next_message(reader)
                get_logger(_logger_name).debug(f"Received message: {message}")
                await self._handle_message(message)
            except Exception as e:
                get_logger(_logger_name).error(f"Error processing message: {e}")
                break

    async def _read_next_message(
        self, reader: asyncio.StreamReader, timeout=None
    ) -> dict:
        wait_for_header = True
        header_buffer = b""
        message_buffer = b""
        message_length = 0

        while True:
            if wait_for_header:
                try:
                    if timeout is not None:
                        data = await asyncio.wait_for(
                            reader.read(256 - len(header_buffer)), timeout
                        )
                    else:
                        data = await reader.read(256 - len(header_buffer))
                    if not data:
                        get_logger(_logger_name).error("No data received")
                        break
                except asyncio.TimeoutError as e:
                    get_logger(_logger_name).error("Failed to read header: Timeout")
                    raise e
                except Exception as e:
                    raise Exception(f"Failed to read header: {e}")

                header_buffer += data

                if len(header_buffer) == 256:
                    try:
                        message_length = struct.unpack("<I", header_buffer[:4])[0]
                        message_buffer = b""
                        wait_for_header = False
                    except struct.error:
                        get_logger(_logger_name).error(
                            "Failed to unpack message length from header"
                        )
                        break
            else:
                try:
                    if timeout is not None:
                        data = await asyncio.wait_for(
                            reader.read(message_length - len(message_buffer)),
                            timeout,
                        )
                    else:
                        data = await reader.read(message_length - len(message_buffer))
                    if not data:
                        break
                except asyncio.TimeoutError as e:
                    get_logger(_logger_name).error("Failed to read message: Timeout")
                    raise e
                except Exception as e:
                    raise Exception(f"Failed to read message: {e}")

                message_buffer += data

                if len(message_buffer) == message_length:

                    wait_for_header = True
                    header_buffer = b""
                    message_length = 0

                    return json.loads(message_buffer.decode("utf-8"))
        return None

    async def _find_service(
        self, service_id: int, instance_id: int, major_version: int, minor_version: int
    ) -> SdService:

        request = create_uds_message(
            FindServiceRequest,
            service_id=service_id,
            instance_id=instance_id,
            major_version=major_version,
            minor_version=minor_version,
        )

        request_bytes = self._prepare_request(request)
        self._tx_queue.put_nowait(request_bytes)

        response = await self._rx_message_queue.get()

        if response["type"] != FindServiceResponse.__name__:
            self._rx_message_queue.task_done()
            raise Exception(
                f"Invalid response from daemon. Expected find_service_res and got {response['type']}"
            )

        if not response["success"]:
            self._rx_message_queue.task_done()
            return None

        service = SdService(
            service_id=response["service_id"],
            instance_id=response["instance_id"],
            major_version=response["major_version"],
            minor_version=response["minor_version"],
            ttl=0,
            endpoint=(
                ipaddress.IPv4Address(response["endpoint_ip"]),
                response["endpoint_port"],
            ),
            protocol=TransportLayerProtocol.UDP,
        )

        self._rx_message_queue.task_done()
        return service

    async def offer_service(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        minor_version: int,
        ttl: int,
        endpoint_ip: str,
        endpoint_port: int,
        eventgroups: List[EventGroup],
        methods: List[Method],
        cyclic_offer_delay_ms: int,
    ):
        request = create_uds_message(
            OfferServiceRequest,
            service_id=service_id,
            instance_id=instance_id,
            major_version=major_version,
            minor_version=minor_version,
            endpoint_ip=endpoint_ip,
            endpoint_port=endpoint_port,
            ttl=ttl,
            eventgroup_list=[eventgroup.to_json() for eventgroup in eventgroups],
            method_list=[method.to_json() for method in methods],
            cyclic_offer_delay_ms=cyclic_offer_delay_ms,
        )
        self.transmit_message_to_daemon(request)

    async def stop_offer_service(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        minor_version: int,
        ttl: int,
        endpoint_ip: str,
        endpoint_port: int,
        eventgroups: List[EventGroup],
        methods: List[Method],
        cyclic_offer_delay_ms: int,
    ):
        request = create_uds_message(
            StopOfferServiceRequest,
            service_id=service_id,
            instance_id=instance_id,
            major_version=major_version,
            minor_version=minor_version,
            endpoint_ip=endpoint_ip,
            endpoint_port=endpoint_port,
            ttl=ttl,
            eventgroup_list=[eventgroup.to_json() for eventgroup in eventgroups],
            method_list=[method.to_json() for method in methods],
            cyclic_offer_delay_ms=cyclic_offer_delay_ms,
        )
        self.transmit_message_to_daemon(request)
