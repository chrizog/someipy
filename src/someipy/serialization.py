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

import codecs
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
        return self


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

            if hasattr(value, "_has_dynamic_size") and value._has_dynamic_size == True:
                # If the length is not known before deserialization, first deserialize using the
                # remaining payload and then calculate the length
                self.__dict__[key].deserialize(payload[pos:])
                type_length = len(self.__dict__[key])
            else:
                # If the length is known beforehand, only deserialize the part of the payload needed
                type_length = len(value)
                self.__dict__[key].deserialize(payload[pos : (pos + type_length)])
            pos += type_length
        return self


T = TypeVar("T")


class SomeIpFixedSizeArray(Generic[T]):
    """
    A datatype for a SOME/IP fixed size array. This type shall be used with someipy datatypes that support serialization and deserialization.
    """

    def __init__(self, class_reference: Type[T], size: int):
        """
        Initializes a new instance of the SomeIpFixedSizeArray class.

        Parameters:
            class_reference (Type[T]): The type of elements to be stored in the array.
            size (int): The number of elements in the array.

        Returns:
            None
        """
        self.data: List[T] = [class_reference() for i in range(size)]

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


class SomeIpDynamicSizeArray(Generic[T]):
    """
    A datatype for a SOME/IP dynamically sized array. This type shall be used in someipy datatypes that support serialization and deserialization.
    """

    _has_dynamic_size = True

    def __init__(self, class_reference: Type[T]):
        """
        Initializes a new instance of the SomeIpDynamicSizeArray class.

        Parameters:
            class_reference (Type[T]): The type of elements to be stored in the array.

        Returns:
            None
        """
        self._data: List[T] = []
        self._length_field_length = 4  # The length of the length field in bytes. It can be either 0 (no length field), 1, 2 or 4 bytes.
        self._single_element_length = len(class_reference())
        self._class_reference = class_reference

    @property
    def data(self) -> List[T]:
        return self._data

    @data.setter
    def data(self, value: List[T]):
        self._data = value

    @property
    def length_field_length(self):
        return self._length_field_length

    @length_field_length.setter
    def length_field_length(self, value):
        if value in [0, 1, 2, 4]:
            self._length_field_length = value
        else:
            raise ValueError("Length field length must be 0, 1, 2 or 4 bytes")

    def __eq__(self, other) -> bool:
        """
        Compare two SomeIpDynamicSizeArray objects for equality.

        This method compares the length (number of elements) of the current array and the other array to determine if they are equal. It also compares the length of the bytes representation of the arrays. Finally, it compares the content of all elements in the arrays to check if they are equal.

        Parameters:
            other (SomeIpDynamicSizeArray): The object to compare with the current object.

        Returns:
            bool: True if the arrays are equal, False otherwise.
        """
        if isinstance(other, SomeIpDynamicSizeArray):
            # Compare if the length (number of elements) of other array is the same
            if len(self.data) != len(other.data):
                return False

            # Compare if bytes length of other is the same
            if len(self) != len(other):
                return False

            if self.length_field_length != other.length_field_length:
                return False

            # Compare if the content of all elements is the same
            for i in range(len(self.data)):
                if self.data[i] != other.data[i]:
                    return False
            return True

        return False

    def __len__(self) -> int:
        """
        Return the length of the object in bytes.

        This method calculates the length of the object based on the number of elements in the `data` list and the length of each element. If the `data` list is empty, it returns 0. Otherwise, it returns the product of the length of the `data` list and the length of the first element in the `data` list.

        Returns:
            int: The length of the object.
        """
        return self.length_field_length + len(self.data) * self._single_element_length

    def serialize(self) -> bytes:
        """
        Serialize the object into bytes by iterating over its attributes, excluding those starting with double underscores or underscores.
        For each attribute, it calls the `serialize` method of the attribute and appends the returned bytes to the output.

        Returns:
            bytes: The serialized representation of the object as bytes.
        """
        result = bytes()
        length_data_in_bytes = len(self.data) * self._single_element_length
        if self._length_field_length == 1:
            result += struct.pack(">B", length_data_in_bytes)
        elif self._length_field_length == 2:
            result += struct.pack(">H", length_data_in_bytes)
        elif self._length_field_length == 4:
            result += struct.pack(">L", length_data_in_bytes)

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

        self.data = []
        length = 0

        if self._length_field_length == 1:
            (length,) = struct.unpack(">B", payload[:1])
        elif self._length_field_length == 2:
            (length,) = struct.unpack(">H", payload[:2])
        elif self._length_field_length == 4:
            (length,) = struct.unpack(">L", payload[:4])
        else:
            return

        number_of_elements = length / self._single_element_length
        for i in range(int(number_of_elements)):
            start_idx = (i * self._single_element_length) + self._length_field_length
            end_idx = start_idx + self._single_element_length
            next_element = self._class_reference().deserialize(
                payload[start_idx:end_idx]
            )
            self.data.append(next_element)

        return self


