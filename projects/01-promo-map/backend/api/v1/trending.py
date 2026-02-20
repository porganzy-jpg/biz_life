# -*- coding: utf-8 -*-
"""트렌딩/인기 할인 API v1"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from services import trending_service

router = APIRouter(prefix="/trending", tags=["trending"])


@router.get("/discounts")
async def get_trending_discounts(
    days: int = Query(7, ge=1, le=90, description="최근 N일"),
    limit: int = Query(10, ge=1, le=50, description="최대 개수"),
    db: Session = Depends(get_db),
):
    """최근 N일간 인기 할인 랭킹"""
    items = trending_service.get_trending_discounts(db, days=days, limit=limit)
    return {"count": len(items), "days": days, "items": items}


@router.get("/stores")
async def get_popular_stores(
    limit: int = Query(10, ge=1, le=50, description="최대 개수"),
    db: Session = Depends(get_db),
):
    """인기 매장 랭킹 (리뷰 + 평점 + 사용량 종합)"""
    items = trending_service.get_popular_stores(db, limit=limit)
    return {"count": len(items), "items": items}


@router.get("/hot-deals")
async def get_hot_deals(
    limit: int = Query(5, ge=1, le=20, description="최대 개수"),
    db: Session = Depends(get_db),
):
    """핫딜 - 절약 속도(원/일)가 높은 할인"""
    items = trending_service.get_hot_deals(db, limit=limit)
    return {"count": len(items), "items": items}


@router.get("/savings-leaders")
async def get_savings_leaders(
    limit: int = Query(5, ge=1, le=20, description="최대 개수"),
    db: Session = Depends(get_db),
):
    """절약 리더보드 - 총 절약 금액 상위 매장"""
    items = trending_service.get_savings_leaders(db, limit=limit)
    return {"count": len(items), "items": items}
