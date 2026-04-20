"""실거래가 이력"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Index
from database import Base


class TransactionHistory(Base):
    __tablename__ = "transaction_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(30))
    district = Column(String(30))
    dong = Column(String(30))
    name = Column(String(100))  # 단지명/건물명
    address = Column(String(200))

    transaction_date = Column(Date)
    price_krw = Column(Integer)  # 원 단위
    area_exclusive = Column(Float)  # 전용면적
    floor = Column(Integer)
    built_year = Column(Integer)
    property_type = Column(String(30))

    # Derived
    price_per_m2 = Column(Integer)

    # Trade type (매매/전세/월세)
    trade_type = Column(String(20), default="매매")
    deposit_krw = Column(Integer)     # 보증금 (전세/월세)
    monthly_rent_krw = Column(Integer) # 월세

    source = Column(String(50), default="molit")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_tx_district_date", "district", "transaction_date"),
        Index("ix_tx_name", "name"),
    )
