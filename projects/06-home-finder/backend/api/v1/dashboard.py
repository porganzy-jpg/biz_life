"""대시보드 API - 종합 요약, 지도 마커, 최근 활동"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database import get_db
from models.property import Property
from models.auction import AuctionListing
from models.subscription import SubscriptionOpportunity
from models.candidate import CandidateProperty
from models.saved_search import SavedSearch
from repositories.candidate_repo import CandidateRepository
from repositories.property_repo import PropertyRepository

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
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    # Property counts
    total_properties = db.query(Property).count()
    active_properties = db.query(Property).filter(Property.is_active == 1).count()

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

    return {
        "total_properties": total_properties,
        "active_properties": active_properties,
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
    }


@router.get("/map-markers")
def get_map_markers(db: Session = Depends(get_db)):
    """활성 매물 지도 마커 데이터"""
    properties = (
        db.query(Property)
        .filter(Property.is_active == 1)
        .filter(Property.lat.isnot(None))
        .filter(Property.lng.isnot(None))
        .all()
    )

    # Get candidate property_ids for "is_candidate" flag
    candidate_prop_ids = set(
        row[0]
        for row in db.query(CandidateProperty.property_id)
        .filter(CandidateProperty.property_id.isnot(None))
        .all()
    )

    markers = []
    for p in properties:
        markers.append({
            "id": p.id,
            "lat": p.lat,
            "lng": p.lng,
            "price_krw": p.price_krw,
            "score_composite": p.score_composite,
            "color": _score_to_color(p.score_composite),
            "label": p.complex_name or p.address or f"매물 {p.id}",
            "property_type": p.property_type,
            "acquisition_type": p.acquisition_type,
            "is_candidate": p.id in candidate_prop_ids,
        })

    return {"markers": markers, "count": len(markers)}


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
