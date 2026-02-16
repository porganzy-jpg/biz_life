"""경매 물건"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, Index
from database import Base


class AuctionListing(Base):
    __tablename__ = "auction_listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_number = Column(String(50), unique=True)  # 사건번호
    court = Column(String(50))  # 법원

    city = Column(String(30))
    district = Column(String(30))
    dong = Column(String(30))
    address = Column(String(200))
    lat = Column(Float)
    lng = Column(Float)

    property_type = Column(String(30))
    area_m2 = Column(Float)
    floor = Column(Integer)
    built_year = Column(Integer)

    appraisal_price = Column(Integer)  # 감정가
    minimum_bid = Column(Integer)  # 최저입찰가
    current_bid_round = Column(Integer, default=1)
    discount_rate = Column(Float)  # 감정가 대비 할인율

    auction_date = Column(Date)
    auction_status = Column(String(30))  # 진행중, 낙찰, 유찰, 취하

    risk_level = Column(String(20))  # 낮음, 보통, 높음
    risk_notes = Column(Text)  # 권리분석 메모
    occupancy_status = Column(String(50))  # 점유현황

    source_url = Column(String(500))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_auction_date", "auction_date"),
        Index("ix_auction_district", "district"),
    )
