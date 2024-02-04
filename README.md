# someipy - A Python Library for the SOME/IP Protocol

someipy is a Python library implementing the SOME/IP protocol, including the SOME/IP SD (Service Discovery) in Python. It's perfectly suited for fast prototyping of applications that need to provide (server) or use (client) SOME/IP services from other ECUs.

someipy also supports serialization and deserialization of SOME/IP payloads, which is a unique feature compared to other libraries.

someipy is still under development; therefore, it does not yet support all features of the SOME/IP and SOME/IP Service Discovery protocol specification.

someipy is based on the specification version of R22-11:
- [SOME/IP Protocol Specification](https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPProtocol.pdf)
- [SOME/IP Service Discovery Protocol Specification](https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPServiceDiscoveryProtocol.pdf)

The library is currently developed and tested under Ubuntu 22.04 and Python 3.12.

## Example Applications

In the directory [example_apps](./example_apps/), examples including explanations, can be found for using the someipy library. In [temperature_msg.py](./example_apps/temperature_msg.py), a payload interface "TemperatureMsg" is defined, which can be serialized and deserialized. In [send_events.py](./example_apps/send_events.py), the service discovery and two services are instantiated. The "TemperatureMsg" is serialized and used as the payload for sending events.

## Supported Features, Limitations and Deviations

The library is still under development. The current major limitations and deviations from the protocol specifications are listed below.

### SOME/IP

- Only events (and field notifiers) are supported. Methods (and field getters/setters) are not supported yet.
- Receiving events is not supported yet. The server-side only is supported for now. Client service instances for receiving SOME/IP events are supported soon.
- Only UDP services are supported.
- Only unicast services are supported.
- SOME/IP-TP is not supported.
- IPv6 endpoints are not supported.
- Session handling is supported only for SOME/IP-SD and not for SOME/IP messages transporting events.

### Service Discovery

- Configuration and load balancing options in SOME/IP SD messages are not supported.
- TTL of Service Discovery entries is not checked yet.
- The Initial Wait Phase and Repetition Phase of the Service Discovery specification are skipped. For simplification, the Main Phase is directly entered, i.e. SD Offer Entries are immediately sent cyclically.
- Multiple Service Discovery entries are not packed together in a single SD message, which is sent via UDP.

### De-/Serialization

- Only fixed size arrays are supported.
- Optional length fields for SOME/IP arrays are not supported.
- Strings are not supported yet.
- Configuration of padding is not supported yet.
