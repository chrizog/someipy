# Integration Test Applications

The integration test applications use the vsomeip library in order to stimulate the someipy applications.

Each test application has a corresponding someipy example application, which are started together. The test applications can be either started manually or run automatically using the scripts `run_all.py` in `automated_tests`. The script will launch each pair of applications (a someipy app and a vsomeip app). After running both applications, the script will evaluate the logfiles.

## Build Test Applications using CMake

```bash
rm -rf build install && mkdir -p build && cd build && cmake .. && make && make install  && cd ..
```

## Setup Python Pip Package from Source

```bash
python3 -m pip install -e .
```

### Network Setup Linux

```bash
sudo ip addr add 127.0.0.2/8 dev lo
sudo ip addr add 224.224.224.245 dev lo autojoin
```
