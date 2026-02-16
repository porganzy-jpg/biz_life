"""아파트 단지 스키마"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ComplexCreate(BaseModel):
    """단지 생성 요청"""

    name: str = Field(max_length=100, description="단지명")
    city: Optional[str] = Field(None, max_length=30, description="시/도")
    district: Optional[str] = Field(None, max_length=30, description="구")
    dong: Optional[str] = Field(None, max_length=30, description="동")
    address: Optional[str] = Field(None, max_length=200, description="주소")
    lat: Optional[float] = Field(None, description="위도")
    lng: Optional[float] = Field(None, description="경도")

    built_year: Optional[int] = Field(None, ge=1950, description="건축년도")
    total_units: Optional[int] = Field(None, ge=1, description="총 세대수")
    total_buildings: Optional[int] = Field(None, ge=1, description="총 동수")
    parking_ratio: Optional[float] = Field(None, ge=0, description="주차 대수 비율")
    heating_type: Optional[str] = Field(None, max_length=30, description="난방 방식")
    developer: Optional[str] = Field(None, max_length=100, description="시공사/건설사")

    avg_price_per_m2: Optional[int] = Field(None, ge=0, description="평균 평당가 (원/m2)")
    min_price: Optional[int] = Field(None, ge=0, description="최저 매매가 (원)")
    max_price: Optional[int] = Field(None, ge=0, description="최고 매매가 (원)")
    price_trend_1y: Optional[float] = Field(None, description="1년 가격 변동률 (%)")

    reconstruction_status: Optional[str] = Field(
        None, max_length=50, description="재건축 상태 (해당없음, 추진중, 확정)"
    )
    reconstruction_year: Optional[int] = Field(None, description="재건축 예정년도")

    description: Optional[str] = Field(None, description="단지 설명")
    source_id: Optional[str] = Field(None, max_length=100, description="소스 고유 ID")


class ComplexResponse(BaseModel):
    """단지 상세 응답"""

    model_config = {"from_attributes": True}

    id: int = Field(description="단지 ID")
    name: str = Field(description="단지명")
    city: Optional[str] = Field(None, description="시/도")
    district: Optional[str] = Field(None, description="구")
    dong: Optional[str] = Field(None, description="동")
    address: Optional[str] = Field(None, description="주소")
    lat: Optional[float] = Field(None, description="위도")
    lng: Optional[float] = Field(None, description="경도")

    built_year: Optional[int] = Field(None, description="건축년도")
    total_units: Optional[int] = Field(None, description="총 세대수")
    total_buildings: Optional[int] = Field(None, description="총 동수")
    parking_ratio: Optional[float] = Field(None, description="주차 대수 비율")
    heating_type: Optional[str] = Field(None, description="난방 방식")
    developer: Optional[str] = Field(None, description="시공사/건설사")

    avg_price_per_m2: Optional[int] = Field(None, description="평균 평당가 (원/m2)")
    min_price: Optional[int] = Field(None, description="최저 매매가 (원)")
    max_price: Optional[int] = Field(None, description="최고 매매가 (원)")
    price_trend_1y: Optional[float] = Field(None, description="1년 가격 변동률 (%)")

    reconstruction_status: Optional[str] = Field(None, description="재건축 상태")
    reconstruction_year: Optional[int] = Field(None, description="재건축 예정년도")

    description: Optional[str] = Field(None, description="단지 설명")
    source_id: Optional[str] = Field(None, description="소스 고유 ID")
    created_at: Optional[datetime] = Field(None, description="등록일시")
    updated_at: Optional[datetime] = Field(None, description="수정일시")
