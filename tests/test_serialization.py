import sys
sys.path.append("src")

import pytest
from someipy.serialization import *


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
