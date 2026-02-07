"""리뷰 API v1"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_db, get_pagination
from schemas.review import ReviewCreateRequest
from services import review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/{store_id}")
async def get_store_reviews(
    store_id: int,
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    return review_service.get_store_reviews(
        db, store_id, page=pagination["page"], size=pagination["size"],
    )


@router.post("")
async def create_review(
    data: ReviewCreateRequest,
    user=Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    return review_service.create_review(db, user, data.store_id, data.rating, data.content)
