from asyncio import DatagramTransport
import logging
import pytest
import pytest_asyncio
from unittest.mock import Mock
from someipy._internal._common.endpoint import Endpoint
from someipy._internal._daemon.uds_messages import (
    OfferServiceRequest,
    SubscribeEventGroupRequest,
    create_uds_message,
)
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
            Event(id=2, protocol=TransportLayerProtocol.UDP),
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
