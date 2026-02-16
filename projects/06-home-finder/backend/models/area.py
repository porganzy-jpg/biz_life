"""지역(구/동) 프로필"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from database import Base


class Area(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(30))
    district = Column(String(30), nullable=False)
    dong = Column(String(30))
    area_code = Column(String(20))  # 법정동코드

    population = Column(Integer)
    households = Column(Integer)
    subway_count = Column(Integer)
    park_count = Column(Integer)
    school_count = Column(Integer)
    hospital_count = Column(Integer)

    avg_price_per_m2 = Column(Integer)
    price_change_1y = Column(Float)  # % change
    price_change_3y = Column(Float)

    development_plan = Column(Text)  # 재개발/GTX 등
    development_score = Column(Float)
    living_score = Column(Float)
    infra_score = Column(Float)
    area_composite_score = Column(Float)

    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
