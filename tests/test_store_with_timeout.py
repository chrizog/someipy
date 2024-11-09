import asyncio
import pytest
import pytest_asyncio
from someipy._internal.store_with_timeout import StoreWithTimeout


class MyTestObjectWithTtl:
    def __init__(self, value: int, ttl: int):
        self.ttl = ttl
        self.value = value

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return self.value == other.value


@pytest.mark.asyncio
async def test_add():
    store = StoreWithTimeout()

    await store.add(MyTestObjectWithTtl(1, 2))
    assert len(store.values) == 1
    assert (MyTestObjectWithTtl(1, 2)) in store

    await store.add(MyTestObjectWithTtl(1, 2))
    assert len(store.values) == 1

    await store.add(MyTestObjectWithTtl(1, 1))
    assert len(store.values) == 1
    await asyncio.sleep(1.5)
    assert len(store.values) == 0

    await store.add(MyTestObjectWithTtl(2, 2))
    assert len(store.values) == 1

    await asyncio.sleep(2.5)
    assert len(store.values) == 0
    await store.clear()


@pytest.mark.asyncio
async def test_clear():
    store = StoreWithTimeout()
    await store.add(MyTestObjectWithTtl(1, 5))
    await store.add(MyTestObjectWithTtl(2, 5))
    await store.add(MyTestObjectWithTtl(3, 5))
    assert len(store.values) == 3

    await store.clear()
    assert len(store.values) == 0


@pytest.mark.asyncio
async def test_remove():
    store = StoreWithTimeout()
    await store.add(MyTestObjectWithTtl(1, 5))
    await store.add(MyTestObjectWithTtl(2, 5))
    await store.add(MyTestObjectWithTtl(3, 5))
    assert len(store.values) == 3

    await store.remove(MyTestObjectWithTtl(2, 5))
    assert len(store.values) == 2
    await store.clear()

    # Try to remove some object that is not in the store
    # This shall not raise an error
    await store.remove(MyTestObjectWithTtl(2, 5))


@pytest.mark.asyncio
async def test_callback():
    store = StoreWithTimeout()

    callback_was_called = 0

    def callback(obj):
        nonlocal callback_was_called
        print("Callback was called")
        callback_was_called += 1

    await store.add(MyTestObjectWithTtl(1, 1), callback)
    await asyncio.sleep(1.5)
    assert callback_was_called == 1
    assert len(store.values) == 0

    callback_was_called = 0

    await store.add(MyTestObjectWithTtl(1, 2), callback)
    assert len(store.values) == 1
    await store.remove(MyTestObjectWithTtl(1, 2))
    assert len(store.values) == 0
    assert callback_was_called == 0
