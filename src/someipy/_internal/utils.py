import asyncio
import ipaddress
import socket
import struct

from typing import Tuple, Union, Any


def create_udp_socket(ip_address: str, port: int) -> socket.socket:
    """
    Create a datagram protocol based socket and bind the socket to an address.

    The option "SO_REUSEADDR" will be set on the socket.

    Parameters
    ----------
    ip_address : str
        The IP address to which the socket is bound
    port : int
        The port to which the socket is bound

    Returns
    -------
    socket.socket
        The newly created socket

    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((ip_address, port))
    return sock


def create_rcv_multicast_socket(ip_address: str, port: int) -> socket.socket:
    """
    Create a datagram protocol based socket for multicast and bind the socket to the passed multicast address.

    The options "SO_REUSEADDR" and "IP_ADD_MEMBERSHIP" will be set on the socket.

    Parameters
    ----------
    ip_address : str
        The multicast IP address to which the socket is bound
    port : int
        The port to which the socket is bound

    Returns
    -------
    socket.socket
        The newly created socket

    """
    sock = create_udp_socket(ip_address, port)
    mreq = struct.pack("4sl", socket.inet_aton(ip_address), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock


EndpointType = Tuple[ipaddress.IPv4Address, int]


def endpoint_to_str_int_tuple(endpoint: EndpointType) -> Tuple[str, int]:
    """A helper function for converting the format of a tuple for an endpoint"""
    return (str(endpoint[0]), endpoint[1])


class DatagramAdapter(asyncio.DatagramProtocol):
    """An adapter class which allows to forward the calls of of asyncio.DatagramProtocol to an injected target class"""

    def __init__(self, target):
        self.target = target

    def datagram_received(self, data: bytes, addr: Tuple[Union[str, Any], int]) -> None:
        self.target.datagram_received(data, addr)

    def connection_lost(self, exc: Exception) -> None:
        self.target.connection_lost(exc)


def set_bit_at_position(number: int, position: int, value: bool) -> int:
    """Set the bit at the specified position to the given boolean value."""
    if value:
        # Set the bit to 1
        return number | (1 << position)
    else:
        # Set the bit to 0
        return number & ~(1 << position)


def is_bit_set(number: int, bit_position: int) -> bool:
    """
    Checks if the bit at the specified position is set in the given number.

    Parameters:
    - number: The integer to check.
    - bit_position: The position of the bit to check (0-based index).

    Returns:
    - True if the bit is set, False otherwise.
    """
    # Left shift 1 to the bit position and perform bitwise AND with the number
    # If the result is non-zero, the bit is set; otherwise, it's not set.
    return (number & (1 << bit_position)) != 0