class SomeIpFixedSizeString(Generic[T]):
    """
    A datatype for a SOME/IP fixed size string.
    """

    def __init__(self, size: int, value: str = ""):
        """
        Initializes a new instance of the SomeIpFixedSizeString class.

        Parameters:
            size (int): The size of the string including the terminating '\0' character.

        Returns:
            None
        """
        self._size = size
        self._data = value
        self._encoding = "utf-8"

    @property
    def size(self) -> int:
        return self._size

    @property
    def data(self) -> str:
        return self._data

    @data.setter
    def data(self, value: str):
        if (
            len(value)
        ) > self._size - 1:  # -1 since the terminating '\0' character is included in the size
            raise ValueError(
                f"String length exceeds maximum size of {self._size} including the terminating character"
            )
        self._data = value

    @property
    def encoding(self) -> str:
        return self._encoding

    @encoding.setter
    def encoding(self, value: str):
        if value not in ["utf-8", "utf-16le", "utf-16be"]:
            raise ValueError(
                f"Encoding {value} is not supported. Supported encodings are 'utf-8', 'utf-16le' and 'utf-16be'"
            )
        self._encoding = value

    def __eq__(self, other):
        """
        Compare two SomeIpFixedSizeString objects for equality.

        Parameters:
            other (SomeIpFixedSizeArray): The object to compare with the current object.

        Returns:
            bool: True if the strings are equal, False otherwise.
        """
        if isinstance(other, SomeIpFixedSizeString):
            # Compare if the length (number of elements) of other array is the same
            if self._size != other._size:
                return False

            return self._data == other._data

        return False

    def __len__(self) -> int:
        """
        Return the length of the object on the wire in bytes. Includes the BOM and terminating '\0' character.

        Returns:
            int: The length of the object on the wire in bytes.
        """

        if self.encoding == "utf-8":
            return self.size + len(codecs.BOM_UTF8)
        elif self.encoding == "utf-16le" or self.encoding == "utf-16be":
            return (self.size * 2) + len(codecs.BOM_UTF16_LE)
        raise ValueError("Unknown encoding")

    def serialize(self) -> bytes:
        """
        Serialize the object into bytes by iterating over its attributes, excluding those starting with double underscores or underscores.
        For each attribute, it calls the `serialize` method of the attribute and appends the returned bytes to the output.

        Returns:
            bytes: The serialized representation of the object as bytes.
        """

        result = bytes()
        if self._encoding == "utf-8":
            result += codecs.BOM_UTF8
            result += self.data.encode("utf-8")
            filler_chars = self.size - len(self._data)
            result += "\0".encode("utf-8") * filler_chars
            assert len(result) == self.size + len(codecs.BOM_UTF8)
        elif self._encoding == "utf-16le":
            result += codecs.BOM_UTF16_LE
            result += self.data.encode("utf-16le")
            filler_chars = self.size - len(self._data)
            result += "\0".encode("utf-16le") * filler_chars
            assert len(result) == (self.size * 2) + len(codecs.BOM_UTF16_LE)
        elif self._encoding == "utf-16be":
            result += codecs.BOM_UTF16_BE
            result += self.data.encode("utf-16be")
            filler_chars = self.size - len(self._data)
            result += "\0".encode("utf-16be") * filler_chars
            assert len(result) == (self.size * 2) + len(codecs.BOM_UTF16_BE)

        return result

    def deserialize(self, payload: bytes):
        """
        Deserialize the payload into the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            self: The deserialized object.

        This method deserializes the payload into the string. It automatically detects the encoding from the BOM
        at the beginning of the payload.
        """

        # Get the byte order mark, either 3 bytes for utf-8 or 2 bytes for utf-16
        bom = payload[:3] if payload.startswith(codecs.BOM_UTF8) else payload[:2]
        if bom == codecs.BOM_UTF8:
            self.encoding = "utf-8"
            start_idx = 3
            end_idx = start_idx + self.size
            decoded_string = payload[start_idx:end_idx].decode("utf-8")
            self.data = decoded_string.rstrip("\0")
        elif bom == codecs.BOM_UTF16_LE:
            self.encoding = "utf-16le"
            start_idx = 2
            end_idx = start_idx + self.size * 2
            decoded_string = payload[start_idx:end_idx].decode("utf-16le")
            self.data = decoded_string.rstrip("\0")
        elif bom == codecs.BOM_UTF16_BE:
            self.encoding = "utf-16be"
            start_idx = 2
            end_idx = start_idx + self.size * 2
            decoded_string = payload[start_idx:end_idx].decode("utf-16be")
            self.data = decoded_string.rstrip("\0")
        else:
            raise ValueError("Unknown encoding")

        return self


