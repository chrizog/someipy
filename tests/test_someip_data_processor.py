import pytest
from someipy._internal.someip_data_processor import SomeipDataProcessor
from someipy._internal.someip_header import SomeIpHeader
from someipy._internal.message_types import MessageType
from someipy._internal.someip_message import SomeIpMessage


@pytest.fixture
def valid_someip_message() -> SomeIpMessage:
    # length is 8 bytes + payload size
    payload_size = 64
    length = 8 + payload_size

    someip_header = SomeIpHeader(
        service_id=1,
        method_id=2,
        length=length,
        client_id=3,
        session_id=4,
        protocol_version=1,
        interface_version=2,
        message_type=MessageType.REQUEST.value,
        return_code=0x00,
    )
    payload = b"\x00" * payload_size
    return SomeIpMessage(header=someip_header, payload=payload)


@pytest.fixture
def corrupt_someip_message() -> SomeIpMessage:
    # length is 8 bytes + payload size
    payload_size = 64
    length = 8 + payload_size + 1  # +1 for corrupt header

    someip_header = SomeIpHeader(
        service_id=1,
        method_id=2,
        length=length,
        client_id=3,
        session_id=4,
        protocol_version=1,
        interface_version=2,
        message_type=MessageType.REQUEST.value,
        return_code=0x00,
    )
    payload = b"\x00" * payload_size
    return SomeIpMessage(header=someip_header, payload=payload)


def test_process_with_datagrams(valid_someip_message):
    data = valid_someip_message.header.to_buffer() + valid_someip_message.payload
    processor = SomeipDataProcessor(datagram_mode=True)
    result = processor.process_data(data)

    assert result is True
    assert processor.someip_message.header == valid_someip_message.header
    assert processor._expected_bytes == 0
    assert len(processor._buffer) == 0

    result = processor.process_data(data)
    assert result is True
    assert processor.someip_message.header == valid_someip_message.header
    assert processor._expected_bytes == 0
    assert len(processor._buffer) == 0


def test_process_with_malformed_datagrams(corrupt_someip_message):
    data = corrupt_someip_message.header.to_buffer() + corrupt_someip_message.payload
    processor = SomeipDataProcessor(datagram_mode=True)

    result = processor.process_data(data)

    assert result is False
