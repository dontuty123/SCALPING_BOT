"""
Trade limit tracking for daily/hourly caps and losses.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from config import risk as risk_config


class TradeLimits:
    """
    Track trade counts and losses to enforce configured limits.
    """

    def __init__(self) -> None:
        self.daily_trades: int = 0
        self.hourly_trades: int = 0
        self.daily_loss: float = 0.0
        self._current_day: dt.date = dt.datetime.utcnow().date()
        self._current_hour_key: int = self._hour_key(dt.datetime.utcnow())

        # Limits from config (static)
        self.max_daily_loss = getattr(risk_config, "MAX_DAILY_LOSS", None)
        self.max_trades_per_day = getattr(risk_config, "MAX_TRADES_PER_DAY", None)
        self.max_trades_per_hour = getattr(risk_config, "MAX_TRADES_PER_HOUR", None)

    def reset_if_needed(self, now_ms: int) -> None:
        now = dt.datetime.utcfromtimestamp(now_ms / 1000.0)
        day = now.date()
        hour_key = self._hour_key(now)
        if day != self._current_day:
            self.daily_trades = 0
            self.daily_loss = 0.0
            self._current_day = day
        if hour_key != self._current_hour_key:
            self.hourly_trades = 0
            self._current_hour_key = hour_key

    def record_trade(self, pnl: float, now_ms: int) -> None:
        """
        Record a completed trade: increment counts and accumulate PnL.
        """
        self.reset_if_needed(now_ms)
        self.daily_trades += 1
        self.hourly_trades += 1
        self.daily_loss = self.daily_loss + pnl if pnl < 0 else self.daily_loss

    def limits_exceeded(self) -> bool:
        """
        Check if any configured limit is exceeded.
        """
        if self.max_daily_loss is not None and self.daily_loss <= -abs(self.max_daily_loss):
            return True
        if self.max_trades_per_day is not None and self.daily_trades > self.max_trades_per_day:
            return True
        if self.max_trades_per_hour is not None and self.hourly_trades > self.max_trades_per_hour:
            return True
        return False

    @staticmethod
    def _hour_key(dt_obj: dt.datetime) -> int:
        return dt_obj.year * 10_000 + dt_obj.timetuple().tm_yday * 24 + dt_obj.hour

