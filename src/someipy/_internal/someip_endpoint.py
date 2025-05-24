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
from typing import Callable, Tuple, Any, Union
from someipy._internal.someip_message import SomeIpMessage
from someipy._internal.tcp_client_manager import (
    TcpClientManagerInterface,
    TcpClientProtocolInterface,
)
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
    def ip(self) -> str:
        pass

    @abstractmethod
    def port(self) -> int:
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

    def ip(self) -> str:
        return self._ip

    def port(self) -> int:
        return self._port


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

    def ip(self) -> str:
        return self._ip

    def port(self) -> int:
        return self._port
