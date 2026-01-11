"""
Global settings configurable via environment variables.
"""

import os

TESTNET = str(os.getenv("BINANCE_TESTNET", "true")).lower() == "true"
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))
SAFETY_MARGIN_MS = int(os.getenv("SAFETY_MARGIN_MS", "1500"))
KLINES_LIMIT = int(os.getenv("KLINES_LIMIT", "200"))
SCHEDULER_WAKE_OFFSET_SEC = float(os.getenv("SCHEDULER_WAKE_OFFSET_SEC", "1.0"))

