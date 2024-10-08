import asyncio
import ipaddress
import logging
import sys
from typing import Tuple

from someipy import TransportLayerProtocol
from someipy.service import ServiceBuilder, Method
from someipy.service_discovery import construct_service_discovery
from someipy.server_service_instance import construct_server_service_instance
from someipy.logging import set_someipy_log_level
from someipy.serialization import Sint32
from addition_method_parameters import Addends, Sum

SD_MULTICAST_GROUP = "224.224.224.245"
SD_PORT = 30490
DEFAULT_INTERFACE_IP = "127.0.0.1"  # Default IP if not provided

SAMPLE_SERVICE_ID = 0x1234
SAMPLE_INSTANCE_ID = 0x5678
SAMPLE_METHOD_ID = 0x0123


def add_method_handler(input_data: bytes, addr: Tuple[str, int]) -> Tuple[bool, bytes]:
    # Process the data and return True/False indicating the success of the operation
    # and the result of the method call in serialized form (bytes object)
    # If False is returned an error message will be sent back to the client. In that case
    # the payload can be an empty bytes-object, e.g. return False, b""

    print(
        f"Received data: {' '.join(f'0x{b:02x}' for b in input_data)} from IP: {addr[0]} Port: {addr[1]}"
    )

    try:
        # Deserialize the input data
        addends = Addends()
        addends.deserialize(input_data)
    except Exception as e:
        print(f"Error during deserialization: {e}")
        return False, b""

    # Perform the addition
    sum = Sum()
    sum.value = Sint32(addends.addend1.value + addends.addend2.value)
    print(f"Send back: {' '.join(f'0x{b:02x}' for b in sum.serialize())}")
    return True, sum.serialize()


async def main():

    # It's possible to configure the logging level of the someipy library, e.g. logging.INFO, logging.DEBUG, logging.WARN, ..
    set_someipy_log_level(logging.DEBUG)

    # Get interface ip to use from command line argument (--interface_ip) or use default
    interface_ip = DEFAULT_INTERFACE_IP
    for i, arg in enumerate(sys.argv):
        if arg == "--interface_ip":
            if i + 1 < len(sys.argv):
                interface_ip = sys.argv[i + 1]
                break

    # Since the construction of the class ServiceDiscoveryProtocol is not trivial and would require an async __init__ function
    # use the construct_service_discovery function
    # The local interface IP address needs to be passed so that the src-address of all SD UDP packets is correctly set
    service_discovery = await construct_service_discovery(
        SD_MULTICAST_GROUP, SD_PORT, interface_ip
    )

    addition_method = Method(id=SAMPLE_METHOD_ID, method_handler=add_method_handler)

    addition_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .with_method(addition_method)
        .build()
    )

    # For offering methods use a ServerServiceInstance
    service_instance_addition = await construct_server_service_instance(
        addition_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint=(
            ipaddress.IPv4Address(interface_ip),
            3000,
        ),  # src IP and port of the service
        ttl=5,
        sd_sender=service_discovery,
        cyclic_offer_delay_ms=2000,
        protocol=TransportLayerProtocol.TCP,
    )

    # The service instance has to be attached always to the ServiceDiscoveryProtocol object, so that the service instance
    # is notified by the ServiceDiscoveryProtocol about e.g. subscriptions from other ECUs
    service_discovery.attach(service_instance_addition)

    # ..it's also possible to construct another ServerServiceInstance and attach it to service_discovery as well

    # After constructing and attaching ServerServiceInstances to the ServiceDiscoveryProtocol object the
    # start_offer method has to be called. This will start an internal timer, which will periodically send
    # Offer service entries with a period of "cyclic_offer_delay_ms" which has been passed above
    print("Start offering service..")
    service_instance_addition.start_offer()

    try:
        # Keep the task alive
        await asyncio.Future()
    except asyncio.CancelledError:
        print("Stop offering service..")
        await service_instance_addition.stop_offer()
    finally:
        print("Service Discovery close..")
        service_discovery.close()

    print("End main task..")


if __name__ == "__main__":
    asyncio.run(main())
