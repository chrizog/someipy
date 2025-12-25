import pytest

from someipy._internal._sd.deserialization.sd_deserialization import (
    CommonEntryData,
    CommonOptionData,
    SdOptionOnWireType,
    deserialize_common_entry_data,
    deserialize_common_option_data,
    deserialize_ipv4_endpoint_option,
    deserialize_ipv4_multicast_option,
    deserialize_ipv4_sd_endpoint_option,
    deserialize_ipv6_endpoint_option,
    deserialize_ipv6_multicast_option,
    deserialize_ipv6_sd_endpoint_option,
    deserialize_load_balancing_option,
)
from someipy._internal._sd.options.endpoint import (
    IpV4EndpointOption,
    IpV6EndpointOption,
)
from someipy._internal._sd.options.load_balancing import LoadBalancingOption
from someipy._internal._sd.options.multicast import (
    IpV4MulticastOption,
    IpV6MulticastOption,
)
from someipy._internal._sd.options.sd_endpoint import (
    IpV4SdEndpointOption,
    IpV6SdEndpointOption,
)
from someipy._internal.transport_layer_protocol import TransportLayerProtocol


def test_deserialize_common_entry_data():
    data = bytes(
        [0x01, 0x02, 0x03, 0x24, 0x00, 0x10, 0x00, 0x20, 0x01, 0x0B, 0x00, 0x0A]
    )
    result = deserialize_common_entry_data(data)
    assert isinstance(result, CommonEntryData)
    assert result.type_field_value == 0x01
    assert result.index_first_option == 0x02
    assert result.index_second_option == 0x03
    assert result.num_options_1 == 2
    assert result.num_options_2 == 4
    assert result.service_id == 0x0010
    assert result.instance_id == 0x0020
    assert result.major_version == 0x01
    assert result.ttl == 0x0B000A


def test_deserialize_common_option_data():
    data = bytes([0x01, 0x05, 0x04, 0x80])
    result = deserialize_common_option_data(data)
    assert isinstance(result, CommonOptionData)
    assert result.option_length == 5 + 256
    assert result.option_type == SdOptionOnWireType.IPV4_ENDPOINT
    assert result.discardable_flag is True


def test_deserialize_ipv4_endpoint_option():
    data = bytes([192, 168, 1, 10, 0x01, 0x11, 0x10, 0x01])
    result = deserialize_ipv4_endpoint_option(data)
    assert isinstance(result, IpV4EndpointOption)
    assert str(result.address) == "192.168.1.10"
    assert result.protocol == TransportLayerProtocol.UDP
    assert result.port == 0x1001


def test_deserialize_ipv6_endpoint_option():
    data = bytes(
        [
            0x20,
            0x01,
            0x0D,
            0xB8,
            0x85,
            0xA3,
            0x00,
            0x00,
            0x00,
            0x00,
            0x8A,
            0x2E,
            0x03,
            0x70,
            0x73,
            0x34,
            0x01,
            0x11,
            0x10,
            0x01,
        ]
    )
    result = deserialize_ipv6_endpoint_option(data)
    assert isinstance(result, IpV6EndpointOption)
    assert str(result.address) == "2001:db8:85a3::8a2e:370:7334"
    assert result.protocol == TransportLayerProtocol.UDP
    assert result.port == 0x1001


def test_deserialize_ipv4_multicast_option():
    data = bytes([192, 168, 1, 10, 0x01, 0x11, 0x10, 0x01])
    result = deserialize_ipv4_multicast_option(data)
    assert isinstance(result, IpV4MulticastOption)
    assert str(result.address) == "192.168.1.10"
    assert result.protocol == TransportLayerProtocol.UDP
    assert result.port == 0x1001


def test_deserialize_ipv6_multicast_option():
    data = bytes(
        [
            0x20,
            0x01,
            0x0D,
            0xB8,
            0x85,
            0xA3,
            0x00,
            0x00,
            0x00,
            0x00,
            0x8A,
            0x2E,
            0x03,
            0x70,
            0x73,
            0x34,
            0x01,
            0x11,
            0x10,
            0x01,
        ]
    )
    result = deserialize_ipv6_multicast_option(data)
    assert isinstance(result, IpV6MulticastOption)
    assert str(result.address) == "2001:db8:85a3::8a2e:370:7334"
    assert result.protocol == TransportLayerProtocol.UDP
    assert result.port == 0x1001


def test_deserialize_ipv4_sd_endpoint_option():
    data = bytes([192, 168, 1, 10, 0x01, 0x11, 0x10, 0x01])
    result = deserialize_ipv4_sd_endpoint_option(data)
    assert isinstance(result, IpV4SdEndpointOption)
    assert str(result.address) == "192.168.1.10"
    assert result.port == 0x1001


def test_deserialize_ipv6_sd_endpoint_option():
    data = bytes(
        [
            0x20,
            0x01,
            0x0D,
            0xB8,
            0x85,
            0xA3,
            0x00,
            0x00,
            0x00,
            0x00,
            0x8A,
            0x2E,
            0x03,
            0x70,
            0x73,
            0x34,
            0x01,
            0x11,
            0x10,
            0x01,
        ]
    )
    result = deserialize_ipv6_sd_endpoint_option(data)
    assert isinstance(result, IpV6SdEndpointOption)
    assert str(result.address) == "2001:db8:85a3::8a2e:370:7334"
    assert result.port == pow(16, 3) + 1


def test_deserialize_load_balancing_option():
    data = bytes([0x01, 0x02, 0x03, 0x04])
    result = deserialize_load_balancing_option(data)
    assert isinstance(result, LoadBalancingOption)
    assert result.priority == 0x0102
    assert result.weight == 0x0304
