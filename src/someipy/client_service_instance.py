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
import base64
from dataclasses import dataclass
from typing import Dict, Tuple, Callable

from someipy import Service
from someipy._internal.daemon_client_abcs import ClientInstanceInterface
from someipy._internal.method_result import MethodResult
from someipy._internal.someip_sd_header import SdService
from someipy._internal.someipy_daemon_client import SomeIpDaemonClient
from someipy._internal.uds_messages import (
    OutboundCallMethodRequest,
    OutboundCallMethodResponse,
    ReceivedEvent,
    StopSubscribeEventGroupRequest,
    SubscribeEventGroupRequest,
    create_uds_message,
)

from someipy._internal.logging import get_logger
from someipy._internal.message_types import MessageType
from someipy._internal.return_codes import ReturnCode
from someipy._internal.someip_endpoint import (
    SomeIpMessage,
)
from someipy.service import EventGroup

_logger_name = "client_service_instance"


@dataclass
class MethodCall:
    service_id: int
    method_id: int
    client_id: int
    session_id: int

    def __hash__(self):
        return hash(
            (
                self.service_id,
                self.method_id,
                self.client_id,
                self.session_id,
            )
        )


class ClientServiceInstance(ClientInstanceInterface):

    def __init__(
        self,
        daemon: SomeIpDaemonClient,
        service: Service,
        instance_id: int,
        endpoint_ip: str,
        endpoint_port: int,
        client_id: int = 0,
    ):
        self._daemon: SomeIpDaemonClient = daemon
        self._service: Service = service
        self._instance_id: int = instance_id
        self._endpoint_ip: str = endpoint_ip
        self._endpoint_port: int = endpoint_port
        self._client_id: int = client_id

        self._eventgroups_to_subscribe = set()
        self._event_callback: Callable[[int, bytes], None] = None

        self._method_call_futures: Dict[MethodCall, asyncio.Future] = {}

        self._session_id: int = 0  # Starts from 1 to 0xFFFF

        self._daemon._client_service_instances.append(self)

    @property
    def service(self) -> Service:
        return self._service

    @property
    def instance_id(self) -> int:
        return self._instance_id

    @property
    def endpoint(self) -> Tuple[str, int]:
        return (self._endpoint_ip, self._endpoint_port)

    def register_callback(self, callback: Callable[[int, bytes], None]) -> None:
        """
        Register a callback function to be called when a SOME/IP event is received.

        Args:
            callback (Callable[[SomeIpMessage], None]): The callback function to be registered.
                This function should take a SomeIpMessage object as its only argument and return None.

        Returns:
            None
        """
        self._event_callback = callback

    def _event_data_received(self, message: ReceivedEvent) -> None:
        if message["service_id"] != self._service.id:
            return

        all_events = [
            e for group in self._service.eventgroups.values() for e in group.events
        ]
        all_event_ids = [e.id for e in all_events]

        if message["event_id"] not in all_event_ids:
            return

        if self._event_callback is not None:
            decoded_payload = base64.b64decode(message["payload"])
            self._event_callback(message["event_id"], decoded_payload)

    def _method_call_data_received(self, message: OutboundCallMethodResponse) -> None:

        method_call_key = MethodCall(
            service_id=message["service_id"],
            method_id=message["method_id"],
            client_id=message["client_id"],
            session_id=message["session_id"],
        )

        if method_call_key not in self._method_call_futures.keys():
            return

        if message["client_id"] != self._client_id:
            return

        call_future = self._method_call_futures[method_call_key]

        if call_future is not None:
            decoded_payload = base64.b64decode(message["payload"])
            result = MethodResult()
            result.message_type = MessageType.RESPONSE
            result.return_code = ReturnCode(message["return_code"])
            result.payload = decoded_payload
            call_future.set_result(result)

    async def call_method(self, method_id: int, payload: bytes) -> MethodResult:
        get_logger(_logger_name).debug(f"Trying to call method 0x{method_id:04X}")

        service: SdService = await self._daemon._find_service(
            self._service.id,
            self._instance_id,
            self._service.major_version,
            self._service.minor_version,
        )

        if service is None:
            error_msg = f"Method 0x{method_id:04x} called, but service 0x{self._service.id:04X} with instance 0x{self._instance_id:04X} not found yet."
            get_logger(_logger_name).warning(error_msg)
            raise RuntimeError(error_msg)

        # Session ID is a 16-bit value and should be incremented for each method call starting from 1
        self._session_id = (self._session_id + 1) % 0xFFFF
        session_id = self._session_id

        # Find method in self._service
        method = self._service.methods.get(method_id, None)
        protocol_to_use = method.protocol.value

        # base64 encoded payload
        payload_encoded = base64.b64encode(payload).decode("utf-8")

        method_request = create_uds_message(
            OutboundCallMethodRequest,
            service_id=service.service_id,
            instance_id=service.instance_id,
            method_id=method_id,
            client_id=self._client_id,
            session_id=session_id,
            protocol_version=0x01,
            major_version=service.major_version,
            minor_version=service.minor_version,
            dst_endpoint_ip=str(service.endpoint[0]),
            dst_endpoint_port=service.endpoint[1],
            src_endpoint_ip=self._endpoint_ip,
            src_endpoint_port=self._endpoint_port,
            protocol=protocol_to_use,
            payload=payload_encoded,
        )

        method_call_key = MethodCall(
            service_id=service.service_id,
            method_id=method_id,
            client_id=self._client_id,
            session_id=session_id,
        )

        future = asyncio.Future()
        self._method_call_futures[method_call_key] = future

        self._daemon.transmit_message_to_daemon(method_request)

        # After sending the method call wait for maximum 10 seconds
        try:
            await asyncio.wait_for(future, 10.0)
        except asyncio.TimeoutError:

            # Remove the call_future from self._method_call_futures
            del self._method_call_futures[method_call_key]

            get_logger(_logger_name).error(
                f"Waiting on response for method call 0x{method_id:04X} timed out."
            )
            raise

        method_result = future.result()
        del self._method_call_futures[method_call_key]
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

            method_call_key = MethodCall(
                service_id=someip_message.header.service_id,
                method_id=someip_message.header.method_id,
                client_id=someip_message.header.client_id,
                session_id=someip_message.header.session_id,
            )

            if method_call_key not in self._method_call_futures.keys():
                return

            if someip_message.header.client_id != self._client_id:
                return

            call_future = self._method_call_futures[method_call_key]

            if call_future is not None:
                result = MethodResult()
                result.message_type = MessageType(someip_message.header.message_type)
                result.return_code = ReturnCode(someip_message.header.return_code)
                result.payload = someip_message.payload
                call_future.set_result(result)

    def subscribe_eventgroup(
        self, eventgroup: EventGroup, ttl_subscription_seconds: int
    ):
        method_request = create_uds_message(
            SubscribeEventGroupRequest,
            service_id=self._service.id,
            instance_id=self.instance_id,
            major_version=self._service.major_version,
            eventgroup=eventgroup.to_json(),
            ttl_subscription=ttl_subscription_seconds,
            client_endpoint_ip=self._endpoint_ip,
            client_endpoint_port=self._endpoint_port,
            udp=eventgroup.has_udp,
            tcp=eventgroup.has_tcp,
        )

        self._daemon.transmit_message_to_daemon(method_request)

    def unsubscribe_eventgroup(self, eventgroup_id: int):
        method_request = create_uds_message(
            StopSubscribeEventGroupRequest,
            service_id=self._service.id,
            instance_id=self.instance_id,
            major_version=self._service.major_version,
            eventgroup_id=eventgroup_id,
            client_endpoint_ip=self._endpoint_ip,
            client_endpoint_port=self._endpoint_port,
        )

        self._daemon.transmit_message_to_daemon(method_request)

    async def is_available(self) -> bool:
        service = await self._daemon._find_service(
            self._service.id,
            self._instance_id,
            self._service.major_version,
            self._service.minor_version,
        )
        if service is None:
            return False
        return True
