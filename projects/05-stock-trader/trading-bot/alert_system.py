"""
StockBot 멀티채널 알림 시스템 v3.7

매매 신호, 체결 결과, 일일 리포트를 Telegram/Discord/Email로 발송.
AlertPriority에 따라 채널 자동 선택:
  CRITICAL → 전체 채널
  HIGH → Telegram + Discord
  NORMAL → Telegram
  LOW → Email + Telegram
"""
import os
import re
import logging
import smtplib
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class AlertPriority(Enum):
    """알림 우선순위"""
    CRITICAL = "critical"   # 전체 채널
    HIGH = "high"           # Telegram + Discord
    NORMAL = "normal"       # Telegram
    LOW = "low"             # Email + Telegram


class AlertChannel(ABC):
    """알림 채널 추상 클래스"""

    @abstractmethod
    def send(self, message: str, priority: AlertPriority = AlertPriority.NORMAL) -> bool:
        """메시지 발송. 성공 시 True 반환."""
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """채널 활성 여부"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class TelegramChannel(AlertChannel):
    """Telegram 알림 채널"""

    def __init__(self):
        self._token = TELEGRAM_TOKEN
        self._chat_id = TELEGRAM_CHAT_ID

    @property
    def name(self) -> str:
        return "Telegram"

    def is_enabled(self) -> bool:
        return bool(self._token and self._chat_id)

    def send(self, message: str, priority: AlertPriority = AlertPriority.NORMAL) -> bool:
        if not self.is_enabled():
            return False
        try:
            import requests
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            resp = requests.post(url, json={
                "chat_id": self._chat_id,
                "text": message,
                "parse_mode": "HTML",
            }, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram 발송 실패: {e}")
            return False


class DiscordChannel(AlertChannel):
    """Discord Webhook 알림 채널"""

    def __init__(self):
        from config import DISCORD_WEBHOOK_URL
        self._webhook_url = DISCORD_WEBHOOK_URL

    @property
    def name(self) -> str:
        return "Discord"

    def is_enabled(self) -> bool:
        return bool(self._webhook_url)

    def _html_to_markdown(self, html: str) -> str:
        """HTML 태그를 Discord Markdown으로 변환"""
        text = html
        text = re.sub(r'<b>(.*?)</b>', r'**\1**', text)
        text = re.sub(r'<i>(.*?)</i>', r'*\1*', text)
        text = re.sub(r'<code>(.*?)</code>', r'`\1`', text)
        text = re.sub(r'<[^>]+>', '', text)  # 나머지 태그 제거
        return text

    def send(self, message: str, priority: AlertPriority = AlertPriority.NORMAL) -> bool:
        if not self.is_enabled():
            return False
        try:
            import requests
            md_message = self._html_to_markdown(message)
            # Discord 2000자 제한
            if len(md_message) > 2000:
                md_message = md_message[:1997] + "..."
            resp = requests.post(self._webhook_url, json={
                "content": md_message,
            }, timeout=10)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Discord 발송 실패: {e}")
            return False


class EmailChannel(AlertChannel):
    """Email (SMTP) 알림 채널"""

    def __init__(self):
        from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO
        self._host = SMTP_HOST
        self._port = SMTP_PORT
        self._user = SMTP_USER
        self._password = SMTP_PASSWORD
        self._to = ALERT_EMAIL_TO

    @property
    def name(self) -> str:
        return "Email"

    def is_enabled(self) -> bool:
        return bool(self._host and self._user and self._password and self._to)

    def _html_to_plain(self, html: str) -> str:
        """HTML 태그 제거하여 텍스트 변환"""
        text = re.sub(r'<[^>]+>', '', html)
        return text

    def send(self, message: str, priority: AlertPriority = AlertPriority.NORMAL) -> bool:
        if not self.is_enabled():
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[StockBot] {priority.value.upper()} Alert"
            msg["From"] = self._user
            msg["To"] = self._to

            # HTML 버전
            html_body = f"<html><body><pre>{message}</pre></body></html>"
            msg.attach(MIMEText(self._html_to_plain(message), "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(self._host, self._port, timeout=15) as server:
                server.starttls()
                server.login(self._user, self._password)
                server.sendmail(self._user, self._to, msg.as_string())
            return True
        except Exception as e:
            logger.error(f"Email 발송 실패: {e}")
            return False


# === 우선순위별 채널 매핑 ===
PRIORITY_CHANNELS = {
    AlertPriority.CRITICAL: ["Telegram", "Discord", "Email"],
    AlertPriority.HIGH: ["Telegram", "Discord"],
    AlertPriority.NORMAL: ["Telegram"],
    AlertPriority.LOW: ["Email", "Telegram"],
}


class AlertSystem:
    """멀티채널 알림 시스템 (v3.7)

    기존 메서드 시그니처 100% 호환.
    env 미설정 채널은 자동 비활성.
    """

    def __init__(self):
        self._channels: List[AlertChannel] = []

        # 채널 초기화 (env 미설정 시 자동 비활성)
        telegram = TelegramChannel()
        if telegram.is_enabled():
            self._channels.append(telegram)
            logger.info("Telegram 알림 활성")
        else:
            logger.info("Telegram 알림 비활성 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정)")

        try:
            discord = DiscordChannel()
            if discord.is_enabled():
                self._channels.append(discord)
                logger.info("Discord 알림 활성")
        except Exception:
            pass

        try:
            email = EmailChannel()
            if email.is_enabled():
                self._channels.append(email)
                logger.info("Email 알림 활성")
        except Exception:
            pass

        self.enabled = len(self._channels) > 0
        if not self.enabled:
            logger.info("활성 알림 채널 없음 (로그 전용 모드)")

    def _dispatch(self, message: str, priority: AlertPriority = AlertPriority.NORMAL):
        """우선순위에 따라 적절한 채널로 메시지 발송"""
        if not self.enabled:
            logger.info(f"[알림] {message[:100]}")
            return

        target_names = PRIORITY_CHANNELS.get(priority, ["Telegram"])
        sent = False
        for ch in self._channels:
            if ch.name in target_names:
                try:
                    ch.send(message, priority)
                    sent = True
                except Exception as e:
                    logger.error(f"{ch.name} 발송 실패: {e}")

        if not sent:
            # 대상 채널이 모두 비활성이면 활성 채널 중 첫 번째로 폴백
            if self._channels:
                self._channels[0].send(message, priority)

    def send(self, message: str):
        """기존 호환: 단순 메시지 발송 (NORMAL 우선순위)"""
        self._dispatch(message, AlertPriority.NORMAL)

    def notify_trade(self, action: str, name: str, symbol: str,
                     qty: int, price: float, pnl_pct: float = 0,
                     score: float = 0, reasons: list = None):
        emoji = {"BUY": "\U0001f7e2", "SELL": "\U0001f534", "STOP_LOSS": "\U0001f6d1",
                 "TAKE_PROFIT": "\U0001f3af", "TRAILING_STOP": "\U0001f4c9",
                 "REBALANCE": "\u2696\ufe0f",
                 "RSI2_BUY": "\u26a1", "RSI2_SL": "\U0001f6d1",
                 "RSI2_TP": "\U0001f3af", "RSI2_TRAIL": "\U0001f4c9",
                 "RSI2_RSI2>90": "\U0001f534",
                 }.get(action, "\U0001f4ca")

        # v3.8.1: RSI(2) 전략 구분 표시
        is_rsi2 = action.startswith("RSI2_")
        strategy_tag = "[RSI2 급락매수] " if is_rsi2 and "BUY" in action else \
                       "[RSI2 청산] " if is_rsi2 else ""

        pnl_str = f" ({pnl_pct:+.1f}%)" if pnl_pct else ""
        reason_str = "\n".join(f"  \u2022 {r}" for r in (reasons or [])[:3])

        msg = (
            f"{emoji} {strategy_tag}<b>{action}</b> {name} ({symbol})\n"
            f"\uc218\ub7c9: {qty:,}\uc8fc | \uac00\uaca9: {price:,.0f}\uc6d0{pnl_str}\n"
            f"\ucd1d\uc561: {qty * price:,.0f}\uc6d0"
        )
        if score:
            msg += f" | \uc810\uc218: {score:.0f}"
        if reason_str:
            msg += f"\n{reason_str}"

        # 손절/서킷브레이커는 HIGH, 일반 거래는 NORMAL
        priority = AlertPriority.HIGH if action in ("STOP_LOSS", "TRAILING_STOP") else AlertPriority.NORMAL
        self._dispatch(msg, priority)

    def notify_rebalance(self, symbol: str, name: str, qty_sold: int,
                         price: float, reason: str):
        """리밸런싱 알림"""
        msg = (
            f"\u2696\ufe0f <b>REBALANCE</b> {name} ({symbol})\n"
            f"\ucd95\uc18c \uc218\ub7c9: {qty_sold:,}\uc8fc | \uac00\uaca9: {price:,.0f}\uc6d0\n"
            f"\uc0ac\uc720: {reason}"
        )
        self._dispatch(msg, AlertPriority.NORMAL)

    def notify_daily_report(self, total_assets: float, cash: float,
                            pnl_day: float, pnl_day_pct: float,
                            total_pnl_pct: float, positions: int,
                            trades_today: int, win_rate: float):
        today = datetime.now().strftime("%Y-%m-%d")
        emoji = "\U0001f4c8" if pnl_day >= 0 else "\U0001f4c9"

        msg = (
            f"\U0001f4ca <b>StockBot \uc77c\uc77c \ub9ac\ud3ec\ud2b8</b> ({today})\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\ucd1d \uc790\uc0b0: {total_assets:,.0f}\uc6d0\n"
            f"\ud604\uae08: {cash:,.0f}\uc6d0\n"
            f"{emoji} \uae08\uc77c \uc190\uc775: {pnl_day:+,.0f}\uc6d0 ({pnl_day_pct:+.2f}%)\n"
            f"\ub204\uc801 \uc218\uc775\ub960: {total_pnl_pct:+.2f}%\n"
            f"\ubcf4\uc720 \uc885\ubaa9: {positions}\uac1c\n"
            f"\uae08\uc77c \uac70\ub798: {trades_today}\uac74\n"
            f"\uc2b9\ub960: {win_rate:.1f}%"
        )
        # 일일 리포트는 모든 채널로
        self._dispatch(msg, AlertPriority.LOW)

    def notify_daily_report_detail(self, total_assets: float, cash: float,
                                    total_pnl: float, total_pnl_pct: float,
                                    positions: list, trades: list,
                                    win_rate: float, regime: str):
        """상세 일일 리포트 (개별 종목 + 거래 내역)"""
        today = datetime.now().strftime("%Y-%m-%d")
        emoji = "\U0001f4c8" if total_pnl >= 0 else "\U0001f4c9"

        lines = [
            f"\U0001f4ca <b>StockBot 일일 리포트</b> ({today})",
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
            f"총 자산: {total_assets:,.0f}원 | 현금: {cash:,.0f}원",
            f"{emoji} 수익: {total_pnl:+,.0f}원 ({total_pnl_pct:+.2f}%)",
            f"시장 국면: {regime} | 승률: {win_rate:.1f}%",
        ]

        # 보유 종목 수익률
        if positions:
            lines.append(f"\n\U0001f4bc <b>보유 종목 ({len(positions)}개)</b>")
            for p in positions:
                arrow = "\u25b2" if p["pnl"] >= 0 else "\u25bc"
                lines.append(
                    f"  {p['name']} {p['qty']}주 | "
                    f"{p['avg']:,.0f}\u2192{p['cur']:,.0f} "
                    f"{arrow}{p['pnl']:+,.0f}원({p['pnl_pct']:+.1f}%)"
                )

        # 오늘 거래 내역
        if trades:
            lines.append(f"\n\U0001f4dd <b>오늘 거래 ({len(trades)}건)</b>")
            for t in trades:
                action = t.get("action", "")
                name = t.get("name", "")
                qty = t.get("qty", 0)
                price = t.get("price", 0)
                pnl = t.get("pnl", 0)
                pnl_pct = t.get("pnl_pct", 0)
                if "BUY" in action:
                    lines.append(f"  \U0001f7e2 {action} {name} {qty}주 @{price:,.0f}원")
                else:
                    lines.append(f"  \U0001f534 {action} {name} {qty}주 @{price:,.0f}원 {pnl:+,.0f}원({pnl_pct:+.1f}%)")
        else:
            lines.append("\n거래 없음")

        msg = "\n".join(lines)
        self._dispatch(msg, AlertPriority.HIGH)

    def notify_circuit_breaker(self, reason: str):
        self._dispatch(
            f"\U0001f6a8 <b>\uc11c\ud0b7\ube0c\ub808\uc774\ucee4 \ubc1c\ub3d9</b>\n\uc0ac\uc720: {reason}\n\ub9e4\ub9e4\uac00 \uc77c\uc2dc \uc911\ub2e8\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
            AlertPriority.CRITICAL,
        )

    def notify_error(self, error: str):
        self._dispatch(
            f"\u26a0\ufe0f <b>StockBot \uc624\ub958</b>\n{error[:200]}",
            AlertPriority.HIGH,
        )

    def notify_bot_start(self, mode: str):
        self._dispatch(
            f"\U0001f916 <b>StockBot \uc2dc\uc791</b>\n\ubaa8\ub4dc: {mode}\n\uc2dc\uac04: {datetime.now().strftime('%H:%M:%S')}",
            AlertPriority.HIGH,
        )

    def notify_bot_stop(self):
        self._dispatch(
            f"\u23f9\ufe0f <b>StockBot \uc911\uc9c0</b>\n\uc2dc\uac04: {datetime.now().strftime('%H:%M:%S')}",
            AlertPriority.HIGH,
        )
