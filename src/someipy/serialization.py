import struct

from dataclasses import dataclass
from typing import Generic, List, Type, TypeVar


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
        return self


@dataclass
class Uint16:
    value: int = 0

    def __len__(self):
        return 2

    def serialize(self) -> bytes:
        return struct.pack(">H", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">H", payload)
        return self


@dataclass
class Sint16:
    value: int = 0

    def __len__(self):
        return 2

    def serialize(self) -> bytes:
        return struct.pack(">h", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">h", payload)
        return self


@dataclass
class Uint32:
    value: int = 0

    def __len__(self):
        return 4

    def serialize(self) -> bytes:
        return struct.pack(">L", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">L", payload)
        return self


@dataclass
class Sint32:
    value: int = 0

    def __len__(self):
        return 4

    def serialize(self) -> bytes:
        return struct.pack(">l", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">l", payload)
        return self


@dataclass
class Uint64:
    value: int = 0

    def __len__(self):
        return 8

    def serialize(self) -> bytes:
        return struct.pack(">Q", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">Q", payload)
        return self


@dataclass
class Sint64:
    value: int = 0

    def __len__(self):
        return 8

    def serialize(self) -> bytes:
        return struct.pack(">q", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">q", payload)
        return self


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
        return self


@dataclass
class Float32:
    value: float = 0.0

    def __len__(self):
        return 4

    def serialize(self) -> bytes:
        return struct.pack(">f", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">f", payload)
        return self

    def __eq__(self, other) -> Bool:
        return self.serialize() == other.serialize()


@dataclass
class Float64:
    value: float = 0.0

    def __len__(self):
        return 8

    def serialize(self) -> bytes:
        return struct.pack(">d", self.value)

    def deserialize(self, payload):
        (self.value,) = struct.unpack(">d", payload)
        return self

    def __eq__(self, other) -> Bool:
        return self.serialize() == other.serialize()


def serialize(obj) -> bytes:
    ordered_items = [
        (name, value)
        for name, value in obj.__dict__.items()
        if not (name.startswith("__") or name.startswith("_"))
    ]
    output = bytes()
    for _, value in ordered_items:
        output += value.serialize()
    return output


class SomeIpPayload:
    def __len__(self) -> int:
        payload_length = 0
        ordered_items = [
            (name, value)
            for name, value in self.__dict__.items()
            if not name.startswith("__")
        ]
        for _, value in ordered_items:
            payload_length += len(value)
        return payload_length

    def serialize(self) -> bytes:
        return serialize(self)

    def deserialize(self, payload: bytes):
        ordered_items = [
            (name, value)
            for name, value in self.__dict__.items()
            if not name.startswith("__")
        ]

        pos = 0

        for key, value in ordered_items:
            type_length = len(value)

            self.__dict__[key].deserialize(payload[pos : (pos + type_length)])

            pos += type_length
        return self


T = TypeVar("T")


class SomeIpFixedSizeArray(Generic[T]):
    # Length fields are not supported yet

    data: List[T]

    def __init__(self, class_reference: Type[T], size: int):
        self.data = [class_reference() for i in range(size)]

    def __eq__(self, other):
        if isinstance(other, SomeIpFixedSizeArray):
            # Compare if the length (number of elements) of other array is the same
            if len(self.data) != len(other.data):
                return False

            # Compare if bytes length of other is the same
            if len(self) != len(other):
                return False

            # Compare if the content of all elements is the same
            for i in range(len(self.data)):
                if self.data[i] != other.data[i]:
                    return False
            return True

        return False

    def __len__(self) -> int:
        if len(self.data) == 0:
            return 0
        else:
            return len(self.data) * len(self.data[0])

    def serialize(self) -> bytes:
        result = bytes()
        for element in self.data:
            result += element.serialize()
        return result

    def deserialize(self, payload: bytes):
        if len(self.data) == 0:
            return

        single_element_length = len(self.data[0])
        for i in range(len(self.data)):
            self.data[i].deserialize(
                payload[(i * single_element_length) : ((i + 1) * single_element_length)]
            )
        return self
