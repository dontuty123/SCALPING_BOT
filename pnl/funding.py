"""
Funding fee aggregation via income history.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from exchange.binance_client import BinanceClient
from infra.logger import get_logger


class FundingCalculator:
    """Compute funding PnL from Binance income history."""

    def __init__(self, client: BinanceClient) -> None:
        self.client = client
        self.logger = get_logger("FundingCalculator")

    def fetch_funding(self, symbol: str, start_time_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        income = self.client.get_income_history(symbol, "FUNDING_FEE", start_time_ms)
        return income if isinstance(income, list) else []

    def funding_pnl_since(self, symbol: str, start_time_ms: Optional[int]) -> float:
        entries = self.fetch_funding(symbol, start_time_ms)
        total = 0.0
        for item in entries:
            total += float(item.get("income", 0.0))
        self.logger.info("Funding PnL since %s for %s: %.6f", start_time_ms, symbol, total)
        return total