class SomeIpDynamicSizeString(Generic[T]):
    """
    A datatype for a SOME/IP dynamically sized string.
    """

    _has_dynamic_size = True

    def __init__(self, value: str = ""):
        """
        Initializes a new instance of the SomeIpDynamicSizeString class.

        Parameters:
            value (str): The initial string data of the object.

        Returns:
            None
        """
        self._data = value
        self._length_field_length = 4  # The length of the length field in bytes. It can be either 1, 2 or 4 bytes.
        # BOM + string + terminating '\0' character
        self._length_field_value = 3 + len(value) + 1
        self._encoding = "utf-8"
        self._length = self._length_field_length + self._length_field_value

    @property
    def data(self) -> str:
        return self._data

    @data.setter
    def data(self, value: str):
        self._data = value
        if self.encoding == "utf-8":
            self._length_field_value = 3 + len(value) + 1
        elif self.encoding == "utf-16le" or self.encoding == "utf-16be":
            self._length_field_value = 2 + len(value) * 2 + 2
        self._length = self._length_field_length + self._length_field_value

    @property
    def length_field_length(self):
        return self._length_field_length

    @length_field_length.setter
    def length_field_length(self, value):
        if value in [1, 2, 4]:
            self._length_field_length = value
            self._length = self._length_field_length + self._length_field_value
        else:
            raise ValueError("Length field length must be 1, 2 or 4 bytes")

    @property
    def encoding(self) -> str:
        return self._encoding

    @encoding.setter
    def encoding(self, value: str):
        if value not in ["utf-8", "utf-16le", "utf-16be"]:
            raise ValueError(
                f"Encoding {value} is not supported. Supported encodings are 'utf-8', 'utf-16le' and 'utf-16be'"
            )
        self._encoding = value
        if self.encoding == "utf-8":
            self._length_field_value = 3 + len(self.data) + 1
        elif self.encoding == "utf-16le" or self.encoding == "utf-16be":
            self._length_field_value = 2 + len(self.data) * 2 + 2
        self._length = self._length_field_length + self._length_field_value

    def __eq__(self, other):
        """
        Compare two SomeIpDynamicSizeString objects for equality.

        Parameters:
            other (SomeIpDynamicSizeString): The object to compare with the current object.

        Returns:
            bool: True if the strings are equal, False otherwise.
        """
        if isinstance(other, SomeIpDynamicSizeString):
            if len(self) != len(other):
                return False
            if self.encoding != other.encoding:
                return False
            if self.length_field_length != other.length_field_length:
                return False

            return self._data == other._data

        return False

    def __len__(self) -> int:
        """
        Return the length of the serialized string in bytes.

        Returns:
            int: The length of the string.
        """
        return self._length

    def serialize(self) -> bytes:
        """
        Serialize the object into bytes by iterating over its attributes, excluding those starting with double underscores or underscores.
        For each attribute, it calls the `serialize` method of the attribute and appends the returned bytes to the output.

        Returns:
            bytes: The serialized representation of the object as bytes.
        """

        # The length field is placed first
        # The length is measured in bytes and includes the BOM length. The length of the length field is not included

        result = bytes()

        bom = None
        encoded_str = None
        if self.encoding == "utf-8":
            bom = codecs.BOM_UTF8
            encoded_str = self.data.encode("utf-8")
        elif self.encoding == "utf-16le":
            bom = codecs.BOM_UTF16_LE
            encoded_str = self.data.encode("utf-16le")
        elif self.encoding == "utf-16be":
            bom = codecs.BOM_UTF16_BE
            encoded_str = self.data.encode("utf-16be")

        length = (
            len(bom) + len(encoded_str) + 1
        )  # +1 for the terminating '\0' character
        if self.encoding == "utf-16le" or self.encoding == "utf-16be":
            length += 1  # The terminating '\0' character is 2 bytes in utf-16

        if self.length_field_length == 1:
            if length > 255:
                raise ValueError(
                    "Length of the string exceeds maximum value of 255 for 1 byte length field."
                )
            result += struct.pack(">B", length)
        elif self.length_field_length == 2:
            if length > 65535:
                raise ValueError(
                    "Length of the string exceeds maximum value of 65535 for 2 byte length field."
                )
            result += struct.pack(">H", length)
        elif self.length_field_length == 4:
            if length > 4294967295:
                raise ValueError(
                    "Length of the string exceeds maximum value of 4294967295 for 4 byte length field."
                )
            result += struct.pack(">L", length)

        result += bom
        result += encoded_str
        result += "\0".encode(self.encoding)
        assert len(result) == self._length
        return result

    def deserialize(self, payload: bytes):
        """
        Deserialize the payload into the object.

        Args:
            payload (bytes): The payload to be deserialized.

        Returns:
            self: The deserialized object.

        This method deserializes the payload into the string. It automatically detects the encoding from the BOM
        at the beginning of the payload.
        """

        if len(payload) < self.length_field_length:
            raise ValueError(
                f"Deserialization failed: Payload is too short. Payload length: {len(payload)}"
            )

        length_field = payload[: self.length_field_length]
        if self.length_field_length == 1:
            (length,) = struct.unpack(">B", length_field)
        elif self.length_field_length == 2:
            (length,) = struct.unpack(">H", length_field)
        elif self.length_field_length == 4:
            (length,) = struct.unpack(">L", length_field)

        if len(payload) < length:
            raise ValueError(
                f"Deserialization failed: Payload is too short. Payload length: {len(payload)}. Expected length: {length}"
            )

        bom_start = self.length_field_length

        # Get the byte order mark, either 3 bytes for utf-8 or 2 bytes for utf-16
        bom = (
            payload[bom_start : bom_start + 3]
            if payload[bom_start:].startswith(codecs.BOM_UTF8)
            else payload[bom_start : bom_start + 2]
        )
        if bom == codecs.BOM_UTF8:
            self.encoding = "utf-8"
            start_idx = self.length_field_length + 3
            end_idx = start_idx + length - 3
            decoded_string = payload[start_idx:end_idx].decode("utf-8")
            self.data = decoded_string.rstrip("\0")
        elif bom == codecs.BOM_UTF16_LE:
            self.encoding = "utf-16le"
            start_idx = self.length_field_length + 2
            end_idx = start_idx + length - 2
            decoded_string = payload[start_idx:end_idx].decode("utf-16le")
            self.data = decoded_string.rstrip("\0")
        elif bom == codecs.BOM_UTF16_BE:
            self.encoding = "utf-16be"
            start_idx = self.length_field_length + 2
            end_idx = start_idx + length - 2
            decoded_string = payload[start_idx:end_idx].decode("utf-16be")
            self.data = decoded_string.rstrip("\0")
        else:
            raise ValueError("Unknown encoding")

        self._length = self._length_field_length + length

        return self
