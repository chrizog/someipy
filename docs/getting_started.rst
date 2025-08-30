Getting Started
=================

This guide demonstrates how to create a SOME/IP service using someipy that broadcasts temperature measurements every second using SOME/IP events. The complete example is available in the `example applications on GitHub <https://github.com/chrizog/someipy/blob/v2.0.0/example_apps/send_events_udp.py>`_.

Prerequisites
----------------

- Linux (Ubuntu 22.04 or equivalent)
- Python 3.8+
- Network interface with multicast support

Installation
------------

Install someipy from PyPI:

.. code-block:: bash

   pip3 install someipy

Service Data Type Definition
---------------------------

Define the temperature data structure using Python dataclasses. No IDL files required.

Create ``temperature_msg.py``:

.. code-block:: python

   from dataclasses import dataclass
   from someipy.serialization import (
       SomeIpPayload,
       SomeIpFixedSizeArray,
       Uint8,
       Uint64,
       Float32,
   )

   @dataclass
   class Version(SomeIpPayload):
       major: Uint8
       minor: Uint8

       def __init__(self):
           self.major = Uint8()
           self.minor = Uint8()

   @dataclass
   class TemperatureMsg(SomeIpPayload):
       version: Version
       timestamp: Uint64
       measurements: SomeIpFixedSizeArray

       def __init__(self):
           self.version = Version()
           self.timestamp = Uint64()
           self.measurements = SomeIpFixedSizeArray(Float32, 4)

Asyncio App Implementation
--------------------------

someipy is an `asyncio <https://docs.python.org/3/library/asyncio.html>`_ based Python library, since multiple concurrent tasks are running in the SOME/IP implementation, e.g. for communicating with the someipy daemon.

First we will set up our application's structure. Typically in an asyncio application, a main coroutine-function is added which is executed using `asyncio.run <https://docs.python.org/3/library/asyncio-runner.html#id1>`_. Our application's logic will be added inside the main coroutine-function *async def main*.

Create ``send_events_udp.py`` with the following structure:

.. code-block:: python

   import asyncio
   import ipaddress
   import logging

   async def main():

       # .. our application will go here

       except asyncio.CancelledError:
           print("Application cancelled...")
       finally:
           print("Cleanup...")
       print("End main task...")

   if __name__ == "__main__":
       try:
           asyncio.run(main())
       except KeyboardInterrupt:
           pass

someipy Logging
---------------

At the beginning of the application the someipy logging level is configured. Logging levels can be chosen from the `Python3 logging module levels <https://docs.python.org/3/library/logging.html#logging-levels>`_.

.. code-block:: python

   import logging

   async def main():
       # .. our application will go here
       set_someipy_log_level(logging.DEBUG)


Connect to the someipy Daemon
-----------------------------

The next step is to connect to the someipy daemon. The daemon is a separate process communicating with the application using someipy via a Unix Domain Socket (UDS). The daemon is responsible for handling all communication with the SOME/IP network, including service discovery and message sending/receiving.

.. code-block:: python

    someipy_daemon = await connect_to_someipy_daemon()

In case, a non-default Unix Domain Socket path is used, a config dictionary can be passed to the *connect_to_someipy_daemon* function.


Defining the SOME/IP Service
----------------------------

For offering a SOME/IP service, you first define a `Service <https://github.com/chrizog/someipy/blob/v1.0.0/src/someipy/service.py#L27>`_ containing **EventGroups** or **Methods** using the `ServiceBuilder <https://github.com/chrizog/someipy/blob/v2.0.0/src/someipy/service.py#L65>`_. Afterwards the Service can be instantiated as a Server- or Client-Instance.

In this example, a *temperature_service* with service ID 0x1234 containing a single event group with ID 0x0321 which in turn contains a single event with ID 0x0123. The service has a major version 1 and minor version 0:

.. code-block:: python

   from someipy import ServiceBuilder, EventGroup

   async def main():
       # ...
       SAMPLE_SERVICE_ID = 0x1234
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
       # ...

Instantiating the SOME/IP Service
---------------------------------

