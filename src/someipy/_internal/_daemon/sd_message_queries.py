# Copyright (C) 2026 Christian H.
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

from itertools import chain
from typing import Iterator
import someipy
from someipy._internal._common.endpoint import Endpoint
from someipy._internal._daemon.subscription import Subscription
from someipy._internal._sd.entries.offer_service_entry import OfferServiceEntry
from someipy._internal._sd.entries.subscribe_ack_entry import (
    SubscribeAckEventGroupEntry,
)
from someipy._internal._sd.entries.subscribe_eventgroup_entry import (
    SubscribeEventGroupEntry,
)
from someipy._internal._sd.entries.subscribe_eventgroup_nack import (
    SubscribeEventGroupNackEntry,
)
from someipy._internal._sd.sd_message import SdMessage
from someipy._internal._sd.service_instance import ServiceInstance
from someipy.service import EventGroup


def get_offered_service_instances(sd_message: SdMessage) -> Iterator[ServiceInstance]:

    for offer_service_entry in [
        o
        for o in sd_message.entries
        if o.type == someipy._internal._sd.entries.sd_entry.SdEntryType.OFFER_SERVICE
    ]:
        entry: OfferServiceEntry = offer_service_entry

        protocols = {
            ep.protocol for ep in chain(entry.ip_v4_endpoints, entry.ip_v6_endpoints)
        }

        endpoint = Endpoint(
            ip=entry.ip_v4_endpoints[0].address,
            port=entry.ip_v4_endpoints[0].port,
        )

        service_instance = ServiceInstance(
            service_id=entry.service_id,
            instance_id=entry.instance_id,
            major_version=entry.major_version,
            minor_version=entry.minor_version,
            ttl=entry.ttl,
            endpoint=endpoint,
            protocols=frozenset(protocols),
            timestamp=sd_message.timestamp,
        )

        yield service_instance


def get_subscriptions(sd_message: SdMessage) -> Iterator[Subscription]:

    for subscribe_eventgroup_entry in [
        e
        for e in sd_message.entries
        if e.type
        == someipy._internal._sd.entries.sd_entry.SdEntryType.SUBSCRIBE_EVENT_GROUP
        and isinstance(e, SubscribeEventGroupEntry)
    ]:
        entry: SubscribeEventGroupEntry = subscribe_eventgroup_entry

        protocols = {
            ep.protocol for ep in chain(entry.ip_v4_endpoints, entry.ip_v6_endpoints)
        }

        endpoint = Endpoint(
            ip=entry.ip_v4_endpoints[0].address,
            port=entry.ip_v4_endpoints[0].port,
        )

        subscription = Subscription(
            service_id=entry.service_id,
            instance_id=entry.instance_id,
            major_version=entry.major_version,
            eventgroup=EventGroup(entry.eventgroup_id, []),
            ttl_seconds=entry.ttl,
            client_endpoint=endpoint,
            server_endpoint=endpoint,  # Placeholder, server endpoint not in SD message
            protocols=frozenset(protocols),
            timestamp_last_update=0.0,
        )

        yield subscription


def get_subscribe_acks(sd_message: SdMessage) -> Iterator[Subscription]:

    for subscribe_ack_eventgroup_entry in [
        e
        for e in sd_message.entries
        if e.type
        == someipy._internal._sd.entries.sd_entry.SdEntryType.SUBSCRIBE_EVENT_GROUP_ACK
        and isinstance(e, SubscribeAckEventGroupEntry)
    ]:
        entry: SubscribeAckEventGroupEntry = subscribe_ack_eventgroup_entry

        subscription = Subscription(
            service_id=entry.service_id,
            instance_id=entry.instance_id,
            major_version=entry.major_version,
            eventgroup=EventGroup(entry.eventgroup_id, []),
            ttl_seconds=entry.ttl,
            client_endpoint=Endpoint(),  # Placeholder, client endpoint not in SD message
            server_endpoint=Endpoint(),  # Placeholder, server endpoint not in SD message
            protocols=frozenset(),
            timestamp_last_update=0.0,
        )

        yield subscription


def get_subscribe_nacks(sd_message: SdMessage) -> Iterator[Subscription]:

    for subscribe_nack_eventgroup_entry in [
        e
        for e in sd_message.entries
        if e.type
        == someipy._internal._sd.entries.sd_entry.SdEntryType.SUBSCRIBE_EVENT_GROUP_NACK
        and isinstance(e, SubscribeEventGroupNackEntry)
    ]:
        entry: SubscribeEventGroupNackEntry = subscribe_nack_eventgroup_entry

        subscription = Subscription(
            service_id=entry.service_id,
            instance_id=entry.instance_id,
            major_version=entry.major_version,
            eventgroup=EventGroup(entry.eventgroup_id, []),
            ttl_seconds=0,
            client_endpoint=Endpoint(),  # Placeholder, client endpoint not in SD message
            server_endpoint=Endpoint(),  # Placeholder, server endpoint not in SD message
            protocols=frozenset(),
            timestamp_last_update=0.0,
        )

        yield subscription
