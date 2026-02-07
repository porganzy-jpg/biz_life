"""매장 서비스"""
from sqlalchemy.orm import Session
from models import User
from repositories.store_repo import StoreRepository
from repositories.discount_repo import DiscountRepository
from repositories.favorite_repo import FavoriteRepository
from repositories.review_repo import ReviewRepository
from geofence import find_nearby_stores, get_bounding_box
from exceptions import NotFoundException


def get_nearby_stores(db: Session, lat: float, lon: float, radius: float = 100.0,
                      category: str = None) -> list:
    store_repo = StoreRepository(db)
    discount_repo = DiscountRepository(db)
    bbox = get_bounding_box(lat, lon, radius)

    stores = store_repo.get_by_bounding_box(
        bbox["min_lat"], bbox["max_lat"],
        bbox["min_lon"], bbox["max_lon"],
        category=category,
    )

    nearby = find_nearby_stores(lat, lon, stores, radius)

    results = []
    for store, distance in nearby:
        discounts = discount_repo.get_active_by_store(store.id)
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
            "discounts": [
                {"id": d.id, "type": d.discount_type, "value": d.discount_value, "description": d.description}
                for d in discounts
            ],
        })
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
    store_repo = StoreRepository(db)
    discount_repo = DiscountRepository(db)
    review_repo = ReviewRepository(db)

    store = store_repo.get_by_id(store_id)
    if not store or store.deleted_at:
        raise NotFoundException("Store not found")

    discounts = discount_repo.get_active_by_store(store.id)
    reviews_count = review_repo.count_by_store(store.id)
    avg_rating = review_repo.avg_rating_by_store(store.id)

    is_favorited = False
    if user:
        fav_repo = FavoriteRepository(db)
        is_favorited = fav_repo.is_favorited(user.id, store.id)

    return {
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
            {"id": d.id, "type": d.discount_type, "value": d.discount_value, "description": d.description}
            for d in discounts
        ],
        "reviews_count": reviews_count,
        "avg_rating": avg_rating,
        "is_favorited": is_favorited,
    }
