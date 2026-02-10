"""
StockBot 알림 시스템 - Telegram Bot

매매 신호, 체결 결과, 일일 리포트를 Telegram으로 발송
"""
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class AlertSystem:
    """텔레그램 알림 시스템"""

    def __init__(self):
        self.enabled = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
        if not self.enabled:
            logger.info("텔레그램 알림 비활성 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정)")

    def send(self, message: str):
        if not self.enabled:
            logger.info(f"[알림] {message[:100]}")
            return

        try:
            import requests
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            }, timeout=10)
        except Exception as e:
            logger.error(f"텔레그램 발송 실패: {e}")

    def notify_trade(self, action: str, name: str, symbol: str,
                     qty: int, price: float, pnl_pct: float = 0,
                     score: float = 0, reasons: list = None):
        emoji = {"BUY": "🟢", "SELL": "🔴", "STOP_LOSS": "🛑", "TAKE_PROFIT": "🎯",
                 "TRAILING_STOP": "📉"}.get(action, "📊")
        pnl_str = f" ({pnl_pct:+.1f}%)" if pnl_pct else ""
        reason_str = "\n".join(f"  • {r}" for r in (reasons or [])[:3])

        msg = (
            f"{emoji} <b>{action}</b> {name} ({symbol})\n"
            f"수량: {qty:,}주 | 가격: {price:,.0f}원{pnl_str}\n"
            f"총액: {qty * price:,.0f}원"
        )
        if score:
            msg += f" | 점수: {score:.0f}"
        if reason_str:
            msg += f"\n{reason_str}"

        self.send(msg)

    def notify_daily_report(self, total_assets: float, cash: float,
                            pnl_day: float, pnl_day_pct: float,
                            total_pnl_pct: float, positions: int,
                            trades_today: int, win_rate: float):
        today = datetime.now().strftime("%Y-%m-%d")
        emoji = "📈" if pnl_day >= 0 else "📉"

        msg = (
            f"📊 <b>StockBot 일일 리포트</b> ({today})\n"
            f"━━━━━━━━━━━━━━━\n"
            f"총 자산: {total_assets:,.0f}원\n"
            f"현금: {cash:,.0f}원\n"
            f"{emoji} 금일 손익: {pnl_day:+,.0f}원 ({pnl_day_pct:+.2f}%)\n"
            f"누적 수익률: {total_pnl_pct:+.2f}%\n"
            f"보유 종목: {positions}개\n"
            f"금일 거래: {trades_today}건\n"
            f"승률: {win_rate:.1f}%"
        )
        self.send(msg)

    def notify_circuit_breaker(self, reason: str):
        self.send(f"🚨 <b>서킷브레이커 발동</b>\n사유: {reason}\n매매가 일시 중단되었습니다.")

    def notify_error(self, error: str):
        self.send(f"⚠️ <b>StockBot 오류</b>\n{error[:200]}")

    def notify_bot_start(self, mode: str):
        self.send(f"🤖 <b>StockBot 시작</b>\n모드: {mode}\n시간: {datetime.now().strftime('%H:%M:%S')}")

    def notify_bot_stop(self):
        self.send(f"⏹️ <b>StockBot 중지</b>\n시간: {datetime.now().strftime('%H:%M:%S')}")
