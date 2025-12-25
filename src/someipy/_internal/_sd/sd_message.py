from typing import List
from someipy._internal._sd.entries.sd_entry import SdEntry


class SdMessage:

    def __init__(self):
        self.source: str = ""
        self.source_port: int = 0
        self.multicast: bool = True
        self.timestamp: float = 0.0

        self.session_id: int = 0
        self.entries: List[SdEntry] = []
