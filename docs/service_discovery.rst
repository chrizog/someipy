Service Discovery Configuration Parameters
==========================================

What is SOME/IP Service Discovery (SD)?
---------------------------------------

To use a SOME/IP service, a client must know the service location—the IP address and port where the service can be accessed. A server providing a service must know the recipients of event messages. Events are delivered only to subscribers (publish-subscribe).

SOME/IP SD provides these capabilities:

- Locating service instances
- Handling publish-subscribe behavior

SD uses UDP multicast. By joining the multicast group, applications can listen to or send SD messages.

.. image:: images/service_discovery/multicast_service_discovery.png
   :align: center

The offering application periodically sends a SOME/IP SD message containing an offer entry to all multicast participants. The offer entry includes the service location (IP and port), instance ID, service ID, major and minor versions, and a TTL for the offer. Subscribers can send back a SOME/IP SD subscribe entry for the eventgroup, including the instance ID, service ID, major version, eventgroup ID, the subscription TTL, and the client endpoint (IP and port). The server responds with a subscribe_acknowledge entry. This handshake implements publish-subscribe. The actual event messages are delivered to the subscribers.

An alternative is to send a find_service entry to query whether a participant offers a specific service. If offered, the participant responds with an offer_service entry, after which subscription proceeds as above. Participants can also send stop_offer entries to indicate shutdown.

SD messages are SOME/IP messages marked with specific magic numbers. For example, the message ID is 0xFFFF81000 and the protocol and interface version are 0x01.

The SOME/IP SD protocol specification is available `here <https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPServiceDiscoveryProtocol.pdf>`_.

Service Discovery Parameters in the someipy Daemon
----------------------------------------------------
As shown in the someipy Daemon guide, the daemon handles all communication with the SOME/IP network, including service discovery, and uses a specific configuration for SD messages.

The configuration is a JSON file with optional parameters:

.. code-block:: json

   {
     "sd_address": "224.224.224.245",
     "sd_port": 30490,
     "interface": "127.0.0.1",
   }

- ``sd_address``: Multicast address for SD. Default: "224.224.224.245".
- ``sd_port``: SD port. Default: 30490.
- ``interface``: Network interface IP the daemon listens on. Default: "127.0.0.1".

Server-Side Parameters
----------------------

Offering a service uses ``ServerServiceInstance``. The constructor accepts SD-related parameters:

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

- ``ttl``: Lifetime of the SD offer entries in seconds. The offer entries are repeated while valid.
- ``cyclic_offer_delay_ms``: Interval in milliseconds between consecutive SD offer messages.

Ensure ``ttl`` > ``cyclic_offer_delay_ms``; otherwise the service may appear unavailable briefly (for example, ttl=1 s and cyclic_offer_delay_ms=2000 ms).

Client-Side Parameters
----------------------

When subscribing to eventgroups as a client, the subscription lifetime is set with ``ttl_subscription_seconds`` in ``subscribe_eventgroup``. If not renewed, the subscription will be removed after this period. Ensure ``ttl_subscription_seconds`` > ``cyclic_offer_delay_ms``; otherwise, the subscription may be removed before the next offer and events will not be delivered.

.. code-block:: python

   service_instance_temperature.subscribe_eventgroup(temperature_eventgroup, ttl_subscription_seconds=5.0)
