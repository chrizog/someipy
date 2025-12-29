# Copyright (C) 2025 Christian H.
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

import asyncio
from typing import TypeVar, Generic, Optional, Callable, Any


T = TypeVar("T")


class Event(Generic[T]):
    def __init__(self):
        self._handlers: list[Callable[[object, Optional[T]], Any]] = []

    def add_handler(self, handler: Callable[[object, Optional[T]], Any]) -> None:
        if handler not in self._handlers:
            self._handlers.append(handler)

    def remove_handler(self, handler: Callable[[object, Optional[T]], Any]) -> None:
        if handler in self._handlers:
            self._handlers.remove(handler)

    async def invoke(self, sender: object, e: Optional[T] = None) -> None:
        """Invoke all handlers, handling both sync and async automatically"""
        for handler in self._handlers[:]:
            result = handler(sender, e)
            if asyncio.iscoroutine(result):
                await result

    def __iadd__(self, handler: Callable[[object, Optional[T]], Any]) -> "Event[T]":
        self.add_handler(handler)
        return self

    def __isub__(self, handler: Callable[[object, Optional[T]], Any]) -> "Event[T]":
        self.remove_handler(handler)
        return self
