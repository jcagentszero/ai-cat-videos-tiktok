"""
utils/logger.py
───────────────
Structured logging setup using loguru.
All modules import `logger` from here.
"""

import sys

from loguru import logger
from config import settings


def setup_logging():
    """Configure loguru with console output and rotating file sink."""
    logger.remove()

    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> — <level>{message}</level>"
        ),
    )

    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        settings.LOGS_DIR / "pipeline_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}",
    )


setup_logging()

__all__ = ["logger", "setup_logging"]
