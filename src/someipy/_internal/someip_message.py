from dataclasses import dataclass
from someipy._internal.someip_header import SomeIpHeader

@dataclass
class SomeIpMessage:
    header: SomeIpHeader
    payload: bytes

    def serialize(self) -> bytes:
        return self.header.to_buffer() + self.payload
