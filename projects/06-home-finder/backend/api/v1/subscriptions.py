"""청약 API"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from repositories.subscription_repo import SubscriptionRepository

router = APIRouter()


def _sub_to_dict(s):
    return {
        "id": s.id,
        "name": s.name,
        "city": s.city,
        "district": s.district,
        "dong": s.dong,
        "address": s.address,
        "lat": s.lat,
        "lng": s.lng,
        "developer": s.developer,
        "total_units": s.total_units,
        "subscription_units": s.subscription_units,
        "subscription_start": s.subscription_start.isoformat() if s.subscription_start else None,
        "subscription_end": s.subscription_end.isoformat() if s.subscription_end else None,
        "announcement_date": s.announcement_date.isoformat() if s.announcement_date else None,
        "move_in_date": s.move_in_date.isoformat() if s.move_in_date else None,
        "min_price": s.min_price,
        "max_price": s.max_price,
        "avg_price_per_m2": s.avg_price_per_m2,
        "min_area_m2": s.min_area_m2,
        "max_area_m2": s.max_area_m2,
        "competition_rate": s.competition_rate,
        "subscription_type": s.subscription_type,
        "status": s.status,
        "source_url": s.source_url,
        "source_id": s.source_id,
        "description": s.description,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.get("/upcoming")
def get_upcoming_subscriptions(
    days: int = Query(30, ge=1, le=180, description="조회 기간 (일)"),
    db: Session = Depends(get_db),
):
    """다가오는 청약 목록"""
    repo = SubscriptionRepository(db)
    items = repo.get_upcoming(days=days)
    return {"items": [_sub_to_dict(s) for s in items], "count": len(items), "days": days}


@router.get("/")
def list_active_subscriptions(db: Session = Depends(get_db)):
    """현재 활성 청약 목록"""
    repo = SubscriptionRepository(db)
    items = repo.get_active()
    return {"items": [_sub_to_dict(s) for s in items], "count": len(items)}


@router.get("/{subscription_id}")
def get_subscription(subscription_id: int, db: Session = Depends(get_db)):
    """청약 상세 조회"""
    repo = SubscriptionRepository(db)
    sub = repo.get_by_id(subscription_id)
    if not sub:
        raise HTTPException(
            status_code=404,
            detail=f"청약 ID {subscription_id}을(를) 찾을 수 없습니다",
        )
    return _sub_to_dict(sub)
