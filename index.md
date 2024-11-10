---
layout: default
title: Getting Started
nav_order: 1
---

# Using SOME/IP has never been easier
{: .fs-9 }
With someipy, spinning up a SOME/IP service only takes five minutes.
{: .fs-6 .fw-300 }

[Get started now](#getting-started){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[View it on GitHub](https://github.com/chrizog/someipy){: .btn .fs-5 .mb-4 .mb-md-0 }

someipy is a Python library implementing the SOME/IP protocol, including the SOME/IP Service Discovery. It's perfectly suited for fast prototyping of applications that need to provide SOME/IP services to other ECUs or use SOME/IP services from other ECUs.

someipy also supports serialization and deserialization of SOME/IP payloads, a unique feature of someipy.

someipy is still under development; therefore, it does not yet support all features of the SOME/IP and SOME/IP Service Discovery protocol specification.

someipy is based on the specification version of R22-11:
- [SOME/IP Protocol Specification](https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPProtocol.pdf)
- [SOME/IP Service Discovery Protocol Specification](https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPServiceDiscoveryProtocol.pdf)

The library is developed and tested on Ubuntu 22.04 and using Python 3.8.

# For Inquiries

For any questions, feature requests, bug reports, or general support regarding someipy, please reach out to us using one of the following methods:
> [someipy.package@gmail.com](mailto:someipy.package@gmail.com)  
[LinkedIn](https://www.linkedin.com/in/ch-herzog/)

# Getting Started

In this section, you will learn how to setup someipy and write an application that offers a service with an event which is fired every second. A datatype to be serialized for the event data is defined as well.

Requirements:
- Linux, e.g. Ubuntu 22.04
- Python >= Python 3.8

The full application source code can also be found in the [someipy example applications](https://github.com/chrizog/someipy/blob/master/example_apps/send_events_udp.py).

## Installation

someipy can be installed from the [Python Package Index](https://pypi.org/project/someipy/) using pip. someipy has no further dependencies, allowing a smooth integration into your project.

```bash
pip3 install someipy
```

## Service Datatype Definition

Before implementing the actual application, we will first define a datatype called *TemperatureMsg* to be used for the SOME/IP event. In someipy no special IDL (interface description language) is needed like Franca IDL or ARXML files. The interface datatypes are simply written in Python.

We will define a datatype *TemperatureMsg*, that consists of another datatype *Version*, a 64-bit timestamp and an array containing four 32-bit floating type measurements. The datatype is declared by inheriting from **SomeIpPayload** which is imported from **someipy.serialization**. The [someipy.serialization module](https://github.com/chrizog/someipy/blob/master/src/someipy/serialization.py) also provides various datatypes that need to be used for the interface definition like **Uint8**, **Uint32**, **Float32** or **SomeIpFixedSizeArray**.

Create a new file *temperature_msg.py* with the following content:

```python
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
class TemparatureMsg(SomeIpPayload):
    version: Version
    timestamp: Uint64
    measurements: SomeIpFixedSizeArray

    def __init__(self):
        self.version = Version()
        self.timestamp = Uint64()
        self.measurements = SomeIpFixedSizeArray(Float32, 4)
```

## asyncio App Implementation

someipy is an [asyncio](https://docs.python.org/3/library/asyncio.html) based Python library, since multiple concurrent tasks are running in the SOME/IP implementation for service discovery, waiting for new clients or waiting on new data.

First we will setup our application's structure. Typically in an asyncio application, a main coroutine-function is added which is executed using [asyncio.run](https://docs.python.org/3/library/asyncio-runner.html#id1). Our application's logic will be added inside the main coroutine-function *async def main*.

Create a new file called *send_events_udp.py* with the following content:

```python
import asyncio
import ipaddress
import logging

async def main():

    # .. our application will go here

    except asyncio.CancelledError:
        print("Application cancelled..")
    finally:
        print("Cleanup..")
    print("End main task..")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

## someipy Logging

At the beginning of the applicatino the someipy logging level is configured. Logging levels can be chosen from the [Python3 logging module levels](https://docs.python.org/3/library/logging.html#logging-levels).

```python
import logging

async def main():
    # .. our application will go here
    set_someipy_log_level(logging.DEBUG)
```

## Starting Service Discovery

Before defining and instatiating our SOME/IP service, a *ServiceDiscoveryProtocol* class has to be instantiated and started. The *ServiceDiscoveryProtocol* object will take care of receiving and sending all service discovery messages on the service discovery multicast group which is typically *224.224.224.245* and on port 30490. Also the IP address of the own used network interface has to be provided. In this example localhost is used and *127.0.0.1* is passed. The construction can be done using the factory function *construct_service_discovery* from the module *someipy.service_discovery*.

Make sure to close the service discovery at the end of your application to ensure ports are freed correctly using the *close()* method.

```python
from someipy.service_discovery import construct_service_discovery

async def main():
    # .. our application will go here
    set_someipy_log_level(logging.DEBUG)

    SD_MULTICAST_GROUP = "224.224.224.245"
    SD_PORT = 30490
    INTERFACE_IP = "127.0.0.1"
    service_discovery = await construct_service_discovery(
            SD_MULTICAST_GROUP, SD_PORT, INTERFACE_IP
        )

    # ...
    finally:
        print("Service Discovery close..")
        service_discovery.close()
```

## Defining the SOME/IP Service

For offering a SOME/IP service, you first define a [Service](https://github.com/chrizog/someipy/blob/master/src/someipy/service.py#L27) containing **EventGroups** or **Methods** using the [ServiceBuilder](https://github.com/chrizog/someipy/blob/master/src/someipy/service.py#L65). Afterwards the Service can be instantiated as a Server- or Client-Instance.

In this example a *temparature_service* with service id 0x1234 containing a single event group with id 0x0321 which in turn contains a single event with id 0x0123. The service has a major version 1 and minor version 0:

```python
from someipy import ServiceBuilder, EventGroup

async def main():
    # ...
    service_discovery = await construct_service_discovery(
            SD_MULTICAST_GROUP, SD_PORT, INTERFACE_IP
        )
    
    SAMPLE_SERVICE_ID = 0x1234
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
    # ...
```

## Instantiating the SOME/IP Service


Once the [Service](https://github.com/chrizog/someipy/blob/master/src/someipy/service.py#L27) is defined it can be instantiated multiple times.
For offering a [Service](https://github.com/chrizog/someipy/blob/master/src/someipy/service.py#L27) in someipy the [ServerServiceInstance](https://github.com/chrizog/someipy/blob/master/src/someipy/server_service_instance.py) class is used. For using a service as client the [ClientServiceInstance](https://github.com/chrizog/someipy/blob/master/src/someipy/client_service_instance.py) class is used.

Since the construction of [ServerServiceInstance](https://github.com/chrizog/someipy/blob/master/src/someipy/server_service_instance.py) is not trivial, the *construct_server_service_instance* factory function is provided. Following information has to be passed to the function:

- The *Service* object (defined above)
- A service instance ID (0x5678 in this example)
- An endpoint tuple consisting of IP and port on which the service is offered (127.0.0.1 and port 3000 in this example)
- The TTL (time to live) of the service discovery offer messages (5 seconds in this example)
- The *ServiceDiscoveryProtocol* object (defined above)
- The period of the service discovery offer messages in milliseconds (2000 ms in this example)
- The protocol of the service instance: Either TransportLayerProtocol.UDP or TransportLayerProtocol.TCP

After instantiating the Service using the *construct_server_service_instance* function, the returned *ServerServiceInstance* has to be attached to the *ServiceDiscoveryProtocol* object. This is needed so that the *ServerServiceInstance* is informed about subscriptions by clients.

Finally the SOME/IP service can be offered using the *start_offer* method. When exiting your application make sure to use *stop_offer* method on the service instance.

```python
from someipy import TransportLayerProtocol, construct_server_service_instance

async def main():
    # ...

    SAMPLE_INSTANCE_ID = 0x5678
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
        protocol=TransportLayerProtocol.UDP
    )

    # The service instance has to be attached to the ServiceDiscoveryProtocol object, so that 
    # the service instance is notified about subscriptions from other ECUs
    service_discovery.attach(service_instance_temperature)
    
    # Starts sending periodic SD offer messages
    service_instance_temperature.start_offer()

    # ...
    # Before exiting the app: service_instance_temperature.stop_offer()
```

## Sending Events

Until now you have defined
- a datatype *TemperatureMsg*
- started the service discovery
- defined a SOME/IP dervice called *temperature_service* containing a single event
- and instantiated and offered the service using a [ServerServiceInstance](https://github.com/chrizog/someipy/blob/master/src/someipy/server_service_instance.py) object.

Now it is time to send events to subscribed clients. First some data has to be prepared: Import and instantiate the *TemperatureMsg* and fill it with some data:

```python
from someipy.serialization import Uint8, Uint64, Float32
from temperature_msg import TemparatureMsg

async def main():
    # ...
    tmp_msg = TemparatureMsg()

    tmp_msg.version.major = Uint8(1)
    tmp_msg.version.minor = Uint8(0)
    tmp_msg.measurements.data[0] = Float32(20.0)
    tmp_msg.measurements.data[1] = Float32(21.0)
    tmp_msg.measurements.data[2] = Float32(22.0)
    tmp_msg.measurements.data[3] = Float32(23.0)
    # ...
```

Afterwards we will start an endless loop sending data every second using the *send_event* method on the service instance. The *send_event* method takes a bytes-object which can be retrieved serializing the *TemperatureMsg*.

```python
async def main():
    # ...

    try:
        # Cyclically send events in an endless loop..
        while True:
            await asyncio.sleep(1)
            tmp_msg.timestamp = Uint64(tmp_msg.timestamp.value + 1)
            payload = tmp_msg.serialize()
            service_instance_temperature.send_event(
                SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload
            )

    except asyncio.CancelledError:
        print("Stop offering service..")
        await service_instance_temperature.stop_offer()
    finally:
        print("Service Discovery close..")
        service_discovery.close()

        # ...
```

## Starting The Application

If you are using Linux, make sure to join the multicast group for your network interface used for the service discovery before starting the applicaiton. In our example we use 224.224.224.245 and the loopback interface. Make sure to adjust the command for your project. Otherwise it will not be possible for clients to subscribe to your SOME/IP service.

```bash
sudo ip addr add 224.224.224.245 dev lo autojoin
```

Afterwards start your app:

```bash
python3 send_events_udp.py
```

## Running Two Applications On The Same Machine

It is recommended two have one someipy application on a machine that communicates to other PCs or ECUs. But, in case you want to run two applications on the same machine, they should use different interfaces, i.e. bind to different IP addresses. If the two applications shall communicate locally, you can add another IP address to the localhost interface, e.g. 127.0.0.2.

```bash
sudo ip addr add 127.0.0.2/24 dev lo
```

Afterwards start one application working with 127.0.0.1 and the other application with 127.0.0.2:

```bash
python3 send_events_udp.py --interface_ip 127.0.0.1
python3 receive_events_udp.py --interface_ip 127.0.0.2
```