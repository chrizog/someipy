from dataclasses import dataclass
from typing import List, Callable, Tuple, Dict


@dataclass
class Method:
    id: int
    method_handler: Callable[[bytes], Tuple[bool, bytes]]

    def __eq__(self, __value: object) -> bool:
        return self.method_id == __value.method_id


@dataclass
class EventGroup:
    id: int
    event_ids: List[int]


@dataclass
class Service:
    id: int
    major_version: int
    minor_version: int

    methods: Dict[int, Method]
    eventgroups: Dict[int, EventGroup]

    def __init__(self):
        self.id = 0
        self.major_version = 0
        self.minor_version = 0
        self.methods = dict()
        self.eventgroups = dict()

    @property
    def eventgroupids(self) -> List[int]:
        return self.eventgroups.keys()

    @property
    def methodids(self) -> List[int]:
        return self.methods.keys()


class ServiceBuilder:
    def __init__(self):
        self._service: Service = Service()

    def with_service_id(self, id: int):
        self._service.id = id
        return self

    def with_major_version(self, major_version: int):
        self._service.major_version = major_version
        return self

    def with_minor_version(self, minor_version: int):
        self._service.minor_version = minor_version
        return self

    def with_method(self, method: Method):
        if self._service.methods.get(method.id) is None:
            self._service.methods[method.id] = method
        return self

    def with_eventgroup(self, eventgroup: EventGroup):
        if self._service.eventgroups.get(eventgroup.id) is None:
            self._service.eventgroups[eventgroup.id] = eventgroup
        return self

    def build(self):
        return self._service
