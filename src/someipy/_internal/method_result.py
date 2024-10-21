from .message_types import MessageType
from .return_codes import ReturnCode


class MethodResult:
    message_type: MessageType
    return_code: ReturnCode
    payload: bytes

    def __init__(self):
        self.message_type = MessageType.RESPONSE
        self.return_code = ReturnCode.E_OK
        self.payload = b""
