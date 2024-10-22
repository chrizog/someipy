import asyncio
import datetime
import ipaddress
import logging
import sys

from someipy import TransportLayerProtocol, MessageType, ReturnCode
from someipy.client_service_instance import (
    MethodResult,
    construct_client_service_instance,
)
from someipy.service import ServiceBuilder
from someipy.service_discovery import construct_service_discovery
from someipy.logging import set_someipy_log_level
from addition_method_parameters import Addends, Sum

SD_MULTICAST_GROUP = "224.224.224.245"
SD_PORT = 30490
DEFAULT_INTERFACE_IP = "127.0.0.1"  # Default IP if not provided

SAMPLE_SERVICE_ID = 0x1234
SAMPLE_INSTANCE_ID = 0x5678
SAMPLE_METHOD_ID = 0x0123


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

    addition_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .build()
    )

    # For calling methods construct a ClientServiceInstance
    client_instance_addition = await construct_client_service_instance(
        service=addition_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint=(ipaddress.IPv4Address(interface_ip), 3002),
        ttl=5,
        sd_sender=service_discovery,
        protocol=TransportLayerProtocol.UDP,
    )

    # The service instance has to be attached always to the ServiceDiscoveryProtocol object, so that the service instance
    # is notified by the ServiceDiscoveryProtocol about e.g. subscriptions or offers from other ECUs
    service_discovery.attach(client_instance_addition)

    try:
        while True:
            method_parameter = Addends(addend1=1, addend2=2)

            try:
                # You can query if the service offering the method was already found via SOME/IP service discovery
                print(f"Service found: {client_instance_addition.service_found()}")

                while not client_instance_addition.service_found():
                    print("Waiting for service..")
                    await asyncio.sleep(0.5)

                # The call_method function can raise an error, e.g. if no TCP connection to the server can be established
                # In case there is an application specific error in the server, the server still returns a response and the
                # message_type and return_code are evaluated.
                method_result = await client_instance_addition.call_method(
                    SAMPLE_METHOD_ID, method_parameter.serialize()
                )

                if method_result.message_type == MessageType.RESPONSE:
                    print(
                        f"Received result for method: {' '.join(f'0x{b:02x}' for b in method_result.payload)}"
                    )
                    if method_result.return_code == ReturnCode.E_OK:
                        sum = Sum().deserialize(method_result.payload)
                        print(f"Sum: {sum.value.value}")
                    else:
                        print(
                            f"Method call returned an error: {method_result.return_code}"
                        )
                elif method_result.message_type == MessageType.ERROR:
                    print("Server returned an error..")
                    # In case the server includes an error message in the payload, it can be deserialized and printed

            except Exception as e:
                print(f"Error during method call: {e}")

            await asyncio.sleep(1)

    except asyncio.CancelledError:
        print("Shutdown..")
    finally:
        print("Service Discovery close..")
        service_discovery.close()

        print("Shutdown service instance..")
        await client_instance_addition.close()

    print("End main task..")


if __name__ == "__main__":
    asyncio.run(main())
