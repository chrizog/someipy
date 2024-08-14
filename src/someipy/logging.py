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

import logging

_log_level = logging.DEBUG


def set_someipy_log_level(logging_level: int):
    """
    Set the log level for the someipy module.

    Args:
        logging_level (int): The log level to set. Must be one of the constants defined in the logging module,
        such as logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, or logging.CRITICAL.
    """
    global _log_level
    _log_level = logging_level


def get_someipy_log_level() -> int:
    """
    Get the current log level for the someipy library.

    Returns:
        int: The current log level.
    """
    global _log_level
    return _log_level
