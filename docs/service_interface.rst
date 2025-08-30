SOME/IP Service Interface Data Types
====================================

Defining a common SOME/IP service interface datatype is essential for service-oriented communication between ECUs (and other middleware). It ensures all participants interpret raw bytes consistently and can serialize data back for transmission.

The `SOME/IP protocol specification <https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPProtocol.pdf>`_ defines the on-wire format. You do not need to manage it directly; someipy provides Python types and serializers to convert between Python objects and bytes.

SOME/IP Interface Datatype Definition in Python
-----------------------------------------------

Many middlewares, such as `ROS (Robot Operating System) <https://www.ros.org/>`_ or `OpenDDS <https://opendds.org/about/articles/Article-Intro.html>`_, use language-agnostic interface descriptions to define data structures. ROS uses .msg files; OpenDDS uses .idl files. Source code is typically generated from these definitions. With someipy, data types can be defined directly in Python, either in the application file or in separate modules imported by the application. Prefer a separate file per datatype.

Defining Datatypes in someipy
-----------------------------

Custom SOME/IP data types can be defined directly in Python. All datatype-related classes and functions can be imported from the ``someipy.serialization`` module. To use an unsigned 8-bit datatype:

.. code-block:: python

   from someipy.serialization import Uint8

All supported data types are listed in the table at the end of this article.

If you need a single value, you can use the basic datatypes directly (e.g., Uint8). For most scenarios, you will define structured types (dataclasses) by subclassing SomeIpPayload.

Defining Datatypes using SomeIpPayload
-------------------------------------

As described above, you can define custom SOME/IP data types in Python. All datatype-related classes and functions reside in the someipy.serialization module. To define a structured type, subclass SomeIpPayload. For example:

.. code-block:: python

   from dataclasses import dataclass
   from someipy.serialization import (
       SomeIpPayload,
       Uint64,
       Float32,
   )

   @dataclass
   class TemperatureMsg(SomeIpPayload):
       timestamp: Uint64
       temperature: Float32

       def __init__(self):
           self.timestamp = Uint64()
           self.temperature = Float32()

Note: Using @dataclass provides auto-generated __repr__ and __eq__.

The TemperatureMsg class can be serialized and deserialized with the base class methods:

- serialize(self) -> bytes
- deserialize(self, payload: bytes) -> TemperatureMsg

Serialize is used to send data (e.g., events or method calls). Example:

.. code-block:: python

   # Create a new instance of TemperatureMsg and fill some dummy values
   tmp_msg = TemperatureMsg()
   tmp_msg.timestamp = Uint64(10)
   tmp_msg.temperature = Float32(20.0)

   payload = tmp_msg.serialize()
   service_instance_temperature.send_event(
                   SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload
               )

Deserialize is used when receiving a bytes payload to interpret as TemperatureMsg. Example callback:

.. code-block:: python

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
           print(f"Received {len(someip_message.payload)} bytes. Deserializing...")
           temperature_msg = TemperatureMsg().deserialize(someip_message.payload)
           print(temperature_msg)
       except Exception as e:
           print(f"Error in deserialization: {e}")

Note: The ``deserialize`` call is wrapped in a try-except block to prevent crashes from malformed data. This improves robustness.

Updating Values
---------------

In the example above, the timestamp and temperature fields are initialized with Uint64(10) and Float32(20.0). Do not assign plain integers directly (e.g., tmp_msg.timestamp = 10); these literals are not compatible with the typed fields. Use the typed constructors and then serialize.

.. code-block:: python

   tmp_msg = TemperatureMsg()
   tmp_msg.timestamp = Uint64(10)
   tmp_msg.temperature = Float32(20.0)
   payload = tmp_msg.serialize()

Directly modifying the value field is also supported:
.. code-block:: python

   tmp_msg.timestamp.value = 10

When accessing ``value``, the numeric literal can be directly assigned.

Nesting Structured Data Types
-----------------------------

You can nest structured types that derive from SomeIpPayload. For example, define a Version datatype and nest it inside TemperatureMsg:

.. code-block:: python

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
       temperature: Float32

       def __init__(self):
           self.version = Version()
           self.version.major.value = 1
           self.version.minor.value = 0
           self.timestamp = Uint64()
           self.temperature = Float32()

.. _someipy-datatypes:

Supported SOME/IP Data Types in someipy
---------------------------------------

The following table lists all supported SOME/IP data types and their respective classes in someipy. All the types are part of the module ``someipy.serialization``.

For inquiries about support for additional data types, contact us at:

- someipy.package@gmail.com
- `LinkedIn <https://www.linkedin.com/in/ch-herzog/>`_

.. list-table:: SOME/IP Data Types
   :header-rows: 1
   :widths: 50 50

   * - SOME/IP Data Type
     - someipy Data Type
   * - boolean
     - Uint8
   * - uint8
     - Uint8
   * - uint16
     - Uint16
   * - uint32
     - Uint32
   * - uint64
     - Uint64
   * - sint8
     - Sint8
   * - sint16
     - Sint16
   * - sint32
     - Sint32
   * - sint64
     - Sint64
   * - float32
     - Float32
   * - float64
     - Float64
   * - structs
     - SomeIpPayload
   * - fixed-length strings
     - SomeIpFixedSizeString
   * - dynamic-length strings
     - SomeIpDynamicSizeString
   * - arrays (fixed-length)
     - SomeIpFixedSizeArray
   * - arrays (dynamic-length)
     - SomeIpDynamicSizeArray
   * - union
     - not supported
