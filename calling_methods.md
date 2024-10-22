---
layout: default
title: Calling SOME/IP Methods
nav_order: 5
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

# Calling SOME/IP Methods
## SOME/IP Methods

Methods implement a request-response communication in the SOME/IP protocol. A server offers a method. A client calls the method by sending a request message to the server. The server answers the request message with a response message. In contrast to SOME/IP events, no subscription of the offered service has to be setup in order to make method request call. 

Request and response messages can carry a serialized payload. Typically, the payload is either the argument to the method or the return value of the method. For defining the service interface data types which can be used in methods and serializing structured data into `bytes` follow the article [SOME/IP Service Interface Data Types](/someipy/service_interface.html).

In SOME/IP there is also the possibility of fire&forget communication. The client sends a request message and does not expect a response from the server. The fire&forget communication is not implemented in someipy yet.

## Step 1: Define the Data Types for Request and Response

In this example, we will call a SOME/IP method that calculates the sum of two signed integers and returns the result back to the client. When we are calling the method, we will pass the two addends with the request message to the server. The server will send back a response message containing the sum. For request and response, we need to define two data types `Addends` and `Sum`. The data types are the same types as defined in the article [Offering SOME/IP Methods](/someipy/offering_methods.html).

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

## Step 2: Definition of the Service

A SOME/IP method is part of a service and so we will define a `Service` as the next step using the method ID and the major version of the service. In the third step, this service will be used for creating a `ClientServiceInstance` on which we can call the SOME/IP method. The `ServiceBuilder` class offers a fluent API, which is used for creation of the `Service` object.

```python
SAMPLE_SERVICE_ID = 0x1234

addition_service = (
        ServiceBuilder()
        .with_service_id(SAMPLE_SERVICE_ID)
        .with_major_version(1)
        .build()
    )
```

## Step 3: Instantiate the Service

The previously defined `Service` can be instantiated into one or multiple service instances. Since we want to call (and not offer) a method, we will instantiate a `ClientServiceInstance`.
The `construct_client_service_instance` is a coroutine since it uses `asyncio` internally and therefore has to be `await`ed.

- You need to pass the instance ID (`SAMPLE_INSTANCE_ID`) of the server service instance that offers the method.
- The endpoint that is passed is the endpoint (ip address and port) of the client and not of the server.
- The `ttl` parameter is the lifetime of a potential subscription in seconds. This is only relevant if you want to [subscribe to an event](someipy/subscribing_events.html).
- It is assumed that the `service_discovery` object was instantiated beforehand. For more information on that topic, read [Service Discovery Configuration Parameters](/someipy/service_discovery.html).
- You can choose either UDP or TCP as the transport protocol. Make sure, that it matches to the service offered by the server.

We will also attach the `ClientServiceInstance` to the `ServiceDiscovery` object. This allows the `ClientServiceInstance` to be notified about service discovery messages.

```python
SAMPLE_INSTANCE_ID = 0x5678

client_instance_addition = await construct_client_service_instance(
    service=addition_service,
    instance_id=SAMPLE_INSTANCE_ID,
    endpoint=(ipaddress.IPv4Address(interface_ip), 3002),
    ttl=5,
    sd_sender=service_discovery,
    protocol=TransportLayerProtocol.UDP,
)

service_discovery.attach(client_instance_addition)
```

## Step 4: Calling the Method

Finally, we need to setup the method parameters for the request and call the SOME/IP method offered by the server. In this case, the parameter to the method is an `Addends` object. After creating the `Addends` object, we will call the method on the `ClientServiceInstance` using the `call_method` function. `call_method` is a coroutine which has to be awaited and will not block until the response from the server is received. This allows other tasks to be scheduled while waiting for a response. The `call_method` function expects a method ID identifying the method on the server to be called. A server could offer multiple methods inside the same service. The second parameter is the payload to be sent with the request: The `Addends` object is serialized into a `bytes` object and passed to the call.

The `call_method` function returns a `MethodResult` object with following members:

- message_type (`MessageType`): The MessageType is an enum and can be either `MessageType.RESPONSE` or `MessageType.ERROR`.
- return_code (`ReturnCode`): The `ReturnCode` enum reflects the return codes defined in the [SOME/IP protocol specification](https://www.autosar.org/fileadmin/standards/R22-11/FO/AUTOSAR_PRS_SOMEIPProtocol.pdf). For indicating a successful method call to the client, `E_OK` is returned by the server.
- payload (`bytes`): The payload is a `bytes` object which can be deserialized into the expected returned message structure. In this case it will be deserialized into a `Sum` object.

The `call_method` function can raise a `RuntimeError` or an `asyncio.TimeoutError`. A `RuntimeError` is raised in case the service instance offered by the server was not found yet. In this case no method request can be sent since the destination IP address and port are not available yet. The `asyncio.TimeoutError` is raised if no response is received by the server after sending the request or in case of TCP, the TCP connection cannot be established.

To avoid the `RuntimeError` it is possible to test whether the service was already found by using the `service_found` method on the `ClientServiceInstance`.

```python
method_parameter = Addends(addend1=1, addend2=2)
try:
    # You can query if the service offering the method was already found via SOME/IP service discovery
    print(f"Service found: {client_instance_addition.service_found()}")
    while not client_instance_addition.service_found():
        print("Waiting for service..")
        await asyncio.sleep(0.5)
    # The call_method function can raise an error, e.g. if no TCP connection to the server can be established
    # In case there is an application specific error in the server, the server still returns a response and the
    # message_type and return_code are evaluated.
    method_result = await client_instance_addition.call_method(
        SAMPLE_METHOD_ID, method_parameter.serialize()
    )
    if method_result.message_type == MessageType.RESPONSE:
        print(
            f"Received result for method: {' '.join(f'0x{b:02x}' for b in method_result.payload)}"
        )
        if method_result.return_code == ReturnCode.E_OK:
            sum = Sum().deserialize(method_result.payload)
            print(f"Sum: {sum.value.value}")
        else:
            print(
                f"Method call returned an error: {method_result.return_code}"
            )
    elif method_result.message_type == MessageType.ERROR:
        print("Server returned an error..")
        # In case the server includes an error message in the payload, it can be deserialized and printed
except Exception as e:
    print(f"Error during method call: {e}")
```
