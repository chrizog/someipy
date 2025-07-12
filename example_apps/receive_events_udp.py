import asyncio
import logging
import sys

from someipy import ServiceBuilder, EventGroup, SomeIpMessage, TransportLayerProtocol
from someipy import connect_to_someipy_daemon
from someipy.client_service_instance import (
    ClientServiceInstance,
)
from someipy.service import Event
from someipy.someipy_logging import set_someipy_log_level
from temperature_msg import TemparatureMsg

SD_MULTICAST_GROUP = "224.224.224.245"
SD_PORT = 30490
DEFAULT_INTERFACE_IP = "127.0.0.1"  # Default IP if not provided

SAMPLE_SERVICE_ID = 0x1234
SAMPLE_INSTANCE_ID = 0x5678
SAMPLE_EVENTGROUP_ID = 0x0321
SAMPLE_EVENT_ID = 0x0123


def temperature_callback(event_id: int, event_payload: bytes) -> None:
    """
    Callback function that is called when a temperature message is received.

    Args:
        someip_message (SomeIpMessage): The SomeIpMessage object containing the received message.

    Returns:
        None: This function does not return anything.
    """
    try:
        print(
            f"Received {len(event_payload)} bytes for event 0x{event_id:04x}. Try to deserialize.."
        )
        temperature_msg = TemparatureMsg().deserialize(event_payload)
        print(temperature_msg)
    except Exception as e:
        print(f"Error in deserialization: {e}")


async def main():
    asyncio.get_running_loop().set_debug(True)
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

    # For calling methods construct a ClientServiceInstance
    service_instance_temperature = ClientServiceInstance(
        daemon=someipy_daemon,
        service=temperature_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint_ip=interface_ip,
        endpoint_port=3002,
    )

    # You can optionally register a callback function which will be called when an event from the
    # subscribed event group is received. The callback function will get the bytes of the payload passed which
    # can be deserialized in the callback function
    service_instance_temperature.register_callback(temperature_callback)

    # The second argument is the time to live (TTL) of the subscription in seconds
    service_instance_temperature.subscribe_eventgroup(temperature_eventgroup, 5.0)

    try:
        # Keep the task alive
        await asyncio.Future()
    except asyncio.CancelledError as e:
        print("Shutdown..")
    finally:

        print("Shutdown service instance..")

        await someipy_daemon.disconnect_from_daemon()

    print("End main task..")
    for t in asyncio.all_tasks():
        print("----")
        print(t)


if __name__ == "__main__":

    asyncio.run(main())
