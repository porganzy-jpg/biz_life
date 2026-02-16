"""지하철역 Repository"""
from math import cos, radians
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.subway_station import SubwayStation
from repositories.base import BaseRepository


class SubwayRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(SubwayStation, db)

    def get_by_name(self, name: str) -> List[SubwayStation]:
        return (
            self.db.query(SubwayStation)
            .filter(SubwayStation.name == name)
            .all()
        )

    def get_by_line(self, line: str) -> List[SubwayStation]:
        return (
            self.db.query(SubwayStation)
            .filter(SubwayStation.line == line)
            .order_by(SubwayStation.name)
            .all()
        )

    def get_nearest(
        self, lat: float, lng: float, limit: int = 5
    ) -> List[SubwayStation]:
        # Bounding box pre-filter (3km radius) then sort by approximate distance
        radius_km = 3.0
        lat_range = radius_km / 111.0
        lng_range = radius_km / (111.0 * cos(radians(lat)))

        # Approximate Euclidean distance for ordering
        distance_expr = func.sqrt(
            func.pow((SubwayStation.lat - lat) * 111.0, 2)
            + func.pow((SubwayStation.lng - lng) * 111.0 * cos(radians(lat)), 2)
        )

        return (
            self.db.query(SubwayStation)
            .filter(
                SubwayStation.lat.between(lat - lat_range, lat + lat_range)
            )
            .filter(
                SubwayStation.lng.between(lng - lng_range, lng + lng_range)
            )
            .order_by(distance_expr)
            .limit(limit)
            .all()
        )

    def get_all_stations(self) -> List[SubwayStation]:
        return (
            self.db.query(SubwayStation)
            .order_by(SubwayStation.line, SubwayStation.name)
            .all()
        )
