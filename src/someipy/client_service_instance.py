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
from typing import Dict, Tuple, Callable

from someipy import Service
from someipy._internal.daemon_client_abcs import ClientInstanceInterface
from someipy._internal.method_result import MethodResult
from someipy._internal.someip_data_processor import SomeipDataProcessor
from someipy._internal.someip_sd_header import (
    SdService,
    TransportLayerProtocol,
)
from someipy._internal.someip_header import (
    SomeIpHeader,
)
from someipy._internal.someipy_daemon_client import SomeIpDaemonClient
from someipy._internal.store_with_timeout import StoreWithTimeout
from someipy._internal.uds_messages import (
    SubscribeEventgroupReadyRequest,
    SubscribeEventgroupReadyResponse,
    create_uds_message,
)
from someipy._internal.utils import (
    create_udp_socket,
    EndpointType,
)
from someipy._internal.logging import get_logger
from someipy._internal.message_types import MessageType
from someipy._internal.return_codes import ReturnCode
from someipy._internal.someip_endpoint import (
    SomeipEndpoint,
    UDPSomeipEndpoint,
    SomeIpMessage,
)
from someipy._internal.tcp_connection import TcpConnection

_logger_name = "client_service_instance"


class ClientServiceInstance(ClientInstanceInterface):

    def __init__(
        self,
        service: Service,
        instance_id: int,
        endpoint: EndpointType,
        protocol: TransportLayerProtocol,
        someip_endpoint: SomeipEndpoint,
        client_id: int = 0,
        daemon: SomeIpDaemonClient = None,
    ):
        self._service: Service = service
        self._instance_id: int = instance_id
        self._endpoint: EndpointType = endpoint
        self._protocol: TransportLayerProtocol = protocol
        self._someip_endpoint: SomeipEndpoint = someip_endpoint

        self._eventgroups_to_subscribe = set()

        self._event_callback: Callable[[SomeIpMessage], None] = None

        self._tcp_connection: TcpConnection = None

        self._tcp_connect_lock = asyncio.Lock()
        self._tcp_task = None
        self._tcp_connection_established_event = asyncio.Event()
        self._shutdown_requested = False

        self._offered_services = StoreWithTimeout()

        self._subscription_active = False
        self._method_call_futures: Dict[int, asyncio.Future] = {}
        self._client_id = client_id

        self._daemon = daemon

        self._session_id: int = 0  # Starts from 1 to 0xFFFF

    def register_callback(self, callback: Callable[[SomeIpMessage], None]) -> None:
        """
        Register a callback function to be called when a SOME/IP event is received.

        Args:
            callback (Callable[[SomeIpMessage], None]): The callback function to be registered.
                This function should take a SomeIpMessage object as its only argument and return None.

        Returns:
            None
        """
        self._event_callback = callback

    async def service_found(self) -> bool:
        """
        Returns whether the service instance represented by the ClientServiceInstance has been offered by a server and was found.
        """
        found, _ = await self._service_found()
        return found

    async def _service_found(self) -> Tuple[bool, SdService]:
        if self._daemon:
            services = await self._daemon._get_offered_services()
            for offered_service in services:

                if (
                    self._instance_id != 0xFFFF
                    and self._instance_id != offered_service.instance_id
                ):
                    # 0xFFFF allows to handle any instance ID
                    continue

                if self._service.major_version != offered_service.major_version:
                    continue

                if (
                    self._service.minor_version != 0xFFFFFFFF
                    and self._service.minor_version != offered_service.minor_version
                ):
                    # 0xFFFFFFFF allows to handle any minor version
                    continue

                # If this point is reached, the service has been found
                return True, offered_service

        return False, None

    async def find_service(self, timeout: float = 10.0) -> bool:
        """
        Finds the service instDaemonClientSubjectance represented by the ClientServiceInstance.

        Args:
            timeout (float, optional): The timeout for the service to be found. Defaults to 10.0 seconds.

        Returns:
            bool: True if the service is found.

        Raises:
            RuntimeError: If the service is not found within the given timeout.
        """
        service_found, found_service = await self._service_found()
        if not service_found:
            error_msg = f"Service 0x{self._service.id:04X} with instance 0x{self._instance_id:04X} not found."
            get_logger(_logger_name).error(error_msg)
            raise RuntimeError(error_msg)

    async def call_method(self, method_id: int, payload: bytes) -> MethodResult:
        """
        Calls a method on the service instance represented by the ClientServiceInstance.

        Args:
            method_id (int): The ID of the method to call.
            payload (bytes): The payload to send with the method call.

        Returns:
            MethodResult: The result of the method call which can contain an error or a successful result including the response payload.

        Raises:
            RuntimeError: If the TCP connection to the server cannot be established or if the server service has not been found yet.
            asyncio.TimeoutError: If the method call times out, i.e. the server does not send back a response within one second.
        """

        get_logger(_logger_name).debug(f"Trying to call method 0x{method_id:04X}")

        service_found, found_service = await self._service_found()
        if not service_found:
            error_msg = f"Method 0x{method_id:04x} called, but service 0x{self._service.id:04X} with instance 0x{self._instance_id:04X} not found yet."

            get_logger(_logger_name).warning(error_msg)
            raise RuntimeError(error_msg)

        # Session ID is a 16-bit value and should be incremented for each method call starting from 1
        self._session_id = (self._session_id + 1) % 0xFFFF
        session_id = self._session_id

        header = SomeIpHeader(
            service_id=self._service.id,
            method_id=method_id,
            client_id=self._client_id,
            session_id=session_id,
            protocol_version=0x01,
            interface_version=self._service.major_version,
            message_type=MessageType.REQUEST.value,
            return_code=0x00,
            length=len(payload) + 8,
        )
        someip_message = SomeIpMessage(header, payload)

        call_future = asyncio.get_running_loop().create_future()
        self._method_call_futures[session_id] = call_future

        dst_address = found_service.endpoint[0]
        dst_port = found_service.endpoint[1]

        if self._protocol == TransportLayerProtocol.TCP:
            # In case of TCP, first try to connect to the TCP server
            # [PRS_SOMEIP_00708] The TCP connection shall be opened by the client, when the
            # first method call shall be transported or the client tries to receive the first notifications
            if self._tcp_task is None:
                get_logger(_logger_name).debug(
                    f"Create new TCP task for client of 0x{self._instance_id:04X}, 0x{self._service.id:04X}"
                )
                self._tcp_task = asyncio.create_task(
                    self.setup_tcp_connection(
                        str(self._endpoint[0]),
                        self._endpoint[1],
                        str(dst_address),
                        dst_port,
                    )
                )

            try:
                # Wait for two seconds until the connection is established, otherwise return an error
                await asyncio.wait_for(self._tcp_connection_established_event.wait(), 2)
            except asyncio.TimeoutError:
                error_msg = (
                    f"Cannot establish TCP connection to {dst_address}:{dst_port}."
                )
                get_logger(_logger_name).error(error_msg)
                raise RuntimeError(error_msg)

            if self._tcp_connection.is_open():
                self._tcp_connection.writer.write(someip_message.serialize())
            else:
                error_msg = f"TCP connection to {dst_address}:{dst_port} is not opened."
                get_logger(_logger_name).error(error_msg)
                raise RuntimeError(error_msg)

        else:
            # In case of UDP, just send out the datagram and wait for the response
            self._someip_endpoint.sendto(
                someip_message.serialize(),
                found_service.endpoint,
            )

        # After sending the method call wait for maximum 10 seconds
        try:
            await asyncio.wait_for(call_future, 10.0)
        except asyncio.TimeoutError:

            # Remove the call_future from self._method_call_futures
            del self._method_call_futures[session_id]

            error_msg = (
                f"Waiting on response for method call 0x{method_id:04X} timed out."
            )
            get_logger(_logger_name).error(error_msg)
            raise RuntimeError(error_msg)

        method_result = call_future.result()
        del self._method_call_futures[session_id]
        return method_result

    def someip_message_received(
        self, someip_message: SomeIpMessage, addr: Tuple[str, int]
    ) -> None:

        if (
            someip_message.header.client_id == 0x00
            and someip_message.header.message_type == MessageType.NOTIFICATION.value
            and someip_message.header.return_code == ReturnCode.E_OK.value
        ):
            if self._event_callback is not None:
                self._event_callback(someip_message)
                return

        # Handling a response message
        if (
            someip_message.header.message_type == MessageType.RESPONSE.value
            or someip_message.header.message_type == MessageType.ERROR.value
        ):
            if someip_message.header.session_id not in self._method_call_futures.keys():
                return
            if someip_message.header.client_id != self._client_id:
                return

            call_future = None
            try:
                call_future = self._method_call_futures[
                    someip_message.header.session_id
                ]
            except KeyError:
                get_logger(_logger_name).error(
                    f"Received response for unknown session ID {someip_message.header.session_id}"
                )
                return

            if call_future is not None:
                result = MethodResult()
                result.message_type = MessageType(someip_message.header.message_type)
                result.return_code = ReturnCode(someip_message.header.return_code)
                result.payload = someip_message.payload
                call_future.set_result(result)

    def subscribe_eventgroup(self, eventgroup_id: int, ttl_subscription_seconds: int):
        eventgroups = [x[0] for x in self._service.eventgroups]
        if eventgroup_id not in eventgroups:
            self._eventgroups_to_subscribe.add(
                (eventgroup_id, ttl_subscription_seconds)
            )

        if self._daemon:
            self._daemon._subscribe_to_eventgroup(
                self._service.id,
                self._instance_id,
                self._service.major_version,
                str(self._endpoint[0]),
                self._endpoint[1],
                self._protocol,
                eventgroup_id,
                ttl_subscription_seconds,
            )

    def unsubscribe_eventgroup(self, eventgroup_id: int):
        if self._daemon:
            sd_service = SdService(
                service_id=self._service.id,
                instance_id=self._instance_id,
                major_version=self._service.major_version,
                minor_version=self._service.minor_version,
                ttl=self._ttl,
                endpoint=self._endpoint,
                protocol=self._protocol,
            )

            self._daemon._unsubscribe_from_eventgroup(sd_service, eventgroup_id)

    def subscribe_ready_request(self, message: SubscribeEventgroupReadyRequest):
        """
        1. Check if service id, instance id, major version, protocol and eventgroup id match
        2. If UDP is requested, then there is nothing to do -> send back a subscribe_ready response with success
        3. If TCP is requuested, first check if the TCP connection is already established
        4. If yes, send back a subscribe_ready response with success
        5. If not, then open the TCP connection and send back a subscribe_ready response with success afterwards
        6. If the TCP connection cannot be established, send back a subscribe_ready response with error
        """
        print(f"Received subscribe_ready request in client: {message}")
        service_id = message["service_id"]
        instance_id = message["instance_id"]
        major_version = message["major_version"]
        protocol = TransportLayerProtocol(message["protocol"])
        eventgroup_id = message["eventgroup_id"]

        eventgroup_ids_to_subscribe = [x[0] for x in self._eventgroups_to_subscribe]

        if (
            service_id != self._service.id
            or instance_id != self._instance_id
            or major_version != self._service.major_version
            or protocol != self._protocol
            or eventgroup_id not in eventgroup_ids_to_subscribe
        ):
            print("No match found")
            return

        if protocol == TransportLayerProtocol.UDP:
            print("Send back response")

            response: SubscribeEventgroupReadyResponse = create_uds_message(
                SubscribeEventgroupReadyResponse,
                success=True,
                service_id=service_id,
                instance_id=instance_id,
                major_version=major_version,
                client_endpoint_ip=str(self._endpoint[0]),
                client_endpoint_port=self._endpoint[1],
                eventgroup_id=eventgroup_id,
                ttl_subscription=message["ttl_subscription"],
                protocol=protocol.value,
                service_endpoint_ip=message["service_endpoint_ip"],
            )
            self._daemon.transmit_message_to_daemon(response)

        elif protocol == TransportLayerProtocol.TCP:
            if (
                self._tcp_connection is not None
                and self._tcp_connection.is_open()
                and self._tcp_connection.remote_ip == message["service_endpoint_ip"]
                and self._tcp_connection.remote_port == message["service_endpoint_port"]
            ):

                print("TCP connection already established")
                response: SubscribeEventgroupReadyResponse = create_uds_message(
                    SubscribeEventgroupReadyResponse,
                    success=True,
                    service_id=service_id,
                    instance_id=instance_id,
                    major_version=major_version,
                    client_endpoint_ip=str(self._endpoint[0]),
                    client_endpoint_port=self._endpoint[1],
                    eventgroup_id=eventgroup_id,
                    ttl_subscription=message["ttl_subscription"],
                    protocol=protocol.value,
                    service_endpoint_ip=message["service_endpoint_ip"],
                )
                self._daemon.transmit_message_to_daemon(response)

            else:
                if self._tcp_connection is None or not self._tcp_connection.is_open():
                    print("TCP connection not established yet")
                    # Open the TCP connection
                    asyncio.create_task(
                        self.setup_tcp_connection_and_respond(
                            str(self._endpoint[0]),
                            self._endpoint[1],
                            str(message["service_endpoint_ip"]),
                            message["service_endpoint_port"],
                            message,
                        )
                    )

    async def setup_tcp_connection_and_respond(
        self,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
        request: SubscribeEventgroupReadyRequest,
    ):
        """
        Setup a TCP connection to the server and respond to the subscribe_ready request.
        """

        def send_response(success: bool):
            response: SubscribeEventgroupReadyResponse = create_uds_message(
                SubscribeEventgroupReadyResponse,
                success=success,
                service_id=self._service.id,
                instance_id=self._instance_id,
                major_version=self._service.major_version,
                client_endpoint_ip=src_ip,
                client_endpoint_port=src_port,
                eventgroup_id=request["eventgroup_id"],
                ttl_subscription=request["ttl_subscription"],
                protocol=self._protocol.value,
                service_endpoint_ip=dst_ip,
            )
            self._daemon.transmit_message_to_daemon(response)

        if self._tcp_task is None:
            get_logger(_logger_name).debug(
                f"Create new TCP task for client of 0x{self._instance_id:04X}, 0x{self._service.id:04X}"
            )
            self._tcp_task = asyncio.create_task(
                self.setup_tcp_connection(
                    src_ip,
                    src_port,
                    dst_ip,
                    dst_port,
                )
            )

            try:
                # Wait for two seconds until the connection is established, otherwise return an error
                await asyncio.wait_for(self._tcp_connection_established_event.wait(), 2)
            except asyncio.TimeoutError:
                error_msg = f"Cannot establish TCP connection to {dst_ip}:{dst_port}."
                get_logger(_logger_name).error(error_msg)
                send_response(False)
                return

            if self._tcp_connection.is_open():
                send_response(True)
                return

            else:
                error_msg = f"TCP connection to {dst_ip}:{dst_port} is not opened."
                get_logger(_logger_name).error(error_msg)
                send_response(False)
                return

    async def setup_tcp_connection(
        self, src_ip: str, src_port: int, dst_ip: str, dst_port: int
    ):
        try:
            while True:

                get_logger(_logger_name).debug(
                    f"Trying to open TCP connection to ({dst_ip}, {dst_port})"
                )
                self._tcp_connection = TcpConnection(dst_ip, dst_port)

                # Reset the event before the first await call
                self._tcp_connection_established_event.clear()
                try:
                    await self._tcp_connection.connect(src_ip, src_port)
                except OSError:
                    get_logger(_logger_name).debug(
                        f"Connection refused to ({dst_ip}, {dst_port}). Try to reconnect in 1 second"
                    )
                    # Wait a second before trying to connect again
                    await asyncio.sleep(1.0)
                    continue

                # Notify other tasks waiting on the event, so the other task could send a method call
                if self._tcp_connection.is_open():
                    self._tcp_connection_established_event.set()

                get_logger(_logger_name).debug(f"Start reading on port {src_port}")

                someip_processor = SomeipDataProcessor()

                while self._tcp_connection.is_open():
                    try:
                        new_data = await asyncio.wait_for(
                            self._tcp_connection.reader.read(
                                someip_processor.expected_bytes
                            ),
                            3.0,
                        )

                        if someip_processor.process_data(new_data):
                            self.someip_message_received(
                                someip_processor.someip_message, (dst_ip, dst_port)
                            )

                    except asyncio.TimeoutError:
                        get_logger(_logger_name).debug(
                            f"Timeout reading from TCP connection ({src_ip}, {src_port})"
                        )

                # Clear the event to avoid that a method call would be sent
                self._tcp_connection_established_event.clear()
                await self._tcp_connection.close()

        except asyncio.CancelledError:
            if self._tcp_connection.is_open():
                await self._tcp_connection.close()
            get_logger(_logger_name).debug("TCP task is cancelled. Raise again.")
            raise

    async def close(self):
        self._shutdown_requested = True
        if self._tcp_task is not None:
            self._tcp_task.cancel()
            try:
                await self._tcp_task
            except asyncio.CancelledError:
                get_logger(_logger_name).debug("TCP task is cancelled.")

        if id(self) in self._daemon._client_service_instances:
            del self._daemon._client_service_instances[id(self)]


