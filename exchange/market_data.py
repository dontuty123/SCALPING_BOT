"""
Market data fetching and normalization for closed klines.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Literal, Optional

from config import settings
from exchange.binance_client import BinanceClient
from infra.logger import get_logger


Interval = Literal["1m", "5m"]

INTERVAL_SECONDS: Dict[Interval, int] = {"1m": 60, "5m": 300}


class MarketDataService:
    """Fetch and normalize closed candles via Binance REST."""

    def __init__(self, client: BinanceClient) -> None:
        self.client = client
        self.logger = get_logger("MarketData")

    def fetch_closed_klines(
        self, symbol: str, interval: Interval, limit: int = 200
    ) -> Dict[str, List[Any]]:
        raw = self.client.get_klines(symbol, interval, limit)
        normalized = self._normalize_klines(raw, interval)
        self.logger.info(
            "Fetched %s klines for %s interval %s (latest close=%s)",
            len(normalized["close"]),
            symbol,
            interval,
            normalized["timestamp"][-1] if normalized["timestamp"] else None,
        )
        return normalized

    def _normalize_klines(self, klines: Any, interval: Interval) -> Dict[str, List[Any]]:
        if not isinstance(klines, list) or not klines:
            raise ValueError("Klines response is empty or invalid")

        interval_ms = INTERVAL_SECONDS[interval] * 1000
        now_ms = int(time.time() * 1000)

        opens: List[float] = []
        highs: List[float] = []
        lows: List[float] = []
        closes: List[float] = []
        volumes: List[float] = []
        timestamps: List[int] = []
        open_times: List[int] = []

        for entry in klines:
            if not isinstance(entry, list) or len(entry) < 7:
                raise ValueError("Unexpected kline format")
            open_time = int(entry[0])
            open_price = float(entry[1])
            high_price = float(entry[2])
            low_price = float(entry[3])
            close_price = float(entry[4])
            volume = float(entry[5])
            close_time = int(entry[6])

            open_times.append(open_time)
            timestamps.append(close_time)
            opens.append(open_price)
            highs.append(high_price)
            lows.append(low_price)
            closes.append(close_price)
            volumes.append(volume)

        self._validate_sequence(open_times, interval_ms)

        safety_margin = getattr(settings, "SAFETY_MARGIN_MS", 1500)
        if not self._is_closed(timestamps[-1], now_ms, safety_margin):
            # Drop the last (forming) candle, keep previous closed candles
            opens = opens[:-1]
            highs = highs[:-1]
            lows = lows[:-1]
            closes = closes[:-1]
            volumes = volumes[:-1]
            timestamps = timestamps[:-1]
            open_times = open_times[:-1]
            self.logger.info("[%s] using previous closed candle", interval)

        if not timestamps:
            return {"open": [], "high": [], "low": [], "close": [], "volume": [], "timestamp": []}

        return {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "timestamp": timestamps,
        }

    def _validate_sequence(self, open_times: List[int], interval_ms: int) -> None:
        for i in range(1, len(open_times)):
            expected = open_times[i - 1] + interval_ms
            if open_times[i] != expected:
                raise ValueError("Missing or unordered candles detected")

    def _is_closed(self, last_close_time: int, now_ms: int, safety_margin_ms: int) -> bool:
        # Consider closed if close time is older than now minus safety margin.
        return last_close_time < (now_ms - safety_margin_ms)

