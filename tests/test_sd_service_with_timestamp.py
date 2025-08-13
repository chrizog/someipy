import ipaddress
import pytest
from someipy._internal.someip_sd_header import SdService2, SdServiceWithTimestamp
from someipy._internal.transport_layer_protocol import TransportLayerProtocol


def test_equality():
    sd_service_1 = SdService2(
        service_id=1234,
        instance_id=5678,
        major_version=1,
        minor_version=0,
        ttl=4,
        endpoint=(ipaddress.IPv4Address("127.0.0.1"), 12345),
        protocols=frozenset([TransportLayerProtocol.TCP]),
    )

    sd_service_2 = SdService2(
        service_id=1234,
        instance_id=5678,
        major_version=1,
        minor_version=0,
        ttl=4,
        endpoint=(ipaddress.IPv4Address("127.0.0.1"), 12345),
        protocols=frozenset([TransportLayerProtocol.TCP]),
    )

    assert sd_service_1 == sd_service_2

    sd_service_with_ts_1 = SdServiceWithTimestamp(sd_service_1, 1.0)
    sd_service_with_ts_2 = SdServiceWithTimestamp(sd_service_2, 2.0)

    assert sd_service_with_ts_1 == sd_service_with_ts_2

    list_to_check = [sd_service_with_ts_1]

    assert sd_service_with_ts_1 in list_to_check
    assert sd_service_with_ts_2 in list_to_check
