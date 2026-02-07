"""알림 서비스"""
from sqlalchemy.orm import Session
from models import User
from repositories.store_repo import StoreRepository
from repositories.discount_repo import DiscountRepository
from geofence import find_nearby_stores, get_bounding_box


def check_geofence(db: Session, lat: float, lon: float, user: User = None) -> list:
    store_repo = StoreRepository(db)
    radius = 100.0
    bbox = get_bounding_box(lat, lon, radius)

    stores = store_repo.get_by_bounding_box(
        bbox["min_lat"], bbox["max_lat"],
        bbox["min_lon"], bbox["max_lon"],
    )
    nearby = find_nearby_stores(lat, lon, stores, radius)

    notifications = []
    for store, distance in nearby:
        discount_repo = DiscountRepository(db)
        discounts = discount_repo.get_active_by_store(store.id)

        # 사용자 회사 할인만 필터
        if user and user.company_id:
            discounts = [d for d in discounts if d.company_id == user.company_id]

        for disc in discounts:
            notifications.append({
                "store_name": store.name,
                "store_id": store.id,
                "brand": store.brand,
                "distance_m": distance,
                "discount_id": disc.id,
                "discount_value": disc.discount_value,
                "discount_type": disc.discount_type,
                "description": disc.description,
                "icon_color": store.icon_color,
                "icon_letter": store.icon_letter,
            })

    return notifications
