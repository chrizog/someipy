import ipaddress
import struct
import socket
from typing import Tuple

def create_udp_socket(ip_bind: str, port_bind: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((ip_bind, port_bind))
    return sock

def create_rcv_multicast_socket(ip: str, port: int) -> socket.socket:
    sock = create_udp_socket(ip, port)
    mreq = struct.pack("4sl", socket.inet_aton(ip), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock

EndpointType = Tuple[ipaddress.IPv4Address, int]

def endpoint_to_str_int_tuple(endpoint: EndpointType) -> Tuple[str, int]:
    return (str(endpoint[0]), endpoint[1])