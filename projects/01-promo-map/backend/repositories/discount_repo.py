"""Discount 리포지토리"""
from datetime import datetime
from sqlalchemy.orm import Session
from models import Discount
from repositories.base import BaseRepository


class DiscountRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(Discount, db)

    def get_active_by_store(self, store_id: int):
        now = datetime.utcnow()
        return (
            self.db.query(Discount)
            .filter(
                Discount.store_id == store_id,
                Discount.is_active == True,
                (Discount.valid_until == None) | (Discount.valid_until >= now),
            )
            .all()
        )

    def get_active_by_company(self, company_id: int):
        now = datetime.utcnow()
        return (
            self.db.query(Discount)
            .filter(
                Discount.company_id == company_id,
                Discount.is_active == True,
                (Discount.valid_until == None) | (Discount.valid_until >= now),
            )
            .all()
        )

    def get_active_by_store_ids(self, store_ids: list) -> dict:
        """Batch fetch active discounts for multiple stores at once."""
        if not store_ids:
            return {}
        now = datetime.utcnow()
        discounts = (
            self.db.query(Discount)
            .filter(
                Discount.store_id.in_(store_ids),
                Discount.is_active == True,
                (Discount.valid_until == None) | (Discount.valid_until >= now),
            )
            .all()
        )
        result: dict[int, list] = {}
        for d in discounts:
            result.setdefault(d.store_id, []).append(d)
        return result

    def get_all_with_relations(self, offset: int = 0, limit: int = 20):
        return self.db.query(Discount).offset(offset).limit(limit).all()
