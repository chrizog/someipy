import struct

from dataclasses import dataclass

'''
The following basic datatypes as shown in Table 4.6 shall be supported:

Type Description Size [bit] Remark
boolean TRUE/FALSE value 8 FALSE (0), TRUE (1)
uint8 unsigned Integer 8
uint16 unsigned Integer 16
uint32 unsigned Integer 32
uint64 unsigned Integer 64
sint8 signed Integer 8
sint16 signed Integer 16
sint32 signed Integer 32
sint64 signed Integer 64
float32 floating point number 32 IEEE 754 binary32 (Single Precision)
float64 floating point number 64 IEEE 754 binary64 (Double Precision)
'''

@dataclass
class Uint8:
    value: int = 0

    def serialize(self) -> bytes:
        return struct.pack(">B", self.value)

@dataclass
class Uint16:
    value: int = 0

    def serialize(self) -> bytes:
        return struct.pack(">H", self.value)

@dataclass
class Uint32:
    value: int = 0

    def serialize(self) -> bytes:
        return struct.pack(">L", self.value)
    
@dataclass
class Uint64:
    value: int = 0

    def serialize(self) -> bytes:
        return struct.pack(">Q", self.value)    

@dataclass
class Bool:
    value: bool = False

    def serialize(self) -> bytes:
        if self.value == True:
            return struct.pack(">B", 1)
        else:
            return struct.pack(">B", 0)

class Float32:
    value: float = 0.0

    def serialize(self) -> bytes:
        return struct.pack(">f", self.value)

def serialize(obj) -> bytes:
    ordered_items = [(name, value) for name, value in obj.__dict__.items() if not name.startswith("__")]
    output = bytes()
    for (_, value) in ordered_items:
        # print(_ + f" {value.serialize()}")
        output += value.serialize()
    return output
