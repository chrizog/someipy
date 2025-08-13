# Copyright (C) 2024 Christian H.
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

from typing import Any, List, TypeVar, TypedDict, get_type_hints


class BaseMessage(TypedDict):
    type: str


class OfferServiceRequest(BaseMessage):
    service_id: int
    instance_id: int
    major_version: int
    minor_version: int
    endpoint_ip: str
    endpoint_port: int
    ttl: int
    eventgroup_list: List[str]
    method_list: List[str]
    cyclic_offer_delay_ms: int


class StopOfferServiceRequest(BaseMessage):
    service_id: int
    instance_id: int
    major_version: int
    minor_version: int
    endpoint_ip: str
    endpoint_port: int
    ttl: int
    eventgroup_list: List[str]
    method_list: List[str]
    cyclic_offer_delay_ms: int


class FindServiceRequest(BaseMessage):
    service_id: int
    instance_id: int
    major_version: int
    minor_version: int


class FindServiceResponse(BaseMessage):
    success: bool
    service_id: int
    instance_id: int
    major_version: int
    minor_version: int
    endpoint_ip: str
    endpoint_port: int


class OutboundCallMethodRequest(BaseMessage):
    service_id: int
    instance_id: int
    method_id: int
    client_id: int
    session_id: int
    protocol_version: int
    major_version: int
    minor_version: int
    dst_endpoint_ip: str
    dst_endpoint_port: int
    src_endpoint_ip: str
    src_endpoint_port: int
    protocol: int
    payload: str


class OutboundCallMethodResponse(BaseMessage):
    service_id: int
    method_id: int
    client_id: int
    session_id: int
    return_code: int
    dst_endpoint_ip: str
    dst_endpoint_port: int
    payload: str


class InboundCallMethodRequest(BaseMessage):
    service_id: int
    instance_id: int
    method_id: int
    client_id: int
    session_id: int
    protocol_version: int
    interface_version: int
    major_version: int
    minor_version: int
    message_type: int
    src_endpoint_ip: str
    src_endpoint_port: int
    protocol: int
    payload: str


class InboundCallMethodResponse(BaseMessage):
    service_id: int
    instance_id: int
    method_id: int
    client_id: int
    session_id: int
    protocol_version: int
    interface_version: int
    major_version: int
    minor_version: int
    message_type: int
    src_endpoint_ip: str
    src_endpoint_port: int
    protocol: int
    payload: str
    return_code: int


class SendEventRequest(BaseMessage):
    service_id: int
    instance_id: int
    major_version: int
    client_id: int
    session_id: int
    eventgroup_id: int
    event: str  # Serialized event object
    src_endpoint_ip: str
    src_endpoint_port: int
    payload: str


class SubscribeEventGroupRequest(BaseMessage):
    service_id: int
    instance_id: int
    major_version: int
    ttl_subscription: int
    eventgroup: str
    client_endpoint_ip: str
    client_endpoint_port: int
    udp: bool
    tcp: bool


class StopSubscribeEventGroupRequest(BaseMessage):
    service_id: int
    instance_id: int
    major_version: int
    eventgroup_id: int
    client_endpoint_ip: str
    client_endpoint_port: int


class ReceivedEvent(BaseMessage):
    service_id: int
    event_id: int
    src_endpoint_ip: str
    src_endpoint_port: str
    payload: str


T = TypeVar("T", bound=BaseMessage)


def create_uds_message(message_python_type: type[T], **kwargs: Any) -> T:
    type_value = message_python_type.__name__
    message = {"type": type_value, **kwargs}

    # For development: Test if all keys are given using type inspection
    if set(message.keys()) != set(get_type_hints(message_python_type).keys()):
        raise RuntimeError(
            f"Invalid data passed to create_uds_message for type {type_value}"
        )

    return message
