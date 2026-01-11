"""
Binance Futures REST client (testnet-ready).
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from config import settings
from infra.logger import get_logger
from infra.retry import retry

requests = importlib.import_module("requests")


MAINNET_BASE = "https://fapi.binance.com"
TESTNET_BASE = "https://testnet.binancefuture.com"


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error response."""


class BinanceClient:
    """Thin REST wrapper for Binance USDT-M Futures with testnet support."""
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        use_testnet: Optional[bool] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.use_testnet = (
            use_testnet
            if use_testnet is not None
            else getattr(
                settings,
                "TESTNET",
                str(os.getenv("BINANCE_TESTNET", "true")).lower() == "true",
            )
        )
        self.logger = get_logger("BinanceClient")
        # Use testnet-specific keys when testnet flag is enabled; otherwise mainnet keys.
        if self.use_testnet:
            self.api_key = api_key or os.getenv("BINANCE_TEST_API_KEY") or os.getenv("BINANCE_API_KEY")
            self.api_secret = api_secret or os.getenv("BINANCE_TEST_API_SECRET") or os.getenv("BINANCE_API_SECRET")
        else:
            self.api_key = api_key or os.getenv("BINANCE_API_KEY")
            self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET")
        self.base_url = TESTNET_BASE if self.use_testnet else MAINNET_BASE
        self.timeout = timeout if timeout is not None else getattr(settings, "REQUEST_TIMEOUT", 10.0)
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-MBX-APIKEY": self.api_key})
        self.logger.info("Binance client initialized (testnet=%s)", self.use_testnet)

    def ping(self) -> Dict[str, Any]:
        return self._public_get("/fapi/v1/ping")

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> Any:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        return self._public_get("/fapi/v1/klines", params=params)

    def get_account_info(self) -> Dict[str, Any]:
        return self._signed_get("/fapi/v2/account")

    def get_balance(self) -> Any:
        return self._signed_get("/fapi/v2/balance")

    def get_available_balance(self, asset: str = "USDT") -> float:
        """
        Return available balance for the asset from account info.
        """
        info = self.get_account_info()
        for bal in info.get("assets", []):
            if bal.get("asset") == asset:
                return float(bal.get("availableBalance", 0.0))
        # Fallback: try walletBalance on balances list if assets not present.
        for bal in info.get("balances", []):
            if bal.get("asset") == asset:
                return float(bal.get("walletBalance", 0.0))
        return 0.0

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """
        Public wrapper to place a market order.
        """
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity}
        return self._signed_post("/fapi/v1/order", params=params)

    def place_take_profit(
        self, symbol: str, side: str, quantity: float, stop_price: float, use_market: bool = True
    ) -> Dict[str, Any]:
        """
        Place reduce-only take profit order.
        """
        order_type = "TAKE_PROFIT_MARKET" if use_market else "TAKE_PROFIT"
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "stopPrice": stop_price,
            "quantity": quantity,
            "reduceOnly": "true",
            "closePosition": "true",
        }
        return self._signed_post("/fapi/v1/order", params=params)

    def place_stop_loss(self, symbol: str, side: str, quantity: float, stop_price: float) -> Dict[str, Any]:
        """
        Place reduce-only stop loss order.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "STOP_MARKET",
            "stopPrice": stop_price,
            "quantity": quantity,
            "reduceOnly": "true",
            "closePosition": "true",
        }
        return self._signed_post("/fapi/v1/order", params=params)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order by ID.
        """
        params = {"symbol": symbol, "orderId": order_id}
        return self._signed_delete("/fapi/v1/order", params=params)

    def get_user_trades(self, symbol: str, order_id: int) -> Any:
        """
        Fetch user trades (fills) for a given order.
        """
        params = {"symbol": symbol, "orderId": order_id}
        return self._signed_get("/fapi/v1/userTrades", params=params)

    def get_user_trades_history(
        self,
        symbol: str,
        start_time_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """
        Public helper to fetch user trades (fills) for PnL calculations.

        Uses signed REST; minimal pagination via fromId when needed.
        """
        trades: list[dict] = []
        params: Dict[str, Any] = {"symbol": symbol, "limit": limit}
        if start_time_ms:
            params["startTime"] = start_time_ms

        while True:
            batch = self._signed_get("/fapi/v1/userTrades", params=params)
            if not isinstance(batch, list) or not batch:
                break
            trades.extend(batch)
            if len(batch) < limit:
                break
            last_id = batch[-1].get("id")
            if last_id is None:
                break
            params["fromId"] = int(last_id) + 1

        return trades

    def get_income_history(
        self,
        symbol: str,
        income_type: str,
        start_time_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """
        Public helper to fetch income history (e.g., funding fees) for PnL.
        """
        params: Dict[str, Any] = {"incomeType": income_type, "limit": limit}
        if symbol:
            params["symbol"] = symbol
        if start_time_ms:
            params["startTime"] = start_time_ms

        entries: list[dict] = []
        while True:
            batch = self._signed_get("/fapi/v1/income", params=params)
            if not isinstance(batch, list) or not batch:
                break
            entries.extend(batch)
            if len(batch) < limit:
                break
            last_time = batch[-1].get("time")
            if last_time is None:
                break
            params["startTime"] = int(last_time) + 1

        return entries

    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch exchange info for a symbol (tickSize, stepSize, etc.).
        """
        params = {"symbol": symbol}
        info = self._public_get("/fapi/v1/exchangeInfo", params=params)
        if not isinstance(info, dict):
            raise BinanceAPIError("Invalid exchangeInfo response")
        symbols = info.get("symbols", [])
        if not symbols:
            raise BinanceAPIError("Symbol info not found")
        return symbols[0]

    @retry(max_retries=3, backoff_factor=0.5, retry_on=(requests.RequestException,))
    def _public_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        return self._handle_response(response)

    @retry(max_retries=3, backoff_factor=0.5, retry_on=(requests.RequestException,))
    def _signed_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self._ensure_credentials()
        signed_params = self._sign_params(params or {})
        url = f"{self.base_url}{path}"
        response = self.session.get(url, params=signed_params, timeout=self.timeout)
        return self._handle_response(response)

    @retry(max_retries=3, backoff_factor=0.5, retry_on=(requests.RequestException,))
    def _signed_post(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self._ensure_credentials()
        signed_params = self._sign_params(params or {})
        url = f"{self.base_url}{path}"
        response = self.session.post(url, params=signed_params, timeout=self.timeout)
        return self._handle_response(response)

    @retry(max_retries=3, backoff_factor=0.5, retry_on=(requests.RequestException,))
    def _signed_delete(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self._ensure_credentials()
        signed_params = self._sign_params(params or {})
        url = f"{self.base_url}{path}"
        response = self.session.delete(url, params=signed_params, timeout=self.timeout)
        return self._handle_response(response)

    def _handle_response(self, response: Any) -> Any:
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            self.logger.error("Binance API error (%s): %s", response.status_code, payload)
            raise BinanceAPIError(f"API error {response.status_code}: {payload}")
        try:
            return response.json()
        except ValueError as exc:
            self.logger.error("Failed to decode JSON response from Binance")
            raise BinanceAPIError("Invalid JSON response") from exc

    def _sign_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = dict(params)
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _ensure_credentials(self) -> None:
        if not self.api_key or not self.api_secret:
            self.logger.error("API credentials are not set")
            raise BinanceAPIError("Missing API credentials")

