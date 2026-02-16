"""경매 API"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_pagination
from repositories.auction_repo import AuctionRepository

router = APIRouter()


def _auction_to_dict(a):
    return {
        "id": a.id,
        "case_number": a.case_number,
        "court": a.court,
        "city": a.city,
        "district": a.district,
        "dong": a.dong,
        "address": a.address,
        "lat": a.lat,
        "lng": a.lng,
        "property_type": a.property_type,
        "area_m2": a.area_m2,
        "floor": a.floor,
        "built_year": a.built_year,
        "appraisal_price": a.appraisal_price,
        "minimum_bid": a.minimum_bid,
        "current_bid_round": a.current_bid_round,
        "discount_rate": a.discount_rate,
        "auction_date": a.auction_date.isoformat() if a.auction_date else None,
        "auction_status": a.auction_status,
        "risk_level": a.risk_level,
        "risk_notes": a.risk_notes,
        "occupancy_status": a.occupancy_status,
        "source_url": a.source_url,
        "description": a.description,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _auction_to_deal(a):
    return {
        "id": a.id,
        "case_number": a.case_number,
        "district": a.district,
        "dong": a.dong,
        "address": a.address,
        "property_type": a.property_type,
        "area_m2": a.area_m2,
        "appraisal_price": a.appraisal_price,
        "minimum_bid": a.minimum_bid,
        "discount_rate": a.discount_rate,
        "current_bid_round": a.current_bid_round,
        "auction_date": a.auction_date.isoformat() if a.auction_date else None,
        "auction_status": a.auction_status,
        "risk_level": a.risk_level,
    }


@router.get("/upcoming")
def get_upcoming_auctions(
    days: int = Query(7, ge=1, le=90, description="조회 기간 (일)"),
    db: Session = Depends(get_db),
):
    """다가오는 경매 목록"""
    repo = AuctionRepository(db)
    items = repo.get_upcoming(days=days)
    return {"items": [_auction_to_dict(a) for a in items], "count": len(items), "days": days}


@router.get("/deals")
def get_best_deals(
    min_discount: float = Query(0.3, ge=0, le=1.0, description="최소 할인율 (0~1)"),
    limit: int = Query(20, ge=1, le=100, description="조회 건수"),
    db: Session = Depends(get_db),
):
    """할인율 높은 경매 물건 (알짜 매물)"""
    repo = AuctionRepository(db)
    items = repo.get_best_deals(min_discount_rate=min_discount, limit=limit)
    return {"items": [_auction_to_deal(a) for a in items], "count": len(items)}


@router.get("/")
def list_auctions(
    district: Optional[str] = Query(None, description="구"),
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    """경매 물건 목록 조회"""
    repo = AuctionRepository(db)

    if district:
        items = repo.get_by_district(district, limit=pagination["size"])
    else:
        items = repo.get_all(offset=pagination["offset"], limit=pagination["size"])

    return {
        "items": [_auction_to_dict(a) for a in items],
        "count": len(items),
        "page": pagination["page"],
        "page_size": pagination["size"],
    }


@router.get("/{auction_id}")
def get_auction(auction_id: int, db: Session = Depends(get_db)):
    """경매 물건 상세 조회"""
    repo = AuctionRepository(db)
    auction = repo.get_by_id(auction_id)
    if not auction:
        raise HTTPException(status_code=404, detail=f"경매 ID {auction_id}을(를) 찾을 수 없습니다")
    return _auction_to_dict(auction)
