import struct

import pytest

from someipy._internal.someip_endpoint import UDPSomeipEndpoint
from someipy._internal.someip_header import SomeIpHeader

ADDR = ("127.0.0.1", 5000)


def make_request(
    service_id=0x1234,
    method_id=0x0001,
    payload=b"\x00\x16",
    client_id=0x0001,
    session_id=0x0001,
    interface_version=0x01,
    message_type=0x00,
) -> bytes:
    length = 8 + len(payload)
    header = struct.pack(
        ">HHIHHBBBB",
        service_id,
        method_id,
        length,
        client_id,
        session_id,
        0x01,
        interface_version,
        message_type,
        0x00,
    )
    return header + payload


@pytest.fixture
def received() -> list:
    return []


@pytest.fixture
def udp_endpoint(received) -> UDPSomeipEndpoint:
    endpoint = UDPSomeipEndpoint("127.0.0.1", 3000)
    endpoint.set_someip_callback(lambda msg, src, dst, proto: received.append(msg))
    return endpoint


def test_valid_datagram_is_delivered(udp_endpoint, received):
    udp_endpoint.datagram_received(make_request(), ADDR)
    assert len(received) == 1


def test_two_valid_datagrams_are_delivered_independently(udp_endpoint, received):
    udp_endpoint.datagram_received(make_request(session_id=1), ADDR)
    udp_endpoint.datagram_received(make_request(session_id=2), ADDR)
    assert [m.header.session_id for m in received] == [1, 2]


def test_short_datagram_is_not_delivered(udp_endpoint, received):
    udp_endpoint.datagram_received(b"\x12\x34\x00\x01\x00\x00", ADDR)  # 6 bytes
    assert received == []


@pytest.mark.parametrize(
    "short",
    [b"", b"\x00", b"\x12\x34\x00\x01\x00\x00", b"\x00" * (SomeIpHeader.MINIMAL_SIZE - 1)],
)
def test_recovery_after_short_datagram(udp_endpoint, received, short):
    # PRS_SOMEIP_00910: a too-short datagram is malformed and must not disable
    # the endpoint; a valid datagram received afterwards must still be delivered.
    udp_endpoint.datagram_received(short, ADDR)
    udp_endpoint.datagram_received(make_request(), ADDR)
    assert len(received) == 1, (
        "endpoint stopped delivering valid datagrams after a short datagram"
    )


def test_recovery_after_oversized_length_field(udp_endpoint, received):
    # PRS_SOMEIP_00910: the length field must not exceed the datagram bytes.
    bogus = struct.pack(
        ">HHIHHBBBB", 0x1234, 0x0001, 0xFFFF, 0x0001, 0x0001, 0x01, 0x01, 0x00, 0x00
    )
    udp_endpoint.datagram_received(bogus, ADDR)
    udp_endpoint.datagram_received(make_request(), ADDR)
    assert len(received) == 1
