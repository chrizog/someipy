from enum import Enum
import struct
from someipy._internal.someip_header import SomeIpHeader
from someipy._internal.someip_message import SomeIpMessage


class SomeipDataProcessor:

    class State(Enum):
        HEADER = 1
        PAYLOAD = 2
        PENDING = 3

    def __init__(self):
        self._reset()
        self._someip_message = None

    def _reset(self):
        self._state = SomeipDataProcessor.State.HEADER
        self._buffer = bytes()
        self._expected_bytes = 8  # 2x 32-bit for header
        self._total_length = 0

    def process_data(self, new_data: bytes) -> bool:
        self._buffer += new_data
        current_length = len(self._buffer)

        if self._state == SomeipDataProcessor.State.HEADER:
            if current_length < self._expected_bytes:
                # The header was not fully received yet
                return False
            else:
                _, _, length = struct.unpack(">HHI", self._buffer[0:8])
                self._total_length = length + 8
                self._expected_bytes = self._total_length - current_length
                self._state = SomeipDataProcessor.State.PAYLOAD

        if self._state == SomeipDataProcessor.State.PAYLOAD:
            if current_length < self._total_length:
                # The payload was not fully received yet
                self._expected_bytes = self._total_length - current_length
                return False
            else:
                payload_length = self._total_length - 16
                header = SomeIpHeader.from_buffer(self._buffer)
                self._someip_message = SomeIpMessage(
                    header=header, payload=self._buffer[16 : (16 + payload_length)]
                )

                self._state = SomeipDataProcessor.State.HEADER
                # If more data was received over the current message boundary, keep the data
                self._buffer = self._buffer[self._total_length :]
                self._expected_bytes = 8
                self._total_length = 0

                return True

    @property
    def someip_message(self):
        """Returns the SomeIpMessage that was received and interpreted"""
        return self._someip_message

    @property
    def expected_bytes(self):
        """Returns the number of bytes that are expected to complete the current message"""
        return self._expected_bytes
