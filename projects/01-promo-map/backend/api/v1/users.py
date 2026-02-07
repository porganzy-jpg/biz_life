"""사용자 API v1"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_db, get_pagination
from schemas.user import UserUpdate, UserProfileResponse, UsageHistoryItem
from schemas.auth import UserResponse
from repositories.user_repo import UserRepository
from repositories.favorite_repo import FavoriteRepository
from repositories.review_repo import ReviewRepository
from repositories.usage_log_repo import UsageLogRepository
from services import discount_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_my_profile(
    user=Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    fav_repo = FavoriteRepository(db)
    review_repo = ReviewRepository(db)
    usage_repo = UsageLogRepository(db)

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "phone": user.phone,
        "company_name": user.company.name if user.company else None,
        "is_admin": user.is_admin,
        "favorites_count": fav_repo.count_by_user(user.id),
        "reviews_count": review_repo.count_by_user(user.id),
        "usage_count": usage_repo.count_by_user(user.id),
    }


@router.put("/me")
async def update_profile(
    data: UserUpdate,
    user=Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    user_repo = UserRepository(db)
    updates = data.model_dump(exclude_none=True)
    if updates:
        user = user_repo.update(user, **updates)
    return UserResponse(
        id=user.id, email=user.email, name=user.name,
        phone=user.phone,
        company_name=user.company.name if user.company else None,
        is_admin=user.is_admin,
    )


@router.get("/me/usage-history")
async def get_usage_history(
    user=Depends(get_current_user_db),
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    return discount_service.get_my_discount_history(
        db, user, page=pagination["page"], size=pagination["size"],
    )
