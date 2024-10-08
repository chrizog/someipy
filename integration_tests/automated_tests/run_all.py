import time
from send_events_udp import TestSendEventsUdp
from send_events_tcp import TestSendEventsTcp
from receive_events_udp import TestReceiveEventsUdp
from receive_events_tcp import TestReceiveEventsTcp
from call_method_udp import TestCallMethodUdp
from call_method_tcp import TestCallMethodTcp
from offer_method_udp import TestOfferMethodUdp
from offer_method_tcp import TestOfferMethodTcp
from offer_multiple_services import TestOfferMultipleServices
import os

vsomeip_library_path = "<path to vsomeip libraries>"
current_file_path = os.path.abspath(__file__)
repository = os.path.dirname(os.path.dirname(current_file_path))
repository = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
test_durations = 10  # duration of each test in seconds

tests = {
    "send_events_udp": TestSendEventsUdp,
    "send_events_tcp": TestSendEventsTcp,
    "receive_events_udp": TestReceiveEventsUdp,
    "receive_events_tcp": TestReceiveEventsTcp,
    "call_method_udp": TestCallMethodUdp,
    "call_method_tcp": TestCallMethodTcp,
    "offer_method_udp": TestOfferMethodUdp,
    "offer_method_tcp": TestOfferMethodTcp,
    "offer_multiple_services": TestOfferMultipleServices,
}

test_summary = {}

for test_name, test_class in tests.items():
    print(f"Starting test: {test_name}")
    test = test_class(repository, ld_library_path=vsomeip_library_path)
    test.run(test_durations)
    success = test.evaluate()
    print(f"{test_name}: {'Success' if success else 'Failure'}\n---\n")
    test_summary[test_name] = success
    time.sleep(1)

print("\n\nTest summary:")
for test_name, success in test_summary.items():
    print(f"{test_name}:\t\t{'Success' if success else 'Failure'}")
