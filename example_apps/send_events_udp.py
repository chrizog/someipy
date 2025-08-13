import asyncio
import logging
import sys

from someipy import (
    TransportLayerProtocol,
    ServiceBuilder,
    EventGroup,
    connect_to_someipy_daemon,
)
from someipy.server_service_instance import ServerServiceInstance
from someipy.service import Event
from someipy.someipy_logging import set_someipy_log_level
from someipy.serialization import Uint8, Uint64, Float32
from temperature_msg import TemparatureMsg

DEFAULT_INTERFACE_IP = "127.0.0.1"  # Default IP if not provided

SAMPLE_SERVICE_ID = 0x1234  # dec 4660
SAMPLE_INSTANCE_ID = 0x5678  # dec 22136
SAMPLE_EVENTGROUP_ID = 0x0321  # dec 801
SAMPLE_EVENT_ID = 0x0123  # dec 291


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
    service_instance_temperature = ServerServiceInstance(
        daemon=someipy_daemon,
        service=temperature_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint_ip=interface_ip,
        endpoint_port=3000,
        ttl=5,
        cyclic_offer_delay_ms=2000,
    )

    # After constructing a ServerServiceInstances the start_offer method has to be called. This will start an internal timer,
    # which will periodically send Offer service entries with a period of "cyclic_offer_delay_ms" which has been passed above
    print("Start offering service..")
    await service_instance_temperature.start_offer()

    tmp_msg = TemparatureMsg()

    # Reminder: Do NOT use "tmp_msg.version.major = 1". Always use the provided classes in someipy like Uint8,
    # so that the data can be properly serialized. Python literals won't be serialized properly
    tmp_msg.version.major = Uint8(1)
    tmp_msg.version.minor = Uint8(0)

    tmp_msg.measurements.data[0] = Float32(20.0)
    tmp_msg.measurements.data[1] = Float32(21.0)
    tmp_msg.measurements.data[2] = Float32(22.0)
    tmp_msg.measurements.data[3] = Float32(23.0)

    try:
        # Either cyclically send events in an endless loop..
        while True:
            await asyncio.sleep(1)
            tmp_msg.timestamp = Uint64(tmp_msg.timestamp.value + 1)
            payload = tmp_msg.serialize()
            service_instance_temperature.send_event(
                SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload
            )

        # .. or in case your app is waiting for external events, use await asyncio.Future() to
        # keep the task alive
        # await asyncio.Future()
    except asyncio.CancelledError:
        print("Stop offering service..")
        await service_instance_temperature.stop_offer()
    finally:
        print("Disconnect from daemon..")
        await someipy_daemon.disconnect_from_daemon()

    print("End main task..")


if __name__ == "__main__":
    asyncio.run(main())
