# someipy - A Python Library implementing the SOME/IP Protocol

## Get in Contact :postbox:

If you want to connect, have a feature request, bug report or need support, send me an email or connect on LinkedIn:
> :email: [someipy.package@gmail.com](mailto:someipy.package@gmail.com)  
:electric_plug: [LinkedIn](https://www.linkedin.com/in/ch-herzog/)

## Documentation :pencil2:

:link: [https://chrizog.github.io/someipy/](https://chrizog.github.io/someipy/)


## What is someipy?

someipy is a Python library implementing the SOME/IP protocol, including the SOME/IP SD (Service Discovery) in Python. It's perfectly suited for fast prototyping of applications that need to provide (server) or use (client) SOME/IP services from other ECUs.

someipy also supports serialization and deserialization of SOME/IP payloads, which is a unique feature compared to other libraries.

someipy is still under development; therefore, it does not yet support all features of the SOME/IP and SOME/IP Service Discovery protocol specification.

someipy is based on the specification version of R22-11:
- [SOME/IP Protocol Specification](https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPProtocol.pdf)
- [SOME/IP Service Discovery Protocol Specification](https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPServiceDiscoveryProtocol.pdf)

The library is currently developed and tested under Ubuntu 22.04 and Python 3.8.

## Typical Use Cases

someipy excels in scenarios where a full-scale Autosar (Adaptive or Classic) integration would be excessive:

- :test_tube: **Develop Test Applications**: Easily create test applications to stimulate the SOME/IP interfaces of your system under test. Whether running on a PC in a SIL environment or on an ECU, someipy allows you to efficiently send and receive SOME/IP events or utilize/provide SOME/IP services. Test data can be seamlessly generated or imported in Python, from sources such as .csv files or ROS bag files. Explore the [example applications](#example-applications) for more details.

- :battery: **Prototype Sensor Integration**: Quickly integrate new sensors into your project using SOME/IP, ideal for evaluating the sensor's potential impact without significant effort. Define the message/parameter layout in Python and create a server service instance in minutes. Check out the [example application](#example-applications) *send_events_udp.py* for a practical demonstration.

- :microscope: **Data Recording**: Set up a SOME/IP recording application in just a few minutes and store data in your preferred format, such as ROS bags, .csv files, or databases. Simply dump the received data within your callback function. The [example application](#example-applications) *receive_events_udp.py* illustrates this process.

## Installation

The package can be installed from [PyPi](https://pypi.org/project/someipy/).

```bash
pip3 install someipy
```

## Example Applications

In the directory [example_apps](./example_apps/), examples including explanations, can be found for using the someipy library.

## Supported Features, Limitations and Deviations

The library is still under development. The current major limitations and deviations from the protocol specifications are listed below.

### SOME/IP

- Only unicast services are supported.
- SOME/IP-TP is not supported.
- IPv6 endpoints are not supported.
- SOME/IP fields are not supported.

### Service Discovery

- Configuration and load balancing options in SOME/IP SD messages are not supported.
- TTL of Service Discovery entries is not checked yet.
- The Initial Wait Phase and Repetition Phase of the Service Discovery specification are skipped. The Main Phase is directly entered, i.e. SD Offer Entries are immediately sent cyclically.

### De-/Serialization

- Only fixed size arrays are supported. Dynamically sized arrays are not supported.
- Optional length fields for SOME/IP arrays are not supported.
- Strings are not supported yet.
- Configuration of padding is not supported yet.
