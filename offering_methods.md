---
layout: default
title: Offering SOME/IP Methods
nav_order: 4
---

<style type="text/css">
pre > code.language-mermaid {
    display: flex;
    justify-content: center;
    align-items: center;
}

p:has(img) {
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>

# Offering SOME/IP Methods
## SOME/IP Methods

Methods implement a request-response communication in the SOME/IP protocol. A server offers a method. A client calls the method by sending a request message to the server. The server answers the request message with a response message. In contrast to SOME/IP events, no subscription of the offered service has to be setup in order to make method request call. 

Request and response messages can carry a serialized payload. Typically, the payload is either the argument to the method or the return value of the method. For defining the service interface data types which can be used in methods and serializing structured data into `bytes` follow the article [SOME/IP Service Interface Data Types](/someipy/service_interface.html).

In SOME/IP there is also the possibility of fire&forget communication. The client sends a request message and does not expect a response from the server. The fire&forget communication is not implemented in someipy yet.

## Step 1: Define the Data Types for Request and Response

In this example we will offer a SOME/IP service that calculates the sum of two signed integers and returns the result back to the client. Therefore, we need to define two data types: one type `Addends` is passed as an argument in the request and the second data type `Sum` is used for transmitting the result in the response message.

```python
@dataclass
class Addends(SomeIpPayload):
    addend1: Sint16
    addend2: Sint16

    def __init__(self, addend1: int = 0, addend2: int = 0):
        self.addend1 = Sint16(addend1)
        self.addend2 = Sint16(addend2)

@dataclass
class Sum(SomeIpPayload):
    value: Sint32

    def __init__(self):
        self.value = Sint32()
```

Details on defining data types can be found [here](/someipy/service_interface.html).

## Step 2: Implementing the Method Handler

In the next step, we will implement the method handler. This function will receive a `bytes` object and a Tuple with the caller's IP address and port. The received `bytes` object will be deserialized into an `Addends` object. After calculating the sum, the result in the `Sum` will be serialized and returned. It is possible to return `True` or `False` from the method handler. In case of `False` the someipy library will send an error response message to the caller indicating that the method call had an internal error. This error handling is always application specific and is not related e.g. to data loss during transmission.

```python
def add_method_handler(input_data: bytes, addr: Tuple[str, int]) -> Tuple[bool, bytes]:
    print(
        f"Received data: {' '.join(f'0x{b:02x}' for b in input_data)} from IP: {addr[0]} Port: {addr[1]}"
    )

    try:
        # Deserialize the input data
        addends = Addends()
        addends.deserialize(input_data)
    except Exception as e:
        print(f"Error during deserialization: {e}")
        return False, b""

    sum = Sum()
    sum.value = Sint32(addends.addend1.value + addends.addend2.value)
    print(f"Send back: {' '.join(f'0x{b:02x}' for b in sum.serialize())}")
    return True, sum.serialize()
```

## Step 3: Definition of the Service

In order to offer a service containing a SOME/IP method, we will instantiate a `Method` and a `Service` object. The `Method` class holds the method ID and the reference to the method handler function. The `Service` object contains the `Method` objects and is used afterwards to instantiate a `ServerServiceInstance`. The `Service` will contain a single method with ID 0x1234. The `ServiceBuilder` class is used to create the `Service` object.

It's also possible to define multiple `Method`s and add them all to the `Service`. The `with_method` function can be called multiple times on the `ServiceBuilder` object.

```python
SAMPLE_SERVICE_ID = 0x1234

addition_method = Method(id=SAMPLE_METHOD_ID, method_handler=add_method_handler)

addition_service = (
    ServiceBuilder()
    .with_service_id(SAMPLE_SERVICE_ID)
    .with_major_version(1)
    .with_method(addition_method)
    .build()
)
```

## Step 4: Instantiate the Service

The previously defined `Service` can be instantiated as one or multiple service instances. Since we are offering the method as a server, a `ServerServiceInstance` object is created using the `construct_server_service_instance` function. The `construct_server_service_instance` is a coroutine and therefore has to be awaited.

- You need to pass an instance ID (`SAMPLE_INSTANCE_ID`) to the function.
- The endpoint that is passed is the endpoint (ip address and port) of the server and to which the client will send the requests.
- The `ttl` parameter will be used for sending service discovery offer messages. The `ttl` in seconds is the lifetime of the service offer.
- It is assumed that the `service_discovery` object was instantiated beforehand. For more information on that topic, read [Service Discovery Configuration Parameters](/someipy/service_discovery.html).
- The `cyclic_offer_delay_ms` is the interval in which the service instance will be offered periodically by the SOME/IP service discovery to clients.
- You can choose to either use UDP or TCP as the transport protocol used for the service instance.

```python
SAMPLE_INSTANCE_ID = 0x5678

service_instance_addition = await construct_server_service_instance(
    addition_service,
    instance_id=SAMPLE_INSTANCE_ID,
    endpoint=(
        ipaddress.IPv4Address(interface_ip),
        3000,
    ),  # src IP and port of the service
    ttl=5,
    sd_sender=service_discovery,
    cyclic_offer_delay_ms=2000,
    protocol=TransportLayerProtocol.UDP,
)
```

## Step 5: Announce the Service via Service Discovery

Finally the service instance has to be offered to clients via service discovery. This step is not specific to SOME/IP methods. For that purpose, we will notify the `service_discovery` about the service instance using the `attach` function and call the `start_offer` function on the service instance. The `start_offer` function starts an internal timer with a period of `cyclic_offer_delay_ms` and send out SOME/IP SD offers to potential clients.

```python
service_discovery.attach(service_instance_temperature)
service_instance_temperature.start_offer()
```
