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