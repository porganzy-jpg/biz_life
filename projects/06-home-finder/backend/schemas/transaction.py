"""실거래가 스키마"""
from __future__ import annotations

import datetime as _dt
from typing import Optional, List

from pydantic import BaseModel, Field


class TransactionResponse(BaseModel):
    """실거래가 이력 응답"""

    model_config = {"from_attributes": True}

    id: int = Field(description="거래 ID")
    city: Optional[str] = Field(None, description="시/도")
    district: Optional[str] = Field(None, description="구")
    dong: Optional[str] = Field(None, description="동")
    name: Optional[str] = Field(None, description="단지명/건물명")
    address: Optional[str] = Field(None, description="주소")

    transaction_date: Optional[_dt.date] = Field(None, description="거래일")
    price_krw: Optional[int] = Field(None, description="거래가 (원)")
    area_exclusive: Optional[float] = Field(None, description="전용면적 (m2)")
    floor: Optional[int] = Field(None, description="층")
    built_year: Optional[int] = Field(None, description="건축년도")
    property_type: Optional[str] = Field(None, description="매물 유형")
    price_per_m2: Optional[int] = Field(None, description="평당가 (원/m2)")

    source: Optional[str] = Field(None, description="데이터 소스")
    created_at: Optional[_dt.datetime] = Field(None, description="수집일시")


class PriceTrendPoint(BaseModel):
    """가격 추이 개별 데이터 포인트"""

    date: _dt.date = Field(description="기준일")
    avg_price_krw: int = Field(description="평균 거래가 (원)")
    avg_price_per_m2: Optional[int] = Field(None, description="평균 평당가 (원/m2)")
    transaction_count: int = Field(description="거래 건수")
    min_price_krw: Optional[int] = Field(None, description="최저 거래가 (원)")
    max_price_krw: Optional[int] = Field(None, description="최고 거래가 (원)")


class PriceTrend(BaseModel):
    """가격 추이 응답"""

    name: Optional[str] = Field(None, description="단지명/지역명")
    district: Optional[str] = Field(None, description="구")
    period_start: _dt.date = Field(description="조회 시작일")
    period_end: _dt.date = Field(description="조회 종료일")
    data_points: List[PriceTrendPoint] = Field(
        default_factory=list, description="기간별 가격 추이 데이터"
    )
    total_transactions: int = Field(default=0, description="총 거래 건수")
    overall_change_pct: Optional[float] = Field(
        None, description="전체 기간 가격 변동률 (%)"
    )
