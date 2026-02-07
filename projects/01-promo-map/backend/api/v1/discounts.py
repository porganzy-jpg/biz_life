"""할인 API v1"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_db, get_pagination
from services import discount_service

router = APIRouter(prefix="/discounts", tags=["discounts"])


@router.get("/active")
async def get_active_discounts(
    user=Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    discounts = discount_service.get_active_discounts(db, user)
    return {"count": len(discounts), "discounts": discounts}


@router.get("/my")
async def get_my_discounts(
    user=Depends(get_current_user_db),
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    return discount_service.get_my_discount_history(
        db, user, page=pagination["page"], size=pagination["size"],
    )
