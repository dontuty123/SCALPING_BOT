"""
Lightweight notifier hooks. Currently console-based.
"""

from __future__ import annotations

from infra.logger import get_logger

logger = get_logger("Notifier")


def notify_info(message: str) -> None:
    logger.info("[NOTIFY] %s", message)


def notify_warning(message: str) -> None:
    logger.warning("[NOTIFY] %s", message)


def notify_error(message: str) -> None:
    logger.error("[NOTIFY] %s", message)

