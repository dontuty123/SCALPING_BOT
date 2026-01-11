"""
Kill switch to prevent new entries when limits are exceeded.
"""

from __future__ import annotations

from infra.logger import get_logger
from risk.trade_limits import TradeLimits


class KillSwitch:
    """
    Blocks new trades when risk limits are hit. Does not close existing positions.
    """

    def __init__(self) -> None:
        self.is_trading_allowed: bool = True
        self.logger = get_logger("KillSwitch")

    def evaluate(self, limits: TradeLimits) -> None:
        if limits.limits_exceeded():
            if self.is_trading_allowed:
                self.logger.warning("KILL SWITCH ACTIVATED: risk limits exceeded")
            self.is_trading_allowed = False

    def reset_daily(self) -> None:
        """
        Reset at a new trading day boundary.
        """
        if not self.is_trading_allowed:
            self.logger.info("Kill switch reset for new day")
        self.is_trading_allowed = True

