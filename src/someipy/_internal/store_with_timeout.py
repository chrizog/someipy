import asyncio
from typing import Set, Generic, TypeVar, Protocol


T = TypeVar("T")


class ObjectWithTtl(Protocol):
    ttl: int  # The TTL of the object in seconds


class StoreWithTimeout:

    class ObjectWithTtlWrapper:
        def __init__(self, value: ObjectWithTtl):
            self.value: ObjectWithTtl = value
            self.timeout_task: asyncio.Task = None
            self.active = False  # Flag needed to prevent callbacks being called during cancellation

        def __eq__(self, other):
            # Two objects are equal if their values are equal even if the timeout is different
            return self.value == other.value

        def __hash__(self):
            return hash(self.value)

        async def _wait(self):
            await asyncio.sleep(self.value.ttl)

    def __init__(self):
        self.values: Set[self.ObjectWithTtlWrapper] = set()
        self._current = 0

    async def add(self, object_to_add: ObjectWithTtl, callback=None):
        wrapper = self.ObjectWithTtlWrapper(object_to_add)

        if wrapper in self.values:
            await self.remove(wrapper.value)

        wrapper.timeout_task = asyncio.create_task(wrapper._wait())
        wrapper.active = True
        wrapper.timeout_task.add_done_callback(
            lambda _: self._done_callback(wrapper, callback)
        )
        self.values.add(wrapper)

    def _done_callback(self, caller: ObjectWithTtlWrapper, callback=None):
        self.values.discard(caller)
        if caller.active is True and callback is not None:
            callback(caller.value)

    async def remove(self, object_to_remove: ObjectWithTtl):
        wrapper = self.ObjectWithTtlWrapper(object_to_remove)
        if wrapper in self.values:
            for value in self.values:
                if value == wrapper:
                    value.active = False
                    value.timeout_task.cancel()
                    try:
                        await value.timeout_task
                    except asyncio.CancelledError:
                        pass
                    break

    async def clear(self):
        while len(self.values) > 0:
            await self.remove(next(iter(self.values)).value)

    def __contains__(self, item):
        wrapper = self.ObjectWithTtlWrapper(item)
        return wrapper in self.values

    def __iter__(self):
        self._current = 0
        return self

    def __next__(self):
        if self._current < len(self.values):
            result = next(iter(self.values))
            self._current += 1
            return result.value
        else:
            raise StopIteration
