"""
EMA Pullback strategy returning LONG / SHORT / None signals.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from infra.logger import get_logger
from strategy.base import Strategy
from strategy.indicators import ema, volume_sma

Signal = Optional[str]


class EmaPullbackStrategy(Strategy):
    """Stateless EMA pullback strategy."""

    def __init__(self) -> None:
        self.logger = get_logger("EmaPullbackStrategy")

    def generate_signal(self, market_data: Dict[str, Dict[str, Any]]) -> Signal:
        data_1m = market_data.get("1m")
        if not data_1m:
            self.logger.info("No 1m data available, returning no signal")
            return None

        closes = data_1m.get("close", [])
        volumes = data_1m.get("volume", [])

        if len(closes) < 2:
            self.logger.info("Not enough candles for signal")
            return None

        ema20 = ema(closes, 20)
        ema50 = ema(closes, 50)
        vol_ma = volume_sma(volumes, 20)

        if ema20 is None or ema50 is None or vol_ma is None:
            self.logger.info("Insufficient data for indicators")
            return None

        latest_close = closes[-1]
        prev_close = closes[-2]
        latest_volume = volumes[-1] if volumes else None

        if latest_volume is None:
            self.logger.info("No volume data available")
            return None

        long_signal = (
            latest_close > ema50
            and ema20 > ema50
            and prev_close > ema20
            and latest_close <= ema20
            and latest_volume > vol_ma
        )

        if long_signal:
            self.logger.info("Strategy decision: LONG (EMA pullback confirmed)")
            return "LONG"

        short_signal = (
            latest_close < ema50
            and ema20 < ema50
            and prev_close < ema20
            and latest_close >= ema20
            and latest_volume > vol_ma
        )

        if short_signal:
            self.logger.info("Strategy decision: SHORT (EMA pullback confirmed)")
            return "SHORT"

        self.logger.info("Strategy decision: None (no pullback signal)")
        return None

