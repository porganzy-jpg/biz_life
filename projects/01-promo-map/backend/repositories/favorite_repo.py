"""Favorite 리포지토리"""
from sqlalchemy.orm import Session
from models import Favorite
from repositories.base import BaseRepository


class FavoriteRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(Favorite, db)

    def get_by_user(self, user_id: int):
        return self.db.query(Favorite).filter(Favorite.user_id == user_id).all()

    def get_by_user_and_store(self, user_id: int, store_id: int) -> Favorite | None:
        return (
            self.db.query(Favorite)
            .filter(Favorite.user_id == user_id, Favorite.store_id == store_id)
            .first()
        )

    def is_favorited(self, user_id: int, store_id: int) -> bool:
        return self.get_by_user_and_store(user_id, store_id) is not None

    def count_by_user(self, user_id: int) -> int:
        return self.db.query(Favorite).filter(Favorite.user_id == user_id).count()
