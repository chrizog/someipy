import asyncio
import ipaddress
import logging
import sys

from someipy import (
    TransportLayerProtocol,
    ServiceBuilder,
    EventGroup,
)
from someipy._internal.someipy_daemon_client import connect_to_someipy_daemon
from someipy.server_service_instance import ServerServiceInstance
from someipy.service import Event
from someipy.someipy_logging import set_someipy_log_level
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

    someipy_daemon = await connect_to_someipy_daemon()

    temperature_event = Event(id=SAMPLE_EVENT_ID, protocol=TransportLayerProtocol.UDP)

    temperature_eventgroup = EventGroup(
        id=SAMPLE_EVENTGROUP_ID, events=[temperature_event]
    )

    temperature_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .with_eventgroup(temperature_eventgroup)
        .build()
    )

    # For sending events use a ServerServiceInstance
    service_instance_temperature_1 = ServerServiceInstance(
        daemon=someipy_daemon,
        service=temperature_service,
        instance_id=SAMPLE_INSTANCE_ID_1,
        endpoint_ip=interface_ip,
        endpoint_port=3000,
        ttl=5,
        cyclic_offer_delay_ms=2000,
    )

    service_instance_temperature_2 = ServerServiceInstance(
        daemon=someipy_daemon,
        service=temperature_service,
        instance_id=SAMPLE_INSTANCE_ID_2,
        endpoint_ip=interface_ip,
        endpoint_port=3001,
        ttl=5,
        cyclic_offer_delay_ms=2000,
    )

    print("Start offering services..")
    await service_instance_temperature_1.start_offer()
    await service_instance_temperature_2.start_offer()

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
        print("Stop offering services..")
        await service_instance_temperature_1.stop_offer()
        await service_instance_temperature_2.stop_offer()
    finally:
        print("Disconnect from daemon..")
        await someipy_daemon.disconnect_from_daemon()

    print("End main task..")


if __name__ == "__main__":
    asyncio.run(main())
