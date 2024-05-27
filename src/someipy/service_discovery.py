import asyncio
import ipaddress
from typing import Any, Iterable, Union, Tuple

from someipy._internal.someip_header import SomeIpHeader
from someipy._internal.someip_sd_header import SdEventGroupEntry, SdIPV4EndpointOption, SdService, SomeIpSdHeader
from someipy._internal.someip_sd_extractors import (
    extract_offered_services,
    extract_subscribe_eventgroup_entries,
    extract_subscribe_ack_eventgroup_entries,
)
from someipy._internal.session_handler import SessionHandler
from someipy._internal.utils import (
    create_rcv_multicast_socket,
    create_udp_socket,
    DatagramAdapter,
)
from someipy._internal.service_discovery_abcs import (
    ServiceDiscoveryObserver,
    ServiceDiscoverySender,
    ServiceDiscoverySubject,
)
from someipy._internal.logging import get_logger

_logger_name = "service_discovery"


class ServiceDiscoveryProtocol(ServiceDiscoverySubject, ServiceDiscoverySender):
    """
    This class implements the ServiceDiscoverySubject and ServiceDiscoverySender
    interfaces. It is responsible for receiving and sending service discovery
    messages. Service instances are usually attached to objects of this class
    in order to receive service discovery updates, e.g. offer entries.
    """

    def __init__(self, multicast_ip: str, interface_ip: str, sd_port: int):
        """
        Initialize the ServiceDiscoveryProtocol instance.

        Args:
            multicast_ip (str): Multicast group IP address.
            interface_ip (str): IP address to be used as source address.
            sd_port (int): Service discovery port.
        """
        self.interface_ip = interface_ip
        self.multicast_ip = multicast_ip
        self.sd_port = sd_port

        self.sender_socket = create_udp_socket(interface_ip, sd_port)

        self.attached_observers: Iterable[ServiceDiscoveryObserver] = []
        self.mcast_transport: asyncio.Transport = None
        self.unicast_transport: asyncio.Transport = None

        self.mcast_session_handler = SessionHandler()
        self.unicast_session_handler = SessionHandler()

    def get_multicast_session_handler(self) -> SessionHandler:
        """
        Get the session handler for the multicast transport.

        Returns:
            SessionHandler: The session handler for service discovery multicast messages.
        """
        return self.mcast_session_handler

    def get_unicast_session_handler(self) -> SessionHandler:
        """
        Get the session handler for the unicast transport.

        Returns:
            SessionHandler: The session handler for service discovery unicast messages.
        """
        return self.unicast_session_handler

    def close(self):
        """
        Closes the transport sockets.
        """
        if self.mcast_transport is not None:
            self.mcast_transport.close()
        if self.unicast_transport is not None:
            self.unicast_transport.close()

    def detach(self, service_instance: ServiceDiscoveryObserver) -> None:
        """
        Detach a service instance. The service instance will no longer be notified about service discovery.

        Args:
            service_instance (ServiceDiscoveryObserver): The service instance to detach.
        """
        self.attached_observers.remove(service_instance)

    def attach(self, service_instance: ServiceDiscoveryObserver) -> None:
        """
        Attach a service instance to be notified about service discovery messages.

        Args:
            service_instance (ServiceDiscoveryObserver): The service instance to attach.
        """
        self.attached_observers.append(service_instance)

    def datagram_received(self, data: bytes, addr: Tuple[Union[str, Any], int]) -> None:
        """
        Handle a datagram received.

        Args:
            data (bytes): The received data.
            addr (Tuple[Union[str, Any], int]): The address of the sender.
        """
        # Ignore packets sent by the app itself
        if addr[0] == self.interface_ip:
            return

        # Ignore packets not sent to the SD port
        if addr[1] != self.sd_port:
            return

        someip_header = SomeIpHeader.from_buffer(data)
        if not someip_header.is_sd_header():
            return

        someip_sd_header = SomeIpSdHeader.from_buffer(data)

        for offered_service in extract_offered_services(someip_sd_header):
            self._handle_offered_service(offered_service)

        for (
            event_group_entry,
            ipv4_endpoint_option,
        ) in extract_subscribe_eventgroup_entries(someip_sd_header):
            self._handle_subscribe_eventgroup_entry(
                event_group_entry, ipv4_endpoint_option
            )

        for event_group_entry in extract_subscribe_ack_eventgroup_entries(
            someip_sd_header
        ):
            self._handle_subscribe_ack_eventgroup_entry(event_group_entry)

    def connection_lost(self, exc: Exception) -> None:
        """
        Handle connection lost.

        Args:
            exc (Exception): The exception that caused the connection loss.
        """
        pass

    def send_multicast(self, buffer: bytes) -> None:
        """
        Send a multicast message.

        Args:
            buffer (bytes): The message to send.
        """
        self.sender_socket.sendto(buffer, (self.multicast_ip, self.sd_port))

    def send_unicast(self, buffer: bytes, dest_ip: ipaddress.IPv4Address) -> None:
        """
        Send a unicast message.

        Args:
            buffer (bytes): The message to send.
            dest_ip (ipaddress.IPv4Address): The destination IP address.
        """
        self.sender_socket.sendto(buffer, (str(dest_ip), self.sd_port))

    def _handle_offered_service(self, offered_service: SdService) -> None:
        """
        Handle an offered service.

        Args:
            offered_service (SdService): The offered service.
        """
        get_logger(_logger_name).debug(
            f"Received offer for instance 0x{offered_service.instance_id:04X}, service 0x{offered_service.service_id:04X}"
        )
        for o in self.attached_observers:
            o.offer_service_update(offered_service)

    def _handle_subscribe_eventgroup_entry(
        self,
        event_group_entry: SdEventGroupEntry,
        ipv4_endpoint_option: SdIPV4EndpointOption,
    ) -> None:
        """
        Handle a subscribe event group entry.

        Args:
            event_group_entry (SdEventGroupEntry): The event group entry.
            ipv4_endpoint_option (SdIPV4EndpointOption): The IPv4 endpoint option.
        """
        get_logger(_logger_name).debug(
            f"Received subscribe for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
        )
        for o in self.attached_observers:
            o.subscribe_eventgroup_update(event_group_entry, ipv4_endpoint_option)

    def _handle_subscribe_ack_eventgroup_entry(
        self, event_group_entry: SdEventGroupEntry
    ) -> None:
        """
        Handle a subscribe ACK event group entry.

        Args:
            event_group_entry (SdEventGroupEntry): The event group entry.
        """
        get_logger(_logger_name).debug(
            f"Received subscribe ACK for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
        )
        # TODO: Implement subscription ACK handling


