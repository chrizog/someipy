CHANGELOG
=========

All notable user-facing changes to this project are documented in this file.

HEAD
----

Code changes to ``master`` that are *not* in the latest release:

Release v2.0.0
-----------------
- Introduced a new architecture with a `someipyd` daemon for centralized network handling.
- Refined application API for easier service definition and instantiation.

Release v1.0.0
--------------

- Support dynamically sized arrays
- Support fixed size strings
- Support dynamically sized strings
- Implement timeouts (ttl checks) for SD messages

Release v0.0.10
---------------

- Fix Python 3.8 issue from version 0.0.9 (Set of asyncio.Task typing)
- Properly handle major version (interface version) of services
- Handle session IDs and client IDs
- Allow multiple asynchronous method calls from a client and handle out of order method responses

Release v0.0.9
--------------

- Enable asynchronous method handlers

Release v0.0.8
--------------

- Improved method error handling
- Update of method handler function signature

Release v0.0.7
--------------

- Improved integration testing
- Bugfix: Handle subscribe acknowledge correctly

Release v0.0.6
--------------

- Pack together service offers in a single Service Discovery message (this requires the offers to be sent within max. 20ms)
- Send SD stop offer entries when a service instance is shut down

Release v0.0.5
--------------

- Fix issue in socket bind for Service Discovery via multicast to use the right network interface
- Add IPv4 SD Endpoint Option to avoid crashes in case it is received
- Implement proper SD option handling ("first and second option run")

Release v0.0.4
--------------

- Publish library under GPL-3.0 license

Release v0.0.3
--------------

- Support Windows
- Automatic multicast group join
- Support method calls via TCP

Release v0.0.2
--------------

- Support TCP as a transport layer
- Support offering and calling methods
- Add an example of how to replay ROS1 bagfiles into SOME/IP events
- Add docstrings for all public classes and functions
