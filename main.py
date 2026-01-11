"""
Phase 3 entry point: fetch data, run strategy, place entries (testnet).
"""

from __future__ import annotations

import time
from typing import Dict

from dotenv import load_dotenv

# Load environment variables before other imports that may read them.
load_dotenv()

from config import settings
from config.symbols import DEFAULT_SYMBOL
from exchange.binance_client import BinanceAPIError, BinanceClient
from exchange.market_data import MarketDataService
from exchange.order_manager import OrderManager
from execution.entry import EntryExecutor
from execution.tp_sl import TpSlManager
from infra.checkpoint import load_checkpoint, save_checkpoint
from infra.logger import get_logger
from infra.notifier import notify_error, notify_info, notify_warning
from pnl.funding import FundingCalculator
from pnl.trade_pnl import TradePnlCalculator
from position.tracker import PositionTracker
from risk.kill_switch import KillSwitch
from risk.trade_limits import TradeLimits
from strategy.ema_pullback import EmaPullbackStrategy


def main() -> None:
    logger = get_logger("Main")
    symbol = DEFAULT_SYMBOL

    client = BinanceClient()
    market_data = MarketDataService(client)
    order_manager = OrderManager(client)
    position_tracker = PositionTracker(client, symbol)
    strategy = EmaPullbackStrategy()
    executor = EntryExecutor(strategy, order_manager, position_tracker, symbol, client)
    tp_sl_manager = TpSlManager(order_manager, position_tracker)
    trade_pnl = TradePnlCalculator(client)
    funding = FundingCalculator(client)
    trade_limits = TradeLimits()
    kill_switch = KillSwitch()

    checkpoint = load_checkpoint()
    last_position_open = False
    last_pnl_check_ms: int = int(checkpoint.get("last_pnl_check_ms", time.time() * 1000))

    logger.info("Starting bot for symbol %s (testnet=%s)", symbol, client.use_testnet)
    notify_info(f"Bot startup for {symbol} (testnet={client.use_testnet})")

    try:
        while True:
            # Sync position from exchange before processing to ensure cleanup when TP/SL fills.
            try:
                position_tracker.sync_from_exchange()
            except BinanceAPIError as exc:
                notify_error(f"Position sync failed: {exc}")
                _sleep_until_next_minute()
                continue
            now_ms = int(time.time() * 1000)
            trade_limits.reset_if_needed(now_ms)
            if not trade_limits.limits_exceeded() and not kill_switch.is_trading_allowed:
                # New day reset scenario.
                kill_switch.reset_daily()

            limit = getattr(settings, "KLINES_LIMIT", 200)
            candles_1m = market_data.fetch_closed_klines(symbol, "1m", limit=limit)
            candles_5m = market_data.fetch_closed_klines(symbol, "5m", limit=limit)

            if candles_1m is None or candles_5m is None:
                logger.info("Skipping cycle; candles not ready")
                _sleep_until_next_minute()
                continue

            data: Dict[str, Dict[str, object]] = {"1m": candles_1m, "5m": candles_5m}
            if kill_switch.is_trading_allowed:
                executor.process(data)
            else:
                logger.info("Kill switch active; skipping new entries")

            tp_sl_manager.sync()

            # Detect position close to finalize PnL.
            currently_open = position_tracker.has_open_position()
            if last_position_open and not currently_open:
                realized = trade_pnl.realized_pnl_since(symbol, last_pnl_check_ms)
                funding_pnl = funding.funding_pnl_since(symbol, last_pnl_check_ms)
                net_pnl = realized + funding_pnl
                trade_limits.record_trade(net_pnl, now_ms)
                if trade_limits.limits_exceeded():
                    kill_switch.evaluate(trade_limits)
                    notify_warning("KILL SWITCH ACTIVATED: limits exceeded")
                logger.info(
                    "Trade closed: realized=%.6f funding=%.6f net=%.6f; daily_loss=%.6f trades_day=%s trades_hour=%s",
                    realized,
                    funding_pnl,
                    net_pnl,
                    trade_limits.daily_loss,
                    trade_limits.daily_trades,
                    trade_limits.hourly_trades,
                )
                last_pnl_check_ms = now_ms
                save_checkpoint({"last_pnl_check_ms": last_pnl_check_ms})

            last_position_open = currently_open
            _sleep_until_next_minute()
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
        notify_info("Bot shutdown requested by user")


def _sleep_until_next_minute() -> None:
    now = time.time()
    offset = getattr(settings, "SCHEDULER_WAKE_OFFSET_SEC", 1.0)
    next_minute = int(now // 60 + 1) * 60 + offset  # slight buffer after close
    time.sleep(max(0.5, next_minute - now))


if __name__ == "__main__":
    main()

