"""
Strategy base interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class Strategy(ABC):
    """Stateless strategy interface returning signals only."""

    @abstractmethod
    def generate_signal(self, market_data: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """
        Produce a signal based solely on provided market data.

        Args:
            market_data: Dict keyed by timeframe (e.g., "1m", "5m") containing OHLCV lists.
        Returns:
            "LONG", "SHORT", or None.
        """
        raise NotImplementedError

