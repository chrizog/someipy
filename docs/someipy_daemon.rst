someipy Daemon
=================

The someipy daemon is a background process responsible for managing all communication with the SOME/IP network, including service discovery. Applications using the someipy library do not need to handle network communication directly, as the daemon manages these complexities. A single daemon instance should be running per ECU or PC. Applications interact with the daemon via Unix Domain Sockets (UDS).

Starting the Daemon
---------------------

The someipy daemon can be started from the command line. After installing the library with `pip3 install someipy`, the `someipyd` command becomes available in your system's PATH.

To start the daemon, simply run:

.. code-block:: bash

   someipyd

Optionally, you can specify a path to a configuration file using the `--config` argument:

.. code-block:: bash

   someipyd --config /path/to/config.json

The configuration file is a JSON file that allows you to customize the daemon's behavior. The following fields are available and all are optional:

.. code-block:: json

   {
       "sd_address": "224.224.224.245",
       "sd_port": 30490,
       "log_level": "DEBUG",
       "interface": "127.0.0.2",
       "log_path": "/var/log/someipy.log"
   }

- ``sd_address``: The multicast address for Service Discovery.
- ``sd_port``: The port for Service Discovery.
- ``log_level``: The logging level (e.g., DEBUG, INFO, WARNING, ERROR).
- ``interface``: The network interface to bind to.
- ``log_path``: The path to the log file.
