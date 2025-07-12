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
from abc import ABC, abstractmethod, abstractproperty
from logging import Logger
from typing import Callable, Tuple, Any, Union
from someipy._internal.logging import get_logger
from someipy._internal.someip_message import SomeIpMessage
from someipy._internal.tcp_client_manager import (
    TcpClientManagerInterface,
    TcpClientProtocolInterface,
)
from someipy._internal.tcp_connection import TcpConnection
from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy._internal.utils import EndpointType
from someipy._internal.someip_data_processor import SomeipDataProcessor


class SomeipEndpoint(ABC):
    """
    A class representing an endpoint (UDP or TCP) which fires a callback when a SomeIpMessage is received.
    It can also send messages to a specific endpoint or broadcast to all connected endpoints (for UDP multicast or to all connected
    TCP clients).
    """

    @abstractmethod
    def set_someip_callback(
        self,
        callback_func: Callable[
            [SomeIpMessage, Tuple[str, int], Tuple[str, int], TransportLayerProtocol],
            None,
        ],
    ) -> None:
        pass

    @abstractmethod
    def sendto(self, data: bytes, addr: EndpointType) -> None:
        pass

    @abstractmethod
    def sendtoall(self, data: bytes) -> None:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass

    @abstractmethod
    def protocol(self) -> TransportLayerProtocol:
        pass

    @abstractmethod
    def src_ip(self) -> str:
        pass

    @abstractmethod
    def src_port(self) -> int:
        pass

    @abstractmethod
    def dst_ip(self) -> str:
        pass

    @abstractmethod
    def dst_port(self) -> int:
        pass


class UDPSomeipEndpoint(SomeipEndpoint, asyncio.DatagramProtocol):
    def __init__(self, ip: str, port: int):
        self._callback: Callable[
            [SomeIpMessage, Tuple[str, int], Tuple[str, int], TransportLayerProtocol],
            None,
        ] = None
        self._transport = None
        self._processor = SomeipDataProcessor()
        self._protocol = TransportLayerProtocol.UDP

        self._ip = ip
        self._port = port

    def set_someip_callback(
        self,
        callback_func: Callable[
            [SomeIpMessage, Tuple[str, int], Tuple[str, int], TransportLayerProtocol],
            None,
        ],
    ) -> None:
        self._callback = callback_func

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self._transport = transport

    def connection_lost(self, exc: Exception) -> None:
        pass

    def datagram_received(self, data: bytes, addr: Tuple[Union[str, Any, int]]) -> None:
        result = self._processor.process_data(data)
        if result and self._callback is not None:
            self._callback(
                self._processor.someip_message,
                addr,
                (self._ip, self._port),
                self._protocol,
            )

    def sendto(self, data: bytes, addr: EndpointType) -> None:
        if self._transport is not None:
            self._transport.sendto(data, (str(addr[0]), addr[1]))

    def sendtoall(self, data: bytes) -> None:
        # TODO: Implement for multicast support
        raise NotImplementedError("No implementation for UDP yet")

    def shutdown(self) -> None:
        if self._transport is not None:
            self._transport.close()

    def protocol(self) -> TransportLayerProtocol:
        return self._protocol

    def src_ip(self) -> str:
        return self._ip

    def src_port(self) -> int:
        return self._port

    def dst_ip(self) -> str:
        return 0

    def dst_port(self) -> int:
        return 0


class TCPSomeipEndpoint(SomeipEndpoint):
    def __init__(self, server, manager, ip: str, port: int):
        self._server: asyncio.Server = server
        self._manager: TcpClientManagerInterface = manager
        self._protocol: TransportLayerProtocol = TransportLayerProtocol.TCP
        self._ip = ip
        self._port = port

    def set_someip_callback(
        self,
        callback_func: Callable[
            [SomeIpMessage, Tuple[str, int], Tuple[str, int], TransportLayerProtocol],
            None,
        ],
    ) -> None:
        self._manager.register_callback(callback_func)

    def sendto(self, data: bytes, addr: EndpointType) -> None:
        if self._manager is None:
            return
        client: TcpClientProtocolInterface = self._manager.get_client(addr[0], addr[1])
        if client is not None:
            client.write(data)

    def sendtoall(self, data: bytes) -> None:
        if self._manager is None:
            return
        for c in self._manager.get_all_clients():
            c.write(data)

    def shutdown(self) -> None:
        if self._manager is None:
            return
        self._server.close()

    def protocol(self) -> TransportLayerProtocol:
        return self._protocol

    def src_ip(self) -> str:
        return self._ip

    def src_port(self) -> int:
        return self._port

    def dst_ip(self) -> str:
        return 0

    def dst_port(self) -> int:
        return 0


