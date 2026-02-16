"""저장된 검색조건 Repository"""
from typing import Optional, List

from sqlalchemy.orm import Session

from models.saved_search import SavedSearch
from repositories.base import BaseRepository


class SavedSearchRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(SavedSearch, db)

    def get_active_alerts(self) -> List[SavedSearch]:
        return (
            self.db.query(SavedSearch)
            .filter(SavedSearch.alert_on_new == 1)
            .all()
        )

    def get_by_name(self, name: str) -> Optional[SavedSearch]:
        return (
            self.db.query(SavedSearch)
            .filter(SavedSearch.name == name)
            .first()
        )
