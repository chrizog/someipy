import struct
from dataclasses import dataclass

SERVICE_ID_SD = 0xFFFF
METHOD_ID_SD = 0x8100
CLIENT_ID_SD = 0x0000
PROTOCOL_VERSION_SD = 0x01
INTERFACE_VERSION_SD = 0x01
MESSAGE_TYPE_SD = 0x02
RETURN_CODE_SD = 0x00

@dataclass
class SomeIpHeader:
    service_id: int
    method_id: int
    length: int
    client_id: int
    session_id: int
    protocol_version: int
    interface_version: int
    message_type: int
    return_code: int

    def is_sd_header(self) -> bool:
        return (
            self.service_id == SERVICE_ID_SD
            and self.method_id == METHOD_ID_SD
            and self.client_id == CLIENT_ID_SD
            and self.protocol_version == PROTOCOL_VERSION_SD
            and self.interface_version == INTERFACE_VERSION_SD
            and self.message_type == MESSAGE_TYPE_SD
            and self.return_code == RETURN_CODE_SD
            and self.session_id != 0
        )

    @classmethod
    def generate_sd_header(cls, length: int, session_id: int):
        return cls(
            service_id=SERVICE_ID_SD,
            method_id=METHOD_ID_SD,
            length=length,
            client_id=CLIENT_ID_SD,
            session_id=session_id,
            protocol_version=PROTOCOL_VERSION_SD,
            interface_version=INTERFACE_VERSION_SD,
            message_type=MESSAGE_TYPE_SD,
            return_code=RETURN_CODE_SD,
        )

    @classmethod
    def from_buffer(cls, buf: bytes):
        service_id, method_id, length = struct.unpack(">HHI", buf[0:8])
        if length <= 0:
            raise ValueError(f"Length in SOME/IP header is <=0 ({length})")

        if length < 8:
            raise ValueError(f"Length in SOME/IP header is <8 ({length})")

        client_id, session_id, protocol_version, interface_version, message_type, return_code = struct.unpack(">HHBBBB", buf[8:16])

        return cls(
            service_id,
            method_id,
            length,
            client_id,
            session_id,
            protocol_version,
            interface_version,
            message_type,
            return_code,
        )

    def to_buffer(self) -> bytes:
        return struct.pack(">HHIHHBBBB", self.service_id, self.method_id, self.length, self.client_id, self.session_id, self.protocol_version, self.interface_version, self.message_type, self.return_code)
    
def get_payload_from_someip_message(someip_header: SomeIpHeader, payload: bytes) -> bytes:
    length = someip_header.length
    payload_length = length - 8 # 8 bytes for request ID, protocol version, etc.
    return payload[16:(16+payload_length)]
