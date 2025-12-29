import pytest
from someipy._internal._daemon.subscription import Subscription
from someipy._internal._daemon.subscription_storage import SubscriptionStorage
from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy.service import EventGroup


@pytest.fixture
def subscription_service_id_1() -> Subscription:
    return Subscription(
        service_id=1,
        instance_id=1,
        major_version=1,
        eventgroup=EventGroup(0, []),
        ttl_seconds=60,
        client_endpoint=None,
        server_endpoint=None,
        protocols=frozenset([TransportLayerProtocol.TCP]),
        timestamp_last_update=0,
    )


@pytest.fixture
def subscription_service_id_2() -> Subscription:
    return Subscription(
        service_id=2,
        instance_id=1,
        major_version=1,
        eventgroup=EventGroup(0, []),
        ttl_seconds=60,
        client_endpoint=None,
        server_endpoint=None,
        protocols=frozenset([TransportLayerProtocol.TCP]),
        timestamp_last_update=0,
    )


def test_add_subscription_adds_subscription(subscription_service_id_1):

    storage = SubscriptionStorage()
    storage.add_subscription(100, subscription_service_id_1)
    assert subscription_service_id_1 in storage.subscriptions


def test_add_subscription_adds_multiple_subscriptions_per_client(
    subscription_service_id_1, subscription_service_id_2
):

    storage = SubscriptionStorage()
    storage.add_subscription(100, subscription_service_id_1)
    storage.add_subscription(100, subscription_service_id_2)
    assert subscription_service_id_1 in storage.subscriptions
    assert subscription_service_id_2 in storage.subscriptions

    assert storage.get_client_ids(subscription_service_id_1) == [100]
    assert storage.get_client_ids(subscription_service_id_2) == [100]


def test_get_client_ids_returns_multiple_clients(subscription_service_id_1):

    storage = SubscriptionStorage()
    storage.add_subscription(100, subscription_service_id_1)
    storage.add_subscription(200, subscription_service_id_1)

    client_ids = storage.get_client_ids(subscription_service_id_1)
    assert 100 in client_ids
    assert 200 in client_ids


def test_remove_subscription_removes_subscription(subscription_service_id_1):

    storage = SubscriptionStorage()
    storage.add_subscription(100, subscription_service_id_1)
    storage.remove_subscription(100, subscription_service_id_1)
    assert subscription_service_id_1 not in storage.subscriptions


def test_remove_client_removes_all_subscriptions(
    subscription_service_id_1, subscription_service_id_2
):

    storage = SubscriptionStorage()
    storage.add_subscription(100, subscription_service_id_1)
    storage.add_subscription(100, subscription_service_id_2)

    storage.remove_client(100)

    assert subscription_service_id_1 not in storage.subscriptions
    assert subscription_service_id_2 not in storage.subscriptions


def test_has_subscriptions_returns_empty_list_when_no_subscriptions(
    subscription_service_id_1, subscription_service_id_2
):
    storage = SubscriptionStorage()
    storage.add_subscription(100, subscription_service_id_1)
    result = storage.has_subscriptions(
        service_id=subscription_service_id_2.service_id,
        instance_id=subscription_service_id_1.instance_id,
        major_version=subscription_service_id_1.major_version,
    )
    assert result == []


def test_has_subscriptions_returns_matching_subscriptions(
    subscription_service_id_1, subscription_service_id_2
):
    storage = SubscriptionStorage()
    storage.add_subscription(100, subscription_service_id_1)
    storage.add_subscription(200, subscription_service_id_2)

    result = storage.has_subscriptions(
        service_id=subscription_service_id_1.service_id,
        instance_id=subscription_service_id_1.instance_id,
        major_version=subscription_service_id_1.major_version,
    )
    assert len(result) == 1
    subscription, client_id = result[0]
    assert subscription == subscription_service_id_1
    assert client_id == 100


def test_has_subscriptions_returns_multiple_matching_subscriptions(
    subscription_service_id_1, subscription_service_id_2
):
    storage = SubscriptionStorage()
    storage.add_subscription(100, subscription_service_id_1)
    storage.add_subscription(200, subscription_service_id_1)
    storage.add_subscription(300, subscription_service_id_2)

    result = storage.has_subscriptions(
        service_id=subscription_service_id_1.service_id,
        instance_id=subscription_service_id_1.instance_id,
        major_version=subscription_service_id_1.major_version,
    )
    assert len(result) == 2
    client_ids = [client_id for _, client_id in result]
    assert 100 in client_ids
    assert 200 in client_ids


def test_len(subscription_service_id_1, subscription_service_id_2):
    storage = SubscriptionStorage()
    assert len(storage) == 0

    storage.add_subscription(100, subscription_service_id_1)
    assert len(storage) == 1

    storage.add_subscription(200, subscription_service_id_1)
    assert len(storage) == 2

    storage.add_subscription(100, subscription_service_id_2)
    assert len(storage) == 3

    storage.remove_subscription(100, subscription_service_id_1)
    assert len(storage) == 2

    storage.remove_subscription(200, subscription_service_id_1)
    assert len(storage) == 1

    storage.remove_subscription(100, subscription_service_id_2)
    assert len(storage) == 0
