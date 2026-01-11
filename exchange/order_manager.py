"""
Order management for Binance Futures entries (market orders only).
"""

from __future__ import annotations

from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional

from exchange.binance_client import BinanceAPIError, BinanceClient
from infra.logger import get_logger


class OrderManager:
    """Place market orders and fetch fills using BinanceClient primitives."""

    def __init__(self, client: BinanceClient) -> None:
        self.client = client
        self.logger = get_logger("OrderManager")
        self._symbol_filters: Dict[str, Dict[str, Decimal]] = {}
        getcontext().prec = 28  # sufficient for futures precision

    def _load_filters(self, symbol: str) -> Dict[str, Decimal]:
        if symbol in self._symbol_filters:
            return self._symbol_filters[symbol]
        info = self.client.get_symbol_info(symbol)
        tick = Decimal("0.01")
        step = Decimal("0.001")
        for f in info.get("filters", []):
            if f.get("filterType") == "PRICE_FILTER":
                tick = Decimal(str(f.get("tickSize", tick)))
            if f.get("filterType") == "LOT_SIZE":
                step = Decimal(str(f.get("stepSize", step)))
        self._symbol_filters[symbol] = {"tickSize": tick, "stepSize": step}
        return self._symbol_filters[symbol]

    def _round_price(self, symbol: str, price: float) -> float:
        filt = self._load_filters(symbol)
        tick = filt["tickSize"]
        return float((Decimal(str(price)) // tick) * tick)

    def _round_qty(self, symbol: str, qty: float) -> float:
        filt = self._load_filters(symbol)
        step = filt["stepSize"]
        return float((Decimal(str(qty)) // step) * step)

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """
        Place a market order.

        Args:
            symbol: Trading pair (e.g., BTCUSDT).
            side: "BUY" or "SELL".
            quantity: Order quantity.
        """
        qty = self._round_qty(symbol, quantity)
        if qty <= 0:
            raise BinanceAPIError("Rounded quantity is zero; aborting order")
        order = self.client.place_market_order(symbol, side, qty)
        self.logger.info("Submitted market order %s %s qty=%.6f", side, symbol, quantity)
        return order

    def fetch_fills(self, symbol: str, order_id: int) -> List[Dict[str, Any]]:
        """
        Fetch user trades (fills) for the given order.
        """
        trades = self.client.get_user_trades(symbol, order_id)
        return trades if isinstance(trades, list) else []

    @staticmethod
    def compute_avg_fill(trades: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
        """
        Compute average fill price and total qty from trades.
        """
        if not trades:
            return None
        total_qty = 0.0
        total_quote = 0.0
        for t in trades:
            qty = float(t.get("qty", 0))
            price = float(t.get("price", 0))
            total_qty += qty
            total_quote += qty * price
        if total_qty == 0:
            return None
        return {"price": total_quote / total_qty, "qty": total_qty}

    def place_take_profit(
        self, symbol: str, side: str, quantity: float, stop_price: float, use_market: bool = True
    ) -> Dict[str, Any]:
        """
        Place a reduce-only take profit order (market preferred).
        """
        qty = self._round_qty(symbol, quantity)
        price = self._round_price(symbol, stop_price)
        if qty <= 0:
            raise BinanceAPIError("Rounded quantity is zero; aborting TP order")
        return self.client.place_take_profit(symbol, side, qty, price, use_market)

    def place_stop_loss(self, symbol: str, side: str, quantity: float, stop_price: float) -> Dict[str, Any]:
        """
        Place a reduce-only stop loss order (stop market).
        """
        qty = self._round_qty(symbol, quantity)
        price = self._round_price(symbol, stop_price)
        if qty <= 0:
            raise BinanceAPIError("Rounded quantity is zero; aborting SL order")
        return self.client.place_stop_loss(symbol, side, qty, price)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order by ID.
        """
        return self.client.cancel_order(symbol, order_id)

