"""
Circuit Breaker - Emergency stop system.

Triggers:
- Daily loss >= 3%
- 4 consecutive losses -> 15 min cooldown
- >20 trades per hour
"""
import logging
import time
from collections import deque

from . import config

logger = logging.getLogger("scalper.circuit")


class CircuitBreaker:

    def __init__(self, initial_balance: float):
        self.initial_daily_balance = initial_balance
        self.current_balance = initial_balance
        self.consecutive_losses = 0
        self.cooldown_until = 0.0
        self.trade_timestamps: deque = deque()  # timestamps of recent trades
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.is_halted = False
        self.halt_reason = ""

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed."""
        now = time.time()

        # Manual halt
        if self.is_halted:
            return False, f"HALTED: {self.halt_reason}"

        # Cooldown check
        if now < self.cooldown_until:
            remaining = int(self.cooldown_until - now)
            return False, f"Cooldown: {remaining}s remaining (consecutive losses)"

        # Daily loss limit
        daily_loss_pct = -self.daily_pnl / self.initial_daily_balance if self.initial_daily_balance > 0 else 0
        if daily_loss_pct >= config.DAILY_LOSS_LIMIT:
            self.is_halted = True
            self.halt_reason = f"Daily loss limit {daily_loss_pct*100:.1f}% >= {config.DAILY_LOSS_LIMIT*100:.0f}%"
            logger.critical(f"CIRCUIT BREAKER: {self.halt_reason}")
            return False, self.halt_reason

        # Hourly trade limit
        one_hour_ago = now - 3600
        while self.trade_timestamps and self.trade_timestamps[0] < one_hour_ago:
            self.trade_timestamps.popleft()

        if len(self.trade_timestamps) >= config.MAX_TRADES_PER_HOUR:
            return False, f"Hourly trade limit reached ({config.MAX_TRADES_PER_HOUR})"

        return True, "OK"

    def record_trade(self, pnl_krw: float):
        """Record a completed trade."""
        now = time.time()
        self.trade_timestamps.append(now)
        self.daily_trades += 1
        self.daily_pnl += pnl_krw
        self.current_balance += pnl_krw

        if pnl_krw < 0:
            self.consecutive_losses += 1
            logger.warning(f"Loss #{self.consecutive_losses}: {pnl_krw:,.0f} KRW "
                           f"(daily PnL: {self.daily_pnl:,.0f})")

            if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
                self.cooldown_until = now + config.COOLDOWN_MINUTES * 60
                logger.warning(f"COOLDOWN: {config.MAX_CONSECUTIVE_LOSSES} consecutive losses. "
                               f"Pausing {config.COOLDOWN_MINUTES} minutes.")
                self.consecutive_losses = 0
        else:
            self.consecutive_losses = 0
            logger.info(f"Win: +{pnl_krw:,.0f} KRW (daily PnL: {self.daily_pnl:,.0f})")

    def reset_daily(self, current_balance: float):
        """Reset daily counters (call at start of new trading day)."""
        self.initial_daily_balance = current_balance
        self.current_balance = current_balance
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.is_halted = False
        self.halt_reason = ""
        self.consecutive_losses = 0
        logger.info(f"Daily reset. Starting balance: {current_balance:,.0f} KRW")

    def force_halt(self, reason: str):
        self.is_halted = True
        self.halt_reason = reason
        logger.critical(f"MANUAL HALT: {reason}")

    def resume(self):
        self.is_halted = False
        self.halt_reason = ""
        self.cooldown_until = 0.0
        logger.info("Trading resumed")

    def get_status(self) -> dict:
        can, reason = self.can_trade()
        return {
            "can_trade": can,
            "reason": reason,
            "daily_pnl": self.daily_pnl,
            "daily_pnl_pct": (self.daily_pnl / self.initial_daily_balance * 100)
                             if self.initial_daily_balance > 0 else 0,
            "daily_trades": self.daily_trades,
            "consecutive_losses": self.consecutive_losses,
            "is_halted": self.is_halted,
            "trades_this_hour": len(self.trade_timestamps),
        }
