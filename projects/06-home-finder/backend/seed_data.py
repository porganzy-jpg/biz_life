"""
시드 데이터 로딩 (지하철역, 공원, 한강 접근점)
"""
import json
import logging
import os
from sqlalchemy.orm import Session
from database import SessionLocal
from models.subway_station import SubwayStation
from models.park import Park

logger = logging.getLogger("homefinder.seed")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def seed():
    """시드 데이터 로딩 (이미 데이터가 있으면 스킵)"""
    db = SessionLocal()
    try:
        _seed_subway_stations(db)
        _seed_parks(db)
        _seed_han_river(db)
    finally:
        db.close()


def _seed_subway_stations(db: Session):
    count = db.query(SubwayStation).count()
    if count > 0:
        logger.info(f"Subway stations already loaded ({count})")
        return

    path = os.path.join(DATA_DIR, "seoul_subway_stations.json")
    if not os.path.exists(path):
        logger.warning(f"Seed file not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        stations = json.load(f)

    for s in stations:
        db.add(SubwayStation(
            name=s["name"],
            line=s["line"],
            lat=s["lat"],
            lng=s["lng"],
            district=s.get("district", ""),
            is_transfer=s.get("is_transfer", 0),
        ))

    db.commit()
    logger.info(f"Loaded {len(stations)} subway stations")


def _seed_parks(db: Session):
    count = db.query(Park).filter(Park.park_type == "대형공원").count()
    if count > 0:
        logger.info(f"Parks already loaded ({count})")
        return

    path = os.path.join(DATA_DIR, "seoul_parks.json")
    if not os.path.exists(path):
        logger.warning(f"Seed file not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        parks = json.load(f)

    for p in parks:
        db.add(Park(
            name=p["name"],
            park_type=p.get("park_type", "대형공원"),
            lat=p["lat"],
            lng=p["lng"],
            district=p.get("district", ""),
            area_m2=p.get("area_m2"),
            description=p.get("description", ""),
        ))

    db.commit()
    logger.info(f"Loaded {len(parks)} parks")


def _seed_han_river(db: Session):
    count = db.query(Park).filter(Park.park_type == "한강").count()
    if count > 0:
        logger.info(f"Han river access points already loaded ({count})")
        return

    path = os.path.join(DATA_DIR, "han_river_access.json")
    if not os.path.exists(path):
        logger.warning(f"Seed file not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        points = json.load(f)

    for p in points:
        db.add(Park(
            name=p["name"],
            park_type="한강",
            lat=p["lat"],
            lng=p["lng"],
            district=p.get("district", ""),
            description=p.get("description", ""),
        ))

    db.commit()
    logger.info(f"Loaded {len(points)} han river access points")
