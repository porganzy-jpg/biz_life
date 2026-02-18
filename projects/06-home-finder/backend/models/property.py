"""매물 (핵심 엔터티)"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from database import Base


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)  # naver, auction, subscription, manual
    property_type = Column(String(30), nullable=False)  # 아파트, 빌라, 단독, 전원, 타운하우스
    acquisition_type = Column(String(20), default="매매")  # 매매, 경매, 청약

    # Location
    city = Column(String(30))
    district = Column(String(30))  # 구
    dong = Column(String(30))  # 동
    address = Column(String(200))
    detail_address = Column(String(200))
    lat = Column(Float)
    lng = Column(Float)

    # Price
    price_krw = Column(Integer)  # 원 단위
    price_per_m2 = Column(Integer)

    # Property details
    area_m2 = Column(Float)  # 전용면적
    area_supply_m2 = Column(Float)  # 공급면적
    floor = Column(Integer)
    total_floors = Column(Integer)
    rooms = Column(Integer)
    bathrooms = Column(Integer)
    direction = Column(String(20))  # 남향, 남동향 등
    built_year = Column(Integer)
    maintenance_fee = Column(Integer)  # 관리비 (만원)

    # Complex info
    complex_name = Column(String(100))
    complex_id = Column(Integer)

    # Land-specific (토지 전용, nullable)
    land_use = Column(String(30))           # 지목: 대, 전, 답, 임야, 잡종지
    zoning_type = Column(String(50))        # 용도지역: 제1종일반주거, 제2종일반주거, ...
    building_coverage_ratio = Column(Float) # 건폐율 (%)
    floor_area_ratio = Column(Float)        # 용적률 (%)
    road_frontage = Column(String(50))      # 접도: 맹지, 4m미만, 4~6m, 6~8m, 8m이상
    topography = Column(String(30))         # 지형: 평지, 완경사, 경사

    # Scoring
    score_location = Column(Float)
    score_price = Column(Float)
    score_property = Column(Float)
    score_area = Column(Float)
    score_composite = Column(Float)

    # Nearest subway
    nearest_subway_name = Column(String(50))
    nearest_subway_distance = Column(Float)  # meters
    nearest_subway_lines = Column(String(100))

    # Nearest park/river
    nearest_park_name = Column(String(50))
    nearest_park_distance = Column(Float)
    nearest_river_distance = Column(Float)

    # Meta
    source_url = Column(String(500))
    source_id = Column(String(100))  # 중복 방지용
    description = Column(Text)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scored_at = Column(DateTime)

    __table_args__ = (
        Index("ix_prop_district_type", "district", "property_type"),
        Index("ix_prop_price", "price_krw"),
        Index("ix_prop_score", "score_composite"),
        Index("ix_prop_source_id", "source", "source_id", unique=True),
        Index("ix_prop_land_use", "land_use"),
        Index("ix_prop_zoning", "zoning_type"),
    )
