---
layout: default
title: Offering SOME/IP Events
nav_order: 2
---

<style type="text/css">
pre > code.language-mermaid {
    display: flex;
    justify-content: center;
    align-items: center;
}

p:has(img) {
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>

# Offering SOME/IP Events
## SOME/IP Events

SOME/IP events implement the publish-subscribe concept in SOME/IP. A server offers a service to which one or more clients can subscribe. In case the server sends an event, all subscribed clients will receive the event.

A SOME/IP event is identified through an event ID which is packed into the header of a SOME/IP message. The event ID can be used by multiple services and does not have to be globally unique. The unique identification of an event comes through the combination of service ID, instance ID and event ID.

A SOME/IP event usually carries a serialized payload. For defining the service interface datatypes and serializing structured data into `bytes` follow the article on [SOME/IP Service Interface Datatypes](/someipy/service_interface.html).

## SOME/IP SD Eventgroups vs. SOME/IP Events

In SOME/IP there is also the term Eventgroups. It's important to understand the difference for setting up a proper SOME/IP communication. If eventgroup and event IDs are mixed up, the service discovery will not be able to subscribe properly.

Eventgroups are only used in **service discovery of SOME/IP** and logically group events together for subscription. Eventgroups only exist at the service discovery level, but never appear in the actual data sent for an event. Once a client subscribed to a service, eventgroups are obsolete.

Grouping events in eventgroups allows clients to subscribe to multiple events at once. For that purpose you could put all your events into a single eventgroup. Then a client can subscribe only to a single eventgroup and will receive notifications for all events. This has the advantage of reduced traffic for service discovery. However, since all events are sent to the client, more bandwidth is used for sending the actual data.

If you want to enable clients to subscribe to single events, create a single eventgroup for each event. Then a client can granularly subscribe to single events. This will require more service discovery traffic, however it may lead to sending only events that are actually used.

## Step 1: Define a Service

In order to offer a service containing a SOME/IP, we will define a `Service` first, which is instantiated afterwards into a `ServerServiceInstance`. The `Service` will contain a single event with 0x0123 in eventgroup 0x0321. The `ServiceBuilder` class is used to build the `Service` object.

```python
SAMPLE_SERVICE_ID = 0x1234
SAMPLE_INSTANCE_ID = 0x5678
SAMPLE_EVENTGROUP_ID = 0x0321
SAMPLE_EVENT_ID = 0x0123

temperature_eventgroup = EventGroup(
        id=SAMPLE_EVENTGROUP_ID, event_ids=[SAMPLE_EVENT_ID]
    )
temperature_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .with_eventgroup(temperature_eventgroup)
        .build()
    )
```

## Step 2: Instantiate the Service

The previously defined `Service` can be instantiated into one or multiple service instances. Since we are offering events as a server the service is instantiated as a `ServerServiceInstance` using the `construct_server_service_instance` function. The `construct_server_service_instance` uses await in its implementation and therefore has to be `await`ed as well.

You can choose to either use UDP or TCP as the transport protocol. Make sure, that the configuration matches with the client subscribing to the service.

```python
# For sending events use a ServerServiceInstance
service_instance_temperature = await construct_server_service_instance(
    temperature_service,
    instance_id=SAMPLE_INSTANCE_ID,
    endpoint=(
        ipaddress.IPv4Address(INTERFACE_IP),
        3000,
    ),  # src IP and port of the service
    ttl=5,
    sd_sender=service_discovery,
    cyclic_offer_delay_ms=2000,
    protocol=TransportLayerProtocol.UDP,
)
```

The parameters `ttl` and `cyclic_offer_delay_ms` are described [SOME/IP Service Interface Datatypes](/someipy/service_discovery.html)

> **_Multiple service instances:_**  If you want to offer multiple service instances in the same application, you would simply construct another service instance here. Read the example application [offer_multiple_services.py](https://github.com/chrizog/someipy/blob/master/example_apps/offer_multiple_services.py) for more details. 


## Step 3: Announce the Service via Service Discovery

At this point, clients are not able to subscribe to the `ServerServiceInstance` and to its eventgroup with ID `0x0321`. First, we need to attach the `ServerServiceInstance` to service discovery. This will enable the `ServerServiceInstance` to be notified about new subscriptions from clients. An observer pattern is implemented in which the `ServerServiceInstance` is the observer.

```python
service_discovery.attach(service_instance_temperature)
```

The next step is to use `start_offer`. This will start an internal timer with a cycle of `cyclic_offer_delay_ms` sending service discovery messages with offer entries. Since this offer message is sent on service instance level, it is sent only once even if your service contains multiple events.

```python
service_instance_temperature.start_offer()
```

## Step 4: Sending Event Notifications to Clients

Now that the service is offered, clients can subscribe to the eventgroup with ID `0x0321` and the server can send data. The `send_event` function expects a `bytes`-object which is typically created by serialized structured data:

```python
payload = tmp_msg.serialize()
service_instance_temperature.send_event(
    SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload
)
```

Typical sending strategies for SOME/IP events are **cyclic updates** or **update on change**. Update on change means that an event is sent whenever the contained value changes. In a cyclic update the event would be sent even if the contained data has not changed since the last publish.
