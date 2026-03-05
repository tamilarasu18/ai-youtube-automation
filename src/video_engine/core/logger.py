"""
Structured logging setup using Loguru.

Provides both console (human-readable) and file (JSON) sinks.
Log level is controlled via the ``LOG_LEVEL`` environment variable.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from video_engine.core.config import get_settings


def setup_logging() -> None:
    """Configure loguru sinks based on application settings."""
    settings = get_settings()

    # Remove default sink
    logger.remove()

    # ── Console sink (coloured, human-readable) ─────────────────
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # ── File sink (structured, rotated) ─────────────────────────
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_path),
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} — {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
    )

    logger.info("Logging initialised (level={})", settings.LOG_LEVEL)


# Re-export logger so other modules can do: from video_engine.core.logger import logger
__all__ = ["logger", "setup_logging"]
