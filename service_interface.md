---
layout: default
title: SOME/IP Service Interface Data Types
nav_order: 4
---

<style type="text/css">
pre > code.language-mermaid {
    display: flex;
    justify-content: center;
    align-items: center;
}

p:has(img) {
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>

# SOME/IP Service Interface Data Types
A major task in setting up a service oriented communication between ECUs via SOME/IP (and also in other middlewares) is to define a common service interface datatype definition, so that all participants know how to interpret and parse received raw bytes into a meaningful data structure. Vice versa participants need to know how to serialize their data structures into bytes to be transmitted to other participants.

The [SOME/IP protocol specification](https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPProtocol.pdf) defines the on-wire format of SOME/IP. The specification describes a header structure and also how different data types are serialized on-wire. As a programmer using someipy, you don't need to take care of the on-wire format. someipy provides data types as Python classes ready to use and functions to serialize a Python object describing a data structure into a Python `bytes()` object and deserializing a received `bytes()` object into a Python object.

## SOME/IP Interface Datatype Definition in Python
Many middlewares and their stacks like [ROS (Robot Operating System)](https://www.ros.org/) or [OpenDDS](https://opendds.org/about/articles/Article-Intro.html) use an interface description language independent of the programming language to define the data structures. E.g. ROS uses ROS message (.msg) files and OpenDDS uses IDL (.idl) files. Out of these separate interface files source code is generated containing the actual data types and (de)serializers to be used in Python or C++.

With someipy you do not need an extra code generator tool. Service interface data types can be directly written in Python, either in the same file as your application or in separate Python files which are imported in your application. It's recommended to use a separate Python file for each datatype defined.

## Defining Datatypes in someipy
As described above, custom SOME/IP data types can be directly defined and used in Python. All datatype related classes and functions can be imported from the `someipy.serialization` module. If you want to use a unsigned 8-bit datatype use:

```python
from someipy.serialization import Uint8
```

All supported data types are listed in the table [at the end of the article](#someipy-datatypes).

If you want to send only a single value like an 8-bit datatype, you could directly use the basic datatypes like `Uint8`. However, in most real world use-cases you want to use structured data types (struct). For that purpose, someipy provides the `SomeIpPayload` class. By creating a class and inheriting from `SomeIpPayload` you can easily define your own structured type. The following example defines a `TemperatureMsg` to demonstrate the approach.

```python
from dataclasses import dataclass
from someipy.serialization import (
    SomeIpPayload,
    Uint64,
    Float32,
)

@dataclass
class TemparatureMsg(SomeIpPayload):
    timestamp: Uint64
    temperature: Float32

    def __init__(self):
        self.timestamp = Uint64()
        self.temperature = Float32()

```

First the needed classes are imported. We also import `dataclass`. By using the `@dataclass` decorator the `__repr__` and a `__eq__` are automatically generated so that we can easily print or log an object and compare two different `TemperatureMsg` objects using the equality operator `==`.

The class `TemperatureMsg` derives from `SomeIpPayload`. Deriving from `SomeIpPayload` allows us to send the message via SOME/IP since the base class introduces the two important methods:
- `def serialize(self) -> bytes`
- `def deserialize(self, payload: bytes) -> T`

`serialize` is used when data shall be sent, e.g. sending SOME/IP events or calling a method an passing parameters. Here is an example for sending events:

```python
# Create a new instance of TemperatureMsg and fill some dummy values
tmp_msg = TemparatureMsg()
tmp_msg.timestamp = Uint64(10)
tmp_msg.temperature = Float32(20.0)

# serialize returns a bytes objects..
payload = tmp_msg.serialize()
# .. than can be used in the send_event method of the service instance
# service_instance_temperature was initialised beforehand
service_instance_temperature.send_event(
                SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload
            )
```

`deserialize` is to be used whenever you receive a `bytes` object that shall be interpreted as the desired data structure `TemperatureMsg`. Here is an example of a SOME/IP event callback. A `SomeIpMessage` is passed into the callback function by someipy. The `SomeIpMessage` consists of a `header` containing metadata like the instance ID and the sender and the `payload` which is a `bytes` object.

```python
def temperature_callback(someip_message: SomeIpMessage) -> None:
    """
    Callback function that is called when a temperature message is received.
    
    Args:
        someip_message (SomeIpMessage): The SomeIpMessage object containing the received message
        consisting of a header and payload.
        
    Returns:
        None: This function does not return anything.
    """
    try:
        print(f"Received {len(someip_message.payload)} bytes. Try to deserialize..")
        temperature_msg = TemparatureMsg().deserialize(someip_message.payload)
        print(temperature_msg)
    except Exception as e:
        print(f"Error in deserialization: {e}")
```

Notice that the `deserialize` call is packed into a try-except block in case malicious or wrong data was sent and received leading to a crash of the application. This increases the robustness of your application.

## Updating Values

In the example above, the `timestamp`and `temperature` fields have been filled with the values `10` and `20.0`. However, the numeric literals are not directly assigned like `tmp_msg.timestamp = 10`. This shall never be done. The data types in someipy like `Uint64` support SOME/IP serialization while usual numeric literals like `10` do not. This would lead to an exception when calling the `serialize` method afterwards.

```python
# Create a new instance of TemperatureMsg and fill some dummy values
tmp_msg = TemparatureMsg()
tmp_msg.timestamp = Uint64(10)
tmp_msg.temperature = Float32(20.0)
```

Another possibility to update the fields is to access the `value` field directly:

```python
tmp_msg.timestamp.value = 10
```

When accessing `value`, the numeric literal can be directly assigned.

## Nesting Structured Data Types

someipy also allows nesting structured data types that derive from `SomeIpPayload`. We will add another struct `Version` containing a `major` and `minor` version field:

```python
@dataclass
class Version(SomeIpPayload):
    major: Uint8
    minor: Uint8

    def __init__(self):
        self.major = Uint8()
        self.minor = Uint8()
```

The `Version` class can now be nested into `TemperatureMsg`:

```python
@dataclass
class TemparatureMsg(SomeIpPayload):
    version: Version
    timestamp: Uint64
    temperature: Float32

    def __init__(self):
        self.version = Version()
        self.version.major.value = 1
        self.version.minor.value = 0
        self.timestamp = Uint64()
        self.temperature = Float32()

```


## Supported SOME/IP Data Types in someipy
<a id="someipy-datatypes"></a>

The following table lists all supported SOME/IP data types and their respective classes in someipy. All the types are part of the module `someipy.serialization`.

For inquiries about support for additional data types, contact us at:
> [someipy.package@gmail.com](mailto:someipy.package@gmail.com)  
[LinkedIn](https://www.linkedin.com/in/ch-herzog/)


| SOME/IP Datatype          | someipy Datatype         |
|---------------------------|--------------------------|
| boolean                   | Uint8                    |
| uint8                     | Uint8                    |
| uint16                    | Uint16                   |
| uint32                    | Uint32                   |
| uint64                    | Uint64                   |
| sint8                     | Sint8                    |
| sint16                    | Sint16                   |
| sint32                    | Sint32                   |
| sint64                    | Sint64                   |
| float32                   | Float32                  |
| float64                   | Float64                  |
| structs                   | SomeIpPayload            |
| fixed-length strings      | not supported            |
| dynamic-length strings    | not supported            |
| arrays (fixed-length)     | SomeIpFixedSizeArray     |
| arrays (dynamic-length)   | not supported            |
| union                     | not supported            |