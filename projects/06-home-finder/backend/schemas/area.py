"""지역(구/동) 스키마"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AreaResponse(BaseModel):
    """지역 상세 응답"""

    model_config = {"from_attributes": True}

    id: int = Field(description="지역 ID")
    city: Optional[str] = Field(None, description="시/도")
    district: str = Field(description="구")
    dong: Optional[str] = Field(None, description="동")
    area_code: Optional[str] = Field(None, description="법정동코드")

    population: Optional[int] = Field(None, description="인구수")
    households: Optional[int] = Field(None, description="세대수")
    subway_count: Optional[int] = Field(None, description="지하철역 수")
    park_count: Optional[int] = Field(None, description="공원 수")
    school_count: Optional[int] = Field(None, description="학교 수")
    hospital_count: Optional[int] = Field(None, description="병원 수")

    avg_price_per_m2: Optional[int] = Field(None, description="평균 평당가 (원/m2)")
    price_change_1y: Optional[float] = Field(None, description="1년 가격 변동률 (%)")
    price_change_3y: Optional[float] = Field(None, description="3년 가격 변동률 (%)")

    development_plan: Optional[str] = Field(None, description="개발 계획 (재개발/GTX 등)")
    development_score: Optional[float] = Field(None, description="개발 호재 점수")
    living_score: Optional[float] = Field(None, description="생활 편의 점수")
    infra_score: Optional[float] = Field(None, description="인프라 점수")
    area_composite_score: Optional[float] = Field(None, description="지역 종합 점수")

    description: Optional[str] = Field(None, description="지역 설명")
    created_at: Optional[datetime] = Field(None, description="등록일시")
    updated_at: Optional[datetime] = Field(None, description="수정일시")


class AreaComparison(BaseModel):
    """지역 비교 응답 (2개 이상 지역 비교용)"""

    district: str = Field(description="구")
    dong: Optional[str] = Field(None, description="동")

    avg_price_per_m2: Optional[int] = Field(None, description="평균 평당가 (원/m2)")
    price_change_1y: Optional[float] = Field(None, description="1년 가격 변동률 (%)")
    price_change_3y: Optional[float] = Field(None, description="3년 가격 변동률 (%)")

    population: Optional[int] = Field(None, description="인구수")
    households: Optional[int] = Field(None, description="세대수")
    subway_count: Optional[int] = Field(None, description="지하철역 수")
    park_count: Optional[int] = Field(None, description="공원 수")
    school_count: Optional[int] = Field(None, description="학교 수")
    hospital_count: Optional[int] = Field(None, description="병원 수")

    development_score: Optional[float] = Field(None, description="개발 호재 점수")
    living_score: Optional[float] = Field(None, description="생활 편의 점수")
    infra_score: Optional[float] = Field(None, description="인프라 점수")
    area_composite_score: Optional[float] = Field(None, description="지역 종합 점수")
