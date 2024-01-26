import ipaddress

from dataclasses import dataclass
from typing import List, Tuple

from src.message_types import MessageType
from src.someip_header import SomeIpHeader
from src.someip_sd_header import (
    SdOfferedService,
    TransportLayerProtocol,
    SdEventGroupEntry,
    construct_subscribe_eventgroup_ack_sd_header,
    construct_subscribe_eventgroup_ack_entry,
)
from src.service_discovery import *
from src.simple_timer import SimplePeriodicTimer
from src.session_handler import SessionHandler
from src.utils import create_udp_socket, endpoint_to_str_int_tuple, EndpointType

@dataclass
class EventGroup:
    eventgroup_id: int
    ttl: int
    event_ids: List[int]

@dataclass
class EventGroupSubscriber:
    eventgroup_id: int
    endpoint: EndpointType


class ClientServiceInstance(ServiceDiscoveryObserver):

    def __init__(self):
        pass

    def find_service(self, id: int, callback) -> None:
        pass

    def subscribe_eventgroup(self, event_group_id: int, callback) -> None:
        pass

    def call_method(self) -> None:
        pass


class ServerServiceInstance(ServiceDiscoveryObserver):
    service_id: int
    instance_id: int
    eventgroups: List[EventGroup]
    is_offered: bool
    ttl: int
    sd_sender: ServiceDiscoverySender
    endpoint: EndpointType
    subscribers: List[EventGroupSubscriber]
    # session_handler: SessionHandler

    def __init__(
        self,
        service_id: int,
        instance_id: int,
        endpoint: EndpointType,
        ttl: int = 0,
        sd_sender=None,
    ):
        self.service_id = service_id
        self.instance_id = instance_id
        self.eventgroups = []
        self.is_offered = False
        self.endpoint = endpoint
        self.subscribers = []

        self.sender_socket = create_udp_socket(ip_bind=str(endpoint[0]), port_bind=endpoint[1])
        self.ttl = ttl
        self.sd_sender = sd_sender

        self.offer_timer = None

        self.major_version = 1  # TODO: pass by init

        # self.session_handler = SessionHandler()

    def find_service_update(self):
        pass

    def offer_service_update(self, offered_service: SdOfferedService):
        # print("offer_service_update")
        # print(offered_service)
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
            client_id=0x00,
            session_id=0x01,
            protocol_version=1,  # TODO,
            interface_version=1,  # TODO,
            message_type=MessageType.NOTIFICATION.value,
            return_code=0x00,
        )

        print("Send Event")
        print(self.subscribers)

        for sub in self.subscribers:
            if sub.eventgroup_id == event_group_id:
                self.sender_socket.sendto(someip_header.to_buffer() + payload, endpoint_to_str_int_tuple(sub.endpoint))

    def subscribe_eventgroup_update(
        self,
        sd_event_group: SdEventGroupEntry,
        ipv4_endpoint_option: SdIPV4EndpointOption,
    ) -> None:
        print("subscribe_eventgroup_update called")
        # print(ipv4_endpoint_option)

        (
            session_id,
            reboot_flag,
        ) = self.sd_sender.get_unicast_session_handler().update_session()

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
            # TODO: enable major version check
            # sd_event_group.sd_entry.major_version == self.major_version:
            # print("Service received subscribe entry -> send back ACK")
            ack_entry = construct_subscribe_eventgroup_ack_entry(
                sd_event_group.sd_entry.service_id,
                instance_id=sd_event_group.sd_entry.instance_id,
                major_version=sd_event_group.sd_entry.major_version,
                ttl=sd_event_group.sd_entry.ttl,
                event_group_id=sd_event_group.eventgroup_id,
            )
            header_output = construct_subscribe_eventgroup_ack_sd_header(
                ack_entry, session_id, reboot_flag
            )

            self.sd_sender.send_unicast(
                header_output.to_buffer(), ipv4_endpoint_option.ipv4_address
            )

            subscriber = EventGroupSubscriber(
                eventgroup_id=sd_event_group.eventgroup_id,
                endpoint=(ipv4_endpoint_option.ipv4_address, ipv4_endpoint_option.port),
            )
            self._insert_subscriber(subscriber)

    def add_eventgroup(self, eventgroup: EventGroup):
        ids = [e.eventgroup_id for e in self.eventgroups]
        if not eventgroup.eventgroup_id in ids:
            self.eventgroups.append(eventgroup)

    def offer_timer_callback(self):
        print("Offer service")

        (
            session_id,
            reboot_flag,
        ) = self.sd_sender.get_multicast_session_handler().update_session()
        service_to_offer = SdOfferedService(
            service_id=self.service_id,
            instance_id=self.instance_id,
            major_version=1,
            minor_version=0,
            ttl=self.ttl,
            endpoint=self.endpoint,
            protocol=TransportLayerProtocol.UDP,
        )
        sd_header = construct_offer_service_sd_header(
            service_to_offer, session_id, reboot_flag
        )
        self.sd_sender.send_multicast(sd_header.to_buffer())


    def start_offer(self):
        self.offer_timer = SimplePeriodicTimer(2, self.offer_timer_callback)
        self.offer_timer.start()

    def stop_offer(self):
        raise NotImplementedError()
