import pytest
from someipy._internal._sd.entries.offer_service_entry import OfferServiceEntry
from someipy._internal._sd.options.endpoint import IpV4EndpointOption


def test_base_types_len():

    ip_endpoint_option_1 = IpV4EndpointOption(
        address="192.168.1.1", protocol=1, port=8080
    )
    ip_endpoint_option_2 = IpV4EndpointOption(
        address="192.168.1.2", protocol=1, port=8080
    )

    offer_service_entry_1 = OfferServiceEntry(
        service_id=1,
        instance_id=1,
        major_version=1,
        minor_version=0,
        ttl=120,
        ip_v4_endpoints=[ip_endpoint_option_1],
        ip_v6_endpoints=[],
    )

    offer_service_entry_2 = OfferServiceEntry(
        service_id=1,
        instance_id=1,
        major_version=1,
        minor_version=0,
        ttl=120,
        ip_v4_endpoints=[ip_endpoint_option_1],
        ip_v6_endpoints=[],
    )

    offer_service_entry_3 = OfferServiceEntry(
        service_id=1,
        instance_id=1,
        major_version=1,
        minor_version=0,
        ttl=120,
        ip_v4_endpoints=[ip_endpoint_option_2],
        ip_v6_endpoints=[],
    )

    assert offer_service_entry_1 == offer_service_entry_2
    assert offer_service_entry_1 != offer_service_entry_3
