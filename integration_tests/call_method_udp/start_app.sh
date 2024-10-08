#!/bin/bash

script_dir="$(dirname "$0")"

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:~/projects/someip/vsomeip_install/lib/
VSOMEIP_CONFIGURATION="${script_dir}/vsomeip-client.json" "${script_dir}/call_method_udp"