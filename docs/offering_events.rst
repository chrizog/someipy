Offering SOME/IP Events
=======================

SOME/IP Events
--------------

SOME/IP events implement the publish-subscribe concept in SOME/IP. A server offers a service to which one or more clients can subscribe. When the server sends an event, all subscribed clients will receive the event.

A SOME/IP event is identified through an event ID which is packed into the header of a SOME/IP message. The event ID can be used by multiple services and does not have to be globally unique. The unique identification of an event comes through the combination of service ID, instance ID, and event ID.

A SOME/IP event usually carries a serialized payload. For defining the service interface data types and serializing structured data into ``bytes`` follow the article on :doc:`service_interface`.

SOME/IP SD Eventgroups vs. SOME/IP Events
-----------------------------------------

In SOME/IP there is also the term of Eventgroups. It's important to understand the difference for setting up a proper SOME/IP communication. If eventgroup and event IDs are mixed up, the service discovery will not be able to create the subscription properly.

Eventgroups are only used in **service discovery of SOME/IP** and group events together for logically subscription. Eventgroups only exist at the service discovery level, but never appear in the actual data sent for an event. Once a client subscribed to a service, eventgroups are obsolete.

Grouping events in eventgroups allows clients to subscribe to multiple events at once reducing the bandwidth used for service discovery. For that purpose you could put all your events into a single eventgroup. Then a client can subscribe to a single eventgroup and will receive notifications for all events. This has the advantage of reduced traffic for service discovery. However, since all events are sent to the client even if they may not need all events for operation, more bandwidth is used for sending the actual data.

If you want to enable clients to subscribe to single events more granularly, create multiple eventgroups or even one eventgroup for each event. This will require more service discovery traffic; however, it may lead to sending only events that are actually needed by a particular client.

Step 1: Connect to the someipy Daemon
------------------------------------------------

The first step is to connect to the someipy daemon. The daemon is a separate process communicating with the application using someipy via a Unix Domain Socket (UDS). The daemon is responsible for handling all communication with the SOME/IP network, including service discovery and message sending/receiving.

.. code-block:: python

    someipy_daemon = await connect_to_someipy_daemon()

In case, a non-default Unix Domain Socket path is used, a config dictionary can be passed to the *connect_to_someipy_daemon* function.


Step 2: Define a Service
------------------------

In order to offer a service containing a SOME/IP event, we will define a ``Service`` first, which is used afterwards to instantiate a ``ServerServiceInstance``. The ``Service`` will contain a single event with ID 0x0123 in the eventgroup with ID 0x0321. The ``ServiceBuilder`` class is used to build the ``Service`` object. Note, that the transport protocol (TCP or UDP) is defined per event and not per service. This means that you can have events in the same service using different transport protocols.

.. code-block:: python

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

The previously defined ``Service`` can be instantiated as one or multiple service instances. Since we are offering events as a server, a ``ServerServiceInstance`` object is created.

The constructor of the ``ServerServiceInstance`` class requires several parameters:

- daemon: The *someipy_daemon* object (defined above)
- service: The *Service* object (defined above)
- instance_id: A service instance ID (0x5678 in this example)
- endpoint_ip: The IP address of the network interface on which the service is offered (127.0.0.1 in this example)
- endpoint_port: The port on which the service is offered (3000 in this example)
- ttl: The time-to-live for the service discovery entries (5 seconds in this example)
- cyclic_offer_delay_ms: The period of the cylic offer service SD messages (2000 ms in this example)

.. code-block:: python

   service_instance_temperature = ServerServiceInstance(
        daemon=someipy_daemon,
        service=temperature_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint_ip=interface_ip,
        endpoint_port=3000,
        ttl=5,
        cyclic_offer_delay_ms=2000,
    )

The parameters ``ttl`` and ``cyclic_offer_delay_ms`` are described in detail in :doc:`service_discovery`.

.. note::
   **Multiple service instances:** If you want to offer multiple service instances in the same application, you would simply construct another service instance here. Read the example application `offer_multiple_services.py <https://github.com/chrizog/someipy/blob/v2.0.0/example_apps/offer_multiple_services.py>`_ for more details.

Step 4: Announce the Service via Service Discovery
--------------------------------------------------

At this point, clients are not able to subscribe to the ``ServerServiceInstance`` and to its eventgroup with ID ``0x0321``. The next step is to use ``start_offer`` to announce the service instance to potential clients. The ``start_offer`` function will communicate with the someipy daemon which will take care of periodically sending service discovery messages with offer entries.

.. code-block:: python

   await service_instance_temperature.start_offer()

Step 5: Sending Event Notifications to Clients
-----------------------------------------------

Now that the service is offered, clients can subscribe to the eventgroup with ID ``0x0321`` and the server can send events to the clients. The ``send_event`` function expects a ``bytes``-object which is typically created by serialized structured data:

.. code-block:: python

   payload = tmp_msg.serialize()
   service_instance_temperature.send_event(
       SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload
   )

Typical sending strategies for SOME/IP events are **cyclic updates** or **update on change**. Update on change means that an event is sent whenever the contained value changes. In a cyclic update, the event would be sent even if the contained data has not changed since the last publish.

Step 6: Shutdown the Application
----------------------------

At the end of your application, make sure to stop offering the service instance and disconnect from the someipy daemon to ensure a clean shutdown of the application.

.. code-block:: python

   await service_instance_temperature.stop_offer()
   await someipy_daemon.disconnect_from_daemon()