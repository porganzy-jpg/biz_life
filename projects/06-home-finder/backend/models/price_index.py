"""가격 지수"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Index
from database import Base


class PriceIndex(Base):
    __tablename__ = "price_indices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(30), nullable=False)  # kb, molit
    index_type = Column(String(50))  # 매매지수, 전세지수 등
    region = Column(String(50))  # 서울, 마포구 등
    date = Column(Date)
    value = Column(Float)
    change_pct = Column(Float)  # 전월 대비 변동률

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_pidx_region_date", "source", "region", "date"),
    )
