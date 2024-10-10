from test_base import TestBase
import re


class TestReceiveEventsUdp(TestBase):

    def __init__(self, repository, ld_library_path=None, interface_ip="127.0.0.1"):
        super().__init__()

        self.ld_library_path = ld_library_path
        self.vsomeip_app = [
            f"{repository}/integration_tests/install/receive_events_udp/receive_events_udp"
        ]
        self.someipy_app = [
            "python3",
            f"{repository}/example_apps/receive_events_udp.py",
            f"--interface_ip {interface_ip}",
        ]
        self.vsomeip_config = f"{repository}/integration_tests/install/receive_events_udp/vsomeip-client.json"

    def evaluate(self) -> bool:
        sent_events = 0
        received_events = 0
        for l in self.output_someipy_app:

            received_bytes_pattern = r"Received (\d+) bytes"
            match = re.search(received_bytes_pattern, l)
            if match:
                received_events += 1

        for l in self.output_vsomeip_app:
            if "Setting event" in l:
                sent_events += 1

        print(f"Received events: {received_events}. Sent events: {sent_events}")
        difference_sent_received = sent_events - received_events
        tolerance = max(0.1 * sent_events, 1)
        if (
            abs(difference_sent_received) <= tolerance
            and sent_events > 0
            and received_events > 0
        ):
            return True
        else:
            print(f"Received events: {received_events}. Sent events: {sent_events}")
            self.print_outputs()
            return False
