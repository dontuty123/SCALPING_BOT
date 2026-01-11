"""
Entry execution logic driven by strategy signals.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import risk as risk_config
from exchange.binance_client import BinanceClient
from exchange.order_manager import OrderManager
from infra.logger import get_logger
from position.position import Position
from position.tracker import PositionTracker
from risk.position_sizer import compute_position_size
from strategy.base import Strategy


DEFAULT_RISK_PERCENT = risk_config.RISK_PERCENT
DEFAULT_SL_PERCENT = risk_config.SL_PERCENT


class EntryExecutor:
    """Executes entry orders based on strategy signals."""

    def __init__(
        self,
        strategy: Strategy,
        order_manager: OrderManager,
        position_tracker: PositionTracker,
        symbol: str,
        client: BinanceClient,
    ) -> None:
        self.strategy = strategy
        self.order_manager = order_manager
        self.position_tracker = position_tracker
        self.symbol = symbol
        self.client = client
        self.logger = get_logger("EntryExecutor")
        self._in_cycle = False  # guard against duplicate processing within a cycle

    def process(self, market_data: Dict[str, Dict[str, Any]]) -> None:
        """Process a cycle: sync, evaluate signal, attempt entry."""
        if self._in_cycle:
            self.logger.info("Entry processing already running; skipping duplicate")
            return
        self._in_cycle = True
        try:
            self.position_tracker.sync_from_exchange()

            if self.position_tracker.has_open_position():
                self.logger.info("Open position detected; skipping entry")
                return

            signal = self.strategy.generate_signal(market_data)
            if signal is None:
                return

            self.logger.info("Signal detected: %s", signal)

            closes_1m = market_data.get("1m", {}).get("close", [])
            if not closes_1m:
                self.logger.info("No price data available for entry")
                return
            entry_price = closes_1m[-1]

            equity = self.client.get_available_balance()
            if equity <= 0:
                self.logger.info("Equity unavailable or zero; skipping entry")
                return

            qty = compute_position_size(
                equity=equity,
                risk_percent=DEFAULT_RISK_PERCENT,
                entry_price=entry_price,
                sl_percent=DEFAULT_SL_PERCENT,
            )
            if qty is None or qty <= 0:
                self.logger.info("Computed quantity invalid; skipping entry")
                return

            order_side = "BUY" if signal == "LONG" else "SELL"

            order = self.order_manager.place_market_order(self.symbol, order_side, qty)
            order_id = order.get("orderId")
            if not order_id:
                self.logger.error("Order response missing orderId; aborting entry")
                return

            trades = self.order_manager.fetch_fills(self.symbol, order_id)
            fill_info = self.order_manager.compute_avg_fill(trades)
            if not fill_info:
                self.logger.error("Order not filled; no fills received")
                return

            position = Position(
                symbol=self.symbol,
                side=signal,
                quantity=fill_info["qty"],
                entry_price=fill_info["price"],
                entry_time=order.get("updateTime", order.get("transactTime", 0)),
            )
            self.position_tracker.set_position(position)
            self.logger.info(
                "Entry confirmed: %s %s qty=%.6f avg_price=%.4f",
                signal,
                self.symbol,
                position.quantity,
                position.entry_price,
            )
        finally:
            self._in_cycle = False

