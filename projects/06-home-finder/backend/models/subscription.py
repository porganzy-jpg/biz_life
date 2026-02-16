"""청약 정보"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text
from database import Base


class SubscriptionOpportunity(Base):
    __tablename__ = "subscription_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # 단지명
    city = Column(String(30))
    district = Column(String(30))
    dong = Column(String(30))
    address = Column(String(200))
    lat = Column(Float)
    lng = Column(Float)

    developer = Column(String(100))
    total_units = Column(Integer)
    subscription_units = Column(Integer)  # 청약 세대수

    subscription_start = Column(Date)
    subscription_end = Column(Date)
    announcement_date = Column(Date)
    move_in_date = Column(Date)

    min_price = Column(Integer)  # 최소 분양가
    max_price = Column(Integer)  # 최대 분양가
    avg_price_per_m2 = Column(Integer)

    min_area_m2 = Column(Float)
    max_area_m2 = Column(Float)

    competition_rate = Column(Float)  # 경쟁률
    subscription_type = Column(String(50))  # 일반, 특별공급 등
    status = Column(String(30))  # 접수중, 마감, 당첨발표

    source_url = Column(String(500))
    source_id = Column(String(100), unique=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
