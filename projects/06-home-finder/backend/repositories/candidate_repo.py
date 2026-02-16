"""후보 매물 파이프라인 Repository"""
from typing import Optional, List, Dict

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from models.candidate import CandidateProperty
from repositories.base import BaseRepository


class CandidateRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(CandidateProperty, db)

    def get_by_status(
        self, status: str, offset: int = 0, limit: int = 20
    ) -> List[CandidateProperty]:
        return (
            self.db.query(CandidateProperty)
            .filter(CandidateProperty.status == status)
            .order_by(CandidateProperty.priority)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_pipeline_counts(self) -> Dict[str, int]:
        results = (
            self.db.query(
                CandidateProperty.status,
                func.count(CandidateProperty.id),
            )
            .group_by(CandidateProperty.status)
            .all()
        )
        return {status: count for status, count in results}

    def get_by_property_id(
        self, property_id: int
    ) -> Optional[CandidateProperty]:
        return (
            self.db.query(CandidateProperty)
            .filter(CandidateProperty.property_id == property_id)
            .first()
        )

    def get_shortlist(self) -> List[CandidateProperty]:
        return (
            self.db.query(CandidateProperty)
            .filter(
                CandidateProperty.status.in_(["관심", "방문예정", "방문완료"])
            )
            .order_by(CandidateProperty.priority)
            .all()
        )

    def update_status(
        self, candidate_id: int, new_status: str
    ) -> Optional[CandidateProperty]:
        candidate = self.get_by_id(candidate_id)
        if candidate is None:
            return None
        candidate.status = new_status
        self.db.commit()
        self.db.refresh(candidate)
        return candidate
