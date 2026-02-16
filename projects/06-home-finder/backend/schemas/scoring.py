"""스코어링 스키마"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScoreWeights(BaseModel):
    """스코어링 가중치 설정 (4개 항목 합계 = 1.0)"""

    weight_location: float = Field(
        default=0.30, ge=0, le=1.0, description="입지 점수 가중치"
    )
    weight_price: float = Field(
        default=0.30, ge=0, le=1.0, description="가격 점수 가중치"
    )
    weight_property: float = Field(
        default=0.20, ge=0, le=1.0, description="매물 자체 점수 가중치"
    )
    weight_area: float = Field(
        default=0.20, ge=0, le=1.0, description="지역 점수 가중치"
    )


class ScoreDetail(BaseModel):
    """스코어 상세 분석 (4개 세부 점수 내역)"""

    # 입지 점수 내역
    score_location: float = Field(description="입지 점수 (0~100)")
    location_subway: Optional[float] = Field(
        None, description="지하철 접근성 점수"
    )
    location_park: Optional[float] = Field(
        None, description="공원/자연환경 점수"
    )
    location_river: Optional[float] = Field(
        None, description="하천 접근성 점수"
    )

    # 가격 점수 내역
    score_price: float = Field(description="가격 점수 (0~100)")
    price_vs_market: Optional[float] = Field(
        None, description="시세 대비 가격 적정성 점수"
    )
    price_trend: Optional[float] = Field(
        None, description="가격 추세 점수"
    )

    # 매물 자체 점수 내역
    score_property: float = Field(description="매물 자체 점수 (0~100)")
    property_age: Optional[float] = Field(
        None, description="건물 연식 점수"
    )
    property_floor: Optional[float] = Field(
        None, description="층수 점수"
    )
    property_direction: Optional[float] = Field(
        None, description="향 점수"
    )
    property_area_ratio: Optional[float] = Field(
        None, description="전용률 점수"
    )

    # 지역 점수 내역
    score_area: float = Field(description="지역 점수 (0~100)")
    area_development: Optional[float] = Field(
        None, description="개발 호재 점수"
    )
    area_living: Optional[float] = Field(
        None, description="생활 편의 점수"
    )
    area_infra: Optional[float] = Field(
        None, description="인프라 점수"
    )


class ScoreResponse(BaseModel):
    """스코어링 결과 응답"""

    property_id: int = Field(description="매물 ID")
    score_composite: float = Field(description="종합 점수 (0~100)")
    detail: ScoreDetail = Field(description="세부 점수 내역")
    weights: ScoreWeights = Field(description="적용된 가중치")
    scored_at: Optional[datetime] = Field(None, description="스코어링 일시")
    rank: Optional[int] = Field(None, description="순위 (전체 매물 중)")
    total_properties: Optional[int] = Field(None, description="전체 매물 수")
