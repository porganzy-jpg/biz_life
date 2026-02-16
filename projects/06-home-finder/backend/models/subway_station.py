"""지하철역 좌표"""
from sqlalchemy import Column, Integer, String, Float
from database import Base


class SubwayStation(Base):
    __tablename__ = "subway_stations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    line = Column(String(30), nullable=False)  # 1호선, 2호선, ...
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    district = Column(String(30))
    is_transfer = Column(Integer, default=0)  # 환승역 여부
