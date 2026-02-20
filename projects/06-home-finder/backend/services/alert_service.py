"""
알림 서비스 - 텔레그램 즉시 알림 + 일간/주간 다이제스트

기존 alerts/alert_system.py의 TelegramAlertSystem을 활용하면서
매칭 엔진 결과를 기반으로 스마트 알림을 발송.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.property import Property
from models.matching import MatchAlert, AlertSettings
from alerts.alert_system import TelegramAlertSystem
from alerts.formatters import format_price_kr, format_area
from backend.config import settings

logger = logging.getLogger("homefinder.alert_service")


class AlertService:
    """매칭 기반 스마트 알림 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.telegram = TelegramAlertSystem(
            bot_token=settings.TELEGRAM_BOT_TOKEN,
            chat_id=settings.TELEGRAM_CHAT_ID,
        )

    # ────────────────────────────────────────────
    # 즉시 알림 (>= instant_threshold)
    # ────────────────────────────────────────────

    def send_telegram_alert(self, alert: MatchAlert) -> bool:
        """
        단일 매칭 알림을 텔레그램으로 전송.
        조용한 시간대에는 큐잉만 하고 전송하지 않음.
        """
        if not self.telegram.enabled:
            logger.debug("Telegram disabled, skipping alert")
            return False

        # 조용한 시간대 체크
        if self._is_quiet_hours():
            logger.info(
                f"Quiet hours active, queuing alert for property {alert.property_id}"
            )
            return False

        # 매물 정보 조회
        prop = (
            self.db.query(Property)
            .filter(Property.id == alert.property_id)
            .first()
        )
        if not prop:
            logger.warning(f"Property {alert.property_id} not found for alert")
            return False

        # 알림 메시지 구성
        message = self._format_match_alert(prop, alert)
        success = self.telegram.send_message(message)

        if success:
            alert.is_sent = 1
            alert.sent_via = "telegram"
            alert.sent_at = datetime.utcnow()
            self.db.commit()
            logger.info(
                f"Sent telegram alert: property={prop.id}, "
                f"score={alert.match_score:.1f}"
            )

        return success

    def process_pending_alerts(self) -> dict:
        """미전송 즉시 알림 처리 (조용한 시간대 후 호출)"""
        alert_settings = self._get_alert_settings()

        pending = (
            self.db.query(MatchAlert)
            .filter(
                MatchAlert.is_sent == 0,
                MatchAlert.alert_type == "instant",
            )
            .order_by(desc(MatchAlert.match_score))
            .all()
        )

        sent_count = 0
        for alert in pending:
            if self._is_quiet_hours():
                break
            if self.send_telegram_alert(alert):
                sent_count += 1

        return {"pending": len(pending), "sent": sent_count}

    # ────────────────────────────────────────────
    # 일간 다이제스트
    # ────────────────────────────────────────────

    def build_daily_digest(self) -> Optional[str]:
        """
        최근 24시간 daily_digest 이상 알림을 모아 요약 메시지 생성.
        Returns: 메시지 문자열 또는 None (해당 없을 때)
        """
        alert_settings = self._get_alert_settings()
        threshold = alert_settings.daily_threshold or 80
        since = datetime.utcnow() - timedelta(hours=24)

        alerts = (
            self.db.query(MatchAlert)
            .filter(
                MatchAlert.created_at >= since,
                MatchAlert.match_score >= threshold,
            )
            .order_by(desc(MatchAlert.match_score))
            .all()
        )

        if not alerts:
            return None

        # 매물 정보 미리 로드
        prop_ids = [a.property_id for a in alerts]
        properties = (
            self.db.query(Property)
            .filter(Property.id.in_(prop_ids))
            .all()
        )
        prop_map = {p.id: p for p in properties}

        today_str = datetime.now().strftime("%Y-%m-%d")
        lines = [
            f"[일간 매칭 리포트] {today_str}",
            "=" * 28,
            f"매칭 {len(alerts)}건 (기준: {threshold}점 이상)",
            "",
        ]

        for i, alert in enumerate(alerts[:10], 1):
            prop = prop_map.get(alert.property_id)
            if not prop:
                continue

            name = prop.complex_name or prop.address or f"{prop.district} {prop.dong}"
            price_str = format_price_kr(prop.price_krw) if prop.price_krw else "가격미정"
            area_str = format_area(prop.area_m2) if prop.area_m2 else ""

            # 점수 내역
            try:
                bd = json.loads(alert.score_breakdown_json or "{}")
            except json.JSONDecodeError:
                bd = {}

            top_factor = ""
            if bd:
                best_key = max(bd, key=bd.get)
                factor_names = {
                    "location": "위치", "price": "가격", "size": "규모",
                    "quality": "품질", "opportunity": "기회", "urgency": "긴급",
                }
                top_factor = f" [{factor_names.get(best_key, best_key)} 강점]"

            lines.append(
                f"{i}. [{alert.match_score:.0f}점]{top_factor}"
            )
            lines.append(f"   {name}")
            lines.append(f"   {price_str} {area_str}")
            if prop.district:
                subway_info = ""
                if prop.nearest_subway_name:
                    dist_m = f"{int(prop.nearest_subway_distance)}m" if prop.nearest_subway_distance else ""
                    subway_info = f" | {prop.nearest_subway_name}역 {dist_m}"
                lines.append(f"   {prop.district}{subway_info}")
            lines.append("")

        if len(alerts) > 10:
            lines.append(f"... 외 {len(alerts) - 10}건")

        lines.append("")
        lines.append("HomeFinder 맞춤 추천")

        return "\n".join(lines)

    def send_daily_digest(self) -> bool:
        """일간 다이제스트 생성 및 전송"""
        message = self.build_daily_digest()
        if not message:
            logger.info("No matches for daily digest")
            return False

        success = self.telegram.send_message(message)
        if success:
            logger.info("Daily digest sent successfully")
        return success

    # ────────────────────────────────────────────
    # 주간 다이제스트
    # ────────────────────────────────────────────

    def build_weekly_digest(self) -> Optional[str]:
        """주간 매칭 요약"""
        alert_settings = self._get_alert_settings()
        threshold = alert_settings.weekly_threshold or 70
        since = datetime.utcnow() - timedelta(days=7)

        alerts = (
            self.db.query(MatchAlert)
            .filter(
                MatchAlert.created_at >= since,
                MatchAlert.match_score >= threshold,
            )
            .order_by(desc(MatchAlert.match_score))
            .all()
        )

        if not alerts:
            return None

        today_str = datetime.now().strftime("%Y-%m-%d")

        # 통계
        scores = [a.match_score for a in alerts]
        avg_score = sum(scores) / len(scores) if scores else 0
        high_count = sum(1 for s in scores if s >= 90)
        mid_count = sum(1 for s in scores if 80 <= s < 90)

        lines = [
            f"[주간 매칭 리포트] {today_str}",
            "=" * 28,
            f"총 매칭: {len(alerts)}건",
            f"평균 점수: {avg_score:.1f}점",
            f"최상위(90+): {high_count}건 | 상위(80+): {mid_count}건",
            "",
        ]

        # TOP 5
        prop_ids = [a.property_id for a in alerts[:5]]
        properties = (
            self.db.query(Property)
            .filter(Property.id.in_(prop_ids))
            .all()
        )
        prop_map = {p.id: p for p in properties}

        lines.append("TOP 5 매칭:")
        lines.append("-" * 20)
        for i, alert in enumerate(alerts[:5], 1):
            prop = prop_map.get(alert.property_id)
            if not prop:
                continue
            name = prop.complex_name or prop.address or f"{prop.district}"
            price_str = format_price_kr(prop.price_krw) if prop.price_krw else ""
            lines.append(
                f"  {i}. [{alert.match_score:.0f}점] {name} {price_str}"
            )

        lines.append("")
        lines.append("HomeFinder 맞춤 추천")

        return "\n".join(lines)

    # ────────────────────────────────────────────
    # 내부 유틸리티
    # ────────────────────────────────────────────

    def _get_alert_settings(self) -> AlertSettings:
        """알림 설정 조회 (없으면 기본값 생성)"""
        s = self.db.query(AlertSettings).first()
        if not s:
            s = AlertSettings()
            self.db.add(s)
            self.db.commit()
            self.db.refresh(s)
        return s

    def _is_quiet_hours(self) -> bool:
        """현재 시각이 조용한 시간대인지 확인"""
        s = self._get_alert_settings()
        now_hour = datetime.now().hour

        start = s.quiet_start_hour or 22
        end = s.quiet_end_hour or 8

        if start > end:
            # 예: 22:00 ~ 08:00 (자정을 넘는 경우)
            return now_hour >= start or now_hour < end
        else:
            return start <= now_hour < end

    def _format_match_alert(self, prop: Property, alert: MatchAlert) -> str:
        """매칭 알림 텔레그램 메시지 포맷"""
        name = prop.complex_name or prop.address or f"{prop.district} {prop.dong}"
        price_str = format_price_kr(prop.price_krw) if prop.price_krw else "가격미정"
        area_str = format_area(prop.area_m2) if prop.area_m2 else ""

        # 점수에 따른 헤더
        score = alert.match_score
        if score >= 95:
            header = "[BEST MATCH] 최고 추천 매물!"
        elif score >= 90:
            header = "[HOT] 강력 추천 매물"
        elif score >= 80:
            header = "[GOOD] 추천 매물"
        else:
            header = "[NEW] 관심 매물"

        lines = [
            header,
            "-" * 24,
            f"매칭 점수: {score:.1f}점",
            "",
            f"[{prop.property_type or ''}] {name}",
            f"{prop.district or ''} {prop.dong or ''}",
            f"{price_str} {area_str}",
        ]

        # 상세 정보
        details = []
        if prop.floor:
            details.append(f"{prop.floor}층")
        if prop.direction:
            details.append(prop.direction)
        if prop.built_year:
            details.append(f"{prop.built_year}년")
        if details:
            lines.append(" / ".join(details))

        # 교통
        if prop.nearest_subway_name:
            dist_str = (
                f" {int(prop.nearest_subway_distance)}m"
                if prop.nearest_subway_distance else ""
            )
            lines.append(f"지하철: {prop.nearest_subway_name}역{dist_str}")

        # 점수 내역
        try:
            bd = json.loads(alert.score_breakdown_json or "{}")
        except json.JSONDecodeError:
            bd = {}

        if bd:
            lines.append("")
            factor_names = {
                "location": "위치", "price": "가격", "size": "규모",
                "quality": "품질", "opportunity": "기회", "urgency": "긴급",
            }
            score_parts = []
            for key in ("location", "price", "size", "quality", "opportunity", "urgency"):
                if key in bd:
                    label = factor_names.get(key, key)
                    score_parts.append(f"{label}:{bd[key]:.0f}")
            lines.append(" | ".join(score_parts))

        # 추천 사유
        if alert.explanation:
            # 첫 번째 줄(종합)만 추가
            exp_lines = alert.explanation.strip().split("\n")
            if exp_lines:
                lines.append("")
                lines.append(exp_lines[0])

        lines.append("")
        lines.append("HomeFinder")

        return "\n".join(lines)

    def mark_alert_read(self, alert_id: int) -> bool:
        """알림 읽음 처리"""
        alert = (
            self.db.query(MatchAlert)
            .filter(MatchAlert.id == alert_id)
            .first()
        )
        if alert:
            alert.is_read = 1
            self.db.commit()
            return True
        return False
