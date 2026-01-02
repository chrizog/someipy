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


from typing import Iterable
from someipy._internal._daemon.offer_service_storage import ServiceToOffer
from someipy._internal._sd.entries.offer_service_entry import OfferServiceEntry
from someipy._internal._sd.entries.stop_offer_service_entry import StopOfferServiceEntry
from someipy._internal._sd.options.endpoint import IpV4EndpointOption
from someipy._internal._sd.sd_message import SdMessage
from someipy._internal.transport_layer_protocol import TransportLayerProtocol


def create_offer_service_message(
    services_to_offer: Iterable[ServiceToOffer], session_id: int, reboot_flag: bool
) -> SdMessage:

    options = set()

    for service in services_to_offer:
        if service.has_udp:
            options.add(
                IpV4EndpointOption(
                    address=service.endpoint.ip,
                    protocol=TransportLayerProtocol.UDP,
                    port=service.endpoint.port,
                )
            )

        if service.has_tcp:
            options.add(
                IpV4EndpointOption(
                    address=service.endpoint.ip,
                    protocol=TransportLayerProtocol.TCP,
                    port=service.endpoint.port,
                )
            )

    options = list(options)

    sd_message = SdMessage()
    sd_message.session_id = session_id
    sd_message.reboot_flag = reboot_flag

    for service in services_to_offer:
        endpoints = []
        if service.has_udp:
            endpoints.extend(
                [
                    option
                    for option in options
                    if option.protocol == TransportLayerProtocol.UDP
                    and option.address == service.endpoint.ip
                    and option.port == service.endpoint.port
                ]
            )
        if service.has_tcp:
            endpoints.extend(
                [
                    option
                    for option in options
                    if option.protocol == TransportLayerProtocol.TCP
                    and option.address == service.endpoint.ip
                    and option.port == service.endpoint.port
                ]
            )

        new_entry = OfferServiceEntry(
            service_id=service.service_id,
            instance_id=service.instance_id,
            major_version=service.major_version,
            minor_version=service.minor_version,
            ttl=service.offer_ttl_seconds,
            ip_v4_endpoints=endpoints,
            ip_v6_endpoints=[],
        )
        sd_message.entries.append(new_entry)
    return sd_message


def create_stop_offer_service_message(
    services_to_stop: Iterable[ServiceToOffer], session_id: int, reboot_flag: bool
) -> SdMessage:

    options = set()

    for service in services_to_stop:
        if service.has_udp:
            options.add(
                IpV4EndpointOption(
                    address=service.endpoint.ip,
                    protocol=TransportLayerProtocol.UDP,
                    port=service.endpoint.port,
                )
            )

        if service.has_tcp:
            options.add(
                IpV4EndpointOption(
                    address=service.endpoint.ip,
                    protocol=TransportLayerProtocol.TCP,
                    port=service.endpoint.port,
                )
            )

    options = list(options)

    sd_message = SdMessage()
    sd_message.session_id = session_id
    sd_message.reboot_flag = reboot_flag

    for service in services_to_stop:
        endpoints = []
        if service.has_udp:
            endpoints.extend(
                [
                    option
                    for option in options
                    if option.protocol == TransportLayerProtocol.UDP
                    and option.address == service.endpoint.ip
                    and option.port == service.endpoint.port
                ]
            )
        if service.has_tcp:
            endpoints.extend(
                [
                    option
                    for option in options
                    if option.protocol == TransportLayerProtocol.TCP
                    and option.address == service.endpoint.ip
                    and option.port == service.endpoint.port
                ]
            )

        new_entry = StopOfferServiceEntry(
            service_id=service.service_id,
            instance_id=service.instance_id,
            major_version=service.major_version,
            minor_version=service.minor_version,
            ip_v4_endpoints=endpoints,
            ip_v6_endpoints=[],
        )
        sd_message.entries.append(new_entry)
    return sd_message
