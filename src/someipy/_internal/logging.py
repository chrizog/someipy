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
from someipy.logging import get_someipy_log_level

def setup_console_handler(formatter: logging.Formatter, level: int) -> logging.StreamHandler:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    return console_handler

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"someipy.{name}")
    log_level = get_someipy_log_level()
    
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(name)s [%(levelname)s]: %(message)s",
        datefmt="%Y-%m-%d,%H:%M:%S",
    )

    # Check if the logger already has a console handler
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        console_handler = setup_console_handler(formatter, log_level)
        logger.addHandler(console_handler)

    logger.setLevel(log_level)
    
    return logger