from dataclasses import dataclass
from typing import List, Callable, Tuple, Dict


@dataclass
class Method:
    """
    Class representing a SOME/IP method with a method id and a method handler.
    """
    id: int
    method_handler: Callable[[bytes], Tuple[bool, bytes]]

    def __eq__(self, __value: object) -> bool:
        return self.method_id == __value.method_id


@dataclass
class EventGroup:
    """
    Class representing a SOME/IP eventgroup with an eventgroup id and a list of event ids.
    """
    id: int
    event_ids: List[int]


@dataclass
class Service:
    """
    Class representing a SOME/IP service. A service has an id, major and minor version and 0 or more methods and/or eventgroups.
    """
    id: int
    major_version: int
    minor_version: int

    methods: Dict[int, Method]
    eventgroups: Dict[int, EventGroup]

    def __init__(self):
        self.id = 0
        self.major_version = 1
        self.minor_version = 0
        self.methods = dict()
        self.eventgroups = dict()

    @property
    def eventgroupids(self) -> List[int]:
        """
        Returns a list of event group IDs associated with the service.

        :return: A list of integers representing the event group IDs.
        """
        return list(self.eventgroups.keys())

    @property
    def methodids(self) -> List[int]:
        """
        Returns a list of method IDs associated with the object.

        :return: A list of integers representing the method IDs.
        :rtype: List[int]
        """
        return list(self.methods.keys())


class ServiceBuilder:
    """
    Class used to build a Service using a fluent API. Call the "with_" methods to add methods and event groups to the service. Call the build method to create the service.
    """

    def __init__(self):
        """
        Initializes a new ServiceBuilder instance.
        """
        self._service = Service()

    def with_service_id(self, id: int) -> "ServiceBuilder":
        """
        Sets the service id for the service to be built.

        :param id: The ID of the service.
        :type id: int
        :return: The ServiceBuilder instance.
        :rtype: ServiceBuilder
        """
        self._service.id = id
        return self

    def with_major_version(self, major_version: int) -> "ServiceBuilder":
        """
        Sets the major version for the service to be built.

        :param major_version: The major version of the service.
        :type major_version: int
        :return: The ServiceBuilder instance.
        :rtype: ServiceBuilder
        """
        self._service.major_version = major_version
        return self

    def with_minor_version(self, minor_version: int) -> "ServiceBuilder":
        """
        Sets the minor version for the service to be built.

        :param minor_version: The minor version of the service.
        :type minor_version: int
        :return: The ServiceBuilder instance.
        :rtype: ServiceBuilder
        """
        self._service.minor_version = minor_version
        return self

    def with_method(self, method: Method) -> "ServiceBuilder":
        """
        Adds a method to the service to be built.

        :param method: The method to be added.
        :type method: Method
        :return: The ServiceBuilder instance.
        :rtype: ServiceBuilder
        """
        if self._service.methods.get(method.id) is None:
            self._service.methods[method.id] = method
        return self

    def with_eventgroup(self, eventgroup: EventGroup) -> "ServiceBuilder":
        """
        Adds an event group to the service to be built.

        :param eventgroup: The event group to be added.
        :type eventgroup: EventGroup
        :return: The ServiceBuilder instance.
        :rtype: ServiceBuilder
        """
        if self._service.eventgroups.get(eventgroup.id) is None:
            self._service.eventgroups[eventgroup.id] = eventgroup
        return self

    def build(self) -> Service:
        """
        Builds and returns a Service instance.

        :return: The built Service instance.
        :rtype: Service
        """
        return self._service
