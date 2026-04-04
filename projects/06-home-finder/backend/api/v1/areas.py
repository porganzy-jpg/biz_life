"""지역(구/동) API"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.transaction import TransactionHistory
from repositories.area_repo import AreaRepository
from exceptions import NotFoundException
from cache import response_cache, make_cache_key

router = APIRouter()


def _area_to_dict(a):
    return {
        "id": a.id,
        "city": a.city,
        "district": a.district,
        "dong": a.dong,
        "area_code": a.area_code,
        "population": a.population,
        "households": a.households,
        "subway_count": a.subway_count,
        "park_count": a.park_count,
        "school_count": a.school_count,
        "hospital_count": a.hospital_count,
        "avg_price_per_m2": a.avg_price_per_m2,
        "price_change_1y": a.price_change_1y,
        "price_change_3y": a.price_change_3y,
        "development_plan": a.development_plan,
        "development_score": a.development_score,
        "living_score": a.living_score,
        "infra_score": a.infra_score,
        "area_composite_score": a.area_composite_score,
        "description": a.description,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _area_to_comparison(a):
    return {
        "district": a.district,
        "dong": a.dong,
        "avg_price_per_m2": a.avg_price_per_m2,
        "price_change_1y": a.price_change_1y,
        "price_change_3y": a.price_change_3y,
        "population": a.population,
        "households": a.households,
        "subway_count": a.subway_count,
        "park_count": a.park_count,
        "school_count": a.school_count,
        "hospital_count": a.hospital_count,
        "development_score": a.development_score,
        "living_score": a.living_score,
        "infra_score": a.infra_score,
        "area_composite_score": a.area_composite_score,
    }


@router.get("/compare")
def compare_districts(
    district1: str = Query(..., description="비교 대상 구 1"),
    district2: str = Query(..., description="비교 대상 구 2"),
    db: Session = Depends(get_db),
):
    """두 지역(구) 비교"""
    # Check cache first (TTL: 1800s) - use sorted key so order doesn't matter
    sorted_districts = tuple(sorted([district1, district2]))
    cache_key = make_cache_key("compare", d1=sorted_districts[0], d2=sorted_districts[1])
    cached = response_cache.get("area_stats", cache_key)
    if cached is not None:
        return cached

    repo = AreaRepository(db)

    areas1 = repo.get_by_district(district1)
    areas2 = repo.get_by_district(district2)

    if not areas1:
        raise HTTPException(status_code=404, detail=f"지역 '{district1}'을(를) 찾을 수 없습니다")
    if not areas2:
        raise HTTPException(status_code=404, detail=f"지역 '{district2}'을(를) 찾을 수 없습니다")

    result = {
        "district1": _area_to_comparison(areas1[0]),
        "district2": _area_to_comparison(areas2[0]),
    }

    # Store in cache (1800s TTL)
    response_cache.set("area_stats", cache_key, result, ttl=1800)
    return result


@router.get("/")
def list_districts(db: Session = Depends(get_db)):
    """전체 구 목록 조회"""
    repo = AreaRepository(db)
    districts = repo.get_all_districts()
    return {"districts": districts, "count": len(districts)}


@router.get("/{district}")
def get_area_profile(district: str, db: Session = Depends(get_db)):
    """지역(구) 프로필 조회"""
    # Check cache first (TTL: 1800s)
    cache_key = make_cache_key("profile", district=district)
    cached = response_cache.get("area_stats", cache_key)
    if cached is not None:
        return cached

    repo = AreaRepository(db)
    areas = repo.get_by_district(district)
    if not areas:
        raise HTTPException(status_code=404, detail=f"지역 '{district}'을(를) 찾을 수 없습니다")

    result = {
        "district": district,
        "areas": [_area_to_dict(a) for a in areas],
        "count": len(areas),
    }

    # Store in cache (1800s TTL)
    response_cache.set("area_stats", cache_key, result, ttl=1800)
    return result


@router.get("/realtime-stats")
def get_realtime_district_stats(db: Session = Depends(get_db)):
    """실거래 데이터 기반 구별 실시간 통계"""
    rows = (
        db.query(
            TransactionHistory.district,
            func.avg(TransactionHistory.price_krw).label("avg_price"),
            func.avg(TransactionHistory.price_per_m2).label("avg_ppm2"),
            func.min(TransactionHistory.price_krw).label("min_price"),
            func.max(TransactionHistory.price_krw).label("max_price"),
            func.count(TransactionHistory.id).label("tx_count"),
        )
        .filter(TransactionHistory.source == "molit")
        .group_by(TransactionHistory.district)
        .all()
    )

    districts = []
    for r in rows:
        districts.append({
            "district": r.district,
            "avg_price_krw": int(r.avg_price) if r.avg_price else 0,
            "avg_price_per_m2": int(r.avg_ppm2) if r.avg_ppm2 else 0,
            "min_price_krw": r.min_price,
            "max_price_krw": r.max_price,
            "transaction_count": r.tx_count,
        })

    districts.sort(key=lambda x: x["avg_price_krw"], reverse=True)
    return {"districts": districts, "count": len(districts)}
