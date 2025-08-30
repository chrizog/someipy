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

import base64
from typing import List
from someipy._internal.daemon_client_abcs import ServerInstanceInterface
from someipy._internal.someipy_daemon_client import SomeIpDaemonClient
from someipy._internal.uds_messages import create_uds_message, SendEventRequest
from someipy.service import EventGroup, Method, Service

from someipy._internal.logging import get_logger

_logger_name = "server_service_instance"


class ServerServiceInstance(ServerInstanceInterface):
    """Server-side representation of a service instance used for offering SOME/IP services.

    This class manages the lifecycle of offering a service instance via
    the Some/IP-SD mechanism and enables sending events to subscribed
    clients.

    Parameters
    ----------
    daemon : SomeIpDaemonClient
        Daemon client used to communicate with the someipy daemon.
    service : Service
        Service configuration for this instance.
    instance_id : int
        Instance ID for this service instance.
    endpoint_ip : str
        IP address of the endpoint on which the service instance is reachable.
    endpoint_port : int
        Port of the endpoint on which the service instance is reachable.
    ttl : int, optional
        TTL used for Service Discovery offers. Default: 0.
    cyclic_offer_delay_ms : int, optional
        Delay between cyclic offers in milliseconds. Default: 2000.
    """

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
        """Initialize a ServerServiceInstance.

        Parameters
        ----------
        daemon : SomeIpDaemonClient
            Daemon client used to communicate with the someipy daemon.
        service : Service
            Service configuration for this instance.
        instance_id : int
            Instance ID for this service instance.
        endpoint_ip : str
            IP address of the endpoint on which the service instance is reachable.
        endpoint_port : int
            Port of the endpoint on which the service instance is reachable.
        ttl : int, optional
            TTL used for Service Discovery offers. Default: 0.
        cyclic_offer_delay_ms : int, optional
            Delay between cyclic offers in milliseconds. Default: 2000.
        """
        self._daemon = daemon
        self._service = service
        self._instance_id = instance_id
        self._endpoint_ip = endpoint_ip
        self._endpoint_port = endpoint_port
        self._ttl = ttl
        self._cyclic_offer_delay_ms = cyclic_offer_delay_ms

        self._daemon._server_service_instances.append(self)

    async def start_offer(self):
        """Start offering the service instance via the service discovery offer entries.

        This method gathers the current service methods and event groups
        and invokes the daemon to advertise the service with the
        configured endpoint and version information.

        Returns
        -------
        None
        """
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
        """Stop offering the service instance and send out a stop offer entry.

        This stops advertising the service instance to clients via the daemon.

        Returns
        -------
        None
        """
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

    def send_event(self, eventgroup_id: int, event_id: int, payload: bytes):
        """Send an event to clients subscribed to the event.

        This method validates the specified event group and event within the
        service definition, encodes the payload in Base64, constructs a
        UDS message and dispatches it through the daemon.

        Parameters
        ----------
        eventgroup_id : int
            ID of the event group the event belongs to.
        event_id : int
            ID of the event to send.
        payload : bytes
            Payload of the event to transmit to clients.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If event group ID or event ID is not found within the service.

        """
        if not eventgroup_id in self._service.eventgroupids:
            raise ValueError(
                f"Event group ID {eventgroup_id} not found in service 0x{self._service.id:04X}"
            )

        eventgroup = self._service.eventgroups[eventgroup_id]
        events = [event for event in eventgroup.events if event.id == event_id]
        if not events:
            raise ValueError(
                f"Event ID {event_id} not found in event group 0x{eventgroup_id:04X} of service 0x{self._service.id:04X}"
            )
        if len(events) > 1:
            raise ValueError(
                f"Multiple events with ID {event_id} found in event group 0x{eventgroup_id:04X} of service 0x{self._service.id:04X}"
            )
        event = events[0]

        base64_encoded_payload = base64.b64encode(payload).decode("utf-8")

        message = create_uds_message(
            SendEventRequest,
            service_id=self._service.id,
            instance_id=self._instance_id,
            major_version=self._service.major_version,
            client_id=0,
            session_id=1,  # TODO: Session ID
            eventgroup_id=eventgroup_id,
            event=event.to_json(),
            src_endpoint_ip=self._endpoint_ip,
            src_endpoint_port=self._endpoint_port,
            payload=base64_encoded_payload,
        )

        self._daemon.transmit_message_to_daemon(message)

    @property
    def service(self) -> Service:
        """Service associated with this server service instance.

        Returns
        -------
        Service
            The service configuration that this instance exposes.
        """
        return self._service

    @property
    def instance_id(self) -> int:
        """Instance ID of this server service instance.

        Returns
        -------
        int
            The unique identifier for this service instance.
        """
        return self._instance_id

    @property
    def endpoint_ip(self) -> str:
        """IP address of the endpoint this instance offers services on.

        Returns
        -------
        str
            Endpoint IP address.
        """
        return self._endpoint_ip

    @property
    def endpoint_port(self) -> int:
        """Port of the endpoint this instance offers services on.

        Returns
        -------
        int
            Endpoint port number.
        """
        return self._endpoint_port
