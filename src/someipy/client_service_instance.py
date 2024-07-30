import asyncio
from enum import Enum
import struct
from typing import Iterable, Tuple, Callable, Set, List

from someipy import Service
from someipy._internal.someip_sd_header import (
    SdService,
    TransportLayerProtocol,
    SdEventGroupEntry,
)
from someipy._internal.someip_header import SomeIpHeader, get_payload_from_message_buffer
from someipy._internal.someip_sd_builder import build_subscribe_eventgroup_entry
from someipy._internal.service_discovery_abcs import (
    ServiceDiscoveryObserver,
    ServiceDiscoverySender,
)
from someipy._internal.utils import create_udp_socket, EndpointType, endpoint_to_str_int_tuple
from someipy._internal.logging import get_logger
from someipy._internal.message_types import MessageType
from someipy._internal.someip_endpoint import (
    SomeipEndpoint,
    UDPSomeipEndpoint,
    SomeIpMessage,
)
from someipy._internal.tcp_connection import TcpConnection

_logger_name = "client_service_instance"

class MethodResult(Enum):
    SUCCESS = 0
    TIMEOUT = 1
    SERVICE_NOT_FOUND = 2
    ERROR = 3

class ExpectedAck:
    def __init__(self, eventgroup_id: int) -> None:
        self.eventgroup_id = eventgroup_id

class FoundService:
    service: SdService

    def __init__(self, service: SdService) -> None:
        self.service = service

    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, FoundService):
            return self.service == __value.service

