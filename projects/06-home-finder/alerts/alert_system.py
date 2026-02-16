"""
HomeFinder - 텔레그램 알림 시스템
CryptoBot 패턴 기반 (단방향 알림 전송)
"""
import logging
from typing import Optional

import requests

from alerts.formatters import (
    format_property_card,
    format_price_change,
    format_price_kr,
    format_auction_card,
    format_subscription_card,
    format_match_alert,
)

logger = logging.getLogger("homefinder.alerts")

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramAlertSystem:
    """텔레그램 단방향 알림 전송 시스템"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
        self._base_url = f"{TELEGRAM_API_BASE}/bot{bot_token}" if bot_token else ""

        if not self.enabled:
            logger.warning(
                "TelegramAlertSystem disabled: bot_token or chat_id not set"
            )

    def send_message(self, message: str, parse_mode: Optional[str] = None) -> bool:
        """
        텔레그램 메시지 전송

        Args:
            message: 전송할 메시지 텍스트
            parse_mode: "HTML" 또는 "Markdown" (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Alert skipped (disabled): %s...", message[:50])
            return False

        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    logger.debug("Telegram message sent successfully")
                    return True
                else:
                    logger.warning(
                        "Telegram API returned ok=false: %s",
                        result.get("description", "unknown"),
                    )
                    return False
            else:
                logger.warning(
                    "Telegram API HTTP %d: %s", resp.status_code, resp.text[:200]
                )
                return False
        except requests.exceptions.Timeout:
            logger.warning("Telegram send timeout")
            return False
        except requests.exceptions.ConnectionError:
            logger.warning("Telegram connection error")
            return False
        except Exception as e:
            logger.error("Telegram send error: %s", e)
            return False

    def new_property_alert(self, prop) -> bool:
        """
        신규 매물 알림

        Args:
            prop: Property ORM object or dict-like
        """
        header = "\U0001f195 신규 매물 등록!\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        card = format_property_card(prop)
        message = header + card
        return self.send_message(message)

    def price_change_alert(self, prop, old_price: int, new_price: int) -> bool:
        """
        가격 변동 알림

        Args:
            prop: Property ORM object or dict-like
            old_price: 이전 가격 (원)
            new_price: 새 가격 (원)
        """
        diff = new_price - old_price
        if diff < 0:
            emoji = "\U0001f4c9"
            direction = "하락"
        elif diff > 0:
            emoji = "\U0001f4c8"
            direction = "상승"
        else:
            return False  # No change

        # Property identifier
        name = ""
        if hasattr(prop, "complex_name"):
            name = prop.complex_name or prop.address or ""
        elif isinstance(prop, dict):
            name = prop.get("complex_name") or prop.get("address", "")

        change_str = format_price_change(old_price, new_price)

        message = (
            f"{emoji} 가격 {direction} 알림!\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\U0001f3e0 {name}\n"
            f"\U0001f4b1 {change_str}\n"
            f"\n"
            f"{format_property_card(prop)}"
        )
        return self.send_message(message)

    def auction_alert(self, auction) -> bool:
        """
        경매 일정 알림

        Args:
            auction: AuctionListing ORM object or dict-like
        """
        header = "\u2757 경매 일정 알림\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        card = format_auction_card(auction)
        message = header + card
        return self.send_message(message)

    def subscription_alert(self, sub) -> bool:
        """
        청약 마감 알림

        Args:
            sub: SubscriptionOpportunity ORM object or dict-like
        """
        # Determine urgency
        sub_end = None
        if hasattr(sub, "subscription_end"):
            sub_end = sub.subscription_end
        elif isinstance(sub, dict):
            sub_end = sub.get("subscription_end")

        urgency = ""
        if sub_end:
            from datetime import date
            days_left = (sub_end - date.today()).days
            if days_left <= 1:
                urgency = "\U0001f6a8 [D-DAY] "
            elif days_left <= 3:
                urgency = f"\u26a0 [D-{days_left}] "
            elif days_left <= 7:
                urgency = f"\U0001f514 [D-{days_left}] "

        header = (
            f"{urgency}\U0001f3d7 청약 알림\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        )
        card = format_subscription_card(sub)
        message = header + card
        return self.send_message(message)

    def daily_report(self, report_text: str) -> bool:
        """
        일일 리포트 전송

        Args:
            report_text: 포맷된 리포트 텍스트 (format_daily_report 사용)
        """
        return self.send_message(report_text)

    def weekly_report(self, report_text: str) -> bool:
        """
        주간 리포트 전송

        Args:
            report_text: 포맷된 리포트 텍스트 (format_weekly_report 사용)
        """
        return self.send_message(report_text)

    def match_alert(self, search_name: str, properties: list) -> bool:
        """
        저장검색 매칭 알림

        Args:
            search_name: 저장검색 이름
            properties: 매칭된 Property 객체 목록
        """
        if not properties:
            return False

        message = format_match_alert(search_name, properties)
        return self.send_message(message)

    def error_alert(self, component: str, error_msg: str) -> bool:
        """
        시스템 오류 알림 (수집 실패 등)

        Args:
            component: 컴포넌트 이름 (e.g., "molit_collector")
            error_msg: 오류 메시지
        """
        message = (
            f"\u26a0 시스템 오류 알림\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\U0001f527 컴포넌트: {component}\n"
            f"\u274c 오류: {error_msg[:300]}"
        )
        return self.send_message(message)

    def collection_complete_alert(
        self, collector_name: str, fetched: int, new: int, updated: int
    ) -> bool:
        """
        수집 완료 알림

        Args:
            collector_name: 수집기 이름
            fetched: 수집 건수
            new: 신규 건수
            updated: 업데이트 건수
        """
        message = (
            f"\u2705 수집 완료: {collector_name}\n"
            f"\U0001f4e6 수집: {fetched}건 | "
            f"\U0001f195 신규: {new}건 | "
            f"\U0001f504 갱신: {updated}건"
        )
        return self.send_message(message)

    def test_alert(self) -> bool:
        """테스트 알림 전송"""
        message = (
            "\U0001f3e0 HomeFinder 알림 테스트\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\u2705 텔레그램 알림이 정상 작동합니다.\n"
            f"\U0001f4e1 봇 연결 상태: OK\n"
            f"\U0001f4ac 채팅 ID: {self.chat_id}"
        )
        return self.send_message(message)
