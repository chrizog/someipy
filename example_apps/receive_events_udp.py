import asyncio
import ipaddress
import logging
import sys

from someipy import ServiceBuilder, EventGroup, TransportLayerProtocol, SomeIpMessage
from someipy import connect_to_someipy_daemon
from someipy.client_service_instance import construct_client_service_instance
from someipy.someipy_logging import set_someipy_log_level
from temperature_msg import TemparatureMsg

SD_MULTICAST_GROUP = "224.224.224.245"
SD_PORT = 30490
DEFAULT_INTERFACE_IP = "127.0.0.2"  # Default IP if not provided

SAMPLE_SERVICE_ID = 0x1234
SAMPLE_INSTANCE_ID = 0x5678
SAMPLE_EVENTGROUP_ID = 0x0321
SAMPLE_EVENT_ID = 0x0123


def temperature_callback(someip_message: SomeIpMessage) -> None:
    """
    Callback function that is called when a temperature message is received.

    Args:
        someip_message (SomeIpMessage): The SomeIpMessage object containing the received message.

    Returns:
        None: This function does not return anything.
    """
    try:
        print(
            f"Received {len(someip_message.payload)} bytes for event {someip_message.header.method_id}. Try to deserialize.."
        )
        temperature_msg = TemparatureMsg().deserialize(someip_message.payload)
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

    # 1. For receiving events use a ClientServiceInstance. Since the construction of the class ClientServiceInstance is not
    # trivial and would require an async __init__ function use the construct_client_service_instance function
    # 2. Pass the service and instance ID, version and endpoint and TTL. The endpoint is needed because it will be the dest IP
    # and port to which the events are sent to and the client will listen to
    # 3. The ServiceDiscoveryProtocol object has to be passed as well, so the ClientServiceInstance can offer his service to
    # other ECUs
    temperature_eventgroup = EventGroup(
        id=SAMPLE_EVENTGROUP_ID, event_ids=[SAMPLE_EVENT_ID]
    )
    temperature_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .build()
    )

    service_instance_temperature = await construct_client_service_instance(
        daemon=someipy_daemon,
        service=temperature_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint=(ipaddress.IPv4Address(interface_ip), 3002),
        protocol=TransportLayerProtocol.UDP,
    )

    # It's possible to optionally register a callback function which will be called when an event from the
    # subscribed event group is received. The callback function will get the bytes of the payload passed which
    # can be deserialized in the callback function
    service_instance_temperature.register_callback(temperature_callback)

    # In order to subscribe to an event group, just pass the event group ID to the subscribe_eventgroup method
    service_instance_temperature.subscribe_eventgroup(SAMPLE_EVENTGROUP_ID, 5.0)

    try:
        # Keep the task alive
        await asyncio.Future()
    except asyncio.CancelledError as e:
        print("Shutdown..")
    finally:

        print("Shutdown service instance..")
        await service_instance_temperature.close()

        await someipy_daemon.disconnect_from_daemon()

    print("End main task..")
    for t in asyncio.all_tasks():
        print("----")
        print(t)


if __name__ == "__main__":

    asyncio.run(main())
