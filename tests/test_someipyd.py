from asyncio import DatagramTransport
import asyncio
import ipaddress
import logging
import time
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, Mock, patch
import someipy
from someipy._internal._common.endpoint import Endpoint
from someipy._internal._daemon.daemon_server import ClientConnectedEventArgs
from someipy._internal._daemon.daemon_server_client import DaemonServerClient
from someipy._internal._daemon.uds_messages import (
    OfferServiceRequest,
    StopOfferServiceRequest,
    SubscribeEventGroupRequest,
    create_uds_message,
)
from someipy._internal._sd.deserialization.sd_serialization import serialize_sd_message
from someipy._internal._sd.entries.offer_service_entry import OfferServiceEntry
from someipy._internal._sd.options.endpoint import IpV4EndpointOption
from someipy._internal._sd.service_instance import ServiceInstance
from someipy._internal.someip_endpoint_factory import SomeipEndpointFactory
from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy.service import Event, EventGroup, Method
from someipy.someipyd import DaemonServer, SomeipDaemon


@pytest.fixture
def mock_logger() -> logging.Logger:
    mock_logger = Mock(spec=logging.Logger)
    return mock_logger


@pytest.fixture
def mock_daemon_server(mock_logger) -> DaemonServer:
    return DaemonServer(mock_logger)


@pytest.fixture
def mock_endpoint_factory() -> Mock:
    return Mock(spec=SomeipEndpointFactory)


@pytest.fixture
def daemon(mock_daemon_server, mock_endpoint_factory, mock_logger) -> SomeipDaemon:
    config = {}
    daemon = SomeipDaemon(
        mock_daemon_server, mock_endpoint_factory, config, mock_logger
    )
    daemon._ucast_transport = Mock(spec=DatagramTransport)
    return daemon


@pytest.fixture
def service_instance() -> ServiceInstance:
    service_instance = ServiceInstance(
        service_id=1,
        instance_id=2,
        major_version=3,
        minor_version=0,
        ttl=10,
        endpoint=Endpoint("123", 1),
        protocols=frozenset([TransportLayerProtocol.UDP]),
        timestamp=1000,
    )
    return service_instance


@pytest.fixture
def eventgroup() -> EventGroup:
    return EventGroup(
        id=1,
        events=[
            Event(id=1, protocol=TransportLayerProtocol.UDP),
            Event(id=2, protocol=TransportLayerProtocol.TCP),
        ],
    )


@pytest.fixture
def method() -> Method:
    return Method(
        id=1,
        protocol=TransportLayerProtocol.UDP,
    )


@pytest.fixture
def subscribe_event_group_request_udp(eventgroup) -> SubscribeEventGroupRequest:
    return SubscribeEventGroupRequest(
        service_id=1,
        instance_id=2,
        major_version=3,
        ttl_subscription=10,
        eventgroup=eventgroup.to_json(),
        client_endpoint_ip="123",
        client_endpoint_port=1,
        udp=True,
        tcp=False,
    )


@pytest.fixture
def subscribe_event_group_request_tcp(eventgroup) -> SubscribeEventGroupRequest:
    return SubscribeEventGroupRequest(
        service_id=1,
        instance_id=2,
        major_version=3,
        ttl_subscription=10,
        eventgroup=eventgroup.to_json(),
        client_endpoint_ip="123",
        client_endpoint_port=1,
        udp=False,
        tcp=True,
    )


@pytest.fixture
def subscribe_event_group_request_udp_and_tcp(eventgroup) -> SubscribeEventGroupRequest:
    return create_uds_message(
        SubscribeEventGroupRequest,
        service_id=1,
        instance_id=2,
        major_version=3,
        ttl_subscription=10,
        eventgroup=eventgroup.to_json(),
        client_endpoint_ip="123",
        client_endpoint_port=1,
        udp=True,
        tcp=True,
    )


@pytest.fixture
def offer_service_request(eventgroup, method) -> OfferServiceRequest:
    return create_uds_message(
        OfferServiceRequest,
        service_id=1,
        instance_id=2,
        major_version=3,
        minor_version=0,
        endpoint_ip="127.0.0.1",
        endpoint_port=1,
        ttl=5,
        eventgroup_list=[eventgroup.to_json()],
        method_list=[method.to_json()],
        cyclic_offer_delay_ms=1000,
    )


