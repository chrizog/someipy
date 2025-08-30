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

from dataclasses import dataclass
import json
from typing import List, Callable, Tuple, Dict, TypeVar

from someipy._internal.method_result import MethodResult
from someipy._internal.transport_layer_protocol import TransportLayerProtocol


MethodHandler = Callable[[bytes, Tuple[str, int]], MethodResult]
_T = TypeVar("_T")


@dataclass
class Method:
    """
    Class representing a SOME/IP method with a method id and a method handler.

    Parameters
    ----------
    id : int
        Method identifier.
    protocol : TransportLayerProtocol
        Transport protocol for the method.
    method_handler : MethodHandler, optional
        Optional method which is called on server side when an offered service is invoked. The handler shall return a MethodResult.
    """

    id: int
    protocol: TransportLayerProtocol
    method_handler: MethodHandler

    def __init__(
        self,
        id: int,
        protocol: TransportLayerProtocol,
        method_handler: MethodHandler = None,
    ):
        """Initialize a Method.

        Parameters
        ----------
        id : int
            Method identifier.
        protocol : TransportLayerProtocol
            Transport protocol for the method.
        method_handler : MethodHandler, optional
            Optional method which is called on server side when an offered service is invoked. The handler shall return a MethodResult.
        """
        self.id = id
        self.protocol = protocol
        self.method_handler = method_handler

    def __eq__(self, __value: object) -> bool:
        """Check equality with another Method based on id and protocol.

        Parameters
        ----------
        __value : object
            Another Method instance.

        Returns
        -------
        bool
            True if ids and protocols match, False otherwise.
        """
        return self.id == __value.id and self.protocol == __value.protocol

    def to_json(self) -> str:
        """Serialize this Method to a JSON string.

        Returns
        -------
        str
            JSON representation of the method.
        """
        as_dict = {
            "id": self.id,
            "protocol": self.protocol.value,
        }
        return json.dumps(as_dict)

    @classmethod
    def from_json(cls: _T, json_str: str) -> _T:
        """Create a Method from a JSON string.

        Parameters
        ----------
        json_str : str
            JSON representation of a Method.

        Returns
        -------
        Method
            The constructed Method instance.
        """
        json_dict = json.loads(json_str)

        id = int(json_dict["id"])
        protocol = TransportLayerProtocol(json_dict["protocol"])
        method_handler = None
        o = cls(id, protocol, method_handler)
        return o


@dataclass
class Event:
    """
    Class representing a SOME/IP event with an event id and a transport layer protocol.
    """

    id: int
    protocol: TransportLayerProtocol

    def to_json(self) -> str:
        """Serialize this Event to JSON.

        Returns
        -------
        str
            JSON representation of the event.
        """
        as_dict = {
            "id": self.id,
            "protocol": self.protocol.value,
        }
        return json.dumps(as_dict)

    @classmethod
    def from_json(cls: _T, json_str: str) -> _T:
        """Create an Event from a JSON string.

        Parameters
        ----------
        json_str : str
            JSON representation of an Event.

        Returns
        -------
        Event
        """
        json_dict = json.loads(json_str)
        o = cls(int(json_dict["id"]), TransportLayerProtocol(json_dict["protocol"]))
        return o


@dataclass
class EventGroup:
    """
    Class representing a SOME/IP eventgroup with an eventgroup id and a list of event ids.
    """

    id: int
    events: List[Event]

    def to_json(self) -> str:
        """Serialize this EventGroup to JSON.

        Returns
        -------
        str
            JSON representation of the event group.
        """
        as_dict = {
            "id": self.id,
            "events": [event.to_json() for event in self.events],
        }
        return json.dumps(as_dict)

    @classmethod
    def from_json(cls: _T, json_str: str) -> _T:
        """Create an EventGroup from a JSON string.

        Parameters
        ----------
        json_str : str
            JSON representation of an EventGroup.

        Returns
        -------
        EventGroup
        """
        json_dict = json.loads(
            json_str
        )  # Contains a dictionary with "id" (int) and "events" (serialized Event)
        events = [Event.from_json(event_json) for event_json in json_dict["events"]]

        o: EventGroup = cls(int(json_dict["id"]), events)
        return o

    def __hash__(self):
        """Return a hash based on the group id and contained event ids."""
        return hash((self.id, tuple(event.id for event in self.events)))

    @property
    def has_udp(self) -> bool:
        """
        Checks if the event group contains any events with UDP protocol.

        Returns
        -------
        bool
            True if at least one event uses UDP, False otherwise.
        """
        return any(
            event.protocol == TransportLayerProtocol.UDP for event in self.events
        )

    @property
    def has_tcp(self) -> bool:
        """
        Checks if the event group contains any events with TCP protocol.

        Returns
        -------
        bool
            True if at least one event uses TCP, False otherwise.
        """
        return any(
            event.protocol == TransportLayerProtocol.TCP for event in self.events
        )


