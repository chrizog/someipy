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

from typing import List
from someipy._internal.daemon_client_abcs import ServerInstanceInterface
from someipy._internal.someipy_daemon_client import SomeIpDaemonClient
from someipy.service import EventGroup, Method, Service

from someipy._internal.logging import get_logger

_logger_name = "server_service_instance"


class ServerServiceInstance(ServerInstanceInterface):

    def __init__(
        self,
        daemon: SomeIpDaemonClient,
        service: Service,
        instance_id: int,
        endpoint_ip: str,
        endpoint_port: int,
        ttl: int = 0,  # TTL used for SD Offer entries
        cyclic_offer_delay_ms=2000,
    ):
        self._daemon = daemon
        self._service = service
        self._instance_id = instance_id
        self._endpoint_ip = endpoint_ip
        self._endpoint_port = endpoint_port
        self._ttl = ttl
        self._cyclic_offer_delay_ms = cyclic_offer_delay_ms

        self._daemon._server_service_instances.append(self)

    async def start_offer(self):
        methods: List[Method] = self._service.methods.values()
        eventgroups: List[EventGroup] = self._service.eventgroups.values()

        await self._daemon.offer_service(
            service_id=self._service.id,
            instance_id=self._instance_id,
            major_version=self._service.major_version,
            minor_version=self._service.minor_version,
            ttl=self._ttl,
            endpoint_ip=self._endpoint_ip,
            endpoint_port=self._endpoint_port,
            eventgroups=eventgroups,
            methods=methods,
            cyclic_offer_delay_ms=self._cyclic_offer_delay_ms,
        )

    async def stop_offer(self):
        methods: List[Method] = self._service.methods.values()
        eventgroups: List[EventGroup] = self._service.eventgroups.values()

        await self._daemon.stop_offer_service(
            service_id=self._service.id,
            instance_id=self._instance_id,
            major_version=self._service.major_version,
            minor_version=self._service.minor_version,
            ttl=self._ttl,
            endpoint_ip=self._endpoint_ip,
            endpoint_port=self._endpoint_port,
            eventgroups=eventgroups,
            methods=methods,
            cyclic_offer_delay_ms=self._cyclic_offer_delay_ms,
        )

    @property
    def service(self) -> Service:
        return self._service

    @property
    def instance_id(self) -> int:
        return self._instance_id

    @property
    def endpoint_ip(self) -> str:
        return self._endpoint_ip

    @property
    def endpoint_port(self) -> int:
        return self._endpoint_port
