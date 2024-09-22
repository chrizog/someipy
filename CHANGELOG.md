---
title: CHANGELOG
layout: default
nav_order: 20
---

# CHANGELOG

All notable user-facing changes to this project are documented in this file.

<!--
{: .highlight }
The project underwent a major maintenance shift in March 2022.
-->

## HEAD


Code changes to `master` that are *not* in the latest release:

## Release v0.0.5
- Fix issue in socket bind for Service Discovery via multicast to use the right network interface
- Add IPv4 SD Endpoint Option to avoid crashes in case it is received
- Implement proper SD option handling ("first and second option run")

## Release v0.0.4
### New Features
- Publish library under GPL-3.0 license

### Bugfixes
-

## Release v0.0.3
### New Features
- Support Windows
- Automatic multicast group join
- Support method calls via TCP

### Bugfixes
-

## Release v0.0.2
### New Features
- Support TCP as a transport layer
- Support offering and calling methods
- Add an example how to replay ROS1 bagfiles into SOME/IP events
- Add docstrings for all public classes and functions

### Bugfixes
-