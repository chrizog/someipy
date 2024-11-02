from dataclasses import dataclass

import pytest
from someipy.serialization import (
    Uint8,
    Uint16,
    Uint32,
    Uint64,
    Sint8,
    Sint16,
    Sint32,
    Sint64,
    Bool,
    Float32,
    Float64,
    SomeIpPayload,
    SomeIpFixedSizeArray,
    SomeIpDynamicSizeArray,
    SomeIpFixedSizeString,
    SomeIpDynamicSizeString,
)


def test_base_types_len():
    assert 1 == len(Uint8(1))
    assert 2 == len(Uint16(1))
    assert 4 == len(Uint32(1))
    assert 8 == len(Uint64(1))

    assert 1 == len(Sint8(-1))
    assert 2 == len(Sint16(-1))
    assert 4 == len(Sint32(-1))
    assert 8 == len(Sint64(-1))

    assert 1 == len(Bool(True))
    assert 4 == len(Float32(1.0))
    assert 8 == len(Float64(1.0))


@dataclass
class MsgBaseTypesOnly(SomeIpPayload):
    """
    The dataclass decorator will generate an __eq__ method which
    can be used for comparing the content of two messages
    """

    # Expected 13 bytes in total
    x: Uint8  # 1 byte
    y: Uint32  # 4 bytes
    z: Float64  # 8 bytes

    def __init__(self):
        self.x = Uint8(0)
        self.y = Uint32(0)
        self.z = Float64(0.0)


@dataclass
class MsgWithOneStruct(SomeIpPayload):
    # Expected 1 + 13 + 4 bytes in total
    a: Uint8
    b: MsgBaseTypesOnly
    c: Sint32

    def __init__(self):
        self.a = Uint8(0)
        self.b = MsgBaseTypesOnly()
        self.c = Sint32(0)


def test_someip_payload_len():
    assert 13 == len(MsgBaseTypesOnly())
    assert (13 + 1 + 4) == len(MsgWithOneStruct())


def test_struct_equals_operator():
    m_1 = MsgBaseTypesOnly()
    m_2 = MsgBaseTypesOnly()
    assert m_1 == m_2

    m_1.x = Uint8(1)
    assert m_1 != m_2

    m_2.x = Uint8(1)
    assert m_1 == m_2


def test_struct_serialization_and_deserialization():
    m = MsgBaseTypesOnly()
    m.y = Uint32(4)
    # Expected: 0x 00 00000004 0000000000000000
    assert bytes.fromhex("00000000040000000000000000") == m.serialize()

    m.x = Uint8(255)
    # Expected: 0x FF 00000004 0000000000000000
    assert bytes.fromhex("ff000000040000000000000000") == m.serialize()

    m_again = MsgBaseTypesOnly().deserialize(
        bytes.fromhex("ff000000040000000000000000")
    )
    assert m_again == m

    # The first byte is changed now to decimal 254
    m_different = MsgBaseTypesOnly().deserialize(
        bytes.fromhex("fe000000040000000000000000")
    )
    assert m_different != m_again
    assert m_different != m


def test_fixed_size_array_length():
    a = SomeIpFixedSizeArray(Uint16, 10)
    expected_bytes = len(Uint16()) * 10
    assert len(a) == expected_bytes


def test_fixed_size_array_equals_operator():
    a = SomeIpFixedSizeArray(Uint16, 10)
    b = SomeIpFixedSizeArray(Uint16, 10)
    assert a == b

    c = SomeIpFixedSizeArray(Uint8, 10)
    assert a != c

    a.data[0] = Uint16(5)
    assert a != b

    b.data[0] = Uint16(5)
    assert a == b


def test_fixed_size_array_serialization_and_deserialization():
    a = SomeIpFixedSizeArray(Uint8, 4)
    # Expected hex: 0x 00 00 00 00
    assert bytes.fromhex("00000000") == a.serialize()

    a.data[0] = Uint8(1)
    a.data[1] = Uint8(2)
    a.data[2] = Uint8(3)
    a.data[3] = Uint8(4)
    # Expected hex: 0x 01 02 03 04
    assert bytes.fromhex("01020304") == a.serialize()

    a_again = SomeIpFixedSizeArray(Uint8, 4).deserialize(bytes.fromhex("01020304"))
    assert a_again == a


