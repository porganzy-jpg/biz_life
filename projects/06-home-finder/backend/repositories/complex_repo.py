"""단지 프로필 Repository"""
from typing import Optional, List

from sqlalchemy.orm import Session

from models.complex import Complex
from repositories.base import BaseRepository


class ComplexRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(Complex, db)

    def search_by_name(self, name_keyword: str, limit: int = 20) -> List[Complex]:
        return (
            self.db.query(Complex)
            .filter(Complex.name.contains(name_keyword))
            .limit(limit)
            .all()
        )

    def get_by_district(self, district: str, limit: int = 50) -> List[Complex]:
        return (
            self.db.query(Complex)
            .filter(Complex.district == district)
            .limit(limit)
            .all()
        )

    def get_by_source_id(self, source_id: str) -> Optional[Complex]:
        return (
            self.db.query(Complex)
            .filter(Complex.source_id == source_id)
            .first()
        )
