"""스코어링 API - 가중치 관리 + 재채점"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from backend.config import settings
from services.scoring_service import ScoringService
from scoring.composite_scorer import CompositeScorer
from exceptions import NotFoundException

router = APIRouter()

# Module-level scorer instance (singleton pattern for weights persistence)
_scorer = CompositeScorer(settings)
_scorer_initialized = False


def _ensure_scorer_reference(db: Session):
    """스코어러에 시드 데이터 로드 (최초 1회)"""
    global _scorer_initialized
    if _scorer_initialized:
        return
    from models.subway_station import SubwayStation
    from models.park import Park
    stations = db.query(SubwayStation).all()
    parks = db.query(Park).filter(Park.park_type != "한강").all()
    rivers = db.query(Park).filter(Park.park_type == "한강").all()
    _scorer.set_reference_data(
        [{"name": s.name, "lat": s.lat, "lng": s.lng, "line": s.line} for s in stations],
        [{"name": p.name, "lat": p.lat, "lng": p.lng} for p in parks],
        [{"name": p.name, "lat": p.lat, "lng": p.lng} for p in rivers],
    )
    _scorer_initialized = True


class WeightsUpdateBody(BaseModel):
    location: float = Field(ge=0, le=1.0, description="입지 가중치")
    price: float = Field(ge=0, le=1.0, description="가격 가중치")
    property: float = Field(ge=0, le=1.0, description="매물 가중치")
    area: float = Field(ge=0, le=1.0, description="지역 가중치")


def _get_scoring_service(db: Session) -> ScoringService:
    _ensure_scorer_reference(db)
    return ScoringService(db, _scorer)


@router.get("/weights")
def get_weights():
    """현재 스코어링 가중치 조회"""
    svc = ScoringService.__new__(ScoringService)
    svc.scorer = _scorer
    return _scorer.get_weights()


@router.put("/weights")
def update_weights(body: WeightsUpdateBody, db: Session = Depends(get_db)):
    """스코어링 가중치 업데이트"""
    total = body.location + body.price + body.property + body.area
    if abs(total - 1.0) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"가중치 합계가 1.0이어야 합니다 (현재: {total:.2f})",
        )

    svc = _get_scoring_service(db)
    svc.update_weights({
        "location": body.location,
        "price": body.price,
        "property": body.property,
        "area": body.area,
    })
    return {
        "message": "가중치가 업데이트되었습니다",
        "weights": _scorer.get_weights(),
    }


@router.post("/rescore-all")
def rescore_all_properties(db: Session = Depends(get_db)):
    """모든 활성 매물 재채점"""
    svc = _get_scoring_service(db)
    result = svc.score_all()
    return {
        "message": "재채점 완료",
        "scored": result["scored"],
        "total": result["total"],
    }


@router.get("/{property_id}")
def get_score_detail(property_id: int, db: Session = Depends(get_db)):
    """매물 스코어 상세 분석"""
    svc = _get_scoring_service(db)
    try:
        result = svc.get_score_detail(property_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e.detail))
    return result
