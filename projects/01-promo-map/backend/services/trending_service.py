# -*- coding: utf-8 -*-
"""
트렌딩/인기 할인 분석 서비스

Usage logs, reviews 테이블 기반 집계로
인기 할인, 인기 매장, 절약 리더보드, 핫딜 등을 제공한다.
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

from models import UsageLog, Review, Store, Discount, Company
from cache import TTLCache

logger = logging.getLogger("promomap.trending")

# 트렌딩 캐시 (3분 TTL)
_trending_cache = TTLCache(maxsize=64, ttl=180)


def get_trending_discounts(db: Session, days: int = 7, limit: int = 10) -> list:
    """
    최근 N일간 사용 횟수(usage_count)가 높은 할인을 랭킹한다.
    반환: [{discount_id, store_name, store_id, brand, category, icon_color, icon_letter,
            discount_type, discount_value, description, valid_until,
            usage_count, company_name}]
    """
    cache_key = ("trending_discounts", days, limit)
    cached = _trending_cache.get(cache_key)
    if cached is not None:
        return cached

    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.query(
            UsageLog.discount_id,
            func.count().label("usage_count"),
        )
        .filter(UsageLog.used_at >= since)
        .group_by(UsageLog.discount_id)
        .order_by(desc("usage_count"))
        .limit(limit)
        .all()
    )

    if not rows:
        _trending_cache[cache_key] = []
        return []

    discount_ids = [r.discount_id for r in rows]
    usage_map = {r.discount_id: r.usage_count for r in rows}

    discounts = (
        db.query(Discount)
        .filter(Discount.id.in_(discount_ids))
        .all()
    )

    # 매장/회사 정보 포함
    results = []
    for d in discounts:
        store = d.store
        company = d.company
        results.append({
            "discount_id": d.id,
            "store_id": d.store_id,
            "store_name": store.name if store else "Unknown",
            "brand": store.brand if store else "",
            "category": store.category if store else "general",
            "icon_color": store.icon_color if store else "#FF6B35",
            "icon_letter": store.icon_letter if store else "S",
            "discount_type": d.discount_type,
            "discount_value": d.discount_value,
            "description": d.description or "",
            "valid_until": d.valid_until.isoformat() if d.valid_until else None,
            "usage_count": usage_map.get(d.id, 0),
            "company_name": company.name if company else "",
        })

    # usage_count 내림차순 정렬 유지
    results.sort(key=lambda x: x["usage_count"], reverse=True)

    _trending_cache[cache_key] = results
    return results


def get_popular_stores(db: Session, limit: int = 10) -> list:
    """
    매장 인기도 = 리뷰 수 * 0.3 + 평균 별점 * 0.4 + 사용 횟수 * 0.3
    (정규화 후 가중합)

    반환: [{store_id, name, brand, category, icon_color, icon_letter,
            address, phone, review_count, avg_rating, usage_count, popularity_score}]
    """
    cache_key = ("popular_stores", limit)
    cached = _trending_cache.get(cache_key)
    if cached is not None:
        return cached

    # 리뷰 집계: store별 count, avg rating
    review_agg = (
        db.query(
            Review.store_id,
            func.count().label("review_count"),
            func.avg(Review.rating).label("avg_rating"),
        )
        .group_by(Review.store_id)
        .subquery()
    )

    # 사용 집계: store별 usage count
    usage_agg = (
        db.query(
            UsageLog.store_id,
            func.count().label("usage_count"),
        )
        .group_by(UsageLog.store_id)
        .subquery()
    )

    rows = (
        db.query(
            Store,
            func.coalesce(review_agg.c.review_count, 0).label("review_count"),
            func.coalesce(review_agg.c.avg_rating, 0).label("avg_rating"),
            func.coalesce(usage_agg.c.usage_count, 0).label("usage_count"),
        )
        .outerjoin(review_agg, Store.id == review_agg.c.store_id)
        .outerjoin(usage_agg, Store.id == usage_agg.c.store_id)
        .filter(Store.is_active == True, Store.deleted_at == None)  # noqa: E712
        .all()
    )

    if not rows:
        _trending_cache[cache_key] = []
        return []

    # 정규화를 위한 최대값 산출
    max_reviews = max((r.review_count for r in rows), default=1) or 1
    max_rating = 5.0
    max_usage = max((r.usage_count for r in rows), default=1) or 1

    items = []
    for store, review_count, avg_rating, usage_count in rows:
        norm_reviews = review_count / max_reviews
        norm_rating = float(avg_rating) / max_rating
        norm_usage = usage_count / max_usage
        score = norm_reviews * 0.3 + norm_rating * 0.4 + norm_usage * 0.3

        items.append({
            "store_id": store.id,
            "name": store.name,
            "brand": store.brand,
            "category": store.category,
            "icon_color": store.icon_color,
            "icon_letter": store.icon_letter,
            "address": store.address,
            "phone": store.phone,
            "review_count": review_count,
            "avg_rating": round(float(avg_rating), 1) if avg_rating else 0,
            "usage_count": usage_count,
            "popularity_score": round(score, 3),
        })

    items.sort(key=lambda x: x["popularity_score"], reverse=True)
    results = items[:limit]

    _trending_cache[cache_key] = results
    return results


def get_savings_leaders(db: Session, limit: int = 5) -> list:
    """
    매장별 총 절약 금액이 높은 상위 N개 매장.

    반환: [{store_id, name, brand, category, icon_color, icon_letter,
            total_saved, usage_count}]
    """
    cache_key = ("savings_leaders", limit)
    cached = _trending_cache.get(cache_key)
    if cached is not None:
        return cached

    rows = (
        db.query(
            UsageLog.store_id,
            func.sum(UsageLog.saved_amount).label("total_saved"),
            func.count().label("usage_count"),
        )
        .group_by(UsageLog.store_id)
        .order_by(desc("total_saved"))
        .limit(limit)
        .all()
    )

    if not rows:
        _trending_cache[cache_key] = []
        return []

    store_ids = [r.store_id for r in rows]
    stores = db.query(Store).filter(Store.id.in_(store_ids)).all()
    store_map = {s.id: s for s in stores}

    results = []
    for r in rows:
        store = store_map.get(r.store_id)
        results.append({
            "store_id": r.store_id,
            "name": store.name if store else "Unknown",
            "brand": store.brand if store else "",
            "category": store.category if store else "general",
            "icon_color": store.icon_color if store else "#FF6B35",
            "icon_letter": store.icon_letter if store else "S",
            "total_saved": round(float(r.total_saved or 0), 0),
            "usage_count": r.usage_count,
        })

    _trending_cache[cache_key] = results
    return results


def get_hot_deals(db: Session, limit: int = 5) -> list:
    """
    최근 7일간 절약 속도(원/일)가 가장 높은 할인.
    velocity = total_saved / days_active

    반환: [{discount_id, store_id, store_name, brand, category,
            icon_color, icon_letter, discount_value, description,
            valid_until, total_saved, usage_count, velocity}]
    """
    cache_key = ("hot_deals", limit)
    cached = _trending_cache.get(cache_key)
    if cached is not None:
        return cached

    since = datetime.utcnow() - timedelta(days=7)

    rows = (
        db.query(
            UsageLog.discount_id,
            func.sum(UsageLog.saved_amount).label("total_saved"),
            func.count().label("usage_count"),
            func.min(UsageLog.used_at).label("first_use"),
            func.max(UsageLog.used_at).label("last_use"),
        )
        .filter(UsageLog.used_at >= since)
        .group_by(UsageLog.discount_id)
        .all()
    )

    if not rows:
        _trending_cache[cache_key] = []
        return []

    now = datetime.utcnow()
    items = []
    for r in rows:
        total_saved = float(r.total_saved or 0)
        if total_saved <= 0:
            continue
        # 활성 기간 (최소 1일)
        first_use = r.first_use or now
        days_active = max((now - first_use).total_seconds() / 86400, 1.0)
        velocity = total_saved / days_active
        items.append({
            "discount_id": r.discount_id,
            "total_saved": round(total_saved, 0),
            "usage_count": r.usage_count,
            "velocity": round(velocity, 0),
        })

    items.sort(key=lambda x: x["velocity"], reverse=True)
    top = items[:limit]

    discount_ids = [i["discount_id"] for i in top]
    discounts = db.query(Discount).filter(Discount.id.in_(discount_ids)).all()
    disc_map = {d.id: d for d in discounts}

    results = []
    for item in top:
        d = disc_map.get(item["discount_id"])
        if not d:
            continue
        store = d.store
        results.append({
            "discount_id": d.id,
            "store_id": d.store_id,
            "store_name": store.name if store else "Unknown",
            "brand": store.brand if store else "",
            "category": store.category if store else "general",
            "icon_color": store.icon_color if store else "#FF6B35",
            "icon_letter": store.icon_letter if store else "S",
            "discount_value": d.discount_value,
            "description": d.description or "",
            "valid_until": d.valid_until.isoformat() if d.valid_until else None,
            "total_saved": item["total_saved"],
            "usage_count": item["usage_count"],
            "velocity": item["velocity"],
        })

    _trending_cache[cache_key] = results
    return results


def get_store_usage_counts(db: Session, store_ids: list) -> dict:
    """
    주어진 매장 ID 목록에 대해 각 매장의 총 사용 횟수를 반환.
    반환: {store_id: usage_count, ...}
    """
    if not store_ids:
        return {}

    rows = (
        db.query(
            UsageLog.store_id,
            func.count().label("usage_count"),
        )
        .filter(UsageLog.store_id.in_(store_ids))
        .group_by(UsageLog.store_id)
        .all()
    )

    return {r.store_id: r.usage_count for r in rows}
