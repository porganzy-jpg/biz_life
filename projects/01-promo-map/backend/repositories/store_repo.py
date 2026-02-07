"""Store 리포지토리"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Store
from repositories.base import BaseRepository


class StoreRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(Store, db)

    def get_active(self, offset: int = 0, limit: int = 20):
        return (
            self.db.query(Store)
            .filter(Store.is_active == True, Store.deleted_at == None)
            .offset(offset).limit(limit).all()
        )

    def count_active(self) -> int:
        return self.db.query(Store).filter(Store.is_active == True, Store.deleted_at == None).count()

    def get_by_bounding_box(self, min_lat, max_lat, min_lon, max_lon, category=None):
        query = self.db.query(Store).filter(
            Store.latitude.between(min_lat, max_lat),
            Store.longitude.between(min_lon, max_lon),
            Store.is_active == True,
            Store.deleted_at == None,
        )
        if category:
            query = query.filter(Store.category == category)
        return query.all()

    def search(self, keyword: str, offset: int = 0, limit: int = 20):
        pattern = f"%{keyword}%"
        return (
            self.db.query(Store)
            .filter(
                Store.is_active == True,
                Store.deleted_at == None,
                (Store.name.ilike(pattern) | Store.brand.ilike(pattern)),
            )
            .offset(offset).limit(limit).all()
        )

    def search_count(self, keyword: str) -> int:
        pattern = f"%{keyword}%"
        return (
            self.db.query(Store)
            .filter(
                Store.is_active == True,
                Store.deleted_at == None,
                (Store.name.ilike(pattern) | Store.brand.ilike(pattern)),
            )
            .count()
        )

    def soft_delete(self, store: Store):
        from datetime import datetime
        store.deleted_at = datetime.utcnow()
        store.is_active = False
        self.db.commit()