@dataclass
class Service:
    """
    Class representing a SOME/IP service. A service has an id, major and minor version and 0 or more methods and/or eventgroups.

    Attributes
    ----------
    id : int
        Service identifier.
    major_version : int
        Major version of the service.
    minor_version : int
        Minor version of the service.
    methods : Dict[int, Method]
        Mapping of method IDs to Method instances.
    eventgroups : Dict[int, EventGroup]
        Mapping of event group IDs to EventGroup instances.
    """

    id: int
    major_version: int
    minor_version: int

    methods: Dict[int, Method]
    eventgroups: Dict[int, EventGroup]

    def __init__(self):
        """Initialize a new Service instance with defaults."""
        self.id = 0
        self.major_version = 1
        self.minor_version = 0
        self.methods = dict()
        self.eventgroups = dict()

    @property
    def eventgroupids(self) -> List[int]:
        """
        Returns a list of event group IDs associated with the service.

        Returns
        -------
        List[int]
            List of event group IDs.
        """
        return list(self.eventgroups.keys())

    @property
    def events(self) -> List[Event]:
        """
        Returns a list of events associated with the service.

        Returns
        -------
        List[Event]
            All events across event groups for this service.
        """
        return [
            event
            for eventgroup in self.eventgroups.values()
            for event in eventgroup.events
        ]

    @property
    def methodids(self) -> List[int]:
        """
        Returns a list of method IDs associated with the object.

        Returns
        -------
        List[int]
            List of method IDs.
        """
        return list(self.methods.keys())


class ServiceBuilder:
    """
    Class used to build a Service using a fluent API. Call the 'with' methods to add methods and event groups to the service. Call the build method to create the service.
    """

    def __init__(self):
        """Initializes a new ServiceBuilder instance."""
        self._service = Service()

    def with_service_id(self, id: int) -> "ServiceBuilder":
        """
        Sets the service id for the service to be built.

        Parameters
        ----------
        id : int
            The ID of the service.

        Returns
        -------
        ServiceBuilder
        """
        self._service.id = id
        return self

    def with_major_version(self, major_version: int) -> "ServiceBuilder":
        """
        Sets the major version for the service to be built.

        Parameters
        ----------
        major_version : int
            The major version of the service.

        Returns
        -------
        ServiceBuilder
        """
        self._service.major_version = major_version
        return self

    def with_minor_version(self, minor_version: int) -> "ServiceBuilder":
        """
        Sets the minor version for the service to be built.

        Parameters
        ----------
        minor_version : int
            The minor version of the service.

        Returns
        -------
        ServiceBuilder
        """
        self._service.minor_version = minor_version
        return self

    def with_method(self, method: Method) -> "ServiceBuilder":
        """
        Adds a method to the service to be built.

        Parameters
        ----------
        method : Method
            The method to be added.

        Returns
        -------
        ServiceBuilder
        """
        if self._service.methods.get(method.id) is None:
            self._service.methods[method.id] = method
        return self

    def with_eventgroup(self, eventgroup: EventGroup) -> "ServiceBuilder":
        """
        Adds an event group to the service to be built.

        Parameters
        ----------
        eventgroup : EventGroup
            The event group to be added.

        Returns
        -------
        ServiceBuilder
        """
        if self._service.eventgroups.get(eventgroup.id) is None:
            self._service.eventgroups[eventgroup.id] = eventgroup
        return self

    def build(self) -> Service:
        """Builds and returns a Service.

        Returns
        -------
        Service
            The built Service.
        """
        return self._service
