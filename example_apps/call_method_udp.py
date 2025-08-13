import asyncio
import ipaddress
import logging
import sys

from someipy import (
    TransportLayerProtocol,
    MessageType,
    ReturnCode,
    connect_to_someipy_daemon,
)
from someipy.client_service_instance import (
    construct_client_service_instance,
)
from someipy.service import ServiceBuilder
from someipy.someipy_logging import set_someipy_log_level
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

    someipy_daemon = await connect_to_someipy_daemon()

    addition_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .build()
    )

    # For calling methods construct a ClientServiceInstance
    client_instance_addition = await construct_client_service_instance(
        daemon=someipy_daemon,
        service=addition_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint=(ipaddress.IPv4Address(interface_ip), 3002),
        ttl=5,
        protocol=TransportLayerProtocol.UDP,
    )

    # await service_instance.find_service(timeout=10)
    # Static config mit daemon=None
    # 5. instance.set_static_destination_configuration((ip, port))

    method_parameter = Addends(addend1=1, addend2=2)

    try:

        while not await client_instance_addition.service_found():
            print("Waiting for service..")
            await asyncio.sleep(0.5)

        while True:

            try:
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
        print("Shutdown service instance..")
        await client_instance_addition.close()

        await someipy_daemon.disconnect_from_daemon()

    print("End main task..")


if __name__ == "__main__":
    asyncio.run(main())