class ClientServiceInstance(ServiceDiscoveryObserver):
    _service: Service
    _instance_id: int
    _endpoint: EndpointType
    _protocol: TransportLayerProtocol
    _someip_endpoint: SomeipEndpoint
    _ttl: int
    _sd_sender: ServiceDiscoverySender

    _eventgroups_to_subscribe: Set[int]
    _expected_acks: List[ExpectedAck]
    _callback: Callable[[bytes], None]
    _found_services: Iterable[FoundService]
    _method_call_future: asyncio.Future

    def __init__(
        self,
        service: Service,
        instance_id: int,
        endpoint: EndpointType,
        protocol: TransportLayerProtocol,
        someip_endpoint: SomeipEndpoint,
        ttl: int = 0,
        sd_sender=None,
    ):
        self._service = service
        self._instance_id = instance_id
        self._endpoint = endpoint
        self._protocol = protocol
        self._someip_endpoint = someip_endpoint
        self._ttl = ttl
        self._sd_sender = sd_sender

        self._eventgroups_to_subscribe = set()
        self._expected_acks = []
        self._callback = None

        self._tcp_connection: TcpConnection = None

        self._tcp_connect_lock = asyncio.Lock()
        self._tcp_task = None

        self._found_services = []
        self._method_call_future = None
        

    def register_callback(self, callback: Callable[[SomeIpMessage], None]) -> None:
        """
        Register a callback function to be called when a SOME/IP event is received.

        Args:
            callback (Callable[[SomeIpMessage], None]): The callback function to be registered.
                This function should take a SomeIpMessage object as its only argument and return None.

        Returns:
            None
        """
        self._callback = callback

    async def call_method(self, method_id: int, payload: bytes) -> Tuple[MethodResult, bytes]:
        
        has_service = False
        for s in self._found_services:
            if s.service.service_id == self._service.id and s.service.instance_id == self._instance_id:
                has_service = True
                break

        if not has_service:
            get_logger(_logger_name).warn(f"Do not execute method call. Service 0x{self._service.id:04X} with instance 0x{self._instance_id:04X} not found.")
            return MethodResult.SERVICE_NOT_FOUND, b""
        
        header = SomeIpHeader(
            service_id=self._service.id,
            method_id=method_id,
            client_id=0x00,
            session_id=0x00,
            protocol_version=0x01,
            interface_version=0x00,
            message_type=MessageType.REQUEST.value,
            return_code=0x00,
            length=len(payload) + 8,
        )
        someip_message = SomeIpMessage(header, payload)

        self._method_call_future = asyncio.get_running_loop().create_future()
        self._someip_endpoint.sendto(someip_message.serialize(), endpoint_to_str_int_tuple(self._found_services[0].service.endpoint))

        try:
            await asyncio.wait_for(self._method_call_future, 1.0)
        except asyncio.TimeoutError:
            get_logger(_logger_name).error(f"Waiting on response for method call 0x{method_id:04X} timed out.")
            return MethodResult.TIMEOUT, b""
        
        return MethodResult.SUCCESS, self._method_call_future.result()


    def someip_message_received(
        self, someip_message: SomeIpMessage, addr: Tuple[str, int]
    ) -> None:
        if (
            someip_message.header.client_id == 0x00
            and someip_message.header.message_type == MessageType.NOTIFICATION.value
            and someip_message.header.return_code == 0x00
        ):
            if self._callback is not None:
                self._callback(someip_message)
        
        if (someip_message.header.message_type == MessageType.RESPONSE.value
            and someip_message.header.return_code == 0x00): # E_OK
            if self._method_call_future is not None:
                self._method_call_future.set_result(someip_message.payload)
                return

        if (someip_message.header.message_type == MessageType.ERROR.value
            and someip_message.header.return_code == 0x01): # E_NOT_OK
            if self._method_call_future is not None:
                self._method_call_future.set_result(b"")
                return

    def subscribe_eventgroup(self, eventgroup_id: int):
        """
        Adds an event group to the list of event groups to subscribe to.

        Args:
            eventgroup_id (int): The ID of the event group to subscribe to.

        Returns:
            None

        Raises:
            None

        Notes:
            - If the event group ID is already in the subscription list, a debug log message is printed.
        """
        if eventgroup_id in self._eventgroups_to_subscribe:
            get_logger(_logger_name).debug(
                f"Eventgroup ID {eventgroup_id} is already in subscription list."
            )
        self._eventgroups_to_subscribe.add(eventgroup_id)

    def stop_subscribe_eventgroup(self, eventgroup_id: int):
        """
        Stops subscribing to an event group. Not implemented yet.

        Args:
            eventgroup_id (int): The ID of the event group to stop subscribing to.

        Raises:
            NotImplementedError: This method is not yet implemented.

        Notes:
            - This method is currently not implemented and raises a `NotImplementedError`.
        """
        # TODO: Implement StopSubscribe
        raise NotImplementedError

    def find_service_update(self):
        # Not needed in client service instance
        pass

    def offer_service_update(self, offered_service: SdService):
        #if len(self._eventgroups_to_subscribe) == 0:
        #    return

        if self._service.id != offered_service.service_id:
            return
        if self._instance_id != offered_service.instance_id:
            return

        if (
            offered_service.service_id == self._service.id
            and offered_service.instance_id == self._instance_id
        ):
            if FoundService(offered_service) not in self._found_services:
                self._found_services.append(FoundService(offered_service))
            
            # Try to subscribe to requested event groups
            for eventgroup_to_subscribe in self._eventgroups_to_subscribe:
                (
                    session_id,
                    reboot_flag,
                ) = self._sd_sender.get_unicast_session_handler().update_session()

                # Improvement: Pack all entries into a single SD message
                subscribe_sd_header = build_subscribe_eventgroup_entry(
                    service_id=self._service.id,
                    instance_id=self._instance_id,
                    major_version=self._service.major_version,
                    ttl=self._ttl,
                    event_group_id=eventgroup_to_subscribe,
                    session_id=session_id,
                    reboot_flag=reboot_flag,
                    endpoint=self._endpoint,
                    protocol=self._protocol,
                )

                get_logger(_logger_name).debug(
                    f"Send subscribe for instance 0x{self._instance_id:04X}, service: 0x{self._service.id:04X}, "
                    f"eventgroup ID: {eventgroup_to_subscribe} TTL: {self._ttl}, version: "
                    f"session ID: {session_id}"
                )

                if self._protocol == TransportLayerProtocol.TCP:
                    if self._tcp_task is None:
                        get_logger(_logger_name).debug(f"Create new TCP task for client of 0x{self._instance_id:04X}, 0x{self._service.id:04X}")
                        self._tcp_task = asyncio.create_task(self.setup_tcp_connection(str(self._endpoint[0]), self._endpoint[1], str(offered_service.endpoint[0]), offered_service.endpoint[1]))

                self._expected_acks.append(ExpectedAck(eventgroup_to_subscribe))
                self._sd_sender.send_unicast(
                    buffer=subscribe_sd_header.to_buffer(),
                    dest_ip=offered_service.endpoint[0],
                )

    async def setup_tcp_connection(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int):
        # TODO: Check for stop condition
        while True:
            try:
                get_logger(_logger_name).debug(f"Try to open TCP connection to ({dst_ip}, {dst_port})")
                self._tcp_connection = TcpConnection(dst_ip, dst_port)
                await self._tcp_connection.connect(src_ip, src_port)
                
                class State(Enum):
                    HEADER = 1
                    PAYLOAD = 2
                    PENDING = 3
                state = State.HEADER

                expected_bytes = 8 # 2x 32-bit for header
                header_data = bytes()
                data: bytes = bytes()              
                get_logger(_logger_name).debug(f"Start TCP read on port {src_port}")
                
                while self._tcp_connection.is_open():                    
                    try:
                        if state == State.HEADER:
                            while len(data) < expected_bytes:
                                new_data = await asyncio.wait_for(self._tcp_connection.reader.read(8), 3.0)
                                data += new_data
                            service_id, method_id, length = struct.unpack(">HHI", data[0:8])
                            header_data = data[0:8]

                            # The length bytes also covers 8 bytes header data without payload
                            expected_bytes = length
                            state = State.PAYLOAD
                            
                        elif state == State.PAYLOAD:
                            data = bytes()
                            while len(data) < expected_bytes:
                                new_data = await asyncio.wait_for(self._tcp_connection.reader.read(expected_bytes), 3.0)
                                data += new_data

                            header_data = header_data + data[0:8]
                            payload_data = data[8:]

                            message_data = header_data + payload_data
                            someip_header = SomeIpHeader.from_buffer(buf=message_data)
                            payload_data = get_payload_from_message_buffer(someip_header, message_data)

                            if self._callback is not None:
                                self._callback(SomeIpMessage(someip_header, payload_data))

                            if len(data) == expected_bytes:
                                data = bytes()
                            else:
                                data = data[expected_bytes:]
                            state = State.HEADER
                            expected_bytes = 8

                    except TimeoutError:
                        get_logger(_logger_name).debug(f"Timeout reading from TCP connection ({src_ip}, {src_port})")
                    

            except Exception as e:
                get_logger(_logger_name).error(f"Exception in setup_tcp_connection: {e}")
            finally:
                await self._tcp_connection.close()
            
            # Sleep for a while before reconnect
            await asyncio.sleep(1)


    def subscribe_eventgroup_update(self, _, __) -> None:
        # Not needed for client instance
        pass

    def subscribe_ack_eventgroup_update(
        self, event_group_entry: SdEventGroupEntry
    ) -> None:
        new_acks: List[ExpectedAck] = []
        ack_found = False
        for expected_ack in self._expected_acks:
            if expected_ack.eventgroup_id == event_group_entry.eventgroup_id:
                ack_found = True
                get_logger(_logger_name).debug(
                    f"Received expected subscribe ACK for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
                )
            else:
                new_acks.append(expected_ack)

        self._expected_acks = new_acks
        if not ack_found:
            get_logger(_logger_name).warn(
                f"Received unexpected subscribe ACK for instance 0x{event_group_entry.sd_entry.instance_id:04X}, service 0x{event_group_entry.sd_entry.service_id:04X}, eventgroup 0x{event_group_entry.eventgroup_id:04X}"
            )