@pytest.fixture
def stop_offer_service_request(eventgroup, method) -> StopOfferServiceRequest:
    return create_uds_message(
        StopOfferServiceRequest,
        service_id=1,
        instance_id=2,
        major_version=3,
        minor_version=0,
        endpoint_ip="127.0.0.1",
        endpoint_port=1,
        ttl=5,
        eventgroup_list=[eventgroup.to_json()],
        method_list=[method.to_json()],
        cyclic_offer_delay_ms=1000,
    )


def test_handle_offered_service_adds_service(
    daemon: SomeipDaemon, service_instance: ServiceInstance
):
    # Initially, the found services list should be empty
    assert len(daemon._found_services) == 0

    # Handle the offered service
    daemon._handle_offered_service(service_instance)

    # Now, the found services list should contain the new service
    assert len(daemon._found_services) == 1
    assert daemon._found_services[0] == service_instance


def test_handle_offered_service_updates_timestamp(
    daemon: SomeipDaemon, service_instance: ServiceInstance
):

    # Initially, the found services list should be empty
    assert len(daemon._found_services) == 0

    # Handle the offered service
    daemon._handle_offered_service(service_instance)

    service_instance_2 = ServiceInstance(
        service_id=service_instance.service_id,
        instance_id=service_instance.instance_id,
        major_version=service_instance.major_version,
        minor_version=service_instance.minor_version,
        ttl=service_instance.ttl,
        endpoint=service_instance.endpoint,
        protocols=service_instance.protocols,
        timestamp=2000,
    )

    # Handle the offered service again with updated timestamp
    daemon._handle_offered_service(service_instance_2)

    # Now, the found services list should contain the updated timestamp
    assert len(daemon._found_services) == 1
    assert daemon._found_services[0] == service_instance
    assert daemon._found_services[0].timestamp == 2000


@pytest.mark.asyncio
async def test_handle_offered_service_opens_tcp_client_endpoint(
    daemon: SomeipDaemon,
    mock_endpoint_factory: Mock,
    service_instance: ServiceInstance,
    subscribe_event_group_request_tcp: SubscribeEventGroupRequest,
):
    service_instance.protocols = frozenset([TransportLayerProtocol.TCP])

    # Add a subscription first
    await daemon._handle_subscribe_eventgroup_request(
        subscribe_event_group_request_tcp, 1
    )

    # Handle the offered service
    daemon._handle_offered_service(service_instance)

    # Verify that create_client_endpoint was called for TCP
    mock_endpoint_factory.create_client_endpoint.assert_called_once_with(
        str(service_instance.endpoint.ip),
        service_instance.endpoint.port,
        str(service_instance.endpoint.ip),
        service_instance.endpoint.port,
        TransportLayerProtocol.TCP,
        daemon._someip_message_callback,
        daemon.logger,
    )

    assert len(daemon._pending_subscriptions) == 1
    assert len(daemon._someip_client_endpoints) == 1
    daemon._ucast_transport.sendto.assert_called_once()


@pytest.mark.asyncio
async def test_handle_subscribe_eventgroup_request_adds_requested_subscription(
    daemon: SomeipDaemon,
    subscribe_event_group_request_udp: SubscribeEventGroupRequest,
):
    # Initially, the requested subscriptions list should be empty
    assert len(daemon._requested_subscriptions) == 0

    # Handle the subscribe event group request
    await daemon._handle_subscribe_eventgroup_request(
        subscribe_event_group_request_udp, 1
    )

    # Now, the requested subscriptions list should contain the new subscription
    assert len(daemon._requested_subscriptions) == 1


@pytest.mark.asyncio
async def test_handle_offer_service_request_opens_server_endpoint(
    daemon: SomeipDaemon,
    offer_service_request: OfferServiceRequest,
):
    assert len(daemon._someip_server_endpoints) == 0

    await daemon._handle_offer_service_request(offer_service_request, 1)

    assert len(daemon._someip_server_endpoints) == 1


@pytest.mark.asyncio
async def test_handle_offer_service_does_not_add_service_twice(
    daemon: SomeipDaemon,
    offer_service_request: OfferServiceRequest,
):
    assert len(daemon._services_to_offer) == 0

    await daemon._handle_offer_service_request(offer_service_request, 1)
    await daemon._handle_offer_service_request(offer_service_request, 1)

    assert len(daemon._services_to_offer) == 1


