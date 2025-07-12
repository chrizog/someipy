from test_base import TestBase


class TestCallMethodTcp(TestBase):

    def __init__(self, repository, ld_library_path=None, interface_ip="127.0.0.2"):
        super().__init__()

        self.ld_library_path = ld_library_path
        self.vsomeip_app = [
            f"{repository}/integration_tests/install/call_method_tcp/call_method_tcp"
        ]
        self.someipy_app = [
            "python3",
            f"{repository}/example_apps/call_method_tcp.py",
            f"--interface_ip",
            f"{interface_ip}",
        ]
        self.vsomeip_config = f"{repository}/integration_tests/install/call_method_tcp/vsomeip-client.json"

        self.someipydaemon_app = [
            "python3",
            f"{repository}/src/someipy/someipyd.py",
            "--config",
            f"{repository}/src/someipy/someipyd.json",
        ]

    def evaluate(self) -> bool:
        method_calls = 0
        responses = 0
        for l in self.output_someipy_app:
            if "Received result for method" in l:
                responses += 1
            if "Trying to call method " in l:
                method_calls += 1

        print(f"Method calls: {method_calls}. Responses: {responses}")
        difference = method_calls - responses
        tolerance = max(0.1 * method_calls, 1)
        if abs(difference) <= tolerance and method_calls > 0 and responses > 0:
            return True
        else:
            print(f"Method calls: {method_calls}. Responses: {responses}")
            self.print_outputs()
            return False
