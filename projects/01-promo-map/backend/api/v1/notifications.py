"""알림 API v1 - 지오펜스 기반 할인 알림"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from dependencies import get_current_user_db
from models import User
from models.notification import Notification, NotificationPreference, NotificationEngagement
from schemas.common import MessageResponse
from services.geofence_engine import GeofenceEngine
from services import usage_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


# === Pydantic 스키마 ===

class LocationCheckRequest(BaseModel):
    lat: float = Field(..., description="위도")
    lng: float = Field(..., description="경도")


class PreferencesUpdateRequest(BaseModel):
    max_radius_m: Optional[int] = Field(None, ge=100, le=2000, description="최대 반경(m)")
    quiet_hours_start: Optional[str] = Field(None, description="방해금지 시작 HH:MM")
    quiet_hours_end: Optional[str] = Field(None, description="방해금지 종료 HH:MM")
    enabled_categories: Optional[str] = Field(None, description="활성 카테고리 (쉼표 구분)")
    daily_limit: Optional[int] = Field(None, ge=1, le=200, description="일일 알림 한도")
    is_enabled: Optional[bool] = Field(None, description="알림 활성화 여부")


# === 엔드포인트 ===

@router.post("/check")
async def check_notifications(
    data: LocationCheckRequest,
    user: User = Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    """사용자 위치 전송 -> 근처 할인 알림 생성/반환"""
    engine = GeofenceEngine(db)
    notifications = engine.generate_notifications(
        user_id=user.id,
        user_lat=data.lat,
        user_lng=data.lng,
        user=user,
    )
    return {"count": len(notifications), "notifications": notifications}


@router.get("/unread")
async def get_unread_notifications(
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    """읽지 않은 알림 목록"""
    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.seen_at.is_(None),
            Notification.dismissed_at.is_(None),
        )
        .order_by(Notification.priority.desc(), Notification.created_at.desc())
        .limit(limit)
        .all()
    )

    unread_count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == user.id,
            Notification.seen_at.is_(None),
            Notification.dismissed_at.is_(None),
        )
        .scalar()
    )

    items = []
    for n in notifications:
        items.append(_serialize_notification(n))

    return {"count": unread_count, "notifications": items}


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    user: User = Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    """알림 읽음 처리 + 클릭 기록"""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if not notif:
        return {"message": "Notification not found"}

    now = datetime.utcnow()
    if notif.seen_at is None:
        notif.seen_at = now
    notif.clicked_at = now
    db.commit()

    # 참여도 업데이트 (클릭)
    _update_engagement(db, user.id, notif.store, "click")

    return {"message": "Marked as read", "notification": _serialize_notification(notif)}


@router.post("/read-all")
async def mark_all_as_read(
    user: User = Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    """모든 알림 읽음 처리"""
    now = datetime.utcnow()
    updated = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.seen_at.is_(None),
        )
        .update({"seen_at": now}, synchronize_session=False)
    )
    db.commit()
    return {"message": f"{updated}개 알림을 읽음 처리했습니다", "updated": updated}


@router.delete("/{notification_id}")
async def dismiss_notification(
    notification_id: int,
    user: User = Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    """알림 해제(dismiss)"""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if not notif:
        return {"message": "Notification not found"}

    notif.dismissed_at = datetime.utcnow()
    db.commit()

    # 참여도 업데이트 (해제)
    _update_engagement(db, user.id, notif.store, "dismiss")

    return {"message": "Notification dismissed"}


@router.get("/preferences")
async def get_preferences(
    user: User = Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    """알림 설정 조회"""
    engine = GeofenceEngine(db)
    pref = engine._get_preferences(user.id)
    return _serialize_preferences(pref)


@router.put("/preferences")
async def update_preferences(
    data: PreferencesUpdateRequest,
    user: User = Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    """알림 설정 업데이트"""
    engine = GeofenceEngine(db)
    pref = engine._get_preferences(user.id)

    if data.max_radius_m is not None:
        pref.max_radius_m = data.max_radius_m
    if data.quiet_hours_start is not None:
        pref.quiet_hours_start = data.quiet_hours_start
    if data.quiet_hours_end is not None:
        pref.quiet_hours_end = data.quiet_hours_end
    if data.enabled_categories is not None:
        pref.enabled_categories = data.enabled_categories
    if data.daily_limit is not None:
        pref.daily_limit = data.daily_limit
    if data.is_enabled is not None:
        pref.is_enabled = data.is_enabled

    pref.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pref)

    return {"message": "설정이 저장되었습니다", "preferences": _serialize_preferences(pref)}


# === 하위 호환: 기존 /use 엔드포인트 유지 ===

@router.post("/use", response_model=MessageResponse)
async def use_discount(
    store_id: int = Query(...),
    discount_id: int = Query(...),
    saved_amount: float = Query(0),
    user=Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    result = usage_service.log_discount_usage(db, user, store_id, discount_id, saved_amount)
    return MessageResponse(message=result["message"])


# === 헬퍼 함수 ===

def _serialize_notification(n: Notification) -> dict:
    """Notification ORM -> dict"""
    return {
        "id": n.id,
        "store_id": n.store_id,
        "discount_id": n.discount_id,
        "title": n.title,
        "body": n.body,
        "distance_m": n.distance_m,
        "priority": n.priority,
        "seen_at": n.seen_at.isoformat() if n.seen_at else None,
        "dismissed_at": n.dismissed_at.isoformat() if n.dismissed_at else None,
        "clicked_at": n.clicked_at.isoformat() if n.clicked_at else None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "store_name": n.store.name if n.store else None,
        "store_brand": n.store.brand if n.store else None,
        "store_category": n.store.category if n.store else None,
        "store_icon_color": n.store.icon_color if n.store else None,
        "store_icon_letter": n.store.icon_letter if n.store else None,
        "store_lat": n.store.latitude if n.store else None,
        "store_lng": n.store.longitude if n.store else None,
    }


def _serialize_preferences(pref: NotificationPreference) -> dict:
    """NotificationPreference ORM -> dict"""
    return {
        "id": pref.id,
        "max_radius_m": pref.max_radius_m,
        "quiet_hours_start": pref.quiet_hours_start,
        "quiet_hours_end": pref.quiet_hours_end,
        "enabled_categories": pref.enabled_categories or "",
        "daily_limit": pref.daily_limit,
        "is_enabled": pref.is_enabled,
    }


def _update_engagement(db: Session, user_id: int, store, action: str):
    """사용자 카테고리 참여도 업데이트"""
    if not store:
        return
    category = store.category or "general"

    engagement = (
        db.query(NotificationEngagement)
        .filter(
            NotificationEngagement.user_id == user_id,
            NotificationEngagement.category == category,
        )
        .first()
    )
    if not engagement:
        engagement = NotificationEngagement(
            user_id=user_id,
            category=category,
        )
        db.add(engagement)

    if action == "click":
        engagement.click_count = (engagement.click_count or 0) + 1
    elif action == "dismiss":
        engagement.dismiss_count = (engagement.dismiss_count or 0) + 1
    elif action == "convert":
        engagement.convert_count = (engagement.convert_count or 0) + 1

    engagement.updated_at = datetime.utcnow()
    db.commit()
