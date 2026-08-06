"""
Centralized logging setup.

Call `configure_logging()` once, at process start (app.py does this).
Every other module just does `from loguru import logger` and logs normally.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from config import settings


def configure_logging(log_dir: Path | None = None) -> None:
    """
    Configure loguru sinks: colored stdout for dev, rotating file for
    anything worth keeping a record of.
    """
    logger.remove()  # drop the default handler so we control format/level

    logger.add(
        sys.stderr,
        level=settings.log_level.value,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
            "- <level>{message}</level>"
        ),
    )

    log_dir = log_dir or (settings.workspace_dir / "logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="00:00",   # new file at midnight
        retention="14 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    logger.info("Logging configured (level={}, env={})", settings.log_level.value, settings.app_env.value)
