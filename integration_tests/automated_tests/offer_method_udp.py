from test_base import TestBase


class TestOfferMethodUdp(TestBase):

    def __init__(self, repository, ld_library_path=None, interface_ip="127.0.0.1"):
        super().__init__()

        self.ld_library_path = ld_library_path
        self.vsomeip_app = [
            f"{repository}/integration_tests/install/offer_method_udp/offer_method_udp"
        ]
        self.someipy_app = [
            "python3",
            f"{repository}/example_apps/offer_method_udp.py",
            f"--interface_ip {interface_ip}",
        ]
        self.vsomeip_config = f"{repository}/integration_tests/install/offer_method_udp/vsomeip-client.json"

    def evaluate(self) -> bool:
        method_calls = 0
        responses = 0
        for l in self.output_vsomeip_app:
            if "Received a response from Service" in l:
                responses += 1
            if "sent a request to Service" in l:
                method_calls += 1

        print(f"Method calls: {method_calls}. Responses: {responses}")
        difference = method_calls - responses
        tolerance = max(0.1 * method_calls, 1)
        if abs(difference) <= tolerance and method_calls > 0 and responses > 0:
            return True
        else:
            self.print_outputs()
            return False
