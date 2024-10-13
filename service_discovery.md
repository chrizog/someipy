---
layout: default
title: Service Discovery Configuration Parameters
nav_order: 10
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

# Service Discovery Configuration Parameters

## What is SOME/IP Service Discovery (SD)?

If a client needs to use a SOME/IP service, e.g. to call a method of a service, it needs to know the location of the service, i.e. on which IP address and on which port the service can be accessed. Vice versa, a server providing a service has to know to which receivers event messages have to be sent. Events only have to be sent to receivers that subscribed to the event beforehand (publish-subscribe pattern).

SOME/IP service discovery primarily offers exactly these two explained features:
- **Locating service instances**
- **Handling the publish-subscribe behavior**

SOME/IP service discovery consists of specific messages that are sent via UDP to a multicast group. By joining this specific multicast group, all applications are able to listen to service discovery messages or send service discovery messages to all participants by themselves.

The following image shows the difference between usual SOME/IP messages (right hand side) and the SOME/IP service discovery messages sent via IP multicast.

![Image]({{ site.baseurl }}/images/service_discovery/multicast_service_discovery.png)

The application offering the service instance, cyclically sends a SOME/IP SD message with a so called *offer entry* to all other participants in the multicast group. The *offer entry* contains the service instance location (IP address and port), the instance ID, service ID, major and minor version and a time-to-live (TTL) of the offer. Participants that want to subscribe to the eventgroup of this offered service instance, can send back a SOME/IP SD *subscribe eventgroup entry*. The subscribe eventgroup entry includes the service instance ID, the service ID, the major version, the eventgroup ID, the lifetime of the subscription (time-to-live) and most important the endpoint (IP address and port) of the client. The client will receive the SOME/IP events on this endpoint from the server. The server offering the service will answer this with a message containing a *subscribe acknowledge* entry. By using this type of handshake, the publish-subscribe pattern is implemented in SOME/IP. On the right-hand side of the image, you can see that the actual SOME/IP messages containing events are only delivered to two subscribers.

Another way of locating a service is to send a *find service* entry to actively ask if another participant in the network offers a specific service. If a participant offers the requested service, it will answer with an *offer service* entry and the subscription happens as described above afterwards. Participants can also send *stop offer* entries to indicate all participants that the service is shutdown.

Service discovery messages are actually SOME/IP messages, but filled with specific magic numbers in order to mark the messages as service discovery messages. E.g. service discovery messages have the message ID set to 0xFFFF81000 and protocol and interface version set to 0x01.

The specification of the SOME/IP service discovery protocol can be found [here](https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPServiceDiscoveryProtocol.pdf).

## Common SOME/IP Service Discovery Parameters in someipy

As shown in the [Getting Started guide](https://chrizog.github.io/someipy/) one of the first steps is to construct a `ServiceDiscoveryProtocol` object. This step is common for both servers and clients.

```python
service_discovery = await construct_service_discovery(SD_MULTICAST_GROUP, SD_PORT, INTERFACE_IP)
```

The `construct_service_discovery` takes three parameters:
- `multicast_group_ip`: The IP address of the multicast group used for SOME/IP service discovery, typically "224.224.224.245".
- `sd_port`: The port used for SOME/IP service discovery, typically 30490.
- `unicast_ip`: The IP address of the participant's network interface, i.e. "your" IP address.

## Server-Side Parameters
For offering a service instance, a `ServerServiceInstance` is used in someipy. This class is constructed using `construct_server_service_instance` and allows to specify two more service discovery specific parameters. Since these parameters can be set independently for multiple service instances, they are not part of the common parameters above.

```python
    service_instance_temperature = await construct_server_service_instance(
        temperature_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint=(
            ipaddress.IPv4Address(INTERFACE_IP),
            3000,
        ttl=5,
        sd_sender=service_discovery,
        cyclic_offer_delay_ms=2000,
        protocol=TransportLayerProtocol.UDP
    )
```

- The parameter `ttl` specifies the lifetime of the SD offer entries in seconds. These entries are sent cyclically in SD messages by the application offering a service. The offer entries are only valid for `ttl` seconds.
- The parameter `cyclic_offer_delay_ms` specifies the period in milliseconds with which the cyclic SD offer entries are sent.

Since also the subscription has a lifetime (read below), the subscription is cyclically renewed with a *subscribe entry* and a *subscribe ack entry*. If the `ttl` is configured smaller than the `cyclic_offer_delay_ms`, your service appears to be not available for a while. E.g. `ttl` is configured as one second and `cyclic_offer_delay_ms` with 2000ms, the service will not be available for second, until the next cyclic offer entry is sent.

## Client-Side Parameters
For using a service as a client a `ClientServiceInstance` object has to be constructed in someipy which is done using the `construct_client_service_instance` factory function. Since these parameters can be set independently for multiple service instances, they are not part of the common parameters above and are specific to client instances.

```python
client_instance_addition = await construct_client_service_instance(
        service=addition_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint=(ipaddress.IPv4Address(INTERFACE_IP), 3002),
        ttl=5,
        sd_sender=service_discovery,
        protocol=TransportLayerProtocol.UDP
    )
```

- The parameter `ttl` specifies the lifetime of eventgroup subscriptions in seconds. The *subscribe eventgroup entry* is sent from an application that wishes to receive event updates to the publishing application. The `ttl` specifies how long the subscription is valid and the server will send SOME/IP events to the subscribed client. Therefore the subscription is cyclically renewed by sending a *subscribe eventgroup entry* to the server.
