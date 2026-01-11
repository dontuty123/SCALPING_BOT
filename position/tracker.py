"""
Track and reconcile a single open position.
"""

from __future__ import annotations

from typing import Optional

from exchange.binance_client import BinanceAPIError, BinanceClient
from infra.logger import get_logger
from position.position import Position


class PositionTracker:
    """In-memory position tracker with exchange reconciliation."""

    def __init__(self, client: BinanceClient, symbol: str) -> None:
        self.client = client
        self.symbol = symbol
        self.position: Optional[Position] = None
        self.logger = get_logger("PositionTracker")

    def has_open_position(self) -> bool:
        return self.position is not None and self.position.quantity > 0

    def set_position(self, position: Position) -> None:
        self.position = position
        self.logger.info(
            "Position set: %s %s qty=%.6f entry=%.4f",
            position.side,
            position.symbol,
            position.quantity,
            position.entry_price,
        )

    def clear_position(self) -> None:
        if self.position:
            self.logger.info("Clearing local position for %s", self.position.symbol)
        self.position = None

    def sync_from_exchange(self) -> None:
        """Sync local position with Binance open positions for the symbol."""
        try:
            account_info = self.client.get_account_info()
        except BinanceAPIError as exc:
            self.logger.error("Failed to fetch account info for sync: %s", exc)
            return

        positions = account_info.get("positions", [])
        remote = None
        for pos in positions:
            if pos.get("symbol") != self.symbol:
                continue
            amt = float(pos.get("positionAmt", 0))
            if amt == 0:
                continue
            side = "LONG" if amt > 0 else "SHORT"
            entry_price = float(pos.get("entryPrice", 0))
            update_time = int(pos.get("updateTime", 0))
            remote = Position(
                symbol=self.symbol,
                side=side,
                quantity=abs(amt),
                entry_price=entry_price,
                entry_time=update_time,
            )
            break

        if remote and not self.position:
            self.logger.info("Adopting existing exchange position: %s qty=%.6f", remote.side, remote.quantity)
            self.position = remote
        elif remote and self.position:
            if (
                self.position.side != remote.side
                or abs(self.position.quantity - remote.quantity) > 1e-8
                or abs(self.position.entry_price - remote.entry_price) > 1e-8
            ):
                self.logger.warning("Local position mismatch; updating from exchange")
                self.position = remote
        elif not remote and self.position:
            # Do not clear local state immediately to avoid wiping a valid exchange position due to transient API issues.
            self.logger.warning("Exchange reports no position for %s; keeping local state for now", self.symbol)

    @property
    def symbol_name(self) -> str:
        return self.symbol

