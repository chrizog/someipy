import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Dict, Iterable, Tuple

from someipy._internal.someip_message import SomeIpMessage
from someipy._internal.someip_data_processor import SomeipDataProcessor

class TcpClientProtocolInterface(ABC):
    @abstractmethod
    def write(self, data: bytes) -> None:
        pass

    @property
    @abstractmethod
    def ip_addr(self) -> str:
        pass

    @property
    @abstractmethod
    def port(self) -> int:
        pass


class TcpClientManagerInterface(ABC):
    @abstractmethod
    def register_client(self, client: TcpClientProtocolInterface) -> None:
        pass

    @abstractmethod
    def unregister_client(self, client: TcpClientProtocolInterface) -> None:
        pass
    
    @abstractmethod
    def get_client(self, ip_addr: str, port: int) -> TcpClientProtocolInterface:
        pass

    @abstractmethod
    def get_all_clients(self) -> Iterable[TcpClientProtocolInterface]:
        pass

    @abstractmethod
    def someip_callback(self, client: TcpClientProtocolInterface, someip_message: SomeIpMessage) -> None:
        pass

    @abstractmethod
    def register_callback(self, callback: Callable[[SomeIpMessage, Tuple[str, int]], None]) -> None:
        pass


class TcpClientManager(TcpClientManagerInterface):

    def __init__(self):
        self._clients: Dict[str, TcpClientProtocolInterface] = {}
        self._someip_callback: Callable[[SomeIpMessage, Tuple[str, int]], None] = None

    def _build_key(self, ip_addr: str, port: int) -> str:
        return f"{ip_addr}-{port}"

    def register_client(self, client: TcpClientProtocolInterface) -> None:
        print(f"Register new client {client.ip_addr}, {client.port}")
        self._clients[self._build_key(client.ip_addr, client.port)] = client

    def unregister_client(self, client: TcpClientProtocolInterface) -> None:
        print(f"Unregister client {client.ip_addr}, {client.port}")
        if self._build_key(client.ip_addr, client.port) in self._clients.keys():
            del self._clients[self._build_key(client.ip_addr, client.port)]

    def get_client(self, ip_addr: str, port: int) -> TcpClientProtocolInterface:
        if self._build_key(ip_addr, port) in self._clients.keys():
            return self._clients[self._build_key(ip_addr, port)]
        else:
            return None
        
    def get_all_clients(self) -> Iterable[TcpClientProtocolInterface]:
        return self._clients.values()

    def someip_callback(self, client: TcpClientProtocolInterface, someip_message: SomeIpMessage) -> None:
        if self._someip_callback is not None:
            self._someip_callback(someip_message, (client.ip_addr, client.port))

    def register_callback(self, callback: Callable[[SomeIpMessage, Tuple[str, int]], None]) -> None:
        self._someip_callback = callback

class TcpClientProtocol(asyncio.Protocol, TcpClientProtocolInterface):

    def __init__(self, client_manager: TcpClientManager):
        self._client_manager: TcpClientManager = client_manager
        self._transport = None
        self._ip_addr_client = None
        self._port_client = None
        self._data_processor = SomeipDataProcessor(datagram_mode=False)

    def connection_made(self, transport: asyncio.BaseTransport):
        peername: Tuple = transport.get_extra_info('peername')
        # print('Connection from {}'.format(peername))
        self._transport = transport
        self._ip_addr_client = peername[0]
        self._port_client = peername[1]

        self._client_manager.register_client(self)

    def data_received(self, data: bytes):
        # print('Data received {}: {}'.format(self.ip_addr, data))

        # Push data to processor
        result = self._data_processor.process_data(data)
        if result and self._client_manager is not None:
            self._client_manager.someip_callback(self, self._data_processor.someip_message)

    def connection_lost(self, _) -> None:
        self._client_manager.unregister_client(self)

    def write(self, data: bytes) -> None:
        if self._transport is not None:
            self._transport.write(data)

    @property
    def ip_addr(self) -> str:
        return self._ip_addr_client

    @property
    def port(self) -> int:
        return self._port_client
