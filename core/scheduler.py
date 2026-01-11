"""
Time-based scheduler that runs once per minute, shortly after candle close.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from config import settings
from core.state import BotState
from exchange.binance_client import BinanceAPIError
from exchange.market_data import MarketDataService
from infra.logger import get_logger


class Scheduler:
    """Simple blocking scheduler loop."""

    def __init__(
        self,
        market_data: MarketDataService,
        state: BotState,
        symbol: str,
        klines_limit: int = 200,
    ) -> None:
        self.market_data = market_data
        self.state = state
        self.symbol = symbol
        self.klines_limit = klines_limit
        self.logger = get_logger("Scheduler")

    def run(self) -> None:
        self.logger.info("Scheduler started for symbol %s", self.symbol)
        while True:
            cycle_start = int(time.time() * 1000)
            try:
                self.logger.info("Cycle start at %s", cycle_start)
                candles_1m = self.market_data.fetch_closed_klines(self.symbol, "1m", limit=self.klines_limit)
                candles_5m = self.market_data.fetch_closed_klines(self.symbol, "5m", limit=self.klines_limit)

                if not candles_1m["timestamp"]:
                    self.logger.info("Skipping cycle: 1m candle not ready")
                    continue

                self._log_candle_snapshot("1m", candles_1m)
                self._log_candle_snapshot("5m", candles_5m)

                self.state.update_cycle_time(cycle_start)
                self.logger.info(
                    "State updated: has_position=%s trades_this_hour=%s daily_loss=%.4f",
                    self.state.has_position,
                    self.state.trades_this_hour,
                    self.state.daily_loss,
                )
            except (ValueError, BinanceAPIError) as exc:
                self.logger.error("Cycle error: %s", exc)
            finally:
                sleep_for = self._seconds_until_next_cycle()
                self.logger.info("Cycle end, sleeping %.2fs", sleep_for)
                time.sleep(sleep_for)

    def _seconds_until_next_cycle(self) -> float:
        now = time.time()
        offset = getattr(settings, "SCHEDULER_WAKE_OFFSET_SEC", 1.0)
        next_minute = int(now // 60 + 1) * 60 + offset
        return max(0.5, next_minute - now)

    def _log_candle_snapshot(self, interval: str, candles: Optional[Dict[str, Any]]) -> None:
        if candles is None:
            self.logger.info("No closed candles ready for interval %s", interval)
            return
        if not candles["timestamp"]:
            self.logger.warning("No candles available for interval %s", interval)
            return
        latest_close = candles["close"][-1]
        latest_ts = candles["timestamp"][-1]
        self.logger.info("Latest %s close=%s at %s", interval, latest_close, latest_ts)

