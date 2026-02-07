"""즐겨찾기 서비스"""
from sqlalchemy.orm import Session
from models import User
from repositories.favorite_repo import FavoriteRepository
from repositories.store_repo import StoreRepository
from exceptions import NotFoundException, DuplicateException


def get_favorites(db: Session, user: User) -> list:
    fav_repo = FavoriteRepository(db)
    favorites = fav_repo.get_by_user(user.id)
    return [
        {
            "id": f.id,
            "store_id": f.store.id,
            "store_name": f.store.name,
            "store_brand": f.store.brand,
            "store_category": f.store.category,
            "icon_color": f.store.icon_color,
            "icon_letter": f.store.icon_letter,
        }
        for f in favorites if f.store
    ]


def add_favorite(db: Session, user: User, store_id: int) -> dict:
    store_repo = StoreRepository(db)
    fav_repo = FavoriteRepository(db)

    store = store_repo.get_by_id(store_id)
    if not store or store.deleted_at:
        raise NotFoundException("Store not found")

    if fav_repo.is_favorited(user.id, store_id):
        raise DuplicateException("Already favorited")

    fav = fav_repo.create(user_id=user.id, store_id=store_id)
    return {
        "id": fav.id,
        "store_id": store.id,
        "store_name": store.name,
        "store_brand": store.brand,
        "store_category": store.category,
        "icon_color": store.icon_color,
        "icon_letter": store.icon_letter,
    }


def remove_favorite(db: Session, user: User, store_id: int):
    fav_repo = FavoriteRepository(db)
    fav = fav_repo.get_by_user_and_store(user.id, store_id)
    if not fav:
        raise NotFoundException("Favorite not found")
    fav_repo.delete(fav)
