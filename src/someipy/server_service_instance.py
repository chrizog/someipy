from dataclasses import dataclass
from typing import List

from someipy.service_discovery import *
from someipy._internal.message_types import MessageType
from someipy._internal.someip_sd_builder import *
from someipy._internal.someip_header import SomeIpHeader
from someipy._internal.someip_sd_header import (
    SdService,
    TransportLayerProtocol,
    SdEventGroupEntry,
)

from someipy._internal.simple_timer import SimplePeriodicTimer
from someipy._internal.utils import (
    create_udp_socket,
    endpoint_to_str_int_tuple,
    EndpointType,
)
from someipy._internal.logging import get_logger

_logger = get_logger("server_service_instance")


@dataclass
class EventGroup:
    eventgroup_id: int
    ttl: int
    event_ids: List[int]


@dataclass
class EventGroupSubscriber:
    eventgroup_id: int
    endpoint: EndpointType


class ServerServiceInstance(ServiceDiscoveryObserver):
    service_id: int
    instance_id: int
    major_version: int
    minor_version: int
    endpoint: EndpointType
    ttl: int

    sd_sender: ServiceDiscoverySender
    cyclic_offer_delay_ms: int

    eventgroups: List[EventGroup]
    subscribers: List[EventGroupSubscriber]
    offer_timer: SimplePeriodicTimer

    def __init__(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
        minor_version: int,
        endpoint: EndpointType,
        ttl: int = 0,
        sd_sender=None,
        cyclic_offer_delay_ms=2000,
    ):
        self.service_id = service_id
        self.instance_id = instance_id
        self.major_version = major_version
        self.minor_version = minor_version
        self.endpoint = endpoint
        self.ttl = ttl
        self.sd_sender = sd_sender
        self.cyclic_offer_delay_ms = cyclic_offer_delay_ms

        self.sender_socket = create_udp_socket(str(endpoint[0]), endpoint[1])

        self.eventgroups = []
        self.subscribers = []

        self.offer_timer = None

    def add_eventgroup(self, eventgroup: EventGroup):
        ids = [e.eventgroup_id for e in self.eventgroups]
        if not eventgroup.eventgroup_id in ids:
            self.eventgroups.append(eventgroup)

    def find_service_update(self):
        # TODO: implement SD behaviour and send back offer
        pass

    def offer_service_update(self, _: SdService):
        # No reaction in a server instance needed
        pass

    def _insert_subscriber(self, new_subscriber: EventGroupSubscriber) -> None:
        for s in self.subscribers:
            if new_subscriber == s:
                return
        self.subscribers.append(new_subscriber)

    def send_event(self, event_group_id: int, event_id: int, payload: bytes) -> None:
        length = 8 + len(payload)
        someip_header = SomeIpHeader(
            service_id=self.service_id,
            method_id=event_id,
            length=length,
            client_id=0x00,  # TODO
            session_id=0x01,  # TODO
            protocol_version=1,  # TODO,
            interface_version=1,  # TODO,
            message_type=MessageType.NOTIFICATION.value,
            return_code=0x00,
        )

        for sub in self.subscribers:
            if sub.eventgroup_id == event_group_id:
                self.sender_socket.sendto(
                    someip_header.to_buffer() + payload,
                    endpoint_to_str_int_tuple(sub.endpoint),
                )

    def subscribe_eventgroup_update(
        self,
        sd_event_group: SdEventGroupEntry,
        ipv4_endpoint_option: SdIPV4EndpointOption,
    ) -> None:
        eventgroup_ids = [e.eventgroup_id for e in self.eventgroups]

        # [PRS_SOMEIPSD_00829] When receiving a SubscribeEventgroupAck or Sub-
        # scribeEventgroupNack the Service ID, Instance ID, Eventgroup ID, and Major Ver-
        # sion shall match exactly to the corresponding SubscribeEventgroup Entry to identify
        # an Eventgroup of a Service Instance.c

        if (
            sd_event_group.sd_entry.service_id == self.service_id
            and sd_event_group.sd_entry.instance_id == self.instance_id
            # and sd_event_group.eventgroup_id in eventgroup_ids
        ):
            (
                session_id,
                reboot_flag,
            ) = self.sd_sender.get_unicast_session_handler().update_session()
            # TODO: enable major version check
            # sd_event_group.sd_entry.major_version == self.major_version:
            # print("Service received subscribe entry -> send back ACK")
            ack_entry = build_subscribe_eventgroup_ack_entry(
                service_id=sd_event_group.sd_entry.service_id,
                instance_id=sd_event_group.sd_entry.instance_id,
                major_version=sd_event_group.sd_entry.major_version,
                ttl=sd_event_group.sd_entry.ttl,
                event_group_id=sd_event_group.eventgroup_id,
            )
            header_output = build_subscribe_eventgroup_ack_sd_header(
                entry=ack_entry, session_id=session_id, reboot_flag=reboot_flag
            )

            self.sd_sender.send_unicast(
                buffer=header_output.to_buffer(),
                dest_ip=ipv4_endpoint_option.ipv4_address,
            )

            subscriber = EventGroupSubscriber(
                eventgroup_id=sd_event_group.eventgroup_id,
                endpoint=(ipv4_endpoint_option.ipv4_address, ipv4_endpoint_option.port),
            )
            self._insert_subscriber(subscriber)

    def subscribe_ack_eventgroup_update(self, _: SdEventGroupEntry) -> None:
        # Not needed for server instance
        pass

    def offer_timer_callback(self):
        (
            session_id,
            reboot_flag,
        ) = self.sd_sender.get_multicast_session_handler().update_session()

        _logger.debug(
            f"Offer service for instance 0x{self.instance_id:04X}, service: 0x{self.service_id:04X}, TTL: {self.ttl}, version: {self.major_version}.{self.minor_version}, session ID: {session_id}"
        )

        service_to_offer = SdService(
            service_id=self.service_id,
            instance_id=self.instance_id,
            major_version=1,
            minor_version=0,
            ttl=self.ttl,
            endpoint=self.endpoint,
            protocol=TransportLayerProtocol.UDP,
        )
        sd_header = build_offer_service_sd_header(
            service_to_offer, session_id, reboot_flag
        )
        self.sd_sender.send_multicast(sd_header.to_buffer())

    def start_offer(self):
        self.offer_timer = SimplePeriodicTimer(
            self.cyclic_offer_delay_ms / 1000.0, self.offer_timer_callback
        )
        self.offer_timer.start()

    async def stop_offer(self):
        _logger.debug(
            f"Stop offer for instance 0x{self.instance_id:04X}, service: 0x{self.service_id:04X}"
        )

        if self.offer_timer is not None:
            self.offer_timer.stop()
            await self.offer_timer.task
        # TODO: send out a stop offer sd message before stopping the timer
