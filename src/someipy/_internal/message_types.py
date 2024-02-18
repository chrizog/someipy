from enum import Enum

class MessageType(Enum):
    REQUEST = 0x00
    REQUEST_NO_RETURN = 0x01
    NOTIFICATION = 0x02
    RESPONSE = 0x80
    ERROR = 0x81
    TP_REQUEST = 0x20
    TP_REQUEST_NO_RETURN = 0x21
    TP_NOTIFICATION = 0x22
    TP_RESPONSE = 0xa0
    TP_ERROR = 0xa1

# PRS_SOMEIP_00191
class ReturnCode(Enum):
    E_OK = 0x00 # No error occurred
    E_NOT_OK = 0x01 # An unspecified error occurred
    E_UNKNOWN_SERVICE = 0x02 # The requested Service ID is unknown. 
    E_UNKNOWN_METHOD = 0x03 # The requested Method ID is unknown.
    E_NOT_READY = 0x04 # Service ID and Method ID are known. Application not running.
    E_NOT_REACHABLE = 0x05 # System running the service is not reachable (inter-nal error code only).
    E_TIMEOUT = 0x06 # A timeout occurred (internal error code only).
    E_WRONG_PROTOCOL_VERSION = 0x07 # Version of SOME/IP protocol not supported
    E_WRONG_INTERFACE_VERSION = 0x08 # Interface version mismatch
    E_MALFORMED_MESSAGE = 0x09 # Deserialization error, so that payload cannot be de-serialized.
    E_WRONG_MESSAGE_TYPE = 0x0a # An unexpected message type was received (e.g. REQUEST_NO_RETURN for a method defined as REQUEST).
