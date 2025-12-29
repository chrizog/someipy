import ipaddress
from someipy._internal._common.endpoint import Endpoint


def test_equality():
    endpoint_1 = Endpoint(ipaddress.ip_address("192.168.0.1"), 3000)
    endpoint_2 = Endpoint(ipaddress.ip_address("192.168.0.1"), 3000)

    assert endpoint_1 == endpoint_2


def test_inequality():
    endpoint_1 = Endpoint(ipaddress.ip_address("192.168.0.1"), 3000)
    endpoint_2 = Endpoint(ipaddress.ip_address("192.168.0.2"), 3000)

    assert endpoint_1 != endpoint_2


def test_endpoint_is_ipv4():
    endpoint_ipv4 = Endpoint(ipaddress.ip_address("192.168.0.1"), 3000)
    assert endpoint_ipv4.is_ipv4 == True


def test_endpoint_is_ipv6():
    endpoint_ipv6 = Endpoint(
        ipaddress.ip_address("2001:0db8:85a3:0000:0000:8a2e:0370:7334"), 3000
    )
    assert endpoint_ipv6.is_ipv4 == False
