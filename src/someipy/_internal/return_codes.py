# Copyright (C) 2024 Christian H.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from enum import Enum


# PRS_SOMEIP_00191
class ReturnCode(Enum):
    E_OK = 0x00  # No error occurred
    E_NOT_OK = 0x01  # An unspecified error occurred
    E_UNKNOWN_SERVICE = 0x02  # The requested Service ID is unknown.
    E_UNKNOWN_METHOD = 0x03  # The requested Method ID is unknown.
    E_NOT_READY = 0x04  # Service ID and Method ID are known. Application not running.
    E_NOT_REACHABLE = (
        0x05  # System running the service is not reachable (internal error code only).
    )
    E_TIMEOUT = 0x06  # A timeout occurred (internal error code only).
    E_WRONG_PROTOCOL_VERSION = 0x07  # Version of SOME/IP protocol not supported
    E_WRONG_INTERFACE_VERSION = 0x08  # Interface version mismatch
    E_MALFORMED_MESSAGE = (
        0x09  # Deserialization error, so that payload cannot be de-serialized.
    )
    E_WRONG_MESSAGE_TYPE = 0x0A  # An unexpected message type was received (e.g. REQUEST_NO_RETURN for a method defined as REQUEST).
