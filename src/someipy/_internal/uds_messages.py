from typing import Any, List, TypeVar, TypedDict, get_type_hints


class BaseMessage(TypedDict):
    type: str


class SubscribeEventgroupReadyRequest(BaseMessage):
    service_id: int
    instance_id: int
    major_version: int
    client_endpoint_ip: str
    client_endpoint_port: int
    eventgroup_id: int
    ttl_subscription: int
    protocol: int
    service_endpoint_ip: str
    service_endpoint_port: int


class SubscribeEventgroupReadyResponse(BaseMessage):
    success: bool
    service_id: int
    instance_id: int
    major_version: int
    client_endpoint_ip: str
    client_endpoint_port: int
    eventgroup_id: int
    ttl_subscription: int
    protocol: int
    service_endpoint_ip: str


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


class CallMethodRequest(BaseMessage):
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


class CallMethodResponse(BaseMessage):
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


if __name__ == "__main__":

    x = create_uds_message(
        SubscribeEventgroupReadyRequest,
        service_id=1,
        instance_id=2,
        major_version=3,
        client_endpoint_ip="1",
        client_endpoint_port=4,
        eventgroup_id=5,
        ttl_subscription=6,
        protocol=7,
        service_endpoint_ip="1",
        service_endpoint_port=2,
    )

    print(x)
