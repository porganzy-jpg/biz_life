"""매물 API - CRUD + 스코어링"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_pagination
from services.property_service import PropertyService
from services.scoring_service import ScoringService
from scoring.composite_scorer import CompositeScorer
from schemas.property import PropertyCreate, PropertyUpdate
from exceptions import NotFoundException
from cache import response_cache, make_cache_key

router = APIRouter()


def _prop_to_dict(p):
    return {
        "id": p.id,
        "source": p.source,
        "property_type": p.property_type,
        "acquisition_type": p.acquisition_type,
        "city": p.city,
        "district": p.district,
        "dong": p.dong,
        "address": p.address,
        "detail_address": p.detail_address,
        "lat": p.lat,
        "lng": p.lng,
        "price_krw": p.price_krw,
        "price_per_m2": p.price_per_m2,
        "area_m2": p.area_m2,
        "area_supply_m2": p.area_supply_m2,
        "floor": p.floor,
        "total_floors": p.total_floors,
        "rooms": p.rooms,
        "bathrooms": p.bathrooms,
        "direction": p.direction,
        "built_year": p.built_year,
        "maintenance_fee": p.maintenance_fee,
        "complex_name": p.complex_name,
        "complex_id": p.complex_id,
        # Land fields
        "land_use": p.land_use,
        "zoning_type": p.zoning_type,
        "building_coverage_ratio": p.building_coverage_ratio,
        "floor_area_ratio": p.floor_area_ratio,
        "road_frontage": p.road_frontage,
        "topography": p.topography,
        "score_location": p.score_location,
        "score_price": p.score_price,
        "score_property": p.score_property,
        "score_area": p.score_area,
        "score_composite": p.score_composite,
        "nearest_subway_name": p.nearest_subway_name,
        "nearest_subway_distance": p.nearest_subway_distance,
        "nearest_subway_lines": p.nearest_subway_lines,
        "nearest_park_name": p.nearest_park_name,
        "nearest_park_distance": p.nearest_park_distance,
        "nearest_river_distance": p.nearest_river_distance,
        "source_url": p.source_url,
        "source_id": p.source_id,
        "description": p.description,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "scored_at": p.scored_at.isoformat() if p.scored_at else None,
    }


def _prop_to_brief(p):
    return {
        "id": p.id,
        "property_type": p.property_type,
        "acquisition_type": p.acquisition_type,
        "district": p.district,
        "dong": p.dong,
        "address": p.address,
        "complex_name": p.complex_name,
        "price_krw": p.price_krw,
        "area_m2": p.area_m2,
        "floor": p.floor,
        "rooms": p.rooms,
        "built_year": p.built_year,
        "score_composite": p.score_composite,
        "nearest_subway_name": p.nearest_subway_name,
        "nearest_subway_distance": p.nearest_subway_distance,
        # Land fields
        "land_use": p.land_use,
        "zoning_type": p.zoning_type,
        "building_coverage_ratio": p.building_coverage_ratio,
        "floor_area_ratio": p.floor_area_ratio,
        "road_frontage": p.road_frontage,
        "topography": p.topography,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/top")
def get_top_properties(
    limit: int = Query(20, ge=1, le=100, description="조회 건수"),
    db: Session = Depends(get_db),
):
    """종합점수 상위 매물 조회"""
    # Check cache first (TTL: 600s)
    cache_key = make_cache_key("top", limit=limit)
    cached = response_cache.get("top_properties", cache_key)
    if cached is not None:
        return cached

    svc = PropertyService(db)
    items = svc.get_top_scored(limit=limit)
    result = {"items": [_prop_to_brief(p) for p in items], "count": len(items)}

    # Store in cache (600s TTL)
    response_cache.set("top_properties", cache_key, result, ttl=600)
    return result


@router.get("/")
def list_properties(
    district: Optional[str] = Query(None, description="구"),
    property_type: Optional[str] = Query(None, description="매물 유형"),
    price_min: Optional[int] = Query(None, ge=0, description="최소 가격 (원)"),
    price_max: Optional[int] = Query(None, ge=0, description="최대 가격 (원)"),
    area_min: Optional[float] = Query(None, gt=0, description="최소 면적 (m2)"),
    area_max: Optional[float] = Query(None, gt=0, description="최대 면적 (m2)"),
    score_min: Optional[float] = Query(None, ge=0, description="최소 종합 점수"),
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    """매물 목록 조회 (필터 + 페이지네이션)"""
    svc = PropertyService(db)
    result = svc.search_properties(
        district=district,
        property_type=property_type,
        price_min=price_min,
        price_max=price_max,
        area_min=area_min,
        area_max=area_max,
        score_min=score_min,
        page=pagination["page"],
        size=pagination["size"],
    )
    total = result["total"]
    page = pagination["page"]
    size = pagination["size"]
    total_pages = (total + size - 1) // size if size > 0 else 0

    return {
        "items": [_prop_to_brief(p) for p in result["items"]],
        "total": total,
        "page": page,
        "page_size": size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.get("/{property_id}")
def get_property(property_id: int, db: Session = Depends(get_db)):
    """매물 상세 조회"""
    svc = PropertyService(db)
    try:
        prop = svc.get_property(property_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e.detail))
    return _prop_to_dict(prop)


@router.post("/")
def create_property(body: PropertyCreate, db: Session = Depends(get_db)):
    """매물 생성"""
    svc = PropertyService(db)
    data = body.model_dump(exclude_none=True)
    # Convert enums to string values
    for key in ("source", "property_type", "acquisition_type"):
        if key in data and hasattr(data[key], "value"):
            data[key] = data[key].value
    prop = svc.create_property(data)

    # Invalidate property-dependent caches
    response_cache.invalidate_on_property_change()

    return _prop_to_dict(prop)


@router.put("/{property_id}")
def update_property(
    property_id: int, body: PropertyUpdate, db: Session = Depends(get_db)
):
    """매물 수정"""
    svc = PropertyService(db)
    data = body.model_dump(exclude_none=True)
    for key in ("property_type", "acquisition_type"):
        if key in data and hasattr(data[key], "value"):
            data[key] = data[key].value
    try:
        prop = svc.update_property(property_id, data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e.detail))

    # Invalidate property-dependent caches
    response_cache.invalidate_on_property_change()

    return _prop_to_dict(prop)


@router.delete("/{property_id}")
def deactivate_property(property_id: int, db: Session = Depends(get_db)):
    """매물 비활성화 (소프트 삭제)"""
    svc = PropertyService(db)
    try:
        svc.deactivate_property(property_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e.detail))

    # Invalidate property-dependent caches
    response_cache.invalidate_on_property_change()

    return {"message": f"매물 ID {property_id} 비활성화 완료"}


@router.post("/{property_id}/score")
def score_property(property_id: int, db: Session = Depends(get_db)):
    """단일 매물 재채점"""
    from api.v1.scoring import _scorer, _ensure_scorer_reference
    _ensure_scorer_reference(db)
    svc = ScoringService(db, _scorer)
    try:
        result = svc.score_property(property_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e.detail))

    # Invalidate property-dependent caches (scores affect rankings)
    response_cache.invalidate_on_property_change()

    return {
        "property_id": property_id,
        "scores": result,
    }
