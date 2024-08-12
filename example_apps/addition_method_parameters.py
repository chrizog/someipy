from dataclasses import dataclass
from someipy.serialization import (
    Sint32,
    Sint16,
    SomeIpPayload,
)

# In this example we define two method parameter types used for the Addition method example.
# In theory, Int16 and Sint32 types could be used directly instead of defining new classes,
# but this way the code is more readable and the types are more descriptive and extensible, i.e.
# you could other information such as version or metadata to the method parameters.


@dataclass
class Addends(SomeIpPayload):
    addend1: Sint16
    addend2: Sint16

    def __init__(self, addend1: int = 0, addend2: int = 0):
        self.addend1 = Sint16(addend1)
        self.addend2 = Sint16(addend2)


@dataclass
class Sum(SomeIpPayload):
    value: Sint32

    def __init__(self):
        self.value = Sint32()
