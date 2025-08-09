Subscribing to SOME/IP Events
=============================

SOME/IP Events
--------------

SOME/IP events implement the publish-subscribe concept in SOME/IP. A server offers a service to which one or more clients can subscribe. When the server sends an event, all subscribed clients will receive the event.

A SOME/IP event is identified through an event ID which is packed into the header of a SOME/IP message. The event ID can be used by multiple services and does not have to be globally unique. The unique identification of an event comes through the combination of service ID, instance ID, and event ID.

A SOME/IP event usually carries a serialized payload. For defining the service interface data types and serializing structured data into ``bytes`` follow the article on :doc:`service_interface`.

SOME/IP SD Eventgroups vs. SOME/IP Events
------------------------------------------

In SOME/IP there is also the definition of Eventgroups. It is important to understand the difference for setting up a proper SOME/IP communication. If eventgroup and event IDs are mixed up, the service discovery will not be able to subscribe properly.

Eventgroups are only used in **service discovery of SOME/IP** and logically group events together for subscription. Eventgroups only exist at the service discovery level, but never appear in the actual data sent for an event. Once a client subscribed to a service, eventgroups are obsolete.

Grouping events in eventgroups allows clients to subscribe to multiple events at once. For that purpose you could put all your events into a single eventgroup. Then a client can subscribe only to a single eventgroup and will receive notifications for all events. This has the advantage of reduced traffic for service discovery. However, since all events are sent to the client, more bandwidth is used for sending the actual data.

If you want to enable clients to subscribe to single events, create a single eventgroup for each event. Then a client can granularly subscribe to single events. This will require more service discovery traffic; however, it may lead to sending only events that are actually used.

Step 1: Connect to the someipy Daemon
------------------------------------------------

The first step is to connect to the someipy daemon. The daemon is a separate process communicating with the application using someipy via a Unix Domain Socket (UDS). The daemon is responsible for handling all communication with the SOME/IP network, including service discovery and message sending/receiving.

.. code-block:: python

    someipy_daemon = await connect_to_someipy_daemon()

In case, a non-default Unix Domain Socket path is used, a config dictionary can be passed to the *connect_to_someipy_daemon* function.

Step 2: Define a Service
------------------------

In order to subscribe to a service containing a SOME/IP event, we will define a ``Service`` first. The ``Service`` object will be used afterwards to construct a ``ClientServiceInstance`` object.

The ``Service`` we define contains a single event with ID 0x0123 belonging to the eventgroup with ID 0x0321. The ``ServiceBuilder`` class is used to build the ``Service`` object for convenience.

.. code-block:: python

   from someipy import ServiceBuilder, EventGroup, Event, TransportLayerProtocol

   SAMPLE_SERVICE_ID = 0x1234
   SAMPLE_INSTANCE_ID = 0x5678
   SAMPLE_EVENTGROUP_ID = 0x0321
   SAMPLE_EVENT_ID = 0x0123

   temperature_event = Event(id=SAMPLE_EVENT_ID, protocol=TransportLayerProtocol.UDP)

   temperature_eventgroup = EventGroup(
       id=SAMPLE_EVENTGROUP_ID, events=[temperature_event]
   )

   temperature_service = (
       ServiceBuilder()
       .with_service_id(SAMPLE_SERVICE_ID)
       .with_major_version(1)
       .with_eventgroup(temperature_eventgroup)
       .build()
   )

Step 3: Instantiate the Service
-------------------------------

The previously defined ``Service`` can be instantiated as a ``ClientServiceInstance``. This instance will be used to subscribe to the eventgroup and receive events. The ``endpoint_ip`` and ``endpoint_port`` parameters are the IP address and port on which the events shall be received.

.. code-block:: python

   from someipy.client_service_instance import ClientServiceInstance

   service_instance_temperature = ClientServiceInstance(
       daemon=someipy_daemon,
       service=temperature_service,
       instance_id=SAMPLE_INSTANCE_ID,
       endpoint_ip=interface_ip,
       endpoint_port=3002,
   )

Step 4: Register a Notification Callback Function
-------------------------------------------------

Register a callback function that will be called when an event notification is received. The callback receives the event ID and payload bytes:

.. code-block:: python

   def temperature_callback(event_id: int, event_payload: bytes) -> None:
       try:
           print(f"Received {len(event_payload)} bytes for event 0x{event_id:04x}")
           temperature_msg = TemperatureMsg().deserialize(event_payload)
           print(temperature_msg)
       except Exception as e:
           print(f"Error in deserialization: {e}")

   service_instance_temperature.register_callback(temperature_callback)

Step 5: Activate Subscription
-----------------------------

Subscribe to the eventgroup with a time-to-live (TTL) for the subscription:

.. code-block:: python

   service_instance_temperature.subscribe_eventgroup(temperature_eventgroup, 5.0)

The TTL defines how long the subscription is valid. After this time, the subscription will be automatically removed unless it is renewed. The details of the service discovery parameters are described in :doc:`service_discovery`.

Step 6: Maintain Connection
---------------------------

Keep the application running to maintain the connection and receive events. At the end of your application, make sure to disconnect from the someipy daemon to ensure a clean shutdown of the application.

.. code-block:: python

   try:
       await asyncio.Future()  # Run forever
   except asyncio.CancelledError:
       print("Shutting down...")
   finally:
       await someipy_daemon.disconnect_from_daemon()
