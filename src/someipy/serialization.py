# Copyright (C) 2024 Christian H.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
    """
    someipy datatype representing an unsigned 8 bit integer on the wire.
    """

    value: int = 0

    def __len__(self):
        """
        Return the length of the object.

        :return: An integer representing the length of the object.
        :rtype: int
        """
        return 1

    def serialize(self) -> bytes:
        """
        Serialize the value of the object into bytes using the big-endian byte order.

        Returns:
            bytes: The serialized value of the object.
        """
        return struct.pack(">B", self.value)

    def deserialize(self, payload):
        """
        Deserialize the payload into the value of the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            None
        """
        (self.value,) = struct.unpack(">B", payload)


@dataclass
class Sint8:
    """
    someipy datatype representing a signed 8 bit integer on the wire.
    """

    value: int = 0

    def __len__(self):
        """
        Return the length of the object.

        :return: An integer representing the length of the object.
        :rtype: int
        """
        return 1

    def serialize(self) -> bytes:
        """
        Serialize the value of the object into bytes using the big-endian byte order.

        Returns:
            bytes: The serialized value of the object.
        """
        return struct.pack(">b", self.value)

    def deserialize(self, payload):
        """
        Deserialize the payload into the value of the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            self: The deserialized object.
        """
        (self.value,) = struct.unpack(">b", payload)
        return self


@dataclass
class Uint16:
    """
    someipy datatype representing an unsigned 16 bit integer on the wire.
    """

    value: int = 0

    def __len__(self):
        """
        Return the length of the object.

        Returns:
            int: The length of the object, which is always 2.
        """
        return 2

    def serialize(self) -> bytes:
        """
        Serialize the value of the object into bytes using the big-endian byte order.

        Returns:
            bytes: The serialized value of the object.
        """
        return struct.pack(">H", self.value)

    def deserialize(self, payload):
        """
        Deserialize the payload into the value of the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            self: The deserialized object.
        """
        (self.value,) = struct.unpack(">H", payload)
        return self


@dataclass
class Sint16:
    """
    someipy datatype representing a signed 16 bit integer on the wire.
    """

    value: int = 0

    def __len__(self):
        """
        Return the length of the object.

        Returns:
            int: The length of the object, which is always 2.
        """
        return 2

    def serialize(self) -> bytes:
        """
        Serialize the value of the object into bytes using the big-endian byte order.

        Returns:
            bytes: The serialized value of the object.
        """
        return struct.pack(">h", self.value)

    def deserialize(self, payload):
        """
        Deserialize the payload into the value of the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            self: The deserialized object.
        """
        (self.value,) = struct.unpack(">h", payload)
        return self


@dataclass
class Uint32:
    """
    someipy datatype representing an unsigned 32 bit integer on the wire.
    """

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
    """
    someipy datatype representing a signed 32 bit integer on the wire.
    """

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
    """
    someipy datatype representing an unsigned 64 bit integer on the wire.
    """

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
    """
    someipy datatype representing a signed 64 bit integer on the wire.
    """

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
    """
    someipy datatype representing a boolean type transported as a single byte on the wire.
    """

    value: bool = False

    def __len__(self):
        """
        Return the length of the object.

        Returns:
            int: The length of the object, which is always 1.
        """
        return 1

    def serialize(self) -> bytes:
        """
        Serialize the value of the object into bytes using the big-endian byte order.

        Returns:
            bytes: The serialized value of the object.
        """
        return struct.pack(">B", int(self.value))

    def deserialize(self, payload):
        """
        Deserialize the payload into the value of the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            self: The deserialized object.

        This method deserializes the payload into the value of the object. It expects the payload to be a single byte representing a boolean value. If the payload is 0, the value of the object is set to False. If the payload is 1, the value of the object is set to True. The deserialized object is then returned.
        """
        (int_value,) = struct.unpack(">B", payload)
        if int_value == 0:
            self.value = False
        elif int_value == 1:
            self.value = True
        return self


@dataclass
class Float32:
    """
    someipy datatype representing a 32 bit floating type.
    """

    value: float = 0.0

    def __len__(self):
        """
        Return the length of the object.

        Returns:
            int: The length of the object, which is always 4.
        """
        return 4

    def serialize(self) -> bytes:
        """
        Serialize the value of the object into bytes using the big-endian byte order.

        Returns:
            bytes: The serialized value of the object.

        This method serializes the value of the object into bytes using the big-endian byte order. It expects the value to be a float. The serialized value is returned as a bytes object.
        """
        return struct.pack(">f", self.value)

    def deserialize(self, payload):
        """
        Deserialize the payload into the value of the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            self: The deserialized object.

        This method deserializes the payload into the value of the object. It expects the payload to be a 4-byte float in big-endian byte order. The deserialized value is assigned to the `value` attribute of the object. The deserialized object is then returned.
        """
        (self.value,) = struct.unpack(">f", payload)
        return self

    def __eq__(self, other) -> Bool:
        """
        Compare two objects for equality.

        This method compares the serialized representation of the current object and the other object to determine if they are equal. It returns a Bool object indicating whether the objects are equal or not.

        Parameters:
            other (Any): The object to compare with the current object.

        Returns:
            Bool: A Bool object indicating whether the objects are equal or not.
        """
        return self.serialize() == other.serialize()