async def construct_client_service_instance(
    daemon: SomeIpDaemonClient,
    service: Service,
    instance_id: int,
    endpoint: EndpointType,
    protocol=TransportLayerProtocol.UDP,
    client_id: int = 0,
) -> ClientServiceInstance:
    """
    Asynchronously constructs a ClientServerInstance. Based on the given transport protocol, proper endpoints are setup before constructing the actual ServerServiceInstance.

    Args:
        service (Service): The service associated with the instance.
        instance_id (int): The ID of the instance.
        endpoint (EndpointType): The endpoint of the client instance containing IP address and port.
        ttl (int, optional): The time-to-live for the instance used for service discovery subscribe entries. A value of 0 means that subscriptions are valid for infinite time.
        protocol (TransportLayerProtocol, optional): The transport layer protocol for the instance. Defaults to TransportLayerProtocol.UDP.

    Returns:
        ClientServerInstance: The constructed ClientServerInstance.

    Raises:
        None
    """

    udp_endpoint = None

    if protocol == TransportLayerProtocol.UDP:
        loop = asyncio.get_running_loop()
        rcv_socket = create_udp_socket(str(endpoint[0]), endpoint[1])

        _, udp_endpoint = await loop.create_datagram_endpoint(
            lambda: UDPSomeipEndpoint(), sock=rcv_socket
        )

    client_instance = ClientServiceInstance(
        service,
        instance_id,
        endpoint,
        protocol,
        udp_endpoint,
        client_id,
        daemon,
    )

    daemon._client_service_instances[id(client_instance)] = client_instance

    if udp_endpoint:
        udp_endpoint.set_someip_callback(client_instance.someip_message_received)

    return client_instance
