import logging

_log_level = logging.INFO


def set_someipy_log_level(log_level: int):
    global _log_level
    _log_level = log_level


def get_someipy_log_level() -> int:
    global _log_level
    return _log_level
