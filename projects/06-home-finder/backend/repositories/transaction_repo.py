"""실거래가 이력 Repository"""
from typing import Optional, List
from datetime import datetime, timedelta, date

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from models.transaction import TransactionHistory
from repositories.base import BaseRepository


class TransactionRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(TransactionHistory, db)

    def get_by_district(
        self, district: str, months_back: int = 6
    ) -> List[TransactionHistory]:
        cutoff = date.today() - timedelta(days=months_back * 30)
        return (
            self.db.query(TransactionHistory)
            .filter(TransactionHistory.district == district)
            .filter(TransactionHistory.transaction_date >= cutoff)
            .order_by(desc(TransactionHistory.transaction_date))
            .all()
        )

    def get_by_name(
        self, name: str, months_back: int = 12
    ) -> List[TransactionHistory]:
        cutoff = date.today() - timedelta(days=months_back * 30)
        return (
            self.db.query(TransactionHistory)
            .filter(TransactionHistory.name == name)
            .filter(TransactionHistory.transaction_date >= cutoff)
            .order_by(desc(TransactionHistory.transaction_date))
            .all()
        )

    def get_price_trend(
        self,
        district: str,
        dong: Optional[str] = None,
        name: Optional[str] = None,
        months: int = 24,
    ) -> List[TransactionHistory]:
        cutoff = date.today() - timedelta(days=months * 30)
        query = (
            self.db.query(TransactionHistory)
            .filter(TransactionHistory.district == district)
            .filter(TransactionHistory.transaction_date >= cutoff)
        )

        if dong:
            query = query.filter(TransactionHistory.dong == dong)
        if name:
            query = query.filter(TransactionHistory.name == name)

        return query.order_by(TransactionHistory.transaction_date).all()

    def get_latest_transactions(self, limit: int = 50) -> List[TransactionHistory]:
        return (
            self.db.query(TransactionHistory)
            .order_by(desc(TransactionHistory.transaction_date))
            .limit(limit)
            .all()
        )
