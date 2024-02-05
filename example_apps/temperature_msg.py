from someipy.serialization import *

# With someipy it's possible to either send and receive payloads unserialized simply as bytes-objects
# You can also define the payloads structure directly as Python classes and serialize your Python object
# to a bytes-payload which can be sent. You can also deserialize a received bytes-object into your defined
# Python object structure.

# In this example we'll define a "temperature message" that consists of another SOME/IP struct and of a fixed size
# SOME/IP array

@dataclass
class Version(SomeIpPayload):
    major: Uint8
    minor: Uint8

    def __init__(self):
        # Ensure that you always write an __init__ function for each struct so that the variables
        # are instance variables owned by each object
        self.major = Uint8()
        self.minor = Uint8()
        # Reminder: Do NOT write "self.major = 1". Always use the provided classes in someipy like Uint8,
        # so that the data can be propery serialized. Python literals won't be serialized properly
        # Instead use self.major = Uint8(1)


@dataclass
class TemparatureMsg(SomeIpPayload):
    # Always define payloads with the @dataclass decorator. This leads to the __eq__ being
    # generated which makes it easy to compare the content of two messages
    # For defining a payload struct just derive from the SomeIpPayload class. This will ensure
    # the Python object can be serialized and deserialized and supports e.g. len() calls which
    # will return the length of the payload in bytes

    version: Version
    timestamp: Uint64
    measurements: SomeIpFixedSizeArray

    def __init__(self):
        self.version = Version()
        self.timestamp = Uint64()
        self.measurements = SomeIpFixedSizeArray(Float32, 4)
        # Arrays can be modelled using the SomeIpFixedSizeArray class which gets the type that
        # the array shall hold (e.g. Float32) and the number of elements
        # The len(self.measurements) call will return the number of bytes (4*len(Float32)).
        # If you need to now the number of elements use len(self.measurements.data).


# Simple example how to instantiate a payload, change values, serialize and deserialize
if __name__ == "__main__":

    tmp_msg = TemparatureMsg()
    
    tmp_msg.version.major = Uint8(2)
    tmp_msg.version.minor = Uint8(0)
    # Reminder: Do NOT use "tmp_msg.version.major = 2". Always use the provided classes by someipy like Uint8,
    # so that the data can be propery serialized. Python literals won't be serialized into SOME/IP payload.

    tmp_msg.timestamp = Uint64(100)

    tmp_msg.measurements.data[0] = Float32(20.0)
    tmp_msg.measurements.data[1] = Float32(20.1)
    tmp_msg.measurements.data[2] = Float32(20.2)
    tmp_msg.measurements.data[3] = Float32(20.3)

    # The @dataclass decorator will also generate a __repr__ function
    print(tmp_msg)

    # serialize() will return a bytes object
    output = tmp_msg.serialize()
    print(output.hex())

    # Create a new TemperatureMsg from the serialized bytes 
    tmp_msg_again = TemparatureMsg().deserialize(output)
    print(tmp_msg_again)

    assert(tmp_msg_again == tmp_msg)
