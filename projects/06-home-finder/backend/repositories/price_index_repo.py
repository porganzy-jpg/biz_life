"""가격 지수 Repository"""
from typing import Optional, List
from datetime import date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from models.price_index import PriceIndex
from repositories.base import BaseRepository


class PriceIndexRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(PriceIndex, db)

    def get_latest(
        self, source: str, region: str
    ) -> Optional[PriceIndex]:
        return (
            self.db.query(PriceIndex)
            .filter(
                and_(
                    PriceIndex.source == source,
                    PriceIndex.region == region,
                )
            )
            .order_by(desc(PriceIndex.date))
            .first()
        )

    def get_trend(
        self, source: str, region: str, months_back: int = 12
    ) -> List[PriceIndex]:
        cutoff = date.today() - timedelta(days=months_back * 30)
        return (
            self.db.query(PriceIndex)
            .filter(
                and_(
                    PriceIndex.source == source,
                    PriceIndex.region == region,
                    PriceIndex.date >= cutoff,
                )
            )
            .order_by(PriceIndex.date)
            .all()
        )