def test_dynamic_size_array_length():
    a = SomeIpDynamicSizeArray(Uint16)

    assert len(a) == a.length_field_length
    e = Uint16(1)
    a.data.append(e)
    assert len(a) == a.length_field_length + len(Uint16())
    del a.data[0]
    assert len(a) == a.length_field_length

    a.length_field_length = 2
    # Except only the length field with 2 bytes to be serialized and no data
    assert bytes.fromhex("0000") == a.serialize()

    a.length_field_length = 4
    # Except only the length field with 4 bytes to be serialized and no data
    assert bytes.fromhex("00000000") == a.serialize()

    a.data.append(Uint16(1))
    assert bytes.fromhex("000000020001") == a.serialize()

    a.data.append(Uint16(4))
    assert len(a) == 2 * len(Uint16()) + a.length_field_length
    assert bytes.fromhex("0000000400010004") == a.serialize()

    b = SomeIpDynamicSizeArray(Uint16)
    b.length_field_length = 4
    b = b.deserialize(bytes.fromhex("0000000400010004"))
    assert b == a
    assert b.data[0] == Uint16(1)
    assert b.data[1] == Uint16(4)
    assert len(b) == 2 * len(Uint16()) + a.length_field_length


def test_someip_fixed_size_string():
    a = SomeIpFixedSizeString(4)
    assert a.size == 4
    assert a.data == ""
    assert a.encoding == "utf-8"
    assert len(a) == 4 + 3

    with pytest.raises(ValueError):
        a.data = "Hello World"
    with pytest.raises(ValueError):
        a.encoding = "Hello World"

    a.data = "He"
    a.encoding = "utf-8"
    assert len(a) == 4 + 3

    b = SomeIpFixedSizeString(4)
    b.data = "He"
    assert a == b

    assert bytes.fromhex("EF BB BF 48 65 00 00") == a.serialize()

    a.encoding = "utf-16le"
    assert bytes.fromhex("FF FE 48 00 65 00 00 00 00 00") == a.serialize()

    a.encoding = "utf-16be"
    assert bytes.fromhex("FE FF 00 48 00 65 00 00 00 00") == a.serialize()

    b = SomeIpFixedSizeString(4)
    b.encoding = "utf-16be"
    b = b.deserialize(bytes.fromhex("EF BB BF 48 65 00 00 00 00"))
    assert b.encoding == "utf-8"
    assert b.data == "He"
    assert len(b) == 7

    b = b.deserialize(bytes.fromhex("FF FE 48 00 65 00 00 00 00 00"))
    assert b.encoding == "utf-16le"
    assert b.data == "He"
    assert len(b) == 10

    b = b.deserialize(bytes.fromhex("FE FF 00 48 00 65 00 00 00 00"))
    assert b.encoding == "utf-16be"
    assert b.data == "He"
    assert len(b) == 10


def test_someip_dynamic_size_string():
    a = SomeIpDynamicSizeString()
    assert a.data == ""
    assert a.encoding == "utf-8"
    assert a.length_field_length == 4
    assert a._length_field_value == 4
    assert len(a) == 4 + 3 + 1

    with pytest.raises(ValueError):
        a.encoding = "Hello World"
    with pytest.raises(ValueError):
        a.length_field_length = 0

    a.data = "He"
    a.encoding = "utf-8"
    assert len(a) == 4 + 3 + 2 + 1
    # 4 bytes for the length field, 3 bytes BOM and 3 bytes for the data including '\0'
    assert bytes.fromhex("00 00 00 06 EF BB BF 48 65 00") == a.serialize()

    a.encoding = "utf-16le"
    assert len(a) == 4 + 2 + 2 * 2 + 2
    assert bytes.fromhex("00 00 00 08 FF FE 48 00 65 00 00 00") == a.serialize()

    a.encoding = "utf-16be"
    assert len(a) == 4 + 2 + 2 * 2 + 2
    assert bytes.fromhex("00 00 00 08 FE FF 00 48 00 65 00 00") == a.serialize()

    a.encoding = "utf-8"
    a.length_field_length = 2
    assert len(a) == 2 + 3 + 2 + 1
    # 2 bytes for the length field, 3 bytes BOM and 3 bytes for the data including '\0'
    assert bytes.fromhex("00 06 EF BB BF 48 65 00") == a.serialize()

    b = SomeIpDynamicSizeString()
    b.encoding = "utf-16be"
    b.length_field_length = 4
    b = b.deserialize(bytes.fromhex("00 00 00 09 EF BB BF 48 65 00 00 00 00"))
    assert len(b) == 13
    assert b.encoding == "utf-8"
    assert b.data == "He"

    b = b.deserialize(bytes.fromhex("00 00 00 0A FF FE 48 00 65 00 00 00 00 00"))
    assert b.encoding == "utf-16le"
    assert b.data == "He"

    b = b.deserialize(bytes.fromhex("00 00 00 0A FE FF 00 48 00 65 00 00 00 00"))
    assert b.encoding == "utf-16be"
    assert b.data == "He"

    b.length_field_length = 2
    b = b.deserialize(bytes.fromhex("00 0A FE FF 00 48 00 65 00 00 00 00"))
    assert b.encoding == "utf-16be"
    assert b.data == "He"


