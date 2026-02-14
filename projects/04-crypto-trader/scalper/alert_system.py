"""
Alert System - Telegram notifications with hourly/daily reports.
Console: plain text (Windows cp949 safe)
Telegram: emoji + formatted
"""
import logging
import re
import time
from datetime import datetime

import requests

from . import config

logger = logging.getLogger("scalper.alert")


def _strip_emoji(text: str) -> str:
    """Remove emoji for Windows console output."""
    return re.sub(
        r'[\U0001f300-\U0001f9ff\u2550-\u2566\u2500-\u257f\u2700-\u27bf'
        r'\u23e9-\u23f3\u2934\u2935\u25aa-\u25fe\u2b05-\u2b07\u2b1b\u2b50\u3030\u303d]',
        '', text
    ).replace('\u2550', '=').replace('\u2192', '->').replace('\u2705', '[OK]')


class AlertSystem:

    def __init__(self):
        self.telegram_enabled = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
        if self.telegram_enabled:
            logger.info("Telegram alerts enabled")

        # Report tracking
        self._last_hourly_report = time.time()
        self._hourly_trades: list[dict] = []

    def trade_alert(self, market: str, side: str, price: float, amount: float,
                    krw_amount: float, reason: str):
        coin = market.split("-")[1]
        console_msg = (
            f"[BUY] {coin} | Price: {price:,.0f} | "
            f"Amount: {amount:.8f} | Value: {krw_amount:,.0f} KRW | {reason}"
        )
        tg_msg = (
            f"\U0001F7E2 매수 신호 | {coin}\n"
            f"================\n"
            f"\U0001F4B0 가격: {price:,.0f} 원\n"
            f"\U0001F4CA 수량: {amount:.8f}\n"
            f"\U0001F4B5 금액: {krw_amount:,.0f} 원\n"
            f"\U0001F4DD 사유: {reason}"
        )
        self._send(console_msg, tg_msg, level="info")
        self._hourly_trades.append({
            "market": market, "side": "buy", "price": price,
            "krw": krw_amount, "time": datetime.now()
        })

    def exit_alert(self, market: str, exit_type: str, entry_price: float,
                   exit_price: float, pnl_krw: float, pnl_pct: float):
        coin = market.split("-")[1]
        status = "WIN" if pnl_krw > 0 else "LOSS"
        tg_status = "익절" if pnl_krw > 0 else "손절"
        tg_icon = "\U0001F389" if pnl_krw > 0 else "\U0001F534"

        exit_labels = {
            "stop_loss": "스탑로스", "take_profit": "익절",
            "trailing_stop": "트레일링", "signal_sell": "시그널 매도",
            "breakeven": "본절매",
        }
        exit_str = exit_labels.get(exit_type, exit_type)

        console_msg = (
            f"[{status}] {coin} | {entry_price:,.0f} -> {exit_price:,.0f} | "
            f"PnL: {pnl_krw:+,.0f} KRW ({pnl_pct:+.2f}%) | {exit_type}"
        )
        tg_msg = (
            f"{tg_icon} {tg_status} | {coin}\n"
            f"================\n"
            f"\U0001F4C8 진입: {entry_price:,.0f} -> 청산: {exit_price:,.0f}\n"
            f"\U0001F4B0 손익: {pnl_krw:+,.0f} 원 ({pnl_pct:+.2f}%)\n"
            f"\U0001F3AF 청산사유: {exit_str}"
        )
        level = "info" if pnl_krw >= 0 else "warning"
        self._send(console_msg, tg_msg, level=level)
        self._hourly_trades.append({
            "market": market, "side": "sell", "pnl_krw": pnl_krw,
            "pnl_pct": pnl_pct, "exit_type": exit_str, "time": datetime.now()
        })

    def circuit_breaker_alert(self, reason: str):
        console_msg = f"[CIRCUIT BREAKER] {reason}"
        tg_msg = f"\u26A0\uFE0F 서킷브레이커 발동!\n================\n{reason}"
        self._send(console_msg, tg_msg, level="critical")

    def hourly_report(self, stats: dict):
        now = datetime.now()
        hour_str = now.strftime("%H:%M")

        buys = [t for t in self._hourly_trades if t["side"] == "buy"]
        sells = [t for t in self._hourly_trades if t["side"] == "sell"]
        hourly_pnl = sum(t.get("pnl_krw", 0) for t in sells)

        total = stats.get("total_trades", 0)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        win_rate = stats.get("win_rate", 0)
        balance = stats.get("balance", 0)
        daily_pnl = stats.get("daily_pnl", 0)
        initial = config.PAPER_INITIAL_KRW
        total_pnl_pct = ((balance - initial) / initial) * 100 if initial > 0 else 0

        positions = stats.get("open_positions", {})
        pos_lines_tg = ""
        pos_lines_con = ""
        if positions:
            for m, p in positions.items():
                coin = m.split("-")[1]
                pos_lines_tg += f"  \U0001F4CC {coin}: {p['entry_price']:,.0f}won ({p['entry_time']})\n"
                pos_lines_con += f"  {coin}: {p['entry_price']:,.0f} ({p['entry_time']})\n"
        else:
            pos_lines_tg = "  none\n"
            pos_lines_con = "  none\n"

        paper_str = " (Paper)" if config.PAPER_TRADING else " (LIVE)"

        console_msg = (
            f"[HOURLY {hour_str}]{paper_str} Balance: {balance:,.0f} | "
            f"Daily PnL: {daily_pnl:+,.0f} ({total_pnl_pct:+.2f}%) | "
            f"1h: buy {len(buys)} sell {len(sells)} pnl {hourly_pnl:+,.0f} | "
            f"Total: {total} (W:{wins}/L:{losses}) WR:{win_rate:.1f}%"
        )
        tg_msg = (
            f"\U0001F4CA {hour_str} 정기 리포트{paper_str}\n"
            f"================\n"
            f"\n"
            f"\U0001F4B0 잔고: {balance:,.0f} 원\n"
            f"\U0001F4C8 총 수익: {daily_pnl:+,.0f} 원 ({total_pnl_pct:+.2f}%)\n"
            f"\n"
            f"\U0001F552 지난 1시간:\n"
            f"  매수: {len(buys)}회 | 매도: {len(sells)}회\n"
            f"  수익: {hourly_pnl:+,.0f} 원\n"
            f"\n"
            f"\U0001F4CA 누적 성적:\n"
            f"  총 거래: {total}회 (W:{wins} / L:{losses})\n"
            f"  승률: {win_rate:.1f}%\n"
            f"\n"
            f"\U0001F4CC 보유 중:\n"
            f"{pos_lines_tg}"
        )
        self._send(console_msg, tg_msg, level="info")

        self._hourly_trades.clear()
        self._last_hourly_report = time.time()

    def daily_summary(self, stats: dict):
        total = stats.get("total_trades", 0)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        win_rate = stats.get("win_rate", 0)
        balance = stats.get("balance", 0)
        daily_pnl = stats.get("daily_pnl", 0)
        initial = config.PAPER_INITIAL_KRW
        total_pnl_pct = ((balance - initial) / initial) * 100 if initial > 0 else 0
        paper_str = " (Paper)" if config.PAPER_TRADING else " (LIVE)"

        console_msg = (
            f"[DAILY SUMMARY]{paper_str} Balance: {balance:,.0f} | "
            f"PnL: {daily_pnl:+,.0f} ({total_pnl_pct:+.2f}%) | "
            f"Trades: {total} (W:{wins}/L:{losses}) WR:{win_rate:.1f}%"
        )
        tg_msg = (
            f"\U0001F319 일일 리포트{paper_str}\n"
            f"================\n"
            f"\n"
            f"\U0001F4B0 최종 잔고: {balance:,.0f} 원\n"
            f"\U0001F4C8 일일 수익: {daily_pnl:+,.0f} 원 ({total_pnl_pct:+.2f}%)\n"
            f"\n"
            f"\U0001F4CA 거래 성적:\n"
            f"  총 거래: {total}회\n"
            f"  승리: {wins}회 | 패배: {losses}회\n"
            f"  승률: {win_rate:.1f}%\n"
            f"\n"
            f"\u2728 내일도 좋은 성과 있길!"
        )
        self._send(console_msg, tg_msg, level="info")

    def startup_alert(self, balance: float, markets: list, paper: bool):
        mode = "Paper" if paper else "LIVE"
        coins = ", ".join(m.split("-")[1] for m in markets)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        console_msg = (
            f"[STARTUP] Mode: {mode} | Balance: {balance:,.0f} KRW | "
            f"Markets: {coins} | Time: {now_str}"
        )
        tg_msg = (
            f"\U0001F680 CryptoBot 시작!\n"
            f"================\n"
            f"\U0001F3AE 모드: {mode}\n"
            f"\U0001F4B0 잔고: {balance:,.0f} 원\n"
            f"\U0001F4B1 대상: {coins}\n"
            f"\u23F0 시작: {now_str}"
        )
        self._send(console_msg, tg_msg, level="info")

    def should_send_hourly_report(self) -> bool:
        return (time.time() - self._last_hourly_report) >= 3600

    def _send(self, console_msg: str, tg_msg: str = "", level: str = "info"):
        # Console (ASCII safe)
        if level == "critical":
            logger.critical(console_msg)
        elif level == "warning":
            logger.warning(console_msg)
        else:
            logger.info(console_msg)

        # Telegram (with emoji)
        if self.telegram_enabled:
            self._send_telegram(tg_msg or console_msg)

    def _send_telegram(self, message: str):
        try:
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message}
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code != 200:
                logger.error(f"Telegram send failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Telegram error: {e}")
