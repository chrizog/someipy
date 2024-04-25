## Build Test Applications using CMake

```bash
rm -rf build install && mkdir -p build && cd build && cmake .. && make && make install  && cd ..
```

## Setup Python Pip Package from Source

```bash
python3.12 -m pip install -e .
```

## Test Procedure

### Network Setup Linux

```bash
sudo ip addr add 127.0.0.2/8 dev lo
sudo ip addr add 224.224.224.245 dev lo autojoin
```

### 1. send_events_udp

Open two terminals (one for Python someipy example app, one for test app).

Start apps:

```bash
python3.12 send_events_udp.py
bash ./install/send_events/start_app.sh
```

Expected in test app:
- Expected log for UDP endpoint on port 3000:
    - *endpoint_manager_impl::create_remote_client: 127.0.0.1:3000 reliable: 0 using local port: 0*
    - *udp_client_endpoint_impl::connect: SO_RCVBUF is: 212992 (1703936) local port:0 remote:127.0.0.1:3000*
- Receive event with frequency 1Hz
- Service ID: 0x1234
- Instance ID: 0x5678
- Eventgroup ID: 0x0321
- Event ID: 0x0123
- SD Offer is sent with 0.5Hz


### 1. send_events_tcp

Open two terminals (one for Python someipy example app, one for test app).

Start apps:

```bash
python3.12 send_events_tcp.py
bash ./install/send_events/start_app.sh
```

Expected in test app:
- Expected log for TCP endpoint on port 3000:
    - *endpoint_manager_impl::create_remote_client: 127.0.0.1:3000 reliable: 1 using local port: 0*
    - Check for "reliable == 1" in above log (i.e. TCP)
    - No "udp_client_endpoint_impl::connect" shall appear
- Receive event with frequency 1Hz
- Service ID: 0x1234
- Instance ID: 0x5678
- Eventgroup ID: 0x0321
- Event ID: 0x0123
- SD Offer is sent with 0.5Hz

### 1. receive_events_udp

Open two terminals (one for Python someipy example app, one for test app).

Start apps:

```bash
python3.12 receive_events_udp.py
bash install/receive_events_udp/start_app.sh
```

Expected in test app:
- Expected log for UDP endpoint: REMOTE SUBSCRIBE(0000): [1234.5678.0321] from 127.0.0.1:3002 unreliable was accepted

Expected in example app:
- Receive event with frequency 1Hz
- Service ID: 0x1234
- Instance ID: 0x5678
- Eventgroup ID: 0x0321
- Event ID: 0x0123
- SD Offer is sent with 0.5Hz