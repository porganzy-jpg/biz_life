"""즐겨찾기 API v1"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_db
from schemas.favorite import FavoriteRequest
from schemas.common import MessageResponse
from services import favorite_service

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("")
async def get_favorites(
    user=Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    favorites = favorite_service.get_favorites(db, user)
    return {"count": len(favorites), "favorites": favorites}


@router.post("")
async def add_favorite(
    data: FavoriteRequest,
    user=Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    return favorite_service.add_favorite(db, user, data.store_id)


@router.delete("/{store_id}", response_model=MessageResponse)
async def remove_favorite(
    store_id: int,
    user=Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    favorite_service.remove_favorite(db, user, store_id)
    return MessageResponse(message="Favorite removed")
