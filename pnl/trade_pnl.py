"""
Trade PnL computation based on Binance userTrades (real fills).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from exchange.binance_client import BinanceClient
from infra.logger import get_logger


class TradePnlCalculator:
    """Compute realized PnL and fees from actual fills."""

    def __init__(self, client: BinanceClient) -> None:
        self.client = client
        self.logger = get_logger("TradePnlCalculator")

    def fetch_trades(self, symbol: str, start_time_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch user trades for a symbol since start_time_ms (if provided) using public client API.
        """
        trades = self.client.get_user_trades_history(symbol, start_time_ms)
        return trades if isinstance(trades, list) else []

    def compute_realized_pnl(self, trades: List[Dict[str, Any]]) -> float:
        """
        Sum realizedPnl from trades; commission is logged separately and not subtracted again
        because Binance Futures realizedPnl is already net of fees.
        """
        realized = 0.0
        fees = 0.0
        for t in trades:
            realized += float(t.get("realizedPnl", 0.0))
            fees += float(t.get("commission", 0.0))
        self.logger.info("Commission (reported) for trades: %.6f", fees)
        return realized

    def realized_pnl_since(self, symbol: str, start_time_ms: Optional[int]) -> float:
        trades = self.fetch_trades(symbol, start_time_ms)
        pnl = self.compute_realized_pnl(trades)
        self.logger.info("Realized PnL since %s for %s: %.6f", start_time_ms, symbol, pnl)
        return pnl

