"""검색 서비스 - 다조건 검색 및 저장된 검색"""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from models.property import Property
from models.saved_search import SavedSearch
from repositories.saved_search_repo import SavedSearchRepository
from exceptions import NotFoundException


class SearchService:
    def __init__(self, db: Session):
        self.db = db
        self.saved_search_repo = SavedSearchRepository(db)

    def search(self, criteria: dict) -> list:
        """다조건 동적 검색"""
        query = self.db.query(Property).filter(Property.is_active == 1)

        # Districts (list)
        districts = criteria.get("districts")
        if districts:
            query = query.filter(Property.district.in_(districts))

        # Property types (list)
        property_types = criteria.get("property_types")
        if property_types:
            query = query.filter(Property.property_type.in_(property_types))

        # Price range
        price_min = criteria.get("price_min")
        if price_min is not None:
            query = query.filter(Property.price_krw >= price_min)

        price_max = criteria.get("price_max")
        if price_max is not None:
            query = query.filter(Property.price_krw <= price_max)

        # Area range
        area_min = criteria.get("area_min")
        if area_min is not None:
            query = query.filter(Property.area_m2 >= area_min)

        area_max = criteria.get("area_max")
        if area_max is not None:
            query = query.filter(Property.area_m2 <= area_max)

        # Minimum composite score
        score_min = criteria.get("score_min")
        if score_min is not None:
            query = query.filter(Property.score_composite >= score_min)

        # Maximum subway distance (meters)
        subway_max_distance = criteria.get("subway_max_distance")
        if subway_max_distance is not None:
            query = query.filter(
                Property.nearest_subway_distance.isnot(None),
                Property.nearest_subway_distance <= subway_max_distance,
            )

        # Maximum building age (years)
        max_age = criteria.get("max_age")
        if max_age is not None:
            min_built_year = datetime.now().year - max_age
            query = query.filter(Property.built_year >= min_built_year)

        # Minimum floor
        min_floor = criteria.get("min_floor")
        if min_floor is not None:
            query = query.filter(Property.floor >= min_floor)

        # Order by composite score descending
        query = query.order_by(Property.score_composite.desc().nullslast())

        return query.all()

    def save_search(
        self, name: str, criteria: dict, alert_on_new: bool = True
    ) -> SavedSearch:
        """검색 조건 저장"""
        return self.saved_search_repo.create(
            name=name,
            criteria_json=json.dumps(criteria, ensure_ascii=False),
            alert_on_new=1 if alert_on_new else 0,
        )

    def get_saved_searches(self) -> list:
        """저장된 검색 목록 조회"""
        searches = self.saved_search_repo.get_all(offset=0, limit=100)
        result = []
        for s in searches:
            result.append({
                "id": s.id,
                "name": s.name,
                "criteria": json.loads(s.criteria_json),
                "alert_on_new": bool(s.alert_on_new),
                "match_count": s.match_count,
                "last_matched_at": (
                    s.last_matched_at.isoformat() if s.last_matched_at else None
                ),
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })
        return result

    def delete_saved_search(self, id: int):
        """저장된 검색 삭제"""
        saved = self.saved_search_repo.get_by_id(id)
        if not saved:
            raise NotFoundException(f"저장된 검색 ID {id}을(를) 찾을 수 없습니다")
        self.saved_search_repo.delete(saved)

    def match_saved_searches(self) -> dict:
        """모든 저장된 검색 실행, 매칭 결과 반환"""
        searches = self.saved_search_repo.get_active_alerts()
        results = {}

        for saved in searches:
            criteria = json.loads(saved.criteria_json)
            matches = self.search(criteria)

            results[saved.name] = {
                "search_id": saved.id,
                "match_count": len(matches),
                "matches": matches,
            }

            # Update match metadata
            saved.match_count = len(matches)
            saved.last_matched_at = datetime.utcnow()

        self.db.commit()
        return results
