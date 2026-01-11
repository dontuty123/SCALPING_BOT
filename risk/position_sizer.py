"""
Position sizing utility using fixed risk percent.
"""

from __future__ import annotations

from typing import Optional


def compute_position_size(
    equity: float,
    risk_percent: float,
    entry_price: float,
    sl_percent: float,
) -> Optional[float]:
    """
    Calculate position quantity based on fixed % risk and reference SL distance.

    qty = (equity * risk_percent) / (entry_price * sl_percent)
    """
    if equity <= 0 or risk_percent <= 0 or entry_price <= 0 or sl_percent <= 0:
        return None
    qty = (equity * risk_percent) / (entry_price * sl_percent)
    return qty if qty > 0 else None

