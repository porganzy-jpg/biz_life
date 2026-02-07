"""Review 리포지토리"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Review
from repositories.base import BaseRepository


class ReviewRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(Review, db)

    def get_by_store(self, store_id: int, offset: int = 0, limit: int = 20):
        return (
            self.db.query(Review)
            .filter(Review.store_id == store_id)
            .order_by(Review.created_at.desc())
            .offset(offset).limit(limit).all()
        )

    def count_by_store(self, store_id: int) -> int:
        return self.db.query(Review).filter(Review.store_id == store_id).count()

    def avg_rating_by_store(self, store_id: int) -> float | None:
        result = (
            self.db.query(func.avg(Review.rating))
            .filter(Review.store_id == store_id)
            .scalar()
        )
        return round(result, 1) if result else None

    def count_by_user(self, user_id: int) -> int:
        return self.db.query(Review).filter(Review.user_id == user_id).count()