class TCPClientSomeipEndpoint(SomeipEndpoint):
    def __init__(
        self,
        dst_ip: str,
        dst_port: str,
        src_ip: str,
        src_port: str,
        logger: Logger = None,
    ):
        self._tcp_connection: TcpConnection = None
        self._protocol: TransportLayerProtocol = TransportLayerProtocol.TCP
        self._dst_ip = dst_ip
        self._dst_port = dst_port
        self._src_ip = src_ip
        self._src_port = src_port
        self._logger = logger

        self._callback: Callable[
            [SomeIpMessage, Tuple[str, int], Tuple[str, int], TransportLayerProtocol],
            None,
        ] = None

        self._connect_and_receive_task: asyncio.Task = asyncio.create_task(
            self._connect_and_receive()
        )

    def _log(self, message: str) -> None:
        if self._logger:
            self._logger.debug(message)

    def is_connected(self) -> bool:
        return self._tcp_connection is not None and self._tcp_connection.is_open()

    async def _connect_and_receive(self) -> None:
        try:
            while True:
                self._log(f"Trying to connect to ({self._dst_ip}, {self._dst_port})")

                self._tcp_connection = TcpConnection(self._dst_ip, self._dst_port)

                try:
                    await self._tcp_connection.connect(self._src_ip, self._src_port)
                except OSError:
                    self._log(
                        f"Connection refused while connecting to ({self._dst_ip}, {self._dst_port}). Try to reconnect in 1 second"
                    )
                    # Wait a second before trying to connect again
                    await asyncio.sleep(1.0)
                    continue

                self._log(f"Start reading on port {self._src_port}")

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
                            self._callback(
                                someip_processor.someip_message,
                                (self._dst_ip, self._dst_port),
                                (self._src_ip, self._src_port),
                                self._protocol,
                            )

                    except asyncio.TimeoutError:
                        self._log(
                            f"Timeout reading from TCP connection ({self._src_ip}, {self._src_port})"
                        )
                    except Exception as e:
                        self._log(
                            f"Error while reading from TCP connection ({self._src_ip}, {self._src_port}): {e}"
                        )

                await self._tcp_connection.close()

        except asyncio.CancelledError:
            if self._tcp_connection.is_open():
                await self._tcp_connection.close()
            self._log("TCP task is cancelled. Raise again.")
            raise

    def set_someip_callback(
        self,
        callback_func: Callable[
            [SomeIpMessage, Tuple[str, int], Tuple[str, int], TransportLayerProtocol],
            None,
        ],
    ) -> None:
        self._callback = callback_func

    def sendto(self, data: bytes, addr: EndpointType) -> None:
        if self._tcp_connection is not None and self._tcp_connection.is_open():
            self._tcp_connection.writer.write(data)

    def sendtoall(self, data: bytes) -> None:
        raise NotImplementedError("No implementation for TCP client endpoint.")

    def shutdown(self) -> None:
        try:
            if self._connect_and_receive_task:
                self._connect_and_receive_task.cancel()
        except asyncio.CancelledError:
            self._log("Shutdown task was cancelled.")

    def protocol(self) -> TransportLayerProtocol:
        return self._protocol

    def src_ip(self) -> str:
        return self._src_ip

    def src_port(self) -> int:
        return self._src_port

    def dst_ip(self) -> str:
        return self._dst_ip

    def dst_port(self) -> int:
        return self._dst_port
