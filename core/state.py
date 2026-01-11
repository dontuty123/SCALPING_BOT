"""
In-memory bot state for tracking basic runtime metrics.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional


class BotState:
    """Track bot runtime state without persistence."""

    def __init__(self) -> None:
        self.has_position: bool = False
        self.last_cycle_time: Optional[int] = None  # epoch ms
        self.trades_this_hour: int = 0
        self.daily_loss: float = 0.0
        self._current_hour: int = self._hour_key(dt.datetime.utcnow())
        self._current_day: dt.date = dt.datetime.utcnow().date()

    def update_cycle_time(self, timestamp_ms: int) -> None:
        """Update last cycle time and perform hour/day boundary resets."""
        self._maybe_reset_hour(timestamp_ms)
        self._maybe_reset_day(timestamp_ms)
        self.last_cycle_time = timestamp_ms

    def set_position(self, has_position: bool) -> None:
        self.has_position = has_position

    def increment_trades(self, count: int = 1) -> None:
        self.trades_this_hour += count

    def add_loss(self, loss_amount: float) -> None:
        self.daily_loss += loss_amount

    def reset_hour(self) -> None:
        self.trades_this_hour = 0
        self._current_hour = self._hour_key(dt.datetime.utcnow())

    def reset_day(self) -> None:
        self.daily_loss = 0.0
        self._current_day = dt.datetime.utcnow().date()

    def _maybe_reset_hour(self, timestamp_ms: int) -> None:
        current = dt.datetime.utcfromtimestamp(timestamp_ms / 1000.0)
        current_hour = self._hour_key(current)
        if current_hour != self._current_hour:
            self.reset_hour()

    def _maybe_reset_day(self, timestamp_ms: int) -> None:
        current_date = dt.datetime.utcfromtimestamp(timestamp_ms / 1000.0).date()
        if current_date != self._current_day:
            self.reset_day()

    @staticmethod
    def _hour_key(dt_obj: dt.datetime) -> int:
        return dt_obj.year * 10_000 + dt_obj.timetuple().tm_yday * 24 + dt_obj.hour

