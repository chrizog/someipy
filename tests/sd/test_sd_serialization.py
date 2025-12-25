import ipaddress

from someipy._internal._sd.deserialization.sd_serialization import (
    serialize_ipv4_endpoint_option,
    serialize_ipv6_endpoint_option,
    serialize_sd_message,
)
from someipy._internal._sd.entries.offer_service_entry import OfferServiceEntry
from someipy._internal._sd.options.endpoint import (
    IpV4EndpointOption,
    IpV6EndpointOption,
)
from someipy._internal._sd.sd_message import SdMessage
from someipy._internal.transport_layer_protocol import TransportLayerProtocol


def test_serialize_ipv4_endpoint_option():
    option = IpV4EndpointOption(
        address=ipaddress.IPv4Address("1.2.3.4"),
        protocol=TransportLayerProtocol.UDP,
        port=0x1F90,
    )
    data = serialize_ipv4_endpoint_option(option)

    expected_data = bytes(
        [0x00, 0x09, 0x04, 0x00, 0x01, 0x02, 0x03, 0x04, 0x00, 0x11, 0x1F, 0x90]
    )

    assert data == expected_data


def test_serialize_ipv6_endpoint_option():
    option = IpV6EndpointOption(
        address=ipaddress.IPv6Address("2001:0db8:85a3:0000:0000:8a2e:0370:7334"),
        protocol=TransportLayerProtocol.TCP,
        port=0x2328,
    )
    data = serialize_ipv6_endpoint_option(option)

    expected_data = bytes(
        [
            0x00,
            0x15,
            0x06,
            0x00,
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
            0x00,
            0x06,
            0x23,
            0x28,
        ]
    )

    assert data == expected_data


def test_serialize_empty_sd_message():
    sd_message = SdMessage()
    sd_message.multicast = False
    sd_message.session_id = 0x2

    data = serialize_sd_message(sd_message)

    # fmt: off
    expected_data = bytes(
        [
            0xFF, 0xFF, 0x81, 0x00, 
            0x00, 0x00, 0x00, 0x14, # length: 20
            0x00, 0x00, 0x00, 0x02,
            0x01, 0x01, 0x02, 0x00,
            0x40, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, # length entries
            0x00, 0x00, 0x00, 0x00]) # length of options
    # fmt: on

    assert len(data) == len(expected_data)
    assert data == expected_data


def test_serialize_sd_message_with_one_offer_service_entry_without_options():
    sd_message = SdMessage()
    sd_message.multicast = True
    sd_message.session_id = 0x1234

    sd_message.entries.append(
        OfferServiceEntry(
            service_id=0x01,
            instance_id=0x02,
            major_version=0x03,
            minor_version=0x04,
            ttl=0x10,
            ip_v4_endpoints=[],
            ip_v6_endpoints=[],
        )
    )

    data = serialize_sd_message(sd_message)

    # fmt: off
    expected_data = bytes(
        [
            0xFF, 0xFF, 0x81, 0x00, 
            0x00, 0x00, 0x00, 0x24, # length: 36
            0x00, 0x00, 0x12, 0x34,
            0x01, 0x01, 0x02, 0x00,
            0x40, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x10, # length entries: 16
            0x01, 0x00, 0x00, 0x00,
            0x00, 0x01, 0x00, 0x02,
            0x03, 0x00, 0x00, 0x10,
            0x00, 0x00, 0x00, 0x04,
            0x00, 0x00, 0x00, 0x00]) # length of options: 0
    # fmt: on

    assert len(data) == len(expected_data)
    assert data == expected_data


def test_serialize_sd_message_with_one_offer_service_entry_with_two_options():
    sd_message = SdMessage()
    sd_message.multicast = True
    sd_message.session_id = 0x1234

    sd_message.entries.append(
        OfferServiceEntry(
            service_id=0x01,
            instance_id=0x02,
            major_version=0x03,
            minor_version=0x04,
            ttl=0x10,
            ip_v4_endpoints=[
                IpV4EndpointOption(
                    address=ipaddress.IPv4Address("192.168.0.1"),
                    protocol=TransportLayerProtocol.TCP,
                    port=0x2328,
                ),
                IpV4EndpointOption(
                    address=ipaddress.IPv4Address("192.168.0.2"),
                    protocol=TransportLayerProtocol.UDP,
                    port=0x2429,
                ),
            ],
            ip_v6_endpoints=[],
        )
    )

    data = serialize_sd_message(sd_message)

    # fmt: off
    expected_data = bytes(
        [
            0xFF, 0xFF, 0x81, 0x00, 
            0x00, 0x00, 0x00, 60, # length: 60
            0x00, 0x00, 0x12, 0x34,
            0x01, 0x01, 0x02, 0x00,
            0x40, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x10, # length entries: 16
            0x01, 0x00, 0x00, 0x20,
            0x00, 0x01, 0x00, 0x02,
            0x03, 0x00, 0x00, 0x10,
            0x00, 0x00, 0x00, 0x04,
            0x00, 0x00, 0x00, 0x18, # length of options: 2 * 12
            0x00, 0x09, 0x04, 0x00,
            192, 168, 0, 1,
            0x00, 0x06, 0x23, 0x28,
            0x00, 0x09, 0x04, 0x00,
            192, 168, 0, 2,
            0x00, 0x11, 0x24, 0x29])
    # fmt: on

    assert len(data) == len(expected_data)
    assert data == expected_data
