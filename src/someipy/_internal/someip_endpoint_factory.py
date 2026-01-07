# Copyright (C) 2025 Christian H.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
from collections.abc import Callable
import logging
from typing import Tuple
from someipy._internal._common.endpoint import Endpoint
from someipy._internal.someip_endpoint import (
    SomeipEndpoint,
    TCPClientSomeipEndpoint,
    TCPSomeipEndpoint,
    UDPSomeipEndpoint,
)
from someipy._internal.someip_message import SomeIpMessage
from someipy._internal.tcp_client_manager import TcpClientManager, TcpClientProtocol
from someipy._internal.transport_layer_protocol import TransportLayerProtocol
from someipy._internal.utils import create_udp_socket


class SomeipEndpointFactory:

    @staticmethod
    async def create_server_endpoint(
        endpoint: Endpoint,
        protocol: TransportLayerProtocol,
        someip_callback: Callable[
            [SomeIpMessage, Tuple[str, int], Tuple[str, int], TransportLayerProtocol],
            None,
        ],
    ) -> SomeipEndpoint:

        if protocol == TransportLayerProtocol.UDP:
            loop = asyncio.get_running_loop()
            rcv_socket = create_udp_socket(str(endpoint.ip), endpoint.port)

            _, udp_endpoint = await loop.create_datagram_endpoint(
                lambda: UDPSomeipEndpoint(str(endpoint.ip), endpoint.port),
                sock=rcv_socket,
            )

            udp_endpoint.set_someip_callback(someip_callback)

            return udp_endpoint
        else:
            tcp_client_manager = TcpClientManager(str(endpoint.ip), endpoint.port)
            loop = asyncio.get_running_loop()
            server = await loop.create_server(
                lambda: TcpClientProtocol(client_manager=tcp_client_manager),
                str(endpoint.ip),
                endpoint.port,
            )
            tcp_someip_endpoint = TCPSomeipEndpoint(
                server, tcp_client_manager, str(endpoint.ip), endpoint.port
            )

            tcp_someip_endpoint.set_someip_callback(someip_callback)

            return tcp_someip_endpoint

    @staticmethod
    async def create_udp_client_endpoint(
        dst_endpoint: Endpoint,
        src_endpoint: Endpoint,
        someip_message_callback: Callable[[SomeIpMessage], None],
        logger: logging.Logger = None,
    ) -> SomeipEndpoint:
        udp_endpoint = await SomeipEndpointFactory.create_server_endpoint(
            src_endpoint,
            TransportLayerProtocol.UDP,
            someip_message_callback,
        )
        return udp_endpoint

    @staticmethod
    def create_tcp_client_endpoint(
        dst_endpoint: Endpoint,
        src_endpoint: Endpoint,
        someip_message_callback: Callable[[SomeIpMessage], None],
        logger: logging.Logger = None,
    ) -> TCPClientSomeipEndpoint:
        tcp_endpoint = TCPClientSomeipEndpoint(
            str(dst_endpoint.ip),
            dst_endpoint.port,
            str(src_endpoint.ip),
            src_endpoint.port,
            logger,
        )
        tcp_endpoint.set_someip_callback(someip_message_callback)
        return tcp_endpoint
