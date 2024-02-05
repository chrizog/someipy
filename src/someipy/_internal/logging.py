import logging
from someipy.logging import get_someipy_log_level

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger("someipy." + name)
    logger.setLevel(get_someipy_log_level())
    console_handler = logging.StreamHandler()
    console_handler.setLevel(get_someipy_log_level())
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(name)s [%(levelname)s]: %(message)s",
            datefmt="%Y-%m-%d,%H:%M:%S",
        )
    )
    logger.addHandler(console_handler)
    return logger