@dataclass
class Float64:
    """
    someipy datatype representing a 64 bit floating type.
    """

    value: float = 0.0

    def __len__(self):
        """
        Return the length of the object.

        Returns:
            int: The length of the object, which is always 8.
        """
        return 8

    def serialize(self) -> bytes:
        """
        Serialize the value of the object into bytes using the big-endian byte order.

        Returns:
            bytes: The serialized value of the object.

        This method serializes the value of the object into bytes using the big-endian byte order. It expects the value to be a float. The serialized value is returned as a bytes object.
        """
        return struct.pack(">d", self.value)

    def deserialize(self, payload):
        """
        Deserialize the payload into the value of the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            self: The deserialized object.

        This method deserializes the payload into the value of the object. It expects the payload to be an 8-byte float in big-endian byte order. The deserialized value is assigned to the `value` attribute of the object. The deserialized object is then returned.
        """
        (self.value,) = struct.unpack(">d", payload)
        return self

    def __eq__(self, other) -> Bool:
        """
        Compare two objects for equality.

        This method compares the serialized representation of the current object and the other object to determine if they are equal. It returns a Bool object indicating whether the objects are equal or not.

        Parameters:
            other (Any): The object to compare with the current object.

        Returns:
            Bool: A Bool object indicating whether the objects are equal or not.
        """
        return self.serialize() == other.serialize()


def serialize(obj) -> bytes:
    """
    Serializes an object into bytes by iterating over its attributes, excluding those starting with double underscores or underscores.
    For each attribute, it calls the `serialize` method of the attribute and appends the returned bytes to the output.

    Parameters:
        obj (object): The object to be serialized.

    Returns:
        bytes: The serialized representation of the object as bytes.
    """
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
    """
    A base class for defining a custom SOME/IP payload ("structs"). It can be recursively nested, i.e. a SomeIpPayload object may contain other SomeIpPayload objects.
    """

    def __len__(self) -> int:
        """
        Return the length of the object.

        Returns:
            int: The length of the object.
        """
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
        """
        Serialize the object into bytes to be transported on the wire.

        Returns:
            bytes: The serialized representation of the object.
        """
        return serialize(self)

    def deserialize(self, payload: bytes):
        """
        Deserialize the payload (on wire representation) into the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            self: The deserialized object.

        This method deserializes the payload into the object. It iterates over the attributes of the object, excluding those starting with "__". For each attribute, it calculates the length of the corresponding value and deserializes it using the `deserialize` method of the value object. The deserialized values are assigned back to the corresponding attributes of the object. Finally, the deserialized object is returned.
        """
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
    """
    A datatype for a SOME/IP fixed size array. This type shall be used with someipy datatypes that support serialization and deserialization.
    """

    data: List[T]

    def __init__(self, class_reference: Type[T], size: int):
        """
        Initializes a new instance of the SomeIpFixedSizeArray class.

        Parameters:
            class_reference (Type[T]): The type of elements to be stored in the array.
            size (int): The number of elements in the array.

        Returns:
            None
        """
        self.data = [class_reference() for i in range(size)]

    def __eq__(self, other):
        """
        Compare two SomeIpFixedSizeArray objects for equality.

        This method compares the length (number of elements) of the current array and the other array to determine if they are equal. It also compares the length of the bytes representation of the arrays. Finally, it compares the content of all elements in the arrays to check if they are equal.

        Parameters:
            other (SomeIpFixedSizeArray): The object to compare with the current object.

        Returns:
            bool: True if the arrays are equal, False otherwise.
        """
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
        """
        Return the length of the object.

        This method calculates the length of the object based on the number of elements in the `data` list and the length of each element. If the `data` list is empty, it returns 0. Otherwise, it returns the product of the length of the `data` list and the length of the first element in the `data` list.

        Returns:
            int: The length of the object.
        """
        if len(self.data) == 0:
            return 0
        else:
            return len(self.data) * len(self.data[0])

    def serialize(self) -> bytes:
        """
        Serialize the object into bytes by iterating over its attributes, excluding those starting with double underscores or underscores.
        For each attribute, it calls the `serialize` method of the attribute and appends the returned bytes to the output.

        Returns:
            bytes: The serialized representation of the object as bytes.
        """
        result = bytes()
        for element in self.data:
            result += element.serialize()
        return result

    def deserialize(self, payload: bytes):
        """
        Deserialize the payload into the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            self: The deserialized object.

        This method deserializes the payload into the object. It iterates over the `data` list and for each element, it calls the `deserialize` method of that element, passing a slice of the payload corresponding to the element's length. The deserialized values are assigned back to the corresponding elements of the `data` list. If the `data` list is empty, the method returns immediately. Finally, the deserialized object is returned.
        """
        if len(self.data) == 0:
            return

        single_element_length = len(self.data[0])
        for i in range(len(self.data)):
            self.data[i].deserialize(
                payload[(i * single_element_length) : ((i + 1) * single_element_length)]
            )
        return self
