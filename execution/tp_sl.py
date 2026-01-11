"""
Server-side take-profit / stop-loss placement and upkeep.
"""

from __future__ import annotations

from typing import Optional, Tuple

from config import risk as risk_config
from exchange.binance_client import BinanceAPIError
from exchange.order_manager import OrderManager
from infra.logger import get_logger
from position.position import Position
from position.tracker import PositionTracker


class TpSlManager:
    """
    Manages TP/SL orders for a single position.

    Keeps order IDs in-memory and reconciles against exchange position state.
    """

    def __init__(self, order_manager: OrderManager, position_tracker: PositionTracker) -> None:
        self.order_manager = order_manager
        self.position_tracker = position_tracker
        self.tp_order_id: Optional[int] = None
        self.sl_order_id: Optional[int] = None
        # Use an explicit protection flag to avoid recreate loops.
        self.is_protected: bool = False
        self.logger = get_logger("TpSlManager")

    def sync(self) -> None:
        """
        Ensure current position is protected; cleanup if no position on exchange.
        """
        position = self._fetch_remote_position()

        if position is None:
            # No position exists on exchange; cancel any leftover protective orders and clear local.
            self._cancel_outstanding(reason="Position closed on exchange")
            self.position_tracker.clear_position()
            self.is_protected = False
            return

        # Place TP/SL only once per position; rely on explicit flag instead of updateTime.
        if not self.is_protected:
            self._cancel_outstanding(reason="Placing initial protection")
            self._place_protection(position)
            self.is_protected = True
            return

        # Already protected; no action needed.

    def _place_protection(self, position) -> None:
        tp_price, sl_price = self._compute_prices(position.entry_price, position.side)
        side_to_close = "SELL" if position.side == "LONG" else "BUY"
        try:
            tp_order = self.order_manager.place_take_profit(
                position.symbol, side_to_close, position.quantity, tp_price
            )
            tp_id = tp_order.get("orderId")
            if not tp_id:
                raise ValueError("TP orderId missing")
            self.tp_order_id = int(tp_id)

            sl_order = self.order_manager.place_stop_loss(
                position.symbol, side_to_close, position.quantity, sl_price
            )
            sl_id = sl_order.get("orderId")
            if not sl_id:
                raise ValueError("SL orderId missing")
            self.sl_order_id = int(sl_id)

            self.logger.info("Placed TP at %.4f, SL at %.4f", tp_price, sl_price)
        except (ValueError, BinanceAPIError) as exc:
            self.logger.error("Failed to place TP/SL: %s", exc)
            self._cancel_outstanding(reason="TP/SL placement failed")
            self.is_protected = False

    def _cancel_outstanding(self, reason: str) -> None:
        if self.tp_order_id:
            try:
                self.order_manager.cancel_order(self.position_tracker.symbol, self.tp_order_id)
                self.logger.info("Cancelled TP order %s (%s)", self.tp_order_id, reason)
            except BinanceAPIError as exc:
                self.logger.error("Failed to cancel TP %s: %s", self.tp_order_id, exc)
        if self.sl_order_id:
            try:
                self.order_manager.cancel_order(self.position_tracker.symbol, self.sl_order_id)
                self.logger.info("Cancelled SL order %s (%s)", self.sl_order_id, reason)
            except BinanceAPIError as exc:
                self.logger.error("Failed to cancel SL %s: %s", self.sl_order_id, exc)
        self.tp_order_id = None
        self.sl_order_id = None
        self.is_protected = False

    def _compute_prices(self, entry_price: float, side: str) -> Tuple[float, float]:
        tp_percent = risk_config.TP_PERCENT
        sl_percent = risk_config.SL_PERCENT
        if side == "LONG":
            tp_price = entry_price * (1 + tp_percent)
            sl_price = entry_price * (1 - sl_percent)
        else:
            tp_price = entry_price * (1 - tp_percent)
            sl_price = entry_price * (1 + sl_percent)
        return tp_price, sl_price

    def _fetch_remote_position(self):
        """
        Fetch position from exchange to avoid relying solely on local tracker state.
        """
        try:
            account_info = self.order_manager.client.get_account_info()
        except BinanceAPIError as exc:
            self.logger.error("Failed to fetch account info for TP/SL sync: %s", exc)
            return self.position_tracker.position

        remote = None
        for pos in account_info.get("positions", []):
            if pos.get("symbol") != self.position_tracker.symbol:
                continue
            amt = float(pos.get("positionAmt", 0))
            if amt == 0:
                continue
            side = "LONG" if amt > 0 else "SHORT"
            entry_price = float(pos.get("entryPrice", 0))
            update_time = int(pos.get("updateTime", 0))
            remote = Position(
                symbol=self.position_tracker.symbol,
                side=side,
                quantity=abs(amt),
                entry_price=entry_price,
                entry_time=update_time,
            )
            break

        if remote:
            # Keep tracker aligned with exchange.
            self.position_tracker.set_position(remote)
        else:
            # No remote position found, treat as no position for protection purposes.
            self.is_protected = False
        return remote