async def construct_service_discovery(
    multicast_group_ip: str,
    sd_port: int,
    unicast_ip: str,
) -> ServiceDiscoveryProtocol:
    """
    Asynchronously constructs a ServiceDiscoveryProtocol instance.
    It opens one socket listening for multicast group address and
    one for listening on service discovery unicast traffic.
    The port is used both for multicast and unicast.

    :param multicast_group_ip: The service discovery multicast group IPv4 address.
    :type multicast_group_ip: str
    :param sd_port: The port number used for service discovery.
    :type sd_port: int
    :param unicast_ip: The IPv4 address used for unicast service discovery.
    :type unicast_ip: str
    :return: An instance of ServiceDiscoveryProtocol with transport protocols set up.
    :rtype: ServiceDiscoveryProtocol
    """
    sd = ServiceDiscoveryProtocol(
        multicast_group_ip,
        unicast_ip,
        sd_port,
    )

    loop = asyncio.get_running_loop()
    sd.mcast_transport, _ = await loop.create_datagram_endpoint(
        lambda: DatagramAdapter(target=sd),
        sock=create_rcv_multicast_socket(multicast_group_ip, sd_port),
    )

    sd.unicast_transport, _ = await loop.create_datagram_endpoint(
        lambda: DatagramAdapter(target=sd),
        sock=create_udp_socket(unicast_ip, sd_port),
    )

    return sd
