import asyncio
import ipaddress
import logging

from someipy import TransportLayerProtocol, ServiceBuilder, EventGroup, construct_server_service_instance
from someipy.service_discovery import construct_service_discovery
from someipy.logging import set_someipy_log_level
from someipy.serialization import Uint8, Uint64, Float32
from temperature_msg import TemparatureMsg

SD_MULTICAST_GROUP = "224.224.224.245"
SD_PORT = 30490
INTERFACE_IP = "127.0.0.1"

SAMPLE_SERVICE_ID = 0x1234
SAMPLE_INSTANCE_ID = 0x5678
SAMPLE_EVENTGROUP_ID = 0x0321
SAMPLE_EVENT_ID = 0x0123


async def main():
    # It's possible to configure the logging level of the someipy library, e.g. logging.INFO, logging.DEBUG, logging.WARN, ..
    set_someipy_log_level(logging.DEBUG)

    # Since the construction of the class ServiceDiscoveryProtocol is not trivial and would require an async __init__ function
    # use the construct_service_discovery function
    # The local interface IP address needs to be passed so that the src-address of all SD UDP packets is correctly set
    service_discovery = await construct_service_discovery(
        SD_MULTICAST_GROUP, SD_PORT, INTERFACE_IP
    )

    temperature_eventgroup = EventGroup(
        id=SAMPLE_EVENTGROUP_ID, event_ids=[SAMPLE_EVENT_ID]
    )
    temperature_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .with_eventgroup(temperature_eventgroup)
        .build()
    )

    # For sending events use a ServerServiceInstance
    service_instance_temperature = await construct_server_service_instance(
        temperature_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint=(
            ipaddress.IPv4Address(INTERFACE_IP),
            3000,
        ),  # src IP and port of the service
        ttl=5,
        sd_sender=service_discovery,
        cyclic_offer_delay_ms=2000,
        protocol=TransportLayerProtocol.TCP
    )

    # The service instance has to be attached always to the ServiceDiscoveryProtocol object, so that the service instance
    # is notified by the ServiceDiscoveryProtocol about e.g. subscriptions from other ECUs
    service_discovery.attach(service_instance_temperature)

    # ..it's also possible to construct another ServerServiceInstance and attach it to service_discovery as well

    # After constructing and attaching ServerServiceInstances to the ServiceDiscoveryProtocol object the
    # start_offer method has to be called. This will start an internal timer, which will periodically send
    # Offer service entries with a period of "cyclic_offer_delay_ms" which has been passed above
    print("Start offering service..")
    service_instance_temperature.start_offer()

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
        print("Service Discovery close..")
        service_discovery.close()

    print("End main task..")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
