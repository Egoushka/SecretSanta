import sys
from loguru import logger


def setup_logging(level: str, log_path: str) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="{time} | {level} | {module}:{function}:{line} | {message}",
    )
    logger.add(
        log_path,
        level="DEBUG",
        format="{time} | {level} | {module}:{function}:{line} | {message}",
        rotation="100 KB",
        compression="zip",
    )
