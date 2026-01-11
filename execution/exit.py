"""
Emergency exit helper (not used in normal flow).
"""

from __future__ import annotations

from exchange.order_manager import OrderManager


def emergency_close_position(order_manager: OrderManager, symbol: str, side: str, quantity: float) -> None:
    """
    Close position via market order. Not used in normal operation.
    TODO: Wire into future kill-switch logic.
    """
    close_side = "SELL" if side == "LONG" else "BUY"
    order_manager.place_market_order(symbol, close_side, quantity)

