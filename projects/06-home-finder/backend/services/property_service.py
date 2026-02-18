"""매물 서비스 - 매물 CRUD 및 조회"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from models.property import Property
from repositories.property_repo import PropertyRepository
from exceptions import NotFoundException, BadRequestException


class PropertyService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PropertyRepository(db)

    def get_property(self, id: int) -> Property:
        """매물 단건 조회"""
        prop = self.repo.get_by_id(id)
        if not prop:
            raise NotFoundException(f"매물 ID {id}을(를) 찾을 수 없습니다")
        return prop

    def search_properties(
        self,
        district: Optional[str] = None,
        property_type: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        area_min: Optional[float] = None,
        area_max: Optional[float] = None,
        score_min: Optional[float] = None,
        page: int = 1,
        size: int = 20,
    ) -> dict:
        """매물 다건 검색 (페이지네이션)"""
        offset = (page - 1) * size
        items, total = self.repo.search_with_count(
            district=district,
            property_type=property_type,
            price_min=price_min,
            price_max=price_max,
            area_min=area_min,
            area_max=area_max,
            score_min=score_min,
            offset=offset,
            limit=size,
        )
        return {"items": items, "total": total}

    def create_property(self, data: dict) -> Property:
        """매물 생성 (price_per_m2 자동 계산)"""
        # Auto-calculate price_per_m2
        price_krw = data.get("price_krw")
        area_m2 = data.get("area_m2")
        if price_krw and area_m2 and area_m2 > 0:
            data["price_per_m2"] = int(price_krw / area_m2)

        # Check for duplicate source_id
        source = data.get("source")
        source_id = data.get("source_id")
        if source and source_id:
            existing = self.repo.get_by_source_id(source, source_id)
            if existing:
                raise BadRequestException(
                    f"이미 등록된 매물입니다 (source={source}, source_id={source_id})"
                )

        return self.repo.create(**data)

    def update_property(self, id: int, data: dict) -> Property:
        """매물 정보 수정"""
        prop = self.get_property(id)

        # Recalculate price_per_m2 if price or area changed
        price_krw = data.get("price_krw", prop.price_krw)
        area_m2 = data.get("area_m2", prop.area_m2)
        if price_krw and area_m2 and area_m2 > 0:
            data["price_per_m2"] = int(price_krw / area_m2)

        data["updated_at"] = datetime.utcnow()
        return self.repo.update(prop, **data)

    def deactivate_property(self, id: int):
        """매물 비활성화 (소프트 삭제)"""
        prop = self.get_property(id)
        self.repo.update(prop, is_active=0, updated_at=datetime.utcnow())

    def get_top_scored(self, limit: int = 20) -> list:
        """종합점수 상위 매물 조회"""
        return self.repo.get_top_scored(limit=limit)

    def get_unscored(self, limit: int = 100) -> list:
        """미채점 매물 목록 조회"""
        return self.repo.get_unscored(limit=limit)
