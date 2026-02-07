"""알림 API v1"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_db
from schemas.common import MessageResponse
from services import notification_service, usage_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/check")
async def check_notifications(
    lat: float = Query(...),
    lon: float = Query(...),
    user=Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    notifications = notification_service.check_geofence(db, lat, lon, user)
    return {"count": len(notifications), "notifications": notifications}


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