@dataclass
class MsgWithStrings(SomeIpPayload):
    a: Uint16
    b: SomeIpDynamicSizeString
    d: Uint32

    def __init__(self):
        self.a = Uint16(10)
        self.b = SomeIpDynamicSizeString("123")
        self.c = Uint32(5)


def test_struct_with_dynamic_sized_types():
    a = MsgWithStrings()
    assert len(a) == len(Uint16()) + len(SomeIpDynamicSizeString("123")) + len(Uint32())
    assert len(a) == 2 + 4 + 3 + 3 + 1 + 4
    assert len(a.serialize()) == len(a)

    assert (
        bytes.fromhex("00 0A 00 00 00 07 EF BB BF 31 32 33 00 00 00 00 05")
        == a.serialize()
    )

    a.b = SomeIpDynamicSizeString("1234")
    assert len(a) == 2 + 4 + 3 + 3 + 1 + 4 + 1
    assert (
        bytes.fromhex("00 0A 00 00 00 08 EF BB BF 31 32 33 34 00 00 00 00 05")
        == a.serialize()
    )

    b = MsgWithStrings().deserialize(
        bytes.fromhex("00 0A 00 00 00 08 EF BB BF 31 32 33 34 00 00 00 00 05")
    )
    assert b.a == Uint16(10)
    assert b.b == SomeIpDynamicSizeString("1234")
    assert b.c == Uint32(5)


@dataclass
class MsgWithTwoStrings(SomeIpPayload):
    a: Uint16
    b: SomeIpDynamicSizeString
    c: SomeIpDynamicSizeString
    d: Uint32

    def __init__(self):
        self.a = Uint16(10)
        self.b = SomeIpDynamicSizeString("123")
        self.c = SomeIpDynamicSizeString("4321")
        self.c.encoding = "utf-16be"
        self.d = Uint32(5)


def test_struct_with_dynamic_sized_types():
    a = MsgWithTwoStrings()
    assert len(a) == 2 + 4 + 3 + 3 + 1 + 4 + 2 + 4 * 2 + 2 + 4
    assert len(a.serialize()) == len(a)

    assert (
        bytes.fromhex(
            "00 0A 00 00 00 07 EF BB BF 31 32 33 00 00 00 00 0C FE FF 00 34 00 33 00 32 00 31 00 00 00 00 00 05"
        )
        == a.serialize()
    )

    b = MsgWithTwoStrings().deserialize(
        bytes.fromhex(
            "00 0A 00 00 00 07 EF BB BF 31 32 33 00 00 00 00 0C FE FF 00 34 00 33 00 32 00 31 00 00 00 00 00 05"
        )
    )
    assert b.a == Uint16(10)
    assert b.b == SomeIpDynamicSizeString("123")

    c = SomeIpDynamicSizeString("4321")
    c.encoding = "utf-16be"
    assert b.c == c
    assert b.d == Uint32(5)


@dataclass
class MsgWithDynamicArrays(SomeIpPayload):
    a: Uint16
    b: SomeIpDynamicSizeArray[Uint8]
    c: Uint32
    d: SomeIpDynamicSizeArray[Uint16]

    def __init__(self):
        self.a = Uint16(10)
        self.b = SomeIpDynamicSizeArray(Uint8)
        self.c = Uint32(5)
        self.d = SomeIpDynamicSizeArray(Uint16)


def test_struct_with_dynamic_arrays():
    a = MsgWithDynamicArrays()
    assert len(a) == 2 + 4 + 4 + 4
    assert len(a.serialize()) == len(a)
    assert bytes.fromhex("00 0A 00 00 00 00 00 00 00 05 00 00 00 00") == a.serialize()

    a.b.data.append(Uint8(1))
    assert len(a.serialize()) == len(a)
    assert (
        bytes.fromhex("00 0A 00 00 00 01 01 00 00 00 05 00 00 00 00") == a.serialize()
    )

    b = MsgWithDynamicArrays().deserialize(
        bytes.fromhex("00 0A 00 00 00 01 01 00 00 00 05 00 00 00 00")
    )

    assert b.a == Uint16(10)
    assert b.b.data[0] == Uint8(1)
    assert b.c == Uint32(5)
    assert len(b.d) == b.d.length_field_length
