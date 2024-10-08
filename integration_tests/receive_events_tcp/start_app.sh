#!/bin/bash

script_dir="$(dirname "$0")"

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:~/projects/someip/vsomeip_install/lib/
export VSOMEIP_CLIENTSIDELOGGING="1"
VSOMEIP_CONFIGURATION="${script_dir}/vsomeip-client.json" "${script_dir}/receive_events_tcp"