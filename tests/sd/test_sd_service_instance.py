import ipaddress
import pytest
from someipy._internal._sd.service_instance import ServiceInstance
from someipy._internal.transport_layer_protocol import TransportLayerProtocol


def test_equality():
    instance_1 = ServiceInstance(
        service_id=1234,
        instance_id=5678,
        major_version=1,
        minor_version=0,
        ttl=4,
        endpoint=(ipaddress.IPv4Address("127.0.0.1"), 12345),
        protocols=frozenset([TransportLayerProtocol.TCP]),
        timestamp=1.0,
    )

    instance_2 = ServiceInstance(
        service_id=1234,
        instance_id=5678,
        major_version=1,
        minor_version=0,
        ttl=4,
        endpoint=(ipaddress.IPv4Address("127.0.0.1"), 12345),
        protocols=frozenset([TransportLayerProtocol.TCP]),
        timestamp=1.0,
    )

    instance_3 = ServiceInstance(
        service_id=1234,
        instance_id=5678,
        major_version=1,
        minor_version=0,
        ttl=4,
        endpoint=(ipaddress.IPv4Address("127.0.0.2"), 12345),
        protocols=frozenset([TransportLayerProtocol.TCP]),
        timestamp=1.0,
    )
    assert instance_1 == instance_2
    assert instance_1 != instance_3
