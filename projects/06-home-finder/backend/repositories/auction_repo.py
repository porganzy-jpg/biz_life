"""경매 물건 Repository"""
from typing import Optional, List
from datetime import date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from models.auction import AuctionListing
from repositories.base import BaseRepository


class AuctionRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(AuctionListing, db)

    def get_upcoming(
        self, days: int = 30, limit: int = 50
    ) -> List[AuctionListing]:
        today = date.today()
        cutoff = today + timedelta(days=days)
        return (
            self.db.query(AuctionListing)
            .filter(AuctionListing.auction_date >= today)
            .filter(AuctionListing.auction_date <= cutoff)
            .filter(AuctionListing.auction_status == "진행중")
            .order_by(AuctionListing.auction_date)
            .limit(limit)
            .all()
        )

    def get_by_district(
        self, district: str, limit: int = 50
    ) -> List[AuctionListing]:
        return (
            self.db.query(AuctionListing)
            .filter(AuctionListing.district == district)
            .order_by(desc(AuctionListing.auction_date))
            .limit(limit)
            .all()
        )

    def get_best_deals(
        self, min_discount_rate: float = 0.3, limit: int = 20
    ) -> List[AuctionListing]:
        return (
            self.db.query(AuctionListing)
            .filter(AuctionListing.auction_status == "진행중")
            .filter(AuctionListing.discount_rate >= min_discount_rate)
            .order_by(desc(AuctionListing.discount_rate))
            .limit(limit)
            .all()
        )

    def get_by_case_number(self, case_number: str) -> Optional[AuctionListing]:
        return (
            self.db.query(AuctionListing)
            .filter(AuctionListing.case_number == case_number)
            .first()
        )
