Service Discovery Configuration Parameters
==========================================

What is SOME/IP Service Discovery (SD)?
---------------------------------------

If a client needs to use a SOME/IP service, e.g., to call a method of a service, it needs to know the location of the service, i.e., on which IP address and on which port the service can be accessed. Vice versa, a server providing a service has to know to which receivers event messages have to be sent. Events only have to be sent to receivers that subscribed to the event beforehand (publish-subscribe pattern).

SOME/IP service discovery primarily offers exactly these two explained features:

- **Locating service instances**
- **Handling the publish-subscribe behavior**

SOME/IP service discovery consists of specific messages that are sent via UDP to a multicast group. By joining this specific multicast group, all applications are able to listen to service discovery messages or send service discovery messages to all participants by themselves.

The following image shows the difference between usual SOME/IP messages (right-hand side) and the SOME/IP service discovery messages sent via IP multicast.

.. image:: images/service_discovery/multicast_service_discovery.png
   :align: center

The application offering the service instance cyclically sends a SOME/IP SD message with a so-called *offer entry* to all other participants in the multicast group. The *offer entry* contains the service instance location (IP address and port), the instance ID, service ID, major and minor version, and a time-to-live (TTL) of the offer. Participants that want to subscribe to the eventgroup of this offered service instance can send back a SOME/IP SD *subscribe eventgroup entry*. The subscribe eventgroup entry includes the service instance ID, the service ID, the major version, the eventgroup ID, the lifetime of the subscription (time-to-live), and most importantly the endpoint (IP address and port) of the client. The client will receive the SOME/IP events on this endpoint from the server. The server offering the service will answer this with a message containing a *subscribe acknowledge* entry. By using this type of handshake, the publish-subscribe pattern is implemented in SOME/IP. On the right-hand side of the image, you can see that the actual SOME/IP messages containing events are only delivered to two subscribers.

Another way of locating a service is to send a *find service* entry to actively ask if another participant in the network offers a specific service. If a participant offers the requested service, it will answer with an *offer service* entry and the subscription happens as described above afterwards. Participants can also send *stop offer* entries to indicate to all participants that the service is shutdown.

Service discovery messages are actually SOME/IP messages, but filled with specific magic numbers in order to mark the messages as service discovery messages. E.g. service discovery messages have the message ID set to 0xFFFF81000 and protocol and interface version set to 0x01.

The specification of the SOME/IP service discovery protocol can be found `here <https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPServiceDiscoveryProtocol.pdf>`_.

Service Discovery Parameters in the someipy Daemon
------------------------------------------------------
As shown in the :doc:`someipy Daemon guide <someipy_daemon>`, the daemon is responsible for handling all communication with the SOME/IP network, including service discovery and message sending/receiving. The daemon uses a specific configuration for the service discovery messages, which can be set in the daemon's configuration file.

The configuration file is a JSON file that contains the following optional parameters:

.. code-block:: json

   {
    "sd_address": "224.224.224.245",
    "sd_port": 30490,
    "interface": "127.0.0.1",
  }


- ``sd_address``: The IP address of the multicast group used for SOME/IP service discovery. The default value is "224.224.224.245".
- ``sd_port``: The port used for SOME/IP service discovery. The default value is 30490.
- ``interface``: The IP address of the network interface on which the daemon listens for service discovery messages. The default value is "127.0.0.1".

Server-Side Parameters
----------------------

For offering a service instance, a ``ServerServiceInstance`` is used in someipy. The constructor of this class allows to specify two service discovery related parameters:

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

- ``ttl``: The lifetime of the SD offer entries in seconds. The offer entries are sent cyclically in SD messages by the application offering a service. The offer entries are only valid for ``ttl`` seconds.
- ``cyclic_offer_delay_ms``: The period in milliseconds with which the cyclic SD offer entries are sent. This is the delay between two consecutive service discovery messages that contain the offer entries.

Make sure that the ``ttl``is configured larger than the ``cyclic_offer_delay_ms``. If the ``ttl`` is smaller than the ``cyclic_offer_delay_ms``, your service appears to be not available for a while. E.g., if ``ttl`` is configured as one second and ``cyclic_offer_delay_ms`` with 2000ms, the service will not be available for a second until the next cyclic offer entry is sent.


Client-Side Parameters
----------------------

When subscribing to eventgroups as a client, the lifetime of the subscription has to be specified. This is done by the ``ttl_subscription_seconds`` parameter of the ``subscribe_eventgroup`` function of the ``ClientServiceInstance`` class. In case the subscription is not renewed, the subscription will be removed after this time. Ensure that the ``ttl_subscription_seconds`` is larger than the ``cyclic_offer_delay_ms`` of the server offering the service. If the ``ttl_subscription_seconds`` is smaller than the ``cyclic_offer_delay_ms``, the subscription will be removed before the next cyclic offer entry is sent, and the client will not receive any events.

.. code-block:: python

   service_instance_temperature.subscribe_eventgroup(temperature_eventgroup, ttl_subscription_seconds=5.0)
