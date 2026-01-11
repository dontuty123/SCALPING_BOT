"""
Risk configuration values are static and MUST NOT be overridden by environment.
This ensures deterministic behavior for a production-grade bot.
"""

RISK_PERCENT = 0.001  # 0.1%
SL_PERCENT = 0.01     # 1% reference distance for SL sizing and SL order
TP_PERCENT = 0.01     # 1% take profit target
# Optional limits (can be set in config or extended later)
MAX_DAILY_LOSS = None
MAX_TRADES_PER_DAY = None
MAX_TRADES_PER_HOUR = None

