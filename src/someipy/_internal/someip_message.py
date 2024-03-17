from dataclasses import dataclass
from someipy._internal.someip_header import SomeIpHeader

@dataclass
class SomeIpMessage:
    header: SomeIpHeader
    payload: bytes
