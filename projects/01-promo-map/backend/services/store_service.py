"""매장 서비스"""
import logging
from sqlalchemy.orm import Session
from models import User
from repositories.store_repo import StoreRepository
from repositories.discount_repo import DiscountRepository
from repositories.favorite_repo import FavoriteRepository
from repositories.review_repo import ReviewRepository
from geofence import find_nearby_stores, get_bounding_box
from exceptions import NotFoundException
from cache import (
    nearby_stores_cache, store_detail_cache,
    _lat_lon_grid_key,
)
from services.trending_service import get_store_usage_counts

logger = logging.getLogger("promomap.cache")


def get_nearby_stores(db: Session, lat: float, lon: float, radius: float = 100.0,
                      category: str = None) -> list:
    # --- Cache lookup (keyed by snapped grid cell) ---
    cache_key = _lat_lon_grid_key(lat, lon, radius, category)
    cached = nearby_stores_cache.get(cache_key)
    if cached is not None:
        logger.debug("nearby_stores cache HIT: %s", cache_key)
        return cached

    store_repo = StoreRepository(db)
    discount_repo = DiscountRepository(db)
    bbox = get_bounding_box(lat, lon, radius)

    stores = store_repo.get_by_bounding_box(
        bbox["min_lat"], bbox["max_lat"],
        bbox["min_lon"], bbox["max_lon"],
        category=category,
    )

    nearby = find_nearby_stores(lat, lon, stores, radius)

    # Batch fetch discounts for all nearby stores (avoids N+1 queries)
    store_ids = [store.id for store, _ in nearby]
    discounts_map = discount_repo.get_active_by_store_ids(store_ids)

    # Batch fetch usage counts for usage badges
    usage_counts = get_store_usage_counts(db, store_ids)

    results = []
    for store, distance in nearby:
        discounts = discounts_map.get(store.id, [])
        results.append({
            "id": store.id,
            "name": store.name,
            "brand": store.brand,
            "category": store.category,
            "address": store.address,
            "latitude": store.latitude,
            "longitude": store.longitude,
            "phone": store.phone,
            "icon_color": store.icon_color,
            "icon_letter": store.icon_letter,
            "distance_m": distance,
            "usage_count": usage_counts.get(store.id, 0),
            "discounts": [
                {"id": d.id, "type": d.discount_type, "value": d.discount_value, "description": d.description,
                 "valid_until": d.valid_until.isoformat() if d.valid_until else None}
                for d in discounts
            ],
        })

    nearby_stores_cache[cache_key] = results
    logger.debug("nearby_stores cache MISS -> stored: %s", cache_key)
    return results


def search_stores(db: Session, keyword: str, page: int = 1, size: int = 20) -> dict:
    store_repo = StoreRepository(db)
    offset = (page - 1) * size
    stores = store_repo.search(keyword, offset=offset, limit=size)
    total = store_repo.search_count(keyword)
    return {
        "items": [
            {
                "id": s.id, "name": s.name, "brand": s.brand,
                "category": s.category, "address": s.address,
                "latitude": s.latitude, "longitude": s.longitude,
                "phone": s.phone, "icon_color": s.icon_color, "icon_letter": s.icon_letter,
                "discounts": [],
            }
            for s in stores
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if total > 0 else 1,
    }


def get_all_stores(db: Session, page: int = 1, size: int = 20) -> dict:
    store_repo = StoreRepository(db)
    offset = (page - 1) * size
    stores = store_repo.get_active(offset=offset, limit=size)
    total = store_repo.count_active()
    return {
        "items": [
            {
                "id": s.id, "name": s.name, "brand": s.brand,
                "category": s.category, "address": s.address,
                "latitude": s.latitude, "longitude": s.longitude,
                "phone": s.phone, "icon_color": s.icon_color, "icon_letter": s.icon_letter,
                "discounts": [],
            }
            for s in stores
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if total > 0 else 1,
    }


def get_store_detail(db: Session, store_id: int, user: User = None) -> dict:
    # --- Cache lookup (store data without user-specific fields) ---
    cached_detail = store_detail_cache.get(store_id)

    if cached_detail is not None:
        logger.debug("store_detail cache HIT: store_id=%s", store_id)
        detail = dict(cached_detail)  # shallow copy so we can mutate is_favorited
    else:
        store_repo = StoreRepository(db)
        discount_repo = DiscountRepository(db)
        review_repo = ReviewRepository(db)

        store = store_repo.get_by_id(store_id)
        if not store or store.deleted_at:
            raise NotFoundException("Store not found")

        discounts = discount_repo.get_active_by_store(store.id)
        reviews_count = review_repo.count_by_store(store.id)
        avg_rating = review_repo.avg_rating_by_store(store.id)

        detail = {
            "id": store.id,
            "name": store.name,
            "brand": store.brand,
            "category": store.category,
            "address": store.address,
            "latitude": store.latitude,
            "longitude": store.longitude,
            "phone": store.phone,
            "icon_color": store.icon_color,
            "icon_letter": store.icon_letter,
            "discounts": [
                {"id": d.id, "type": d.discount_type, "value": d.discount_value, "description": d.description,
                 "valid_until": d.valid_until.isoformat() if d.valid_until else None}
                for d in discounts
            ],
            "reviews_count": reviews_count,
            "avg_rating": avg_rating,
            "is_favorited": False,
        }
        store_detail_cache[store_id] = detail
        logger.debug("store_detail cache MISS -> stored: store_id=%s", store_id)
        detail = dict(detail)  # copy for safe mutation below

    # is_favorited is user-specific, always computed live (cheap single query)
    is_favorited = False
    if user:
        fav_repo = FavoriteRepository(db)
        is_favorited = fav_repo.is_favorited(user.id, store_id)
    detail["is_favorited"] = is_favorited

    return detail
