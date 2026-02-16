"""아파트 단지 프로필"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from database import Base


class Complex(Base):
    __tablename__ = "complexes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    city = Column(String(30))
    district = Column(String(30))
    dong = Column(String(30))
    address = Column(String(200))
    lat = Column(Float)
    lng = Column(Float)

    built_year = Column(Integer)
    total_units = Column(Integer)
    total_buildings = Column(Integer)
    parking_ratio = Column(Float)
    heating_type = Column(String(30))
    developer = Column(String(100))

    # Price info
    avg_price_per_m2 = Column(Integer)
    min_price = Column(Integer)
    max_price = Column(Integer)
    price_trend_1y = Column(Float)  # % change

    # Reconstruction
    reconstruction_status = Column(String(50))  # 해당없음, 추진중, 확정
    reconstruction_year = Column(Integer)

    description = Column(Text)
    source_id = Column(String(100), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