@pytest.mark.asyncio
async def test_handle_stop_offer_service_removes_service_to_offer(
    daemon: SomeipDaemon,
    offer_service_request: OfferServiceRequest,
    stop_offer_service_request: StopOfferServiceRequest,
):
    assert len(daemon._services_to_offer) == 0

    await daemon._handle_offer_service_request(offer_service_request, 1)
    assert len(daemon._services_to_offer) == 1

    daemon._handle_stop_offer_service_request(stop_offer_service_request, 1)

    assert len(daemon._services_to_offer) == 0


@pytest.mark.asyncio
async def test_client_connected_disconnected(
    daemon: SomeipDaemon,
):
    initial_queue_count = len(daemon._tx_queues)

    # Simulate a new client connection
    client_id = 42

    new_client = Mock(spec=DaemonServerClient)
    new_client.id = client_id
    new_client.message_received = someipy._internal._common.event.Event()
    new_client.message_received.add_handler = Mock()
    new_client.message_received.remove_handler = Mock()

    new_client_args = ClientConnectedEventArgs(new_client)

    await daemon.new_client_connected(new_client, new_client_args)

    # Verify that a new queue has been created for the client
    assert client_id in daemon._tx_queues.keys()
    assert daemon._tx_queues[client_id] is not None

    new_client.message_received.add_handler.assert_called_once()

    await asyncio.sleep(0.0)  # Allow tx task to be scheduled

    await daemon.client_disconnected(daemon, new_client_args)

    # Verify that the client's queue and tx task was removed
    assert client_id not in daemon._tx_queues.keys()
    assert client_id not in daemon._tx_tasks.keys()

    # Message received event handler was removed
    new_client.message_received.remove_handler.assert_called_once()

    """ Cleanup of:
        - Offer timers
        - Services to be offered
        - Subscriptions (pending)
        - Subscriptions (active)
        - Method calls pending
        - Pending find calls
        - Close server or client endpoints that are only used by the disconnected client
    """


def test_datagram_received_mcast_calls_handle_offered_service(
    daemon: SomeipDaemon,
):

    # Create an SdMessage with an OfferService entry
    sd_message = someipy._internal._sd.sd_message.SdMessage()
    sd_message.session_id = 1

    ip_endpoint_option_1 = IpV4EndpointOption(
        address=ipaddress.IPv4Address("192.168.1.1"),
        protocol=TransportLayerProtocol.TCP,
        port=8080,
    )
    ip_endpoint_option_2 = IpV4EndpointOption(
        address=ipaddress.IPv4Address("192.168.1.2"),
        protocol=TransportLayerProtocol.UDP,
        port=8080,
    )

    offer_service_entry = OfferServiceEntry(
        service_id=1,
        instance_id=1,
        major_version=1,
        minor_version=0,
        ttl=120,
        ip_v4_endpoints=[ip_endpoint_option_1],
        ip_v6_endpoints=[],
    )

    sd_message.entries.append(offer_service_entry)
    data = serialize_sd_message(sd_message)

    # Patch the _handle_offered_service method to monitor its calls
    with patch.object(
        daemon, "_handle_offered_service", wraps=daemon._handle_offered_service
    ) as mock_handle_offered_service:
        # Simulate receiving a multicast datagram
        daemon.datagram_received_mcast(data, ("127.0.0.1", 5000))

        mock_handle_offered_service.assert_called_once()


def test_check_services_ttl_task_removes_expired_offered_services(
    daemon: SomeipDaemon, service_instance: ServiceInstance
):
    service_instance.timestamp = time.time()
    service_instance.ttl = 10  # seconds

    # Add a service instance with a short TTL
    daemon._found_services.append(service_instance)

    # Run the TTL check task once
    daemon._check_service_ttl_task_impl()

    # Service is still valid
    assert len(daemon._found_services) == 1

    service_instance.timestamp -= service_instance.ttl + 1  # Simulate time passage
    daemon._check_service_ttl_task_impl()

    # Service should be removed due to TTL expiry
    assert len(daemon._found_services) == 0


def test_find_service_request_sends_negative_response(daemon: SomeipDaemon):
    pass


def test_find_service_request_sends_positive_response(daemon: SomeipDaemon):
    pass
