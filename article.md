Everybody needs a "five minutes" article to get started with a new topic. Here is a quick overview about SOME/IP.

## SOME/IP

SOME/IP stands for "**S**calable service-**O**riented **M**iddlewar**E** over **IP**". It is a communication protocol which targets embedded projects and typically the automotive industry. It is driven by the AUTOSAR (**AUT**omotive **O**pen **S**ystem **AR**chitecture) consortium. Therefore you can find the specification of the SOME/IP communication protocol on [autosar.org](autosar.org), e.g. [Release 22-11](https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPProtocol.pdf).

## Use Cases

SOME/IP is typically used for **inter-ECU** communication. Since SOME/IP works over UDP or TCP, it does not matter which operating system is running on the ECUs or PCs. It could Linux, Windows, QNX, AUTOSAR Classic or even a bare-metal microcontroller as long as UDP or TCP is supported.

For **intra-ECU** communication, using an IPC mechanism is recommended. The SOME/IP serialization for communication on the same ECU is not needed. Therefore an IPC mechanism is the better choice, e.g. Unix Domain Sockets or Shared Memory communication.

Here is an example network topology showing ECUs and PCs using different operating operating systems. The devices could be connected via switched Ethernet.

![Network Topology for SOME/IP](./network_topology.svg)

## Services

In SOME/IP everything is based on **Services**. A service is a functionality offered by an ECU (= server). A Server can offer multiple services. Clients, i.e. other ECUs can use the offered services.

### Methods

For example one ECU could offer a "Calculator service" via SOME/IP. Clients could call the Calculator Service remotely and pass an operation code (add/subtract/multiply/divide) and two operands. The Server will calculate the result and send back a response to the calling client. This type of Service is called a **Method** in SOME/IP. It describes a request-response-communication.

### Notification Events 

Another type of Services are Notification Events. If one ECU has a button connected and wants to notify other ECUs everytime the button is pressed, it can offer a SOME/IP containing an Event. Other ECUs can subscribe to this service and will receive a notification everytime the button is pressed. Notification Events in SOME/IP describe a publish/subscribe-communication.

### Services, Instances and IDs

In SOME/IP Services can be seen as a schema similar to a class in object oriented programming. Services are instantiated into Service instances allowing ECUs to offer multiple instances of the same service. E.g. if there a three buttons connected, the ECU could simply offer three service instances all providing the "button press service".

Services, Instances, Methods and Events are identified by IDs (numbers) in SOME/IP. In other middlewares, e.g. in ROS (Robot Operating System) instances (ROS topics) are identified by names.

## On-wire serialization

Besides providing functionality as Methods and Notification Events, SOME/IP also takes care of the on-wire serialization of data. SOME/IP allows you to use basic datatypes (like unsigned/signed integers and floating point numbers) and strings or define structures and arrays. SOME/IP takes care of properly serializing data on sender-side in order to transport it via UDP or TCP and deserialize data on reception.  

## SOME/IP SD (Service Discovery)

While it is possible to statically define a network topology and all IDs in a system beforehand, a major feature of SOME/IP is **Service Discovery**. Service Discovery allows a Service to announce itself on the network to potential clients by sending SOME/IP SD "Offer Entries" via UDP multicast.

Clients can search for services by sending Find Entries via multicast. In case the offered and request IDs match, server and client can dynamically find each other without knowing the IP addresses of each ECU beforehand. For applications using SOME/IP the network topology is therefore transparent which allows it to develop portable applications being only dependent on Service, Service Instance and Method/Event IDs.


## Implementations

## Further Reading