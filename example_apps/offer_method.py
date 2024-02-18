import asyncio
import ipaddress
import logging
from typing import Tuple

from someipy.service_discovery import construct_service_discovery
from someipy.server_service_instance import Method, construct_server_service_instance
from someipy.logging import set_someipy_log_level

SD_MULTICAST_GROUP = "224.224.224.245"
SD_PORT = 30490
INTERFACE_IP = "127.0.0.1"

SAMPLE_INSTANCE_ID = 1000
SAMPLE_SERVICE_ID = 1001
SAMPLE_METHOD_ID = 1002

def temperature_method_handler(input_data: bytes) -> Tuple[bool, bytes]:
    # Process the data and return True/False indicating the success of the operation
    # and the result of the method call in serialized form (bytes object)
    # If False is returned an error message will be sent back to the client. In that case
    # the payload can be an empty bytes-object
    return True, input_data

async def main():

    # It's possible to configure the logging level of the someipy library, e.g. logging.INFO, logging.DEBUG, logging.WARN, ..
    set_someipy_log_level(logging.DEBUG)

    # Since the construction of the class ServiceDiscoveryProtocol is not trivial and would require an async __init__ function
    # use the construct_service_discovery function
    # The local interface IP address needs to be passed so that the src-address of all SD UDP packets is correctly set
    service_discovery = await construct_service_discovery(SD_MULTICAST_GROUP, SD_PORT, INTERFACE_IP)

    # 1. For sending events use a ServerServiceInstance
    # 2. Pass the service and instance ID, version and endpoint and TTL. The endpoint is needed again as the src-address
    # and port of all sent events
    # 3. The ServiceDiscoveryProtocol object has to be passed as well, so the ServerServiceInstance can offer his service to 
    # other ECUs
    # 4. cyclic_offer_delay_ms is the period of sending cyclic SD Offer service entries
    service_instance_temperature = await construct_server_service_instance(
        service_id=SAMPLE_SERVICE_ID,
        instance_id=SAMPLE_INSTANCE_ID,
        major_version=1,
        minor_version=0,
        endpoint=(ipaddress.IPv4Address(INTERFACE_IP), 3000), # src IP and port of the service
        ttl=5,
        sd_sender=service_discovery,
        cyclic_offer_delay_ms=2000
    )

    # Create a method by defining a method ID and a method handler function
    # The method handler function takes in a payload bytes-object as an argument and
    # has to return a boolean (success) and a bytes-object for the result
    temperature_method = Method(method_id=SAMPLE_METHOD_ID, method_handler=temperature_method_handler)
    
    # Append the method to the server instance
    service_instance_temperature.add_method(temperature_method)

    # The service instance has to be attached always to the ServiceDiscoveryProtocol object, so that the service instance
    # is notified by the ServiceDiscoveryProtocol about e.g. subscriptions from other ECUs
    service_discovery.attach(service_instance_temperature)

    # After constructing and attaching ServerServiceInstances to the ServiceDiscoveryProtocol objects the
    # start_offer method has to be called. This will start an internal timer, which will periodically send
    # Offer service entries with a period of "cyclic_offer_delay_ms" which has been passed above
    print("Start offering services..")
    service_instance_temperature.start_offer()

    try:
        # Keep the task alive until Crtl+C is pressed
        await asyncio.Future()
    except asyncio.CancelledError as _:
        print("Stop offering services..")
        await service_instance_temperature.stop_offer()
    finally:
        print("Service Discovery close..")
        service_discovery.close()

    print("End main task..")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt as _:
        pass
