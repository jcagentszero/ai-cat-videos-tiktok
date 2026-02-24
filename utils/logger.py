"""
utils/logger.py
───────────────
Structured logging setup using loguru.
All modules import `logger` from here.

TODO: configure log rotation, levels, and optional remote sink
"""

from loguru import logger
from config import settings

# TODO: configure logger
# logger.add(
#     settings.LOGS_DIR / "pipeline_{time}.log",
#     rotation="1 day",
#     retention="30 days",
#     level="INFO",
#     format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
# )

__all__ = ["logger"]
