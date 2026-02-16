"""후보 매물 서비스 - 파이프라인 관리"""
from datetime import datetime

from sqlalchemy.orm import Session

from models.candidate import CandidateProperty
from models.property import Property
from models.note import PropertyNote
from repositories.candidate_repo import CandidateRepository
from repositories.property_repo import PropertyRepository
from exceptions import NotFoundException, BadRequestException

VALID_STATUSES = ["발견", "조사", "관심", "방문예정", "방문완료", "결정"]


class CandidateService:
    def __init__(self, db: Session):
        self.db = db
        self.candidate_repo = CandidateRepository(db)
        self.property_repo = PropertyRepository(db)

    def add_candidate(self, property_id: int, priority: int = 3) -> CandidateProperty:
        """매물을 후보 파이프라인에 추가"""
        # Verify property exists
        prop = self.property_repo.get_by_id(property_id)
        if not prop:
            raise NotFoundException(f"매물 ID {property_id}을(를) 찾을 수 없습니다")

        # Check for duplicate candidate
        existing = self.candidate_repo.get_by_property_id(property_id)
        if existing:
            raise BadRequestException(
                f"매물 ID {property_id}은(는) 이미 후보에 등록되어 있습니다"
            )

        return self.candidate_repo.create(
            property_id=property_id,
            priority=priority,
            status="발견",
        )

    def update_status(self, candidate_id: int, status: str) -> CandidateProperty:
        """후보 상태 변경"""
        if status not in VALID_STATUSES:
            raise BadRequestException(
                f"유효하지 않은 상태입니다: {status}. "
                f"허용 상태: {', '.join(VALID_STATUSES)}"
            )

        candidate = self.candidate_repo.update_status(candidate_id, status)
        if not candidate:
            raise NotFoundException(f"후보 ID {candidate_id}을(를) 찾을 수 없습니다")
        return candidate

    def rate_candidate(
        self, candidate_id: int, rating: int, notes: str = None
    ) -> CandidateProperty:
        """후보 평점 및 메모 기록"""
        if not (1 <= rating <= 5):
            raise BadRequestException("평점은 1~5 사이여야 합니다")

        candidate = self.candidate_repo.get_by_id(candidate_id)
        if not candidate:
            raise NotFoundException(f"후보 ID {candidate_id}을(를) 찾을 수 없습니다")

        update_data = {"rating": rating, "updated_at": datetime.utcnow()}
        if notes is not None:
            update_data["visit_notes"] = notes

        return self.candidate_repo.update(candidate, **update_data)

    def get_pipeline(self) -> dict:
        """파이프라인 단계별 건수"""
        return self.candidate_repo.get_pipeline_counts()

    def get_by_status(self, status: str, page: int = 1, size: int = 20) -> dict:
        """상태별 후보 목록 (페이지네이션)"""
        offset = (page - 1) * size
        items = self.candidate_repo.get_by_status(
            status=status, offset=offset, limit=size
        )
        total = (
            self.db.query(CandidateProperty)
            .filter(CandidateProperty.status == status)
            .count()
        )
        return {"items": items, "total": total}

    def get_shortlist(self) -> list:
        """관심/방문예정/방문완료 후보 목록"""
        return self.candidate_repo.get_shortlist()

    def compare_candidates(self, id1: int, id2: int) -> dict:
        """두 후보 매물 상세 비교"""
        cand1 = self.candidate_repo.get_by_id(id1)
        if not cand1:
            raise NotFoundException(f"후보 ID {id1}을(를) 찾을 수 없습니다")

        cand2 = self.candidate_repo.get_by_id(id2)
        if not cand2:
            raise NotFoundException(f"후보 ID {id2}을(를) 찾을 수 없습니다")

        prop1 = self.property_repo.get_by_id(cand1.property_id)
        prop2 = self.property_repo.get_by_id(cand2.property_id)

        def _prop_to_dict(prop, cand):
            return {
                "candidate_id": cand.id,
                "status": cand.status,
                "priority": cand.priority,
                "rating": cand.rating,
                "property_id": prop.id if prop else None,
                "complex_name": prop.complex_name if prop else None,
                "district": prop.district if prop else None,
                "dong": prop.dong if prop else None,
                "address": prop.address if prop else None,
                "property_type": prop.property_type if prop else None,
                "price_krw": prop.price_krw if prop else None,
                "price_per_m2": prop.price_per_m2 if prop else None,
                "area_m2": prop.area_m2 if prop else None,
                "floor": prop.floor if prop else None,
                "total_floors": prop.total_floors if prop else None,
                "direction": prop.direction if prop else None,
                "built_year": prop.built_year if prop else None,
                "maintenance_fee": prop.maintenance_fee if prop else None,
                "rooms": prop.rooms if prop else None,
                "bathrooms": prop.bathrooms if prop else None,
                "score_composite": prop.score_composite if prop else None,
                "score_location": prop.score_location if prop else None,
                "score_price": prop.score_price if prop else None,
                "score_property": prop.score_property if prop else None,
                "score_area": prop.score_area if prop else None,
                "nearest_subway_name": prop.nearest_subway_name if prop else None,
                "nearest_subway_distance": prop.nearest_subway_distance if prop else None,
                "nearest_park_name": prop.nearest_park_name if prop else None,
                "nearest_park_distance": prop.nearest_park_distance if prop else None,
                "nearest_river_distance": prop.nearest_river_distance if prop else None,
                "pros": cand.pros,
                "cons": cand.cons,
                "visit_notes": cand.visit_notes,
            }

        return {
            "candidate_1": _prop_to_dict(prop1, cand1),
            "candidate_2": _prop_to_dict(prop2, cand2),
        }

    def add_note(
        self, candidate_id: int, note_type: str, content: str
    ) -> PropertyNote:
        """후보 매물에 메모 추가"""
        candidate = self.candidate_repo.get_by_id(candidate_id)
        if not candidate:
            raise NotFoundException(f"후보 ID {candidate_id}을(를) 찾을 수 없습니다")

        note = PropertyNote(
            property_id=candidate.property_id,
            candidate_id=candidate_id,
            note_type=note_type,
            content=content,
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note
