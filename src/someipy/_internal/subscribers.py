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

import time
from typing import List
from someipy._internal.utils import EndpointType


class EventGroupSubscriber:
    eventgroup_id: int
    endpoint: EndpointType
    ttl: int
    last_ts_ms: int

    def __init__(self, eventgroup_id: int, endpoint: EndpointType, ttl: int):
        self.eventgroup_id = eventgroup_id
        self.endpoint = endpoint
        self.ttl = ttl
        self.last_ts_ms = int(time.time() * 1000)

    def __eq__(self, __value: object) -> bool:
        return (
            self.eventgroup_id == __value.eventgroup_id
            and self.endpoint[0] == __value.endpoint[0]
            and self.endpoint[1] == __value.endpoint[1]
        )


class Subscribers:
    def __init__(self):
        self._subscribers: List[EventGroupSubscriber] = []

    def update(self):
        # From SOME/IP specification:
        # TTL shall be set to the lifetime of the subscription.
        # If set to 0xFFFFFF, the Subscribe Eventgroup entry shall be considered valid
        # until the next reboot.
        time_now_ms = int(time.time() * 1000)

        self._subscribers = [
            s
            for s in self._subscribers
            if (s.ttl == 0xFFFFFF) or (time_now_ms < (s.last_ts_ms + (s.ttl * 1000.0)))
        ]

    def add_subscriber(self, new_subscriber: EventGroupSubscriber) -> None:
        time_now_ms = int(time.time() * 1000.0)
        for s in self._subscribers:
            if new_subscriber == s:
                s.last_ts_ms = time_now_ms
                return
        new_subscriber.last_ts_ms = time_now_ms
        self._subscribers.append(new_subscriber)

    def remove_subscriber(self, subscriber: EventGroupSubscriber) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    @property
    def subscribers(self) -> List[EventGroupSubscriber]:
        return self._subscribers
