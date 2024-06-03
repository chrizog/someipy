import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Tuple, Any, Union
from someipy._internal.someip_message import SomeIpMessage
from someipy._internal.tcp_client_manager import (
    TcpClientManagerInterface,
    TcpClientProtocolInterface,
)
from someipy._internal.utils import EndpointType
from someipy._internal.someip_data_processor import SomeipDataProcessor


class SomeipEndpoint(ABC):
    @abstractmethod
    def set_someip_callback(
        self, callback_func: Callable[[SomeIpMessage, Tuple[str, int]], None]
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


class UDPSomeipEndpoint(SomeipEndpoint, asyncio.DatagramProtocol):
    def __init__(self):
        self._callback: Callable[[SomeIpMessage, Tuple[str, int]], None] = None
        self._transport = None
        self._processor = SomeipDataProcessor(datagram_mode=True)

    def set_someip_callback(
        self, callback_func: Callable[[SomeIpMessage, Tuple[str, int]], None]
    ) -> None:
        self._callback = callback_func

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self._transport = transport

    def connection_lost(self, exc: Exception) -> None:
        pass

    def datagram_received(self, data: bytes, addr: Tuple[Union[str, Any, int]]) -> None:
        result = self._processor.process_data(data)
        if result and self._callback is not None:
            self._callback(self._processor.someip_message, addr)

    def sendto(self, data: bytes, addr: EndpointType) -> None:
        if self._transport is not None:
            self._transport.sendto(data, addr)

    def sendtoall(self, data: bytes) -> None:
        # TODO: Implement for multicast support
        raise NotImplementedError("No implementation for UDP yet")

    def shutdown(self) -> None:
        if self._transport is not None:
            self._transport.close()


class TCPSomeipEndpoint(SomeipEndpoint):
    def __init__(self, server, manager):
        self._server: asyncio.Server = server
        self._manager: TcpClientManagerInterface = manager

    def set_someip_callback(
        self, callback_func: Callable[[SomeIpMessage, Tuple[str, int]], None]
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
