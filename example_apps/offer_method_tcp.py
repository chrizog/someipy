import asyncio
import ipaddress
import logging
import sys
from typing import Tuple

from someipy import (
    TransportLayerProtocol,
    MethodResult,
    ReturnCode,
    MessageType,
    ServerServiceInstance,
    connect_to_someipy_daemon,
    ServiceBuilder,
    Method,
)
from someipy.someipy_logging import set_someipy_log_level
from someipy.serialization import Sint32
from addition_method_parameters import Addends, Sum

DEFAULT_INTERFACE_IP = "127.0.0.1"  # Default IP if not provided

SAMPLE_SERVICE_ID = 0x1234
SAMPLE_INSTANCE_ID = 0x5678
SAMPLE_METHOD_ID = 0x0123


async def add_method_handler(input_data: bytes, addr: Tuple[str, int]) -> MethodResult:
    print(
        f"Received data: {' '.join(f'0x{b:02x}' for b in input_data)} from IP: {addr[0]} Port: {addr[1]}"
    )

    result = MethodResult()

    try:
        # Deserialize the input data
        addends = Addends()
        addends.deserialize(input_data)
    except Exception as e:
        print(f"Error during deserialization: {e}")

        # Set the return code to E_MALFORMED_MESSAGE and return
        result.message_type = MessageType.RESPONSE
        result.return_code = ReturnCode.E_MALFORMED_MESSAGE
        return result

    # Perform the addition
    sum = Sum()
    sum.value = Sint32(addends.addend1.value + addends.addend2.value)
    print(f"Send back: {' '.join(f'0x{b:02x}' for b in sum.serialize())}")

    result.message_type = MessageType.RESPONSE
    result.return_code = ReturnCode.E_OK
    result.payload = sum.serialize()
    return result


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

    addition_method = Method(
        id=SAMPLE_METHOD_ID,
        protocol=TransportLayerProtocol.TCP,
        method_handler=add_method_handler,
    )

    addition_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .with_method(addition_method)
        .build()
    )

    # For offering methods use a ServerServiceInstance
    service_instance_addition = ServerServiceInstance(
        daemon=someipy_daemon,
        service=addition_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint_ip=interface_ip,
        endpoint_port=3000,
        ttl=5,
        cyclic_offer_delay_ms=2000,
    )

    # After constructing ServerServiceInstances the start_offer method has to be called.
    # This will start an internal timer, which will periodically send
    # Offer service entries with a period of "cyclic_offer_delay_ms"
    print("Start offering service..")
    await service_instance_addition.start_offer()

    try:
        # Keep the task alive
        await asyncio.Future()
    except asyncio.CancelledError:
        print("Stop offering service..")
        await service_instance_addition.stop_offer()
    finally:
        print("Disconnect from daemon..")
        await someipy_daemon.disconnect_from_daemon()

    print("End main task..")


if __name__ == "__main__":
    asyncio.run(main())
