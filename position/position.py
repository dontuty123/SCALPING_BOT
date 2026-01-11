"""
Position model for a single open futures position.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    side: str  # "LONG" or "SHORT"
    quantity: float
    entry_price: float
    entry_time: int  # epoch ms

