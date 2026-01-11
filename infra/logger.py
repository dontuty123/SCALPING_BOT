"""
Simple structured logger for console and file output.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Optional


DEFAULT_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def get_logger(name: Optional[str] = None, level: int = DEFAULT_LEVEL) -> logging.Logger:
    """
    Return a configured logger instance.

    Ensures handlers are attached only once to avoid duplicate logs.
    """
    logger = logging.getLogger(name if name else "scalp_bot")
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(console_handler)

        # File handler (daily folder: logs/YYYY-MM-DD/bot-HHMMSS-<pid>.log)
        date_folder = datetime.utcnow().strftime("%Y-%m-%d")
        log_dir = os.path.join("logs", date_folder)
        os.makedirs(log_dir, exist_ok=True)
        timestamp_part = datetime.utcnow().strftime("%H%M%S")
        file_path = os.path.join(log_dir, f"bot-{timestamp_part}-{os.getpid()}.log")
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(file_handler)

        logger.setLevel(level)
        logger.propagate = False
    return logger