async def construct_client_service_instance(
    service: Service,
    instance_id: int,
    endpoint: EndpointType,
    ttl: int = 0,
    sd_sender=None,
    protocol=TransportLayerProtocol.UDP,
) -> ClientServiceInstance:
    """
    Asynchronously constructs a ClientServerInstance. Based on the given transport protocol, proper endpoints are setup before constructing the actual ServerServiceInstance.

    Args:
        service (Service): The service associated with the instance.
        instance_id (int): The ID of the instance.
        endpoint (EndpointType): The endpoint of the client instance containing IP address and port.
        ttl (int, optional): The time-to-live for the instance used for service discovery subscribe entries. A value of 0 means that subscriptions are valid for infinite time.
        sd_sender (Any, optional): The service discovery sender.
        protocol (TransportLayerProtocol, optional): The transport layer protocol for the instance. Defaults to TransportLayerProtocol.UDP.

    Returns:
        ClientServerInstance: The constructed ClientServerInstance.

    Raises:
        None
    """
    if protocol == TransportLayerProtocol.UDP:
        loop = asyncio.get_running_loop()
        rcv_socket = create_udp_socket(str(endpoint[0]), endpoint[1])

        _, udp_endpoint = await loop.create_datagram_endpoint(
            lambda: UDPSomeipEndpoint(), sock=rcv_socket
        )

        client_instance = ClientServiceInstance(
            service,
            instance_id,
            endpoint,
            TransportLayerProtocol.UDP,
            udp_endpoint,
            ttl,
            sd_sender,
        )

        udp_endpoint.set_someip_callback(client_instance.someip_message_received)

        return client_instance

    elif protocol == TransportLayerProtocol.TCP:
        
        server_instance = ClientServiceInstance(
            service,
            instance_id,
            endpoint,
            TransportLayerProtocol.TCP,
            None,
            ttl,
            sd_sender,
        )
        return server_instance

    client_instance = ClientServiceInstance(service, instance_id, ttl, sd_sender)

    return client_instance