Once the `Service <https://github.com/chrizog/someipy/blob/v2.0.0/src/someipy/service.py#L27>`_ is defined it can be instantiated multiple times.
For offering a `Service <https://github.com/chrizog/someipy/blob/v20.0/src/someipy/service.py#L27>`_ in someipy the `ServerServiceInstance <https://github.com/chrizog/someipy/blob/v1.0.0/src/someipy/server_service_instance.py>`_ class is used. For using a service as client the `ClientServiceInstance <https://github.com/chrizog/someipy/blob/v1.0.0/src/someipy/client_service_instance.py>`_ class is used.

The constructor of the *ServerServiceInstance* class requires several parameters:
- daemon: The *someipy_daemon* object (defined above)
- service: The *Service* object (defined above)
- instance_id: A service instance ID (0x5678 in this example)
- endpoint_ip: The IP address of the network interface on which the service is offered (127.0.0.1 in this example)
- endpoint_port: The port on which the service is offered (3000 in this example)
- ttl: The time-to-live for the service discovery entries (5 seconds in this example)
- cyclic_offer_delay_ms: The period of the cylic offer service SD messages (2000 ms in this example)

Afterwards, the the SOME/IP service can be offered using the *start_offer* method. When exiting your application make sure to use *stop_offer* method on the service instance.

.. code-block:: python

   from someipy import TransportLayerProtocol, construct_server_service_instance

   async def main():
        # ...
        SAMPLE_INSTANCE_ID = 0x5678

        service_instance_temperature = ServerServiceInstance(
            daemon=someipy_daemon,
            service=temperature_service,
            instance_id=SAMPLE_INSTANCE_ID,
            endpoint_ip=interface_ip,
            endpoint_port=3000,
            ttl=5,
            cyclic_offer_delay_ms=2000,
        )

    # After constructing a ServerServiceInstances the start_offer method has to be called. This will start an internal timer,
    # which will periodically send Offer service entries with a period of "cyclic_offer_delay_ms" which has been passed above
    print("Start offering service..")
    await service_instance_temperature.start_offer()

    # ...
    # Before exiting the app: service_instance_temperature.stop_offer()

Sending Events
--------------

Now it is time to send events to subscribed clients. First some data has to be prepared: Import and instantiate the *TemperatureMsg* and fill it with some data:

.. code-block:: python

   from someipy.serialization import Uint8, Uint64, Float32
   from temperature_msg import TemperatureMsg

   async def main():
       # ...
       tmp_msg = TemperatureMsg()

       tmp_msg.version.major = Uint8(1)
       tmp_msg.version.minor = Uint8(0)
       tmp_msg.measurements.data[0] = Float32(20.0)
       tmp_msg.measurements.data[1] = Float32(21.0)
       tmp_msg.measurements.data[2] = Float32(22.0)
       tmp_msg.measurements.data[3] = Float32(23.0)
       # ...

Afterwards we will start an endless loop sending data every second using the *send_event* method on the service instance. The *send_event* method takes a bytes-object which can be retrieved serializing the *TemperatureMsg*.

.. code-block:: python

   async def main():
       # ...

       try:
           # Cyclically send events in an endless loop...
           while True:
               await asyncio.sleep(1)
               tmp_msg.timestamp = Uint64(tmp_msg.timestamp.value + 1)
               payload = tmp_msg.serialize()
               service_instance_temperature.send_event(
                   SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload
               )

       except asyncio.CancelledError:
           print("Stop offering service...")
           await service_instance_temperature.stop_offer()
       finally:
           print("Service Discovery close...")
           service_discovery.close()

           # ...

Network Configuration
---------------------

If you are using Linux, make sure to join the multicast group for your network interface used for the service discovery before starting the application. In our example we use 224.224.224.245 and the loopback interface. Make sure to adjust the command for your project. Otherwise, it will not be possible for clients to subscribe to your SOME/IP service.

.. code-block:: bash

   sudo ip addr add 224.224.224.245 dev lo autojoin
   python3 send_events_udp.py

Start the someipy Daemon
-----------------------------

Before running the application, ensure that the someipy daemon is running. The daemon can be started using the following command:

.. code-block:: bash

   someipyd --config someipyd.json

The .json configuration file is optional and can be omitted.

Start the Application
----------------------

Run the application using Python 3:

.. code-block:: bash

   python3 send_events_udp.py
