"""
Thin account accessor built on BinanceClient.
"""

from __future__ import annotations

from typing import Any, Dict

from exchange.binance_client import BinanceClient


class AccountService:
    def __init__(self, client: BinanceClient) -> None:
        self.client = client

    def get_account_info(self) -> Dict[str, Any]:
        return self.client.get_account_info()

    def get_balance(self) -> Any:
        return self.client.get_balance()

