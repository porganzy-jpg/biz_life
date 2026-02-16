"""청약 정보 Repository"""
from typing import Optional, List
from datetime import date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.subscription import SubscriptionOpportunity
from repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(SubscriptionOpportunity, db)

    def get_active(self) -> List[SubscriptionOpportunity]:
        today = date.today()
        return (
            self.db.query(SubscriptionOpportunity)
            .filter(SubscriptionOpportunity.subscription_end >= today)
            .order_by(SubscriptionOpportunity.subscription_end)
            .all()
        )

    def get_upcoming(self, days: int = 30) -> List[SubscriptionOpportunity]:
        today = date.today()
        cutoff = today + timedelta(days=days)
        return (
            self.db.query(SubscriptionOpportunity)
            .filter(SubscriptionOpportunity.subscription_start >= today)
            .filter(SubscriptionOpportunity.subscription_start <= cutoff)
            .order_by(SubscriptionOpportunity.subscription_start)
            .all()
        )

    def get_by_district(
        self, district: str
    ) -> List[SubscriptionOpportunity]:
        return (
            self.db.query(SubscriptionOpportunity)
            .filter(SubscriptionOpportunity.district == district)
            .order_by(SubscriptionOpportunity.subscription_start)
            .all()
        )

    def get_by_source_id(
        self, source_id: str
    ) -> Optional[SubscriptionOpportunity]:
        return (
            self.db.query(SubscriptionOpportunity)
            .filter(SubscriptionOpportunity.source_id == source_id)
            .first()
        )
