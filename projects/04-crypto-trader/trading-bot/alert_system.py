"""
CryptoBot 알림 시스템

텔레그램 봇 및 콘솔 알림을 통해 중요 이벤트를 실시간 통보합니다.
- 매매 체결 알림
- 손절/익절 알림
- 서킷브레이커 발동 알림
- 시장 이상 감지 알림
"""
import os
import logging
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class AlertSystem:
    """알림 시스템"""

    def __init__(self):
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.alert_history = []

    def _send_telegram(self, message: str) -> bool:
        """텔레그램 메시지 전송"""
        if not self.telegram_token or not self.telegram_chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        try:
            resp = requests.post(url, json={
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML",
            }, timeout=10)
            return resp.ok
        except Exception as e:
            logger.error(f"텔레그램 전송 실패: {e}")
            return False

    def _log_alert(self, level: str, title: str, message: str):
        """알림 로그 기록"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "title": title,
            "message": message,
        }
        self.alert_history.append(alert)
        # 최근 100건만 유지
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]

    def send(self, level: str, title: str, message: str):
        """
        알림 전송

        Args:
            level: "info", "warning", "critical"
            title: 알림 제목
            message: 상세 내용
        """
        # 콘솔 출력
        emoji = {"info": "[INFO]", "warning": "[WARN]", "critical": "[CRIT]"}.get(level, "[INFO]")
        formatted = f"{emoji} {title}: {message}"

        if level == "critical":
            logger.critical(formatted)
        elif level == "warning":
            logger.warning(formatted)
        else:
            logger.info(formatted)

        # 텔레그램 전송
        tg_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(level, "ℹ️")
        tg_message = f"{tg_emoji} <b>{title}</b>\n{message}\n<i>{datetime.now().strftime('%H:%M:%S')}</i>"
        self._send_telegram(tg_message)

        self._log_alert(level, title, message)

    def alert_trade(self, action: str, symbol: str, amount: float, price: float,
                    confidence: float = 0.0):
        """매매 체결 알림"""
        self.send(
            "info",
            f"매매 체결: {action}",
            f"{symbol} | {amount:,.0f}원 @ {price:,.0f}원 | 신뢰도: {confidence:.0%}",
        )

    def alert_stop_loss(self, symbol: str, pnl_pct: float, price: float):
        """손절 알림"""
        self.send(
            "warning",
            f"손절 실행",
            f"{symbol} | 수익률: {pnl_pct:+.2f}% | 가격: {price:,.0f}원",
        )

    def alert_take_profit(self, symbol: str, pnl_pct: float, price: float):
        """익절 알림"""
        self.send(
            "info",
            f"익절 실행",
            f"{symbol} | 수익률: {pnl_pct:+.2f}% | 가격: {price:,.0f}원",
        )

    def alert_circuit_breaker(self, reason: str):
        """서킷브레이커 발동 알림"""
        self.send(
            "critical",
            "서킷브레이커 발동",
            f"사유: {reason}\n매매가 자동 중지되었습니다.",
        )

    def alert_error(self, error: str):
        """에러 알림"""
        self.send("critical", "시스템 오류", error)

    def get_recent_alerts(self, limit: int = 20) -> list:
        """최근 알림 목록"""
        return self.alert_history[-limit:]
