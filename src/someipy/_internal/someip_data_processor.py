import struct
from someipy._internal.someip_header import SomeIpHeader
from someipy._internal.someip_message import SomeIpMessage


class SomeipDataProcessor:

    def __init__(self, datagram_mode=True):
        self._buffer = bytes()
        self._expected_bytes = 0
        self._datagram_mode = datagram_mode
        self.someip_message = None

    def _reset(self):
        self._buffer = bytes()
        self._expected_bytes = 0

    def process_data(self, new_data: bytes) -> bool:

        received_length = len(new_data)

        print(" ".join(f"{byte:02X}" for byte in new_data))

        # UDP case
        if self._datagram_mode:
            header = SomeIpHeader.from_buffer(new_data)
            expected_total_length = 8 + header.length
            payload_length = expected_total_length - 16
            if received_length == expected_total_length:
                self.someip_message = SomeIpMessage(header=header, payload=new_data[16:])
                return True
            else:
                # Malformed package -> return False
                return False
        
        # From here on: TCP case
        if self._expected_bytes == 0 and len(self._buffer) == 0:

            if received_length >= 8:
                service_id, method_id, length = struct.unpack(">HHI", new_data[0:8])
                expected_total_length = 8 + length
                payload_length = expected_total_length - 16

                # Case 1: Received exactly one SOME/IP message
                if received_length == expected_total_length:
                    header = SomeIpHeader.from_buffer(new_data)
                    self.someip_message = SomeIpMessage(header=header, payload=new_data[16:(16+payload_length)])
                    self._reset()
                    return True
                # Case 2: Received less bytes than expected
                elif received_length < expected_total_length:
                    self._expected_bytes = (expected_total_length - received_length)
                    self._buffer = new_data
                    return False
                # Case 3: Received more bytes than expected
                elif received_length > expected_total_length:
                    # Assume it is the beginning of a new SOME/IP message, store remaining bytes in buffer
                    end_payload = 16 + payload_length
                    header = SomeIpHeader.from_buffer(new_data)
                    self.someip_message = SomeIpMessage(header=header, payload=new_data[16:end_payload])
                    self._buffer = new_data[end_payload:]
                    self._expected_bytes = 0

                    return True
                    
            else:
                pass # store in buffer