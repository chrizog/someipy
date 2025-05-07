from typing import Any, TypeVar, TypedDict, get_type_hints


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


T = TypeVar("T", bound=BaseMessage)


def create_uds_message(message_type: type[T], **kwargs: Any) -> T:
    type_value = message_type.__name__
    message = {"type": type_value, **kwargs}

    # For development: Test if all keys are given using type inspection

    if set(message.keys()) != set(get_type_hints(message_type).keys()):
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
