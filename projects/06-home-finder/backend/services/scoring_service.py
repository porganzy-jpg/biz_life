"""채점 서비스 - 매물 스코어링 실행 및 관리"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.property import Property
from repositories.property_repo import PropertyRepository
from repositories.area_repo import AreaRepository
from scoring.composite_scorer import CompositeScorer
from exceptions import NotFoundException

logger = logging.getLogger("homefinder.scoring_service")


class ScoringService:
    def __init__(self, db: Session, scorer: CompositeScorer):
        self.db = db
        self.repo = PropertyRepository(db)
        self.area_repo = AreaRepository(db)
        self.scorer = scorer

    def score_property(self, property_id: int) -> dict:
        """단일 매물 채점 후 DB 업데이트"""
        prop = self.repo.get_by_id(property_id)
        if not prop:
            raise NotFoundException(f"매물 ID {property_id}을(를) 찾을 수 없습니다")

        # Load area info for the property's district
        area_info = self._get_area_info(prop.district)

        # Run scoring
        result = self.scorer.score_property(prop, area_info)

        # Extract location details from scoring result
        loc = result.get("location", {})

        # Update property scores in DB
        self.repo.update(
            prop,
            score_location=result["location"]["total"],
            score_price=result["price"]["total"],
            score_property=result["property"]["total"],
            score_area=result["area"]["total"],
            score_composite=result["composite"],
            scored_at=datetime.utcnow(),
            nearest_subway_name=loc.get("nearest_subway"),
            nearest_subway_distance=loc.get("subway_distance"),
            nearest_subway_lines=loc.get("subway_lines"),
            nearest_park_name=loc.get("nearest_park"),
            nearest_park_distance=loc.get("park_distance"),
            nearest_river_distance=loc.get("river_distance"),
        )

        logger.info(
            f"Property {property_id} scored: composite={result['composite']}"
        )
        return result

    def score_all(self) -> dict:
        """모든 활성 매물 재채점"""
        properties = (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .all()
        )

        scored_count = 0
        for prop in properties:
            try:
                area_info = self._get_area_info(prop.district)
                result = self.scorer.score_property(prop, area_info)
                loc = result.get("location", {})

                prop.score_location = result["location"]["total"]
                prop.score_price = result["price"]["total"]
                prop.score_property = result["property"]["total"]
                prop.score_area = result["area"]["total"]
                prop.score_composite = result["composite"]
                prop.scored_at = datetime.utcnow()
                prop.nearest_subway_name = loc.get("nearest_subway")
                prop.nearest_subway_distance = loc.get("subway_distance")
                prop.nearest_subway_lines = loc.get("subway_lines")
                prop.nearest_park_name = loc.get("nearest_park")
                prop.nearest_park_distance = loc.get("park_distance")
                prop.nearest_river_distance = loc.get("river_distance")

                scored_count += 1
            except Exception as e:
                logger.error(f"Failed to score property {prop.id}: {e}")

        self.db.commit()
        logger.info(f"Scored {scored_count}/{len(properties)} properties")
        return {"scored": scored_count, "total": len(properties)}

    def get_score_detail(self, property_id: int) -> dict:
        """매물 점수 상세 분석 결과"""
        prop = self.repo.get_by_id(property_id)
        if not prop:
            raise NotFoundException(f"매물 ID {property_id}을(를) 찾을 수 없습니다")

        area_info = self._get_area_info(prop.district)
        result = self.scorer.score_property(prop, area_info)

        return {
            "property_id": property_id,
            "district": prop.district,
            "complex_name": prop.complex_name,
            "price_krw": prop.price_krw,
            "area_m2": prop.area_m2,
            "scores": result,
            "area_info": area_info,
            "scored_at": prop.scored_at.isoformat() if prop.scored_at else None,
        }

    def update_weights(self, weights: dict):
        """채점 가중치 업데이트"""
        self.scorer.update_weights(
            location=weights.get("location"),
            price=weights.get("price"),
            property_w=weights.get("property"),
            area=weights.get("area"),
        )

    def get_weights(self) -> dict:
        """현재 가중치 조회"""
        return self.scorer.get_weights()

    def _get_area_info(self, district: Optional[str]) -> dict:
        """지역 정보를 dict 형태로 반환"""
        if not district:
            return {}

        areas = self.area_repo.get_by_district(district)
        if not areas:
            return {}

        # Use the first area record (district-level) for scoring
        area = areas[0]
        return {
            "avg_price_per_m2": area.avg_price_per_m2,
            "price_change_1y": area.price_change_1y,
            "price_change_3y": area.price_change_3y,
            "development_score": area.development_score,
            "living_score": area.living_score,
            "infra_score": area.infra_score,
            "subway_count": area.subway_count or 0,
            "school_count": area.school_count or 0,
            "hospital_count": area.hospital_count or 0,
            "park_count": area.park_count or 0,
        }
