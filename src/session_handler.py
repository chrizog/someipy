from typing import Tuple

class SessionHandler:
    session_id: int
    reboot_flag: bool

    def __init__(self, initial_value=0):
        self.session_id = initial_value
        self.reboot_flag = True

    def update_session(self) -> Tuple[int, bool]:
        self.session_id += 1
        if self.session_id > 0xFFFF:
            self.session_id = 1
            self.reboot_flag = False

        return self.session_id, self.reboot_flag