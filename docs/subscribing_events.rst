Subscribing to SOME/IP Events
=============================

SOME/IP Events
--------------

SOME/IP events implement the publish-subscribe concept in SOME/IP. A server offers a service to which one or more clients can subscribe. In case the server sends an event, all subscribed clients will receive the event.

A SOME/IP event is identified through an event ID which is packed into the header of a SOME/IP message. The event ID can be used by multiple services and does not have to be globally unique. The unique identification of an event comes through the combination of service ID, instance ID and event ID.

A SOME/IP event usually carries a serialized payload. For defining the service interface data types and serializing structured data into ``bytes`` follow the article on :doc:`service_interface`.

SOME/IP SD Eventgroups vs. SOME/IP Events
------------------------------------------

In SOME/IP there is also the definition Eventgroups. It is important to understand the difference for setting up a proper SOME/IP communication. If eventgroup and event IDs are mixed up, the service discovery will not be able to subscribe properly.

Eventgroups are only used in **service discovery of SOME/IP** and logically group events together for subscription. Eventgroups only exist at the service discovery level, but never appear in the actual data sent for an event. Once a client subscribed to a service, eventgroups are obsolete.

Grouping events in eventgroups allows clients to subscribe to multiple events at once. For that purpose you could put all your events into a single eventgroup. Then a client can subscribe only to a single eventgroup and will receive notifications for all events. This has the advantage of reduced traffic for service discovery. However, since all events are sent to the client, more bandwidth is used for sending the actual data.

If you want to enable clients to subscribe to single events, create a single eventgroup for each event. Then a client can granularly subscribe to single events. This will require more service discovery traffic, however it may lead to sending only events that are actually used.

Step 1: Define a Service
------------------------

In order to subscribe to a service containing a SOME/IP event, we will define a ``Service`` first. The ``Service`` object will be used afterwards to construct a ``ClientServiceInstance`` object.

The ``Service`` we define contains a single event with ID 0x0123 belonging to the eventgroup with ID 0x0321. If you want to pack more events into the eventgroup, you can pass more IDs in the ``event_ids`` parameter of the ``EventGroup`` constructor. The ``ServiceBuilder`` class is used to build the ``Service`` object for convenience.

.. code-block:: python

   SAMPLE_SERVICE_ID = 0x1234
   SAMPLE_INSTANCE_ID = 0x5678

   temperature_service = (
           ServiceBuilder()
           .with_service_id(SAMPLE_SERVICE_ID)
           .with_major_version(1)
           .build()
       )

Step 2: Instantiate the Service
-------------------------------

The previously defined ``Service`` can be instantiated into one or multiple service instances. Since we want to subscribe to an event, we will instantiate a ``ClientServiceInstance``.
The ``construct_client_service_instance`` is a coroutine since it uses ``asyncio`` internally and therefore has to be ``await``ed.

- You need to pass the instance ID (``SAMPLE_INSTANCE_ID``) of the server service instance to the function.
- The endpoint that is passed is the endpoint (ip address and port) of the client and not of the server.
- The ttl parameter is the lifetime of the subscription in seconds. The subscription is always renewed when the server cyclically offers its service.
- It is assumed that the ``service_discovery`` object was instantiated beforehand. For more information on that topic, read :doc:`service_discovery`.
- You can choose to either use UDP or TCP as the transport protocol. Make sure, that the configuration matches with the client subscribing to the service.

.. code-block:: python

   service_instance_temperature = await construct_client_service_instance(
           service=temperature_service,
           instance_id=SAMPLE_INSTANCE_ID,
           endpoint=(ipaddress.IPv4Address(interface_ip), 3002),
           ttl=5,
           sd_sender=service_discovery,
           protocol=TransportLayerProtocol.UDP,
       )

Step 3: Register a Notification Callback Function
-------------------------------------------------

A callback function has to be registered which will be called when a notification is received from the server. The callback function will be called with a ``SomeIpMessage`` object. This object has a ``payload`` property which are the received bytes. The bytes can be optionally deserialized into a structured message. In case you want to identify for which event the callback was triggered, you can read ``someip_message.header.method_id`` which is the event ID.

Here is an example callback function:

.. code-block:: python

   try:
       print(
           f"Received {len(someip_message.payload)} bytes for event {someip_message.header.method_id}. Try to deserialize.."
       )
       temperature_msg = TemparatureMsg().deserialize(someip_message.payload)
       print(temperature_msg)
   except Exception as e:
       print(f"Error in deserialization: {e}")

The callback function is registered with the ``ClientServiceInstance`` using the ``register_callback`` function:

.. code-block:: python

   service_instance_temperature.register_callback(temperature_callback)

Step 4: Activate Subscription
-----------------------------

As the last step, you finally need to subscribe to eventgroups. The ``subscribe_eventgroup`` will store the passed eventgroup ID internally. When a server offers a service with the corresponding eventgroup ID the ``ClientServiceInstance`` will actually subscribe to the server. The ``subscribe_eventgroup`` function can be called multiple teams with different eventgroup IDs.

.. code-block:: python

   SAMPLE_EVENTGROUP_ID = 0x0321
   service_instance_temperature.subscribe_eventgroup(SAMPLE_EVENTGROUP_ID)

As a last step, a ``ClientServiceInstance`` always has to be attached to a ``ServiceDiscovery`` object. This is not specific to subscribing events. It allows the ``ClientServiceInstance`` to be notified e.g. about incoming service offers.

.. code-block:: python

   service_discovery.attach(service_instance_temperature)
