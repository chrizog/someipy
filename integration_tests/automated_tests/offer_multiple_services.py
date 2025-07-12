from test_base import TestBase


class TestOfferMultipleServices(TestBase):

    def __init__(self, repository, ld_library_path=None, interface_ip="127.0.0.1"):
        super().__init__()

        self.ld_library_path = ld_library_path
        self.vsomeip_app = [
            f"{repository}/integration_tests/install/offer_multiple_services/offer_multiple_services"
        ]
        self.someipy_app = [
            "python3",
            f"{repository}/example_apps/offer_multiple_services.py",
            f"--interface_ip",
            f"{interface_ip}",
        ]
        self.vsomeip_config = f"{repository}/integration_tests/install/offer_multiple_services/vsomeip-client.json"

        self.someipydaemon_app = [
            "python3",
            f"{repository}/src/someipy/someipyd.py",
            "--config",
            f"{repository}/src/someipy/someipyd.json",
        ]

    def evaluate(self) -> bool:
        sent_events = 0
        received_events = 0
        for l in self.output_someipy_app:
            if "Transmitting message: {'type': 'SendEventRequest'" in l:
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
