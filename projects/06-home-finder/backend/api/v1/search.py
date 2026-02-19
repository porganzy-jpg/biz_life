"""검색 API - 다조건 검색 + 저장된 검색"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from database import get_db
from models.property import Property
from models.complex import Complex
from repositories.property_repo import PropertyRepository
from repositories.saved_search_repo import SavedSearchRepository
from schemas.search import SearchCriteria, SavedSearchCreate
from schemas.common import SortOrder

router = APIRouter()


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
        "direction": p.direction,
        "built_year": p.built_year,
        "score_location": p.score_location,
        "score_price": p.score_price,
        "score_property": p.score_property,
        "score_area": p.score_area,
        "score_composite": p.score_composite,
        "nearest_subway_name": p.nearest_subway_name,
        "nearest_subway_distance": p.nearest_subway_distance,
        "lat": p.lat,
        "lng": p.lng,
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


def _saved_to_dict(s):
    return {
        "id": s.id,
        "name": s.name,
        "criteria_json": s.criteria_json,
        "alert_on_new": s.alert_on_new,
        "alert_on_price_change": s.alert_on_price_change,
        "last_matched_at": s.last_matched_at.isoformat() if s.last_matched_at else None,
        "match_count": s.match_count,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _execute_search(db: Session, criteria: SearchCriteria) -> dict:
    """SearchCriteria를 기반으로 실제 검색 수행"""
    query = db.query(Property)

    # Active filter (default: active only)
    if criteria.is_active is not None:
        query = query.filter(Property.is_active == criteria.is_active)
    else:
        query = query.filter(Property.is_active == 1)

    # Price filter
    if criteria.price_min is not None:
        query = query.filter(Property.price_krw >= criteria.price_min)
    if criteria.price_max is not None:
        query = query.filter(Property.price_krw <= criteria.price_max)

    # Area filter
    if criteria.area_min is not None:
        query = query.filter(Property.area_m2 >= criteria.area_min)
    if criteria.area_max is not None:
        query = query.filter(Property.area_m2 <= criteria.area_max)

    # Location filters
    if criteria.city:
        query = query.filter(Property.city == criteria.city)
    if criteria.districts:
        # Districts may contain both 구 (district) and 시 (city) names
        # e.g. ["마포구", "하남시", "성남시 분당구"]
        district_names = []
        city_names = []
        compound_filters = []
        for d in criteria.districts:
            if " " in d:
                # Compound like "성남시 분당구" -> city + district
                parts = d.split(" ", 1)
                compound_filters.append(
                    (Property.city.contains(parts[0])) & (Property.district == parts[1])
                )
            elif d.endswith("시"):
                city_names.append(d)
            else:
                district_names.append(d)
        conditions = []
        if district_names:
            conditions.append(Property.district.in_(district_names))
        if city_names:
            conditions.append(Property.city.in_(city_names))
        for cf in compound_filters:
            conditions.append(cf)
        if conditions:
            query = query.filter(or_(*conditions))
    if criteria.dongs:
        query = query.filter(Property.dong.in_(criteria.dongs))

    # Property type filter
    if criteria.property_types:
        type_values = [t.value if hasattr(t, "value") else t for t in criteria.property_types]
        query = query.filter(Property.property_type.in_(type_values))
    if criteria.acquisition_types:
        acq_values = [a.value if hasattr(a, "value") else a for a in criteria.acquisition_types]
        query = query.filter(Property.acquisition_type.in_(acq_values))

    # Subway distance
    if criteria.subway_max_distance is not None:
        query = query.filter(Property.nearest_subway_distance <= criteria.subway_max_distance)

    # Score filter
    if criteria.score_min is not None:
        query = query.filter(Property.score_composite >= criteria.score_min)

    # Property detail filters
    if criteria.rooms_min is not None:
        query = query.filter(Property.rooms >= criteria.rooms_min)
    if criteria.floor_min is not None:
        query = query.filter(Property.floor >= criteria.floor_min)
    if criteria.built_year_min is not None:
        query = query.filter(Property.built_year >= criteria.built_year_min)
    if criteria.built_year_max is not None:
        query = query.filter(Property.built_year <= criteria.built_year_max)

    # Direction filter
    if criteria.directions:
        query = query.filter(Property.direction.in_(criteria.directions))

    # Land / Building category filter
    if criteria.property_category == "건물":
        query = query.filter(Property.property_type != "토지")
    elif criteria.property_category == "토지":
        query = query.filter(Property.property_type == "토지")

    # Land-specific filters
    if criteria.land_uses:
        query = query.filter(Property.land_use.in_(criteria.land_uses))
    if criteria.zoning_types:
        query = query.filter(Property.zoning_type.in_(criteria.zoning_types))
    if criteria.min_bcr is not None:
        query = query.filter(Property.building_coverage_ratio >= criteria.min_bcr)
    if criteria.min_far is not None:
        query = query.filter(Property.floor_area_ratio >= criteria.min_far)
    if criteria.road_frontage_types:
        query = query.filter(Property.road_frontage.in_(criteria.road_frontage_types))
    if criteria.topography_types:
        query = query.filter(Property.topography.in_(criteria.topography_types))

    # Total units filter (JOIN Complex)
    if criteria.min_total_units is not None:
        query = query.join(
            Complex, Property.complex_id == Complex.id, isouter=False
        ).filter(Complex.total_units >= criteria.min_total_units)

    # Count before pagination
    total = query.count()

    # Sort
    sort = criteria.sort
    if sort == SortOrder.price_asc:
        query = query.order_by(Property.price_krw.asc())
    elif sort == SortOrder.price_desc:
        query = query.order_by(Property.price_krw.desc())
    elif sort == SortOrder.score_desc:
        query = query.order_by(desc(Property.score_composite))
    elif sort == SortOrder.newest:
        query = query.order_by(desc(Property.created_at))
    elif sort == SortOrder.area_desc:
        query = query.order_by(Property.area_m2.desc())
    else:
        query = query.order_by(desc(Property.score_composite))

    # Pagination
    page = criteria.page
    page_size = criteria.page_size
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return {
        "items": [_prop_to_brief(p) for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.post("/query")
def search_properties(body: SearchCriteria, db: Session = Depends(get_db)):
    """다조건 검색"""
    return _execute_search(db, body)


@router.get("/saved")
def list_saved_searches(db: Session = Depends(get_db)):
    """저장된 검색조건 목록"""
    repo = SavedSearchRepository(db)
    items = repo.get_all(limit=100)
    return {"items": [_saved_to_dict(s) for s in items], "count": len(items)}


@router.post("/saved")
def save_search(body: SavedSearchCreate, db: Session = Depends(get_db)):
    """검색조건 저장"""
    repo = SavedSearchRepository(db)

    # Check for duplicate name
    existing = repo.get_by_name(body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"이름 '{body.name}'은(는) 이미 사용 중입니다")

    criteria_json = body.criteria.model_dump_json()
    saved = repo.create(
        name=body.name,
        criteria_json=criteria_json,
        alert_on_new=1 if body.alert_on_new else 0,
        alert_on_price_change=1 if body.alert_on_price_change else 0,
    )
    return _saved_to_dict(saved)


@router.delete("/saved/{search_id}")
def delete_saved_search(search_id: int, db: Session = Depends(get_db)):
    """저장된 검색조건 삭제"""
    repo = SavedSearchRepository(db)
    saved = repo.get_by_id(search_id)
    if not saved:
        raise HTTPException(status_code=404, detail=f"저장된 검색 ID {search_id}을(를) 찾을 수 없습니다")
    repo.delete(saved)
    return {"message": f"저장된 검색 ID {search_id} 삭제 완료"}


@router.post("/saved/{search_id}/run")
def run_saved_search(search_id: int, db: Session = Depends(get_db)):
    """저장된 검색조건 실행"""
    repo = SavedSearchRepository(db)
    saved = repo.get_by_id(search_id)
    if not saved:
        raise HTTPException(status_code=404, detail=f"저장된 검색 ID {search_id}을(를) 찾을 수 없습니다")

    # Parse criteria from JSON
    criteria_dict = json.loads(saved.criteria_json)
    criteria = SearchCriteria(**criteria_dict)

    # Execute search
    result = _execute_search(db, criteria)

    # Update last_matched_at and match_count
    saved.last_matched_at = datetime.utcnow()
    saved.match_count = result["total"]
    db.commit()

    return {
        "search_id": search_id,
        "search_name": saved.name,
        **result,
    }
