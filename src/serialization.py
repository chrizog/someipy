import struct

from dataclasses import dataclass


"""
PRS_SOMEIP_00065
This table about basic datatypes is taken from
https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPProtocol.pdf

Type Description Size [bit] Remark
boolean TRUE/FALSE value 8 FALSE (0), TRUE (1)
uint8 unsigned Integer 8
uint16 unsigned Integer 16
uint32 unsigned Integer 32
uint64 unsigned Integer 64
sint8 signed Integer 8 
sint16 signed Integer 16
sint32 signed Integer 32
sint64 signed Integer 64
float32 floating point number 32 IEEE 754 binary32 (Single Precision)
float64 floating point number 64 IEEE 754 binary64 (Double Precision)
"""


@dataclass
class Uint8:
    value: int = 0

    def __len__(self):
        return 1

    def serialize(self) -> bytes:
        return struct.pack(">B", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">B", payload)


@dataclass
class Sint8:
    value: int = 0

    def __len__(self):
        return 1

    def serialize(self) -> bytes:
        return struct.pack(">b", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">b", payload)


@dataclass
class Uint16:
    value: int = 0

    def __len__(self):
        return 2

    def serialize(self) -> bytes:
        return struct.pack(">H", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">H", payload)


@dataclass
class Sint16:
    value: int = 0

    def __len__(self):
        return 2

    def serialize(self) -> bytes:
        return struct.pack(">h", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">h", payload)


@dataclass
class Uint32:
    value: int = 0

    def __len__(self):
        return 4

    def serialize(self) -> bytes:
        return struct.pack(">L", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">L", payload)


@dataclass
class Sint32:
    value: int = 0

    def __len__(self):
        return 4

    def serialize(self) -> bytes:
        return struct.pack(">l", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">l", payload)


@dataclass
class Uint64:
    value: int = 0

    def __len__(self):
        return 8

    def serialize(self) -> bytes:
        return struct.pack(">Q", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">Q", payload)


@dataclass
class Sint64:
    value: int = 0

    def __len__(self):
        return 8

    def serialize(self) -> bytes:
        return struct.pack(">q", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">q", payload)


@dataclass
class Bool:
    value: bool = False

    def __len__(self):
        return 1

    def serialize(self) -> bytes:
        if self.value == True:
            return struct.pack(">B", 1)
        else:
            return struct.pack(">B", 0)

    def deserialize(self, payload):
        (int_value,) = struct.unpack(">B", payload)
        if int_value == 0:
            self.value = False
        elif int_value == 1:
            self.value = True


@dataclass
class Float32:
    value: float = 0.0

    def __len__(self):
        return 4

    def serialize(self) -> bytes:
        return struct.pack(">f", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">f", payload)


@dataclass
class Float64:
    value: float = 0.0

    def __len__(self):
        return 8

    def serialize(self) -> bytes:
        return struct.pack(">d", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">d", payload)


def serialize(obj) -> bytes:
    ordered_items = [
        (name, value)
        for name, value in obj.__dict__.items()
        if not name.startswith("__")
    ]
    output = bytes()
    for _, value in ordered_items:
        output += value.serialize()
    return output


class SomeIpPayload:
    def __init__(self):
        pass

    def __len__(self) -> int:
        len = 0
        ordered_items = [
            (name, value)
            for name, value in self.__dict__.items()
            if not name.startswith("__")
        ]
        for _, value in ordered_items:
            len += len(value)
        return len

    def serialize(self) -> bytes:
        return serialize(self)

    def deserialize(self, payload: bytes):
        ordered_items = [
            (name, value)
            for name, value in self.__dict__.items()
            if not name.startswith("__")
        ]

        for key, value in ordered_items:
            deserialized_value = self.__dict__[key].deserialize(payload)
