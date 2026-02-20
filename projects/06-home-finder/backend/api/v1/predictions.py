"""가격 예측 & 기회 매물 API"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from price_predictor import PricePredictor

router = APIRouter()

_predictor = PricePredictor()


@router.get("/district-forecast")
def get_district_forecast(db: Session = Depends(get_db)):
    """
    모든 구의 6개월 가격 예측 데이터를 반환.
    현재 평균, 예측 평균, 변동률, 추세 방향, 신뢰도 포함.
    """
    forecasts = _predictor.get_district_forecasts(db)
    return {
        "forecasts": forecasts,
        "count": len(forecasts),
    }


@router.get("/opportunities")
def get_opportunities(
    limit: int = Query(10, ge=1, le=50, description="조회 건수"),
    db: Session = Depends(get_db),
):
    """
    기회 점수 상위 매물 목록을 반환.
    할인율, 종합점수, 신규 보너스, 지역 개발 점수를 종합 평가.
    """
    opportunities = _predictor.get_hot_opportunities(db, limit=limit)
    return {
        "opportunities": opportunities,
        "count": len(opportunities),
    }


@router.get("/property/{property_id}/analysis")
def get_property_analysis(
    property_id: int,
    db: Session = Depends(get_db),
):
    """
    특정 매물의 가격 예측 및 기회 분석 컨텍스트를 반환.
    구 추세, 기회 점수, 유사 매물 비교 포함.
    """
    analysis = _predictor.get_property_analysis(property_id, db)
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail=f"매물 ID {property_id}을(를) 찾을 수 없습니다",
        )
    return analysis
