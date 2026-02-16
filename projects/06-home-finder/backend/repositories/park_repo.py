"""공원/한강 접근점 Repository"""
from math import cos, radians
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.park import Park
from repositories.base import BaseRepository


class ParkRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(Park, db)

    def get_by_type(self, park_type: str) -> List[Park]:
        return (
            self.db.query(Park)
            .filter(Park.park_type == park_type)
            .order_by(Park.name)
            .all()
        )

    def get_nearest(
        self, lat: float, lng: float, limit: int = 5
    ) -> List[Park]:
        # Bounding box pre-filter (5km radius) then sort by approximate distance
        radius_km = 5.0
        lat_range = radius_km / 111.0
        lng_range = radius_km / (111.0 * cos(radians(lat)))

        distance_expr = func.sqrt(
            func.pow((Park.lat - lat) * 111.0, 2)
            + func.pow((Park.lng - lng) * 111.0 * cos(radians(lat)), 2)
        )

        return (
            self.db.query(Park)
            .filter(Park.lat.between(lat - lat_range, lat + lat_range))
            .filter(Park.lng.between(lng - lng_range, lng + lng_range))
            .order_by(distance_expr)
            .limit(limit)
            .all()
        )

    def get_all_parks(self) -> List[Park]:
        return (
            self.db.query(Park)
            .order_by(Park.park_type, Park.name)
            .all()
        )
