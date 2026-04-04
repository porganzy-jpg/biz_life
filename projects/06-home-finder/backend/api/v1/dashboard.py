"""대시보드 API - 종합 요약, 지도 마커, 최근 활동"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database import get_db
from models.property import Property
from models.transaction import TransactionHistory
from models.auction import AuctionListing
from models.subscription import SubscriptionOpportunity
from models.candidate import CandidateProperty
from models.saved_search import SavedSearch
from repositories.candidate_repo import CandidateRepository
from repositories.property_repo import PropertyRepository
from cache import response_cache

router = APIRouter()


def _score_to_color(score):
    """점수 기반 마커 색상 결정"""
    if score is None:
        return "gray"
    if score >= 80:
        return "green"
    if score >= 60:
        return "blue"
    if score >= 40:
        return "orange"
    return "red"


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """대시보드 종합 요약"""
    # Check cache first (TTL: 300s)
    cache_key = "all"
    cached = response_cache.get("dashboard_summary", cache_key)
    if cached is not None:
        return cached

    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    # Property counts
    total_properties = db.query(Property).count()
    active_properties = db.query(Property).filter(Property.is_active == 1).count()
    land_count = db.query(Property).filter(
        Property.is_active == 1, Property.property_type == "토지"
    ).count()
    building_count = active_properties - land_count

    # Auction counts
    total_auctions = db.query(AuctionListing).count()
    active_auctions = (
        db.query(AuctionListing)
        .filter(AuctionListing.auction_status == "진행중")
        .count()
    )

    # Subscription counts
    total_subscriptions = db.query(SubscriptionOpportunity).count()
    active_subscriptions = (
        db.query(SubscriptionOpportunity)
        .filter(SubscriptionOpportunity.status == "접수중")
        .count()
    )

    # Pipeline counts
    cand_repo = CandidateRepository(db)
    pipeline_counts = cand_repo.get_pipeline_counts()
    pipeline_total = sum(pipeline_counts.values())

    # Price stats for active properties
    price_stats_row = (
        db.query(
            func.avg(Property.price_krw).label("avg_price"),
            func.min(Property.price_krw).label("min_price"),
            func.max(Property.price_krw).label("max_price"),
            func.avg(Property.price_per_m2).label("avg_ppm2"),
        )
        .filter(Property.is_active == 1)
        .filter(Property.price_krw.isnot(None))
        .first()
    )

    price_stats = None
    if price_stats_row and price_stats_row.avg_price:
        price_stats = {
            "avg_price_krw": int(price_stats_row.avg_price),
            "min_price_krw": price_stats_row.min_price,
            "max_price_krw": price_stats_row.max_price,
            "avg_price_per_m2": int(price_stats_row.avg_ppm2) if price_stats_row.avg_ppm2 else None,
            "median_price_krw": None,  # Median requires window function
        }

    # Recent activity counts
    new_properties_7d = (
        db.query(Property)
        .filter(Property.created_at >= seven_days_ago)
        .count()
    )
    new_candidates_7d = (
        db.query(CandidateProperty)
        .filter(CandidateProperty.created_at >= seven_days_ago)
        .count()
    )
    saved_search_count = db.query(SavedSearch).count()

    # Transaction stats (실거래가)
    total_transactions = db.query(TransactionHistory).count()
    land_transactions = db.query(TransactionHistory).filter(
        TransactionHistory.property_type == "토지"
    ).count()
    recent_transactions = (
        db.query(TransactionHistory)
        .filter(TransactionHistory.created_at >= seven_days_ago)
        .count()
    )
    tx_price_stats = (
        db.query(
            func.avg(TransactionHistory.price_krw).label("avg"),
            func.count(TransactionHistory.id).label("cnt"),
        )
        .filter(TransactionHistory.source == "molit")
        .first()
    )
    tx_avg_price = int(tx_price_stats.avg) if tx_price_stats and tx_price_stats.avg else None

    # 구별 최근 평균가 (실거래 기반)
    district_avgs = (
        db.query(
            TransactionHistory.district,
            func.avg(TransactionHistory.price_krw).label("avg_price"),
            func.count(TransactionHistory.id).label("count"),
        )
        .filter(TransactionHistory.source == "molit")
        .group_by(TransactionHistory.district)
        .all()
    )
    district_price_summary = [
        {
            "district": row.district,
            "avg_price_krw": int(row.avg_price),
            "transaction_count": row.count,
        }
        for row in district_avgs
        if row.avg_price
    ]

    # Top candidates (shortlist with scores)
    shortlist = cand_repo.get_shortlist()
    prop_repo = PropertyRepository(db)
    top_candidates = []
    for c in shortlist[:5]:  # Top 5
        entry = {
            "candidate_id": c.id,
            "property_id": c.property_id,
            "status": c.status,
            "priority": c.priority,
        }
        if c.property_id:
            prop = prop_repo.get_by_id(c.property_id)
            if prop:
                entry["complex_name"] = prop.complex_name
                entry["district"] = prop.district
                entry["dong"] = prop.dong
                entry["price_krw"] = prop.price_krw
                entry["area_m2"] = prop.area_m2
                entry["score_composite"] = prop.score_composite
        top_candidates.append(entry)

    result = {
        "total_properties": total_properties,
        "active_properties": active_properties,
        "building_count": building_count,
        "land_count": land_count,
        "total_auctions": total_auctions,
        "active_auctions": active_auctions,
        "total_subscriptions": total_subscriptions,
        "active_subscriptions": active_subscriptions,
        "pipeline": {
            "total": pipeline_total,
            "counts": pipeline_counts,
        },
        "top_candidates": top_candidates,
        "price_stats": price_stats,
        "new_properties_7d": new_properties_7d,
        "new_candidates_7d": new_candidates_7d,
        "saved_search_count": saved_search_count,
        "total_transactions": total_transactions,
        "land_transactions": land_transactions,
        "recent_transactions_7d": recent_transactions,
        "tx_avg_price_krw": tx_avg_price,
        "district_price_summary": district_price_summary,
    }

    # Store in cache (300s TTL)
    response_cache.set("dashboard_summary", cache_key, result, ttl=300)
    return result


# 경기 근교 시군구 대표 좌표
DISTRICT_CENTER_COORDS = {
    # 서울
    "종로구": (37.5735, 126.9790), "중구": (37.5641, 126.9979),
    "용산구": (37.5326, 126.9906), "성동구": (37.5633, 127.0371),
    "광진구": (37.5385, 127.0823), "동대문구": (37.5744, 127.0400),
    "중랑구": (37.6063, 127.0928), "성북구": (37.5894, 127.0167),
    "강북구": (37.6397, 127.0255), "도봉구": (37.6688, 127.0471),
    "노원구": (37.6542, 127.0568), "은평구": (37.6027, 126.9291),
    "서대문구": (37.5791, 126.9368), "마포구": (37.5638, 126.9084),
    "양천구": (37.5170, 126.8665), "강서구": (37.5510, 126.8495),
    "구로구": (37.4954, 126.8875), "금천구": (37.4519, 126.8955),
    "영등포구": (37.5264, 126.8963), "동작구": (37.5124, 126.9393),
    "관악구": (37.4784, 126.9516), "서초구": (37.4837, 127.0324),
    "강남구": (37.5172, 127.0473), "송파구": (37.5146, 127.1059),
    "강동구": (37.5301, 127.1238),
    # 경기 근교
    "하남시": (37.5393, 127.2148), "과천시": (37.4292, 126.9876),
    "광명시": (37.4786, 126.8644), "구리시": (37.5943, 127.1295),
    "남양주시": (37.6360, 127.2164),
    "성남시 분당구": (37.3826, 127.1189), "성남시 수정구": (37.4503, 127.1457),
    "성남시 중원구": (37.4317, 127.1370),
    "고양시 덕양구": (37.6375, 126.8322), "고양시 일산동구": (37.6586, 126.7742),
    "고양시 일산서구": (37.6753, 126.7518),
    "의정부시": (37.7381, 127.0337), "김포시": (37.6153, 126.7156),
    "파주시": (37.7590, 126.7803),
}


@router.get("/map-markers")
def get_map_markers(db: Session = Depends(get_db)):
    """활성 매물 + 실거래 지역 마커 데이터"""
    cache_key = "all"
    cached = response_cache.get("map_markers", cache_key)
    if cached is not None:
        return cached

    # 1) Property 테이블 매물 마커
    properties = (
        db.query(Property)
        .filter(Property.is_active == 1)
        .filter(Property.lat.isnot(None))
        .filter(Property.lng.isnot(None))
        .all()
    )

    candidate_prop_ids = set(
        row[0]
        for row in db.query(CandidateProperty.property_id)
        .filter(CandidateProperty.property_id.isnot(None))
        .all()
    )

    markers = []
    property_districts = set()
    for p in properties:
        if p.district:
            property_districts.add(p.district)
        markers.append({
            "id": p.id,
            "lat": p.lat,
            "lng": p.lng,
            "price_krw": p.price_krw,
            "area_m2": p.area_m2,
            "score_composite": p.score_composite,
            "color": _score_to_color(p.score_composite),
            "label": p.complex_name or p.address or f"매물 {p.id}",
            "property_type": p.property_type,
            "acquisition_type": p.acquisition_type,
            "is_candidate": p.id in candidate_prop_ids,
            "marker_type": "property",
            "land_use": p.land_use,
            "zoning_type": p.zoning_type,
            "building_coverage_ratio": p.building_coverage_ratio,
            "floor_area_ratio": p.floor_area_ratio,
        })

    # 2) 실거래 지역 요약 마커 (Property가 없는 지역만)
    tx_districts = (
        db.query(
            TransactionHistory.district,
            func.avg(TransactionHistory.price_krw).label("avg_price"),
            func.count(TransactionHistory.id).label("tx_count"),
            func.avg(TransactionHistory.area_exclusive).label("avg_area"),
        )
        .filter(TransactionHistory.source == "molit")
        .group_by(TransactionHistory.district)
        .all()
    )

    for row in tx_districts:
        coords = DISTRICT_CENTER_COORDS.get(row.district)
        if not coords:
            continue
        avg_price = int(row.avg_price) if row.avg_price else 0
        markers.append({
            "id": None,
            "lat": coords[0],
            "lng": coords[1],
            "price_krw": avg_price,
            "area_m2": round(row.avg_area, 1) if row.avg_area else None,
            "score_composite": None,
            "color": "gray",
            "label": f"{row.district} ({row.tx_count}건)",
            "property_type": "실거래",
            "acquisition_type": "매매",
            "is_candidate": False,
            "marker_type": "transaction_summary",
            "tx_count": row.tx_count,
            "land_use": None,
            "zoning_type": None,
            "building_coverage_ratio": None,
            "floor_area_ratio": None,
        })

    result = {"markers": markers, "count": len(markers)}
    response_cache.set("map_markers", cache_key, result, ttl=300)
    return result


@router.get("/recent-activity")
def get_recent_activity(
    days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
    limit: int = Query(20, ge=1, le=100, description="조회 건수"),
    db: Session = Depends(get_db),
):
    """최근 활동 내역 (신규 등록, 가격 변동 등)"""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # New properties
    new_properties = (
        db.query(Property)
        .filter(Property.created_at >= cutoff)
        .order_by(desc(Property.created_at))
        .limit(limit)
        .all()
    )

    # Recently updated properties (price changes, etc.)
    updated_properties = (
        db.query(Property)
        .filter(Property.updated_at >= cutoff)
        .filter(Property.updated_at != Property.created_at)
        .order_by(desc(Property.updated_at))
        .limit(limit)
        .all()
    )

    # New candidates
    new_candidates = (
        db.query(CandidateProperty)
        .filter(CandidateProperty.created_at >= cutoff)
        .order_by(desc(CandidateProperty.created_at))
        .limit(limit)
        .all()
    )

    activities = []

    for p in new_properties:
        activities.append({
            "type": "new_property",
            "id": p.id,
            "description": f"신규 매물: {p.complex_name or p.address or '매물 ' + str(p.id)} ({p.district})",
            "price_krw": p.price_krw,
            "timestamp": p.created_at.isoformat() if p.created_at else None,
        })

    for p in updated_properties:
        activities.append({
            "type": "property_updated",
            "id": p.id,
            "description": f"매물 수정: {p.complex_name or p.address or '매물 ' + str(p.id)} ({p.district})",
            "price_krw": p.price_krw,
            "timestamp": p.updated_at.isoformat() if p.updated_at else None,
        })

    for c in new_candidates:
        activities.append({
            "type": "new_candidate",
            "id": c.id,
            "description": f"신규 후보: 후보 ID {c.id} (매물 ID {c.property_id})",
            "timestamp": c.created_at.isoformat() if c.created_at else None,
        })

    # Sort all activities by timestamp descending
    activities.sort(
        key=lambda x: x.get("timestamp") or "",
        reverse=True,
    )

    return {
        "activities": activities[:limit],
        "count": len(activities[:limit]),
        "days": days,
    }
