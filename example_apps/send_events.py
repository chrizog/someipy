import sys
sys.path.append("..")

import asyncio
import ipaddress
import logging

import src.service_discovery
import src._internal.someip_header
import src._internal.someip_sd_header
import src.server_service_instance
from src.logging import set_someipy_log_level
from src.serialization import Uint8, Uint64, Float32
from temperature_msg import TemparatureMsg

SD_MULTICAST_GROUP = "224.224.224.245"
SD_PORT = 30490
INTERFACE_IP = "127.0.0.1"

SAMPLE_EVENTGROUP_ID = 20
SAMPLE_EVENT_ID = 32796

async def main():

    # It's possible to configure the logging level of the someipy library, e.g. logging.INFO, logging.DEBUG, logging.WARN, ..
    set_someipy_log_level(logging.DEBUG)

    # Since the construction of the class ServiceDiscoveryProtocol is not trivial and would require an async __init__ function
    # use the construct_service_discovery function
    # The local interface IP address needs to be passed so that the src-address of all SD UDP packets is correctly set
    service_discovery = await src.service_discovery.construct_service_discovery(SD_MULTICAST_GROUP, SD_PORT, INTERFACE_IP)

    # 1. For sending events use a ServerServiceInstance
    # 2. Pass the service and instance ID, version and endpoint and TTL. The endpoint is needed again as the src-address
    # and port of all sent events
    # 3. The ServiceDiscoveryProtocol object has to be passed as well, so the ServerServiceInstance can offer his service to 
    # other ECUs
    # 4. cyclic_offer_delay_ms is the period of sending cyclic SD Offer service entries
    service_instance_temperature = src.server_service_instance.ServerServiceInstance(
        service_id=1,
        instance_id=1000,
        major_version=1,
        minor_version=0,
        endpoint=(ipaddress.IPv4Address(INTERFACE_IP), 3000), # src IP and port of the service
        ttl=5,
        sd_sender=service_discovery,
        cyclic_offer_delay_ms=2000
    )

    # The service instance has to be attached always to the ServiceDiscoveryProtocol object, so that the service instance
    # is notified by the ServiceDiscoveryProtocol about e.g. subscriptions from other ECUs
    service_discovery.attach(service_instance_temperature)

    # For demonstration purposes we will construct a second ServerServiceInstance
    service_instance_2 = src.server_service_instance.ServerServiceInstance(
        service_id=2,
        instance_id=2000,
        major_version=1,
        minor_version=0,
        endpoint=(ipaddress.IPv4Address(INTERFACE_IP), 3001), # src IP and port of the service
        ttl=5,
        sd_sender=service_discovery,
        cyclic_offer_delay_ms=2000
    )
    service_discovery.attach(service_instance_2)

    # After constructing and attaching ServerServiceInstances to the ServiceDiscoveryProtocol objects the
    # start_offer method has to be called. This will start an internal timer, which will periodically send
    # Offer service entries with a period of "cyclic_offer_delay_ms" which has been passed above
    print("Start offering services..")
    service_instance_temperature.start_offer()
    service_instance_2.start_offer()

    tmp_msg = TemparatureMsg()

    # Reminder: Do NOT write "tmp_msg.version.major = 1". Always use the provided classes in someipy like Uint8,
    # so that the data can be propery serialized. Python literals won't be serialized properly
    tmp_msg.version.major = Uint8(1)
    tmp_msg.version.minor = Uint8(0)
    
    tmp_msg.measurements.data[0] = Float32(20.0)
    tmp_msg.measurements.data[1] = Float32(21.0)
    tmp_msg.measurements.data[2] = Float32(22.0)
    tmp_msg.measurements.data[3] = Float32(23.0)

    try:
        # Either cyclically send events in an endless loop..
        while True:
            await asyncio.sleep(5)
            tmp_msg.timestamp = Uint64(tmp_msg.timestamp.value + 1)
            payload = tmp_msg.serialize()
            service_instance_temperature.send_event(SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload)

        # .. or in case your app is waiting for external events, using await asyncio.Future() to
        # keep the task alive
        # await asyncio.Future()
    except asyncio.CancelledError as e:
        print("Stop offering services..")
        await service_instance_temperature.stop_offer()
        await service_instance_2.stop_offer()
    finally:
        print("Service Discovery close..")
        service_discovery.close()

    print("End main task..")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt as e:
        pass
