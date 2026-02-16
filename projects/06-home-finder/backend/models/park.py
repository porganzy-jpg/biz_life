"""공원/한강 접근점"""
from sqlalchemy import Column, Integer, String, Float
from database import Base


class Park(Base):
    __tablename__ = "parks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    park_type = Column(String(30), nullable=False)  # 한강, 대형공원, 근린공원
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    district = Column(String(30))
    area_m2 = Column(Float)
    description = Column(String(200))
