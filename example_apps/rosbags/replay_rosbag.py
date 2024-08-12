import asyncio
import ipaddress
import logging
import rosbag
import TurtlesimPose

from someipy import (
    TransportLayerProtocol,
    ServiceBuilder,
    EventGroup,
    construct_server_service_instance,
)
from someipy.service_discovery import construct_service_discovery
from someipy.logging import set_someipy_log_level
from someipy.serialization import Float32

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

    turtle_eventgroup = EventGroup(id=SAMPLE_EVENTGROUP_ID, event_ids=[SAMPLE_EVENT_ID])
    turtle_pose_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .with_eventgroup(turtle_eventgroup)
        .build()
    )

    # For sending events use a ServerServiceInstance
    service_instance_turtle_pose = await construct_server_service_instance(
        turtle_pose_service,
        instance_id=SAMPLE_INSTANCE_ID,
        endpoint=(
            ipaddress.IPv4Address(INTERFACE_IP),
            3000,
        ),  # src IP and port of the service
        ttl=5,
        sd_sender=service_discovery,
        cyclic_offer_delay_ms=2000,
        protocol=TransportLayerProtocol.UDP,
    )

    # The service instance has to be attached always to the ServiceDiscoveryProtocol object, so that the service instance
    # is notified by the ServiceDiscoveryProtocol about e.g. subscriptions from other ECUs
    service_discovery.attach(service_instance_turtle_pose)

    # ..it's also possible to construct another ServerServiceInstance and attach it to service_discovery as well

    # After constructing and attaching ServerServiceInstances to the ServiceDiscoveryProtocol object the
    # start_offer method has to be called. This will start an internal timer, which will periodically send
    # Offer service entries with a period of "cyclic_offer_delay_ms" which has been passed above
    print("Start offering service..")
    service_instance_turtle_pose.start_offer()

    bag = rosbag.Bag("test.bag")

    # Get the timestamp of the first message of /turtle1/pose in order to reproduce the timing of the recording
    starting_timestamp = next(bag.read_messages(topics=["/turtle1/pose"])).timestamp

    for topic, msg, t in bag.read_messages(topics=["/turtle1/pose"]):

        # Calculate the time difference between the current message and the message before
        time_sleep = (t - starting_timestamp).to_sec()

        # Use asyncio.sleep to wait for the time difference between the current message and the message before
        print(f"Sleeping for {(t - starting_timestamp).to_sec()} seconds")
        await asyncio.sleep(time_sleep)

        # Create a SomeIpPayload object and fill it with the values from the rosbag message
        someipPose = TurtlesimPose.TurtlesimPose()
        someipPose.x = Float32(msg.x)
        someipPose.y = Float32(msg.y)
        someipPose.theta = Float32(msg.theta)
        someipPose.linear_velocity = Float32(msg.linear_velocity)
        someipPose.angular_velocity = Float32(msg.angular_velocity)

        # Serialize the SomeIpPayload object to a byte array
        payload = someipPose.serialize()

        print(f"Sending event for message {msg}")
        # Send the serialized byte array to all subscribers of the event group
        service_instance_turtle_pose.send_event(
            SAMPLE_EVENTGROUP_ID, SAMPLE_EVENT_ID, payload
        )

        starting_timestamp = t

    bag.close()

    await service_instance_turtle_pose.stop_offer()
    print("Service Discovery close..")
    service_discovery.close()
    print("End main task..")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
