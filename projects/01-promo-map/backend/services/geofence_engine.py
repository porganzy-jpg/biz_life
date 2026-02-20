"""
PromoMap 지오펜스 알림 엔진

사용자 위치 기반으로 근처 할인 매장을 감지하고
중복 없이 우선순위 기반 알림을 생성한다.
"""
import math
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Store, Discount, User
from models.notification import Notification, NotificationPreference, NotificationEngagement
from repositories.store_repo import StoreRepository
from repositories.discount_repo import DiscountRepository
from geofence import get_bounding_box

logger = logging.getLogger("promomap.geofence_engine")

# 카테고리 한글 매핑
CATEGORY_KR = {
    "food": "음식점",
    "cafe": "카페",
    "shopping": "쇼핑",
    "convenience": "편의점",
    "entertainment": "엔터",
    "general": "기타",
}


class GeofenceEngine:
    """지오펜스 기반 알림 생성 엔진"""

    # 중복 알림 방지 기간 (시간)
    DEDUP_HOURS = 24

    # 알림 자동 삭제 기간 (일)
    CLEANUP_DAYS = 7

    def __init__(self, db: Session):
        self.db = db
        self.store_repo = StoreRepository(db)
        self.discount_repo = DiscountRepository(db)

    @staticmethod
    def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """두 GPS 좌표 사이의 거리 계산 (미터)"""
        R = 6371000  # 지구 반경(m)
        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)

        a = (math.sin(dlat / 2) ** 2
             + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def check_proximity(
        self, user_lat: float, user_lng: float, radius_m: float = 500
    ) -> List[Tuple[Store, float]]:
        """
        반경 내 활성 할인 매장 검색.
        바운딩 박스로 DB 쿼리 최적화 후 정확한 거리 계산.
        """
        bbox = get_bounding_box(user_lat, user_lng, radius_m)
        stores = self.store_repo.get_by_bounding_box(
            bbox["min_lat"], bbox["max_lat"],
            bbox["min_lon"], bbox["max_lon"],
        )

        nearby = []
        for store in stores:
            dist = self._haversine_distance(
                user_lat, user_lng, store.latitude, store.longitude
            )
            if dist <= radius_m:
                nearby.append((store, round(dist, 1)))

        # 가까운 순 정렬
        nearby.sort(key=lambda x: x[1])
        return nearby

    def _get_preferences(self, user_id: int) -> NotificationPreference:
        """사용자 알림 설정 조회 (없으면 기본값)"""
        pref = (
            self.db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == user_id)
            .first()
        )
        if not pref:
            # 기본 설정으로 생성
            pref = NotificationPreference(user_id=user_id)
            self.db.add(pref)
            self.db.commit()
            self.db.refresh(pref)
        return pref

    def _is_quiet_hours(self, pref: NotificationPreference) -> bool:
        """방해금지 시간대 확인"""
        now = datetime.utcnow()
        # UTC+9 (한국 시간) 보정
        kst_now = now + timedelta(hours=9)
        current_time = kst_now.strftime("%H:%M")

        start = pref.quiet_hours_start or "22:00"
        end = pref.quiet_hours_end or "08:00"

        if start <= end:
            return start <= current_time <= end
        else:
            # 자정 넘어가는 경우 (예: 22:00 ~ 08:00)
            return current_time >= start or current_time <= end

    def _get_time_boost(self) -> float:
        """시간대 기반 우선순위 가중치"""
        now = datetime.utcnow() + timedelta(hours=9)  # KST
        hour = now.hour
        minute = now.minute
        t = hour + minute / 60.0

        # 점심시간 (11:30~13:30) 부스트
        if 11.5 <= t <= 13.5:
            return 1.5

        # 퇴근 후 (17:30~19:00) 부스트
        if 17.5 <= t <= 19.0:
            return 1.3

        return 1.0

    def _get_category_preference_score(self, user_id: int, category: str) -> float:
        """사용자의 카테고리 참여도 기반 가중치"""
        engagement = (
            self.db.query(NotificationEngagement)
            .filter(
                NotificationEngagement.user_id == user_id,
                NotificationEngagement.category == category,
            )
            .first()
        )
        if not engagement:
            return 1.0

        # 클릭 + 전환 대비 해제 비율로 점수 계산
        total_positive = engagement.click_count + engagement.convert_count * 2
        total_negative = engagement.dismiss_count
        total = total_positive + total_negative

        if total == 0:
            return 1.0

        # 0.5 ~ 2.0 범위로 정규화
        ratio = total_positive / max(total, 1)
        return 0.5 + ratio * 1.5

    def _calculate_priority(
        self,
        discount_value: float,
        distance_m: float,
        category: str,
        user_id: int,
        is_favorite: bool = False,
    ) -> int:
        """
        알림 우선순위 계산.
        높은 값 = 더 중요한 알림.

        요소:
        - 할인율 (가장 큰 영향)
        - 거리 (가까울수록 높음)
        - 시간대 부스트
        - 카테고리 선호도
        - 즐겨찾기 여부
        """
        # 기본 점수: 할인율 (0~100 범위)
        score = float(discount_value)

        # 거리 가중치 (100m 이내: 2x, 200m: 1.5x, 500m: 1x)
        if distance_m <= 100:
            score *= 2.0
        elif distance_m <= 200:
            score *= 1.5
        elif distance_m <= 300:
            score *= 1.2

        # 시간대 부스트
        score *= self._get_time_boost()

        # 카테고리 선호도
        score *= self._get_category_preference_score(user_id, category)

        # 즐겨찾기 부스트
        if is_favorite:
            score *= 1.5

        return int(score)

    def _was_recently_notified(
        self, user_id: int, store_id: int, discount_id: int
    ) -> bool:
        """24시간 내 동일 매장/할인에 대한 알림이 있었는지 확인"""
        cutoff = datetime.utcnow() - timedelta(hours=self.DEDUP_HOURS)
        exists = (
            self.db.query(Notification.id)
            .filter(
                Notification.user_id == user_id,
                Notification.store_id == store_id,
                Notification.discount_id == discount_id,
                Notification.created_at >= cutoff,
            )
            .first()
        )
        return exists is not None

    def _get_today_notification_count(self, user_id: int) -> int:
        """오늘 생성된 알림 수"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            self.db.query(func.count(Notification.id))
            .filter(
                Notification.user_id == user_id,
                Notification.created_at >= today_start,
            )
            .scalar()
        )

    def _get_user_favorites(self, user_id: int) -> set:
        """사용자 즐겨찾기 매장 ID 집합"""
        from models import Favorite
        favs = (
            self.db.query(Favorite.store_id)
            .filter(Favorite.user_id == user_id)
            .all()
        )
        return {f[0] for f in favs}

    def generate_notifications(
        self,
        user_id: int,
        user_lat: float,
        user_lng: float,
        user: Optional[User] = None,
    ) -> List[dict]:
        """
        사용자 위치 기반 알림 생성.

        1. 설정 확인 (비활성/방해금지 → 빈 리스트)
        2. 반경 내 매장 검색
        3. 활성 할인 조회 (회사 필터 적용)
        4. 중복 제거
        5. 우선순위 계산 및 정렬
        6. 일일 한도 적용
        """
        # 1. 설정 확인
        pref = self._get_preferences(user_id)
        if not pref.is_enabled:
            return []
        if self._is_quiet_hours(pref):
            return []

        # 일일 한도 확인
        today_count = self._get_today_notification_count(user_id)
        remaining = max(0, pref.daily_limit - today_count)
        if remaining <= 0:
            return []

        # 활성 카테고리 필터
        enabled_cats = set()
        if pref.enabled_categories and pref.enabled_categories.strip():
            enabled_cats = {c.strip() for c in pref.enabled_categories.split(",") if c.strip()}

        # 2. 반경 내 매장 검색
        radius = float(pref.max_radius_m)
        nearby_stores = self.check_proximity(user_lat, user_lng, radius)

        if not nearby_stores:
            return []

        # 즐겨찾기 목록
        favorites = self._get_user_favorites(user_id)

        # 3. 매장별 활성 할인 조회 (배치)
        store_ids = [s.id for s, _ in nearby_stores]
        discounts_map = self.discount_repo.get_active_by_store_ids(store_ids)

        notifications = []

        for store, distance in nearby_stores:
            # 카테고리 필터 적용
            if enabled_cats and store.category not in enabled_cats:
                continue

            discounts = discounts_map.get(store.id, [])

            # 회사 할인 필터
            if user and user.company_id:
                discounts = [d for d in discounts if d.company_id == user.company_id]

            is_fav = store.id in favorites

            for disc in discounts:
                # 4. 중복 제거
                if self._was_recently_notified(user_id, store.id, disc.id):
                    continue

                # 5. 우선순위 계산
                priority = self._calculate_priority(
                    disc.discount_value, distance, store.category, user_id, is_fav
                )

                # 알림 제목/본문 생성
                cat_kr = CATEGORY_KR.get(store.category, "매장")
                title = f"{store.name} {disc.discount_value}% 할인!"
                body = (
                    f"{store.brand} ({cat_kr}) - {disc.description or '임직원 할인'}"
                    f" | {int(distance)}m 거리"
                )

                # DB에 저장
                notif = Notification(
                    user_id=user_id,
                    store_id=store.id,
                    discount_id=disc.id,
                    title=title,
                    body=body,
                    distance_m=distance,
                    priority=priority,
                )
                self.db.add(notif)
                self.db.flush()  # ID 할당을 위해 flush

                notifications.append({
                    "id": notif.id,
                    "store_id": store.id,
                    "store_name": store.name,
                    "brand": store.brand,
                    "category": store.category,
                    "icon_color": store.icon_color,
                    "icon_letter": store.icon_letter,
                    "discount_id": disc.id,
                    "discount_value": disc.discount_value,
                    "discount_type": disc.discount_type,
                    "description": disc.description,
                    "distance_m": distance,
                    "priority": priority,
                    "title": title,
                    "body": body,
                    "is_favorite": is_fav,
                    "created_at": notif.created_at.isoformat() if notif.created_at else None,
                })

        # 커밋
        self.db.commit()

        # 우선순위 내림차순 정렬, 일일 한도 적용
        notifications.sort(key=lambda n: n["priority"], reverse=True)
        notifications = notifications[:remaining]

        return notifications

    def cleanup_old_notifications(self, days: int = None):
        """오래된 알림 자동 삭제"""
        if days is None:
            days = self.CLEANUP_DAYS
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = (
            self.db.query(Notification)
            .filter(Notification.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        if deleted:
            logger.info(f"Cleaned up {deleted} old notifications")
        return deleted
