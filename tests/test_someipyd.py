import logging
import pytest
from unittest.mock import Mock
from someipy._internal._common.endpoint import Endpoint
from someipy._internal._sd.service_instance import ServiceInstance
from someipy.someipyd import DaemonServer, SomeipDaemon


@pytest.fixture
def mock_logger() -> logging.Logger:
    mock_logger = Mock(spec=logging.Logger)
    return mock_logger


@pytest.fixture
def mock_daemon_server(mock_logger) -> DaemonServer:
    return DaemonServer(mock_logger)


@pytest.fixture
def daemon(mock_daemon_server, mock_logger) -> SomeipDaemon:
    config = {}

    return SomeipDaemon(mock_daemon_server, config, mock_logger)


def test_handle_offered_service_adds_service(daemon: SomeipDaemon):
    service_instance = ServiceInstance(
        service_id=1,
        instance_id=1,
        major_version=1,
        minor_version=0,
        ttl=10,
        endpoint=Endpoint("123", 1),
        protocols=frozenset(),
        timestamp=1000,
    )

    # Initially, the found services list should be empty
    assert len(daemon._found_services) == 0

    # Handle the offered service
    daemon._handle_offered_service(service_instance)

    # Now, the found services list should contain the new service
    assert len(daemon._found_services) == 1
    assert daemon._found_services[0] == service_instance


def test_handle_offered_service_updates_timestamp(daemon: SomeipDaemon):
    service_instance = ServiceInstance(
        service_id=1,
        instance_id=1,
        major_version=1,
        minor_version=0,
        ttl=10,
        endpoint=Endpoint("123", 1),
        protocols=frozenset(),
        timestamp=1000,
    )

    # Initially, the found services list should be empty
    assert len(daemon._found_services) == 0

    # Handle the offered service
    daemon._handle_offered_service(service_instance)

    service_instance_2 = ServiceInstance(
        service_id=1,
        instance_id=1,
        major_version=1,
        minor_version=0,
        ttl=10,
        endpoint=Endpoint("123", 1),
        protocols=frozenset(),
        timestamp=2000,
    )

    # Handle the offered service again with updated timestamp
    daemon._handle_offered_service(service_instance_2)

    # Now, the found services list should contain the updated timestamp
    assert len(daemon._found_services) == 1
    assert daemon._found_services[0] == service_instance
    assert daemon._found_services[0].timestamp == 2000
