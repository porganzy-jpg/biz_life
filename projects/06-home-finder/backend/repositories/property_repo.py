"""매물 Repository"""
from math import cos, radians
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from models.property import Property
from repositories.base import BaseRepository


class PropertyRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(Property, db)

    def search(
        self,
        district: Optional[str] = None,
        property_type: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        area_min: Optional[float] = None,
        area_max: Optional[float] = None,
        score_min: Optional[float] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> List[Property]:
        query = self.db.query(Property).filter(Property.is_active == 1)

        if district:
            query = query.filter(Property.district == district)
        if property_type:
            query = query.filter(Property.property_type == property_type)
        if price_min is not None:
            query = query.filter(Property.price_krw >= price_min)
        if price_max is not None:
            query = query.filter(Property.price_krw <= price_max)
        if area_min is not None:
            query = query.filter(Property.area_m2 >= area_min)
        if area_max is not None:
            query = query.filter(Property.area_m2 <= area_max)
        if score_min is not None:
            query = query.filter(Property.score_composite >= score_min)

        return query.offset(offset).limit(limit).all()

    def search_with_count(
        self,
        district: Optional[str] = None,
        property_type: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        area_min: Optional[float] = None,
        area_max: Optional[float] = None,
        score_min: Optional[float] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple:
        """Search with total count in single query build."""
        query = self.db.query(Property).filter(Property.is_active == 1)

        if district:
            query = query.filter(Property.district == district)
        if property_type:
            query = query.filter(Property.property_type == property_type)
        if price_min is not None:
            query = query.filter(Property.price_krw >= price_min)
        if price_max is not None:
            query = query.filter(Property.price_krw <= price_max)
        if area_min is not None:
            query = query.filter(Property.area_m2 >= area_min)
        if area_max is not None:
            query = query.filter(Property.area_m2 <= area_max)
        if score_min is not None:
            query = query.filter(Property.score_composite >= score_min)

        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return items, total

    def find_near_subway(
        self,
        subway_lat: float,
        subway_lng: float,
        radius_km: float = 1.0,
        offset: int = 0,
        limit: int = 20,
    ) -> List[Property]:
        lat_range = radius_km / 111.0
        lng_range = radius_km / (111.0 * cos(radians(subway_lat)))

        return (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .filter(
                Property.lat.between(
                    subway_lat - lat_range, subway_lat + lat_range
                )
            )
            .filter(
                Property.lng.between(
                    subway_lng - lng_range, subway_lng + lng_range
                )
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_source_id(self, source: str, source_id: str) -> Optional[Property]:
        return (
            self.db.query(Property)
            .filter(
                and_(
                    Property.source == source,
                    Property.source_id == source_id,
                )
            )
            .first()
        )

    def get_top_scored(self, limit: int = 20) -> List[Property]:
        return (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .filter(Property.score_composite.isnot(None))
            .order_by(desc(Property.score_composite))
            .limit(limit)
            .all()
        )

    def get_by_district(
        self, district: str, offset: int = 0, limit: int = 20
    ) -> List[Property]:
        return (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .filter(Property.district == district)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_unscored(self, limit: int = 50) -> List[Property]:
        return (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .filter(Property.score_composite.is_(None))
            .limit(limit)
            .all()
        )
