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
