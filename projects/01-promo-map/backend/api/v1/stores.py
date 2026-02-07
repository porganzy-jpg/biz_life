"""매장 API v1"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from dependencies import get_optional_user_db, get_pagination
from services import store_service

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("/nearby")
async def get_nearby_stores(
    lat: float = Query(..., description="위도"),
    lon: float = Query(..., description="경도"),
    radius: float = Query(100.0, description="반경(m)"),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    stores = store_service.get_nearby_stores(db, lat, lon, radius, category)
    return {"count": len(stores), "stores": stores}


@router.get("/search")
async def search_stores(
    q: str = Query("", description="검색어"),
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    return store_service.search_stores(db, q, page=pagination["page"], size=pagination["size"])


@router.get("/all")
async def get_all_stores(
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    return store_service.get_all_stores(db, page=pagination["page"], size=pagination["size"])


@router.get("/{store_id}")
async def get_store_detail(
    store_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user_db),
):
    return store_service.get_store_detail(db, store_id, user=user)
