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
from models.area import Area

logger = logging.getLogger("homefinder.seed")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def seed():
    """시드 데이터 로딩 (이미 데이터가 있으면 스킵)"""
    db = SessionLocal()
    try:
        _seed_subway_stations(db)
        _seed_parks(db)
        _seed_han_river(db)
        _seed_areas(db)
        _seed_properties(db)
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


def _seed_areas(db: Session):
    count = db.query(Area).count()
    if count > 0:
        logger.info(f"Areas already loaded ({count})")
        return

    path = os.path.join(DATA_DIR, "areas.json")
    if not os.path.exists(path):
        logger.warning(f"Seed file not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        areas = json.load(f)

    for a in areas:
        # Compute composite score from sub-scores
        dev = a.get("development_score", 0) or 0
        liv = a.get("living_score", 0) or 0
        infra = a.get("infra_score", 0) or 0
        composite = round((dev * 0.4 + liv * 0.3 + infra * 0.3), 1)

        db.add(Area(
            city=a.get("city", "서울특별시"),
            district=a["district"],
            area_code=a.get("area_code", ""),
            population=a.get("population"),
            households=a.get("households"),
            subway_count=a.get("subway_count"),
            park_count=a.get("park_count"),
            school_count=a.get("school_count"),
            hospital_count=a.get("hospital_count"),
            avg_price_per_m2=a.get("avg_price_per_m2"),
            price_change_1y=a.get("price_change_1y"),
            price_change_3y=a.get("price_change_3y"),
            development_plan=a.get("development_plan"),
            development_score=dev,
            living_score=liv,
            infra_score=infra,
            area_composite_score=composite,
            description=a.get("description", ""),
        ))

    db.commit()
    logger.info(f"Loaded {len(areas)} area profiles")


def _seed_properties(db: Session):
    """Property 테이블이 비어있으면 시드 데이터 자동 로드"""
    from models.property import Property
    count = db.query(Property).count()
    if count > 0:
        logger.info(f"Properties already loaded ({count})")
        return

    try:
        import sys
        project_root = os.path.dirname(os.path.dirname(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from collect_real_data import (
            generate_properties, generate_land_parcels,
            generate_transactions, generate_auctions,
            generate_subscriptions, generate_areas,
        )
        logger.info("Auto-loading seed properties...")
        generate_properties(db)
        generate_land_parcels(db)
        generate_transactions(db)
        generate_auctions(db)
        generate_subscriptions(db)
        generate_areas(db)
        logger.info("Seed properties loaded successfully")
    except Exception as e:
        logger.error(f"Failed to auto-load seed properties: {e}")
