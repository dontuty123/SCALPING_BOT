"""
Minimal indicator implementations for strategy use.
"""

from __future__ import annotations

from typing import List, Optional


def ema(values: List[float], period: int) -> Optional[float]:
    """
    Compute the latest Exponential Moving Average value.

    Args:
        values: Price series (oldest -> newest).
        period: EMA period.
    Returns:
        Latest EMA value, or None if not enough data.
    """
    if period <= 0 or len(values) < period:
        return None

    k = 2 / (period + 1)
    ema_value = sum(values[:period]) / period  # start with SMA seed
    for price in values[period:]:
        ema_value = price * k + ema_value * (1 - k)
    return ema_value


def volume_sma(volumes: List[float], period: int) -> Optional[float]:
    """
    Compute the latest simple moving average of volume.

    Returns:
        Latest SMA value, or None if not enough data.
    """
    if period <= 0 or len(volumes) < period:
        return None
    window = volumes[-period:]
    return sum(window) / period

