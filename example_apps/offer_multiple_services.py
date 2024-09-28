import asyncio
import ipaddress
import logging
import sys

from someipy import (
    TransportLayerProtocol,
    ServiceBuilder,
    EventGroup,
    construct_server_service_instance,
)
from someipy.service_discovery import construct_service_discovery
from someipy.logging import set_someipy_log_level
from someipy.serialization import Uint8, Uint64, Float32
from temperature_msg import TemparatureMsg

SD_MULTICAST_GROUP = "224.224.224.245"
SD_PORT = 30490
DEFAULT_INTERFACE_IP = "127.0.0.1"  # Default IP if not provided

SAMPLE_SERVICE_ID = 0x1234
SAMPLE_INSTANCE_ID_1 = 0x5678
SAMPLE_INSTANCE_ID_2 = 0x6789
SAMPLE_EVENTGROUP_ID = 0x0321
SAMPLE_EVENT_ID = 0x0123

"""
This application demonstrates how to offer multiple services on different endpoints.
For simplicity and keeping the example short, it uses the same service, event group and event ID for both instances.
Only the instance ID and the port offers. Both instances send an event via UDP to subscribed clients.
"""


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

    temperature_eventgroup = EventGroup(
        id=SAMPLE_EVENTGROUP_ID, event_ids=[SAMPLE_EVENT_ID]
    )

    # In this example the same service is offered in two different service instances. Of course
    # a second different service can be defined and passed to the second server service instance.
    temperature_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .with_eventgroup(temperature_eventgroup)
        .build()
    )

    # For sending events use a ServerServiceInstance
    # We will construct two instances that provide the same service, but have different instance
    # IDs and run on different endpoints (ports 3000 and 3001)
    service_instance_temperature_1 = await construct_server_service_instance(
        temperature_service,
        instance_id=SAMPLE_INSTANCE_ID_1,
        endpoint=(
            ipaddress.IPv4Address(interface_ip),
            3000,
        ),  # src IP and port of the service
        ttl=5,
        sd_sender=service_discovery,
        cyclic_offer_delay_ms=2000,
        protocol=TransportLayerProtocol.UDP,
    )

    service_instance_temperature_2 = await construct_server_service_instance(
        temperature_service,
        instance_id=SAMPLE_INSTANCE_ID_2,
        endpoint=(
            ipaddress.IPv4Address(interface_ip),
            3001,
        ),  # src IP and port of the service
        ttl=5,
        sd_sender=service_discovery,
        cyclic_offer_delay_ms=2000,
        protocol=TransportLayerProtocol.UDP,
    )

    # The service instances have to be attached always to the ServiceDiscoveryProtocol object, so that the service instances
    # are notified by the ServiceDiscoveryProtocol about e.g. subscriptions from other ECUs
    service_discovery.attach(service_instance_temperature_1)
    service_discovery.attach(service_instance_temperature_2)

    # After constructing and attaching ServerServiceInstances to the ServiceDiscoveryProtocol object the
    # start_offer method has to be called. This will start an internal timer, which will periodically send
    # Offer service entries with a period of "cyclic_offer_delay_ms" which has been passed above
    print("Start offering services..")
    service_instance_temperature_1.start_offer()
    service_instance_temperature_2.start_offer()

    tmp_msg = TemparatureMsg()

    # Reminder: Do NOT use "tmp_msg.version.major = 1". Always use the provided classes in someipy like Uint8,
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
            await asyncio.sleep(0.5)
            tmp_msg.timestamp = Uint64(tmp_msg.timestamp.value + 1)
            payload = tmp_msg.serialize()

            # Send out an event on the first instance
            service_instance_temperature_1.send_event(
                SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload
            )

            # Sleep for half a second and send out an event on the second service instance
            await asyncio.sleep(0.5)
            service_instance_temperature_2.send_event(
                SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload
            )

        # .. or in case your app is waiting for external events like method calss,
        # use await asyncio.Future() to keep the task alive
        # await asyncio.Future()
    except asyncio.CancelledError:
        print("Stop offering service.s.")
        await service_instance_temperature_1.stop_offer()
        await service_instance_temperature_2.stop_offer()
    finally:
        print("Service Discovery close..")
        service_discovery.close()

    print("End main task..")


if __name__ == "__main__":
    asyncio.run(main())
