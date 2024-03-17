import time
from someipy._internal.subscribers import EventGroupSubscriber, Subscribers

def test_eventgroupsubscriber_equal():
    e_1 = ("123", 5)
    e_2 = ("123", 5)
    e_3 = ("456", 4)

    s_1 = EventGroupSubscriber(1, e_1, 500)
    s_2 = EventGroupSubscriber(1, e_2, 600)
    assert s_1 == s_2

    s_2.endpoint = e_3
    assert s_1 != s_2

    s_2.endpoint = e_2
    assert s_1 == s_2

    s_2.eventgroup_id = 2
    assert s_1 != s_2

 
def test_add_remove_update():

    subscriber = EventGroupSubscriber(eventgroup_id=1, endpoint=("123", 1), ttl=1)

    subscribers = Subscribers()
    initial_ts = subscriber.last_ts_ms
    time.sleep(0.1)

    assert len(subscribers.subscribers) == 0
    subscribers.add_subscriber(subscriber)
    assert initial_ts != subscribers.subscribers[0].last_ts_ms
    assert len(subscribers.subscribers) == 1
    
    # Add same subscriber. Length shall not change, but timestamp shall be updated
    initial_ts = subscribers.subscribers[0].last_ts_ms
    time.sleep(0.2)
    subscribers.add_subscriber(subscriber)
    assert initial_ts != subscribers.subscribers[0].last_ts_ms
    assert len(subscribers.subscribers) == 1

    subscriber_2 = EventGroupSubscriber(eventgroup_id=2, endpoint=("123", 1), ttl=1)
    subscribers.add_subscriber(subscriber_2)
    assert len(subscribers.subscribers) == 2

    subscriber_3 = EventGroupSubscriber(eventgroup_id=2, endpoint=("123", 1), ttl=1)
    subscribers.remove_subscriber(subscriber_3)
    assert len(subscribers.subscribers) == 1

    subscriber_4 = EventGroupSubscriber(eventgroup_id=1, endpoint=("123", 1), ttl=1)
    subscribers.remove_subscriber(subscriber_4)
    assert len(subscribers.subscribers) == 0

    subscribers.add_subscriber(EventGroupSubscriber(eventgroup_id=1, endpoint=("123", 1), ttl=1))
    subscribers.add_subscriber(EventGroupSubscriber(eventgroup_id=2, endpoint=("123", 1), ttl=3))
    subscribers.add_subscriber(EventGroupSubscriber(eventgroup_id=3, endpoint=("123", 1), ttl=2))
    assert len(subscribers.subscribers) == 3
    time.sleep(1.1)
    subscribers.update()
    assert len(subscribers.subscribers) == 2
    time.sleep(3)
    subscribers.update()
    assert len(subscribers.subscribers) == 0