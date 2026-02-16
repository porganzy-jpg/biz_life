"""아파트 단지 API"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from repositories.complex_repo import ComplexRepository
from repositories.transaction_repo import TransactionRepository
from exceptions import NotFoundException

router = APIRouter()


def _complex_to_dict(c):
    return {
        "id": c.id,
        "name": c.name,
        "city": c.city,
        "district": c.district,
        "dong": c.dong,
        "address": c.address,
        "lat": c.lat,
        "lng": c.lng,
        "built_year": c.built_year,
        "total_units": c.total_units,
        "total_buildings": c.total_buildings,
        "parking_ratio": c.parking_ratio,
        "heating_type": c.heating_type,
        "developer": c.developer,
        "avg_price_per_m2": c.avg_price_per_m2,
        "min_price": c.min_price,
        "max_price": c.max_price,
        "price_trend_1y": c.price_trend_1y,
        "reconstruction_status": c.reconstruction_status,
        "reconstruction_year": c.reconstruction_year,
        "description": c.description,
        "source_id": c.source_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _tx_to_dict(t):
    return {
        "id": t.id,
        "city": t.city,
        "district": t.district,
        "dong": t.dong,
        "name": t.name,
        "address": t.address,
        "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
        "price_krw": t.price_krw,
        "area_exclusive": t.area_exclusive,
        "floor": t.floor,
        "built_year": t.built_year,
        "property_type": t.property_type,
        "price_per_m2": t.price_per_m2,
        "source": t.source,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("/")
def search_complexes(
    keyword: Optional[str] = Query(None, description="단지명 검색어"),
    district: Optional[str] = Query(None, description="구"),
    db: Session = Depends(get_db),
):
    """단지 검색 (키워드 또는 구)"""
    repo = ComplexRepository(db)

    if keyword:
        items = repo.search_by_name(keyword)
    elif district:
        items = repo.get_by_district(district)
    else:
        items = repo.get_all(limit=50)

    return {"items": [_complex_to_dict(c) for c in items], "count": len(items)}


@router.get("/{complex_id}")
def get_complex(complex_id: int, db: Session = Depends(get_db)):
    """단지 상세 조회"""
    repo = ComplexRepository(db)
    c = repo.get_by_id(complex_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"단지 ID {complex_id}을(를) 찾을 수 없습니다")
    return _complex_to_dict(c)


@router.get("/{complex_id}/prices")
def get_complex_prices(
    complex_id: int,
    months: int = Query(12, ge=1, le=60, description="조회 개월 수"),
    db: Session = Depends(get_db),
):
    """단지 실거래 가격 이력"""
    complex_repo = ComplexRepository(db)
    c = complex_repo.get_by_id(complex_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"단지 ID {complex_id}을(를) 찾을 수 없습니다")

    tx_repo = TransactionRepository(db)
    transactions = tx_repo.get_by_name(c.name, months_back=months)

    return {
        "complex_id": complex_id,
        "complex_name": c.name,
        "district": c.district,
        "months": months,
        "transactions": [_tx_to_dict(t) for t in transactions],
        "count": len(transactions),
    }
