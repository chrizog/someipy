from test_base import TestBase


class TestSendEventsTcp(TestBase):

    def __init__(self, repository, ld_library_path=None, interface_ip="127.0.0.1"):
        super().__init__()

        self.ld_library_path = ld_library_path
        self.vsomeip_app = [
            f"{repository}/integration_tests/install/send_events/send_events"
        ]
        self.someipy_app = [
            "python3",
            f"{repository}/example_apps/send_events_tcp.py",
            f"--interface_ip {interface_ip}",
        ]
        self.vsomeip_config = (
            f"{repository}/integration_tests/install/send_events/vsomeip-client.json"
        )

    def evaluate(self) -> bool:
        sent_events = 0
        received_events = 0
        for l in self.output_someipy_app:
            if "Send event for instance" in l:
                sent_events += 1

        for l in self.output_vsomeip_app:
            if "received a notification for event" in l:
                received_events += 1

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
            self.print_outputs()
            return False
