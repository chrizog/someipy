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

from abc import ABC, abstractmethod
from typing import Tuple

from someipy._internal.uds_messages import InboundCallMethodResponse, ReceivedEvent
from someipy.service import Service


class ClientInstanceInterface(ABC):

    @abstractmethod
    def _method_call_data_received(self, message: InboundCallMethodResponse) -> None:
        pass

    @abstractmethod
    def _event_data_received(self, message: ReceivedEvent) -> None:
        pass

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
    def endpoint(self) -> Tuple[str, int]:
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
