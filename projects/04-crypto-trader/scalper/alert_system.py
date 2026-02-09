"""
Alert System - Console and optional Telegram notifications.
"""
import logging
import time
from datetime import datetime

import requests

from . import config

logger = logging.getLogger("scalper.alert")


class AlertSystem:

    def __init__(self):
        self.telegram_enabled = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
        if self.telegram_enabled:
            logger.info("Telegram alerts enabled")

    def trade_alert(self, market: str, side: str, price: float, amount: float,
                    krw_amount: float, reason: str):
        emoji = "BUY" if side == "buy" else "SELL"
        msg = (
            f"[{emoji}] {market}\n"
            f"  Price: {price:,.0f} KRW\n"
            f"  Amount: {amount:.8f}\n"
            f"  Value: {krw_amount:,.0f} KRW\n"
            f"  Reason: {reason}"
        )
        self._send(msg, level="info")

    def exit_alert(self, market: str, exit_type: str, entry_price: float,
                   exit_price: float, pnl_krw: float, pnl_pct: float):
        status = "WIN" if pnl_krw > 0 else "LOSS"
        msg = (
            f"[{status}] {market} - {exit_type}\n"
            f"  Entry: {entry_price:,.0f} -> Exit: {exit_price:,.0f}\n"
            f"  PnL: {pnl_krw:+,.0f} KRW ({pnl_pct:+.2f}%)"
        )
        level = "info" if pnl_krw >= 0 else "warning"
        self._send(msg, level=level)

    def circuit_breaker_alert(self, reason: str):
        msg = f"[CIRCUIT BREAKER] {reason}"
        self._send(msg, level="critical")

    def daily_summary(self, stats: dict):
        msg = (
            f"=== Daily Summary ===\n"
            f"  Trades: {stats.get('total_trades', 0)}\n"
            f"  Wins: {stats.get('wins', 0)} / Losses: {stats.get('losses', 0)}\n"
            f"  Win Rate: {stats.get('win_rate', 0):.1f}%\n"
            f"  PnL: {stats.get('daily_pnl', 0):+,.0f} KRW ({stats.get('daily_pnl_pct', 0):+.2f}%)\n"
            f"  Balance: {stats.get('balance', 0):,.0f} KRW"
        )
        self._send(msg, level="info")

    def _send(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}"

        # Console
        if level == "critical":
            logger.critical(full_msg)
        elif level == "warning":
            logger.warning(full_msg)
        else:
            logger.info(full_msg)

        # Telegram
        if self.telegram_enabled:
            self._send_telegram(full_msg)

    def _send_telegram(self, message: str):
        try:
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code != 200:
                logger.error(f"Telegram send failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Telegram error: {e}")
