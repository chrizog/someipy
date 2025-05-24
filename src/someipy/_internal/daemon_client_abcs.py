from abc import ABC, abstractmethod

from someipy.service import Service


class ClientInstanceInterface(ABC):

    @abstractmethod
    def subscribe_ready_request(self, message: dict) -> None:

        pass


class ServerInstanceInterface(ABC):

    @property
    @abstractmethod
    def service(self) -> Service:
        pass

    @property
    @abstractmethod
    def instance_id(self) -> int:
        pass

    @property
    @abstractmethod
    def endpoint_ip(self) -> str:
        pass

    @property
    @abstractmethod
    def endpoint_port(self) -> int:
        pass
