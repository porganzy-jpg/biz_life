"""Company 리포지토리"""
from sqlalchemy.orm import Session
from models import Company
from repositories.base import BaseRepository


class CompanyRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(Company, db)

    def get_by_code(self, code: str) -> Company | None:
        return self.db.query(Company).filter(Company.code == code).first()

    def get_active(self, offset: int = 0, limit: int = 20):
        return self.db.query(Company).filter(Company.is_active == True).offset(offset).limit(limit).all()

    def count_active(self) -> int:
        return self.db.query(Company).filter(Company.is_active == True).count()
