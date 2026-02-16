"""지역(구/동) 프로필 Repository"""
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.area import Area
from repositories.base import BaseRepository


class AreaRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(Area, db)

    def get_by_district(self, district: str) -> List[Area]:
        return (
            self.db.query(Area)
            .filter(Area.district == district)
            .all()
        )

    def get_by_district_dong(self, district: str, dong: str) -> Optional[Area]:
        return (
            self.db.query(Area)
            .filter(Area.district == district)
            .filter(Area.dong == dong)
            .first()
        )

    def get_all_districts(self) -> List[str]:
        results = (
            self.db.query(Area.district)
            .distinct()
            .order_by(Area.district)
            .all()
        )
        return [r[0] for r in results]
