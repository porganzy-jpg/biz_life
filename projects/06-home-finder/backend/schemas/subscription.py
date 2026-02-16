"""청약 스키마"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class SubscriptionResponse(BaseModel):
    """청약 정보 응답"""

    model_config = {"from_attributes": True}

    id: int = Field(description="청약 ID")
    name: str = Field(description="단지명")
    city: Optional[str] = Field(None, description="시/도")
    district: Optional[str] = Field(None, description="구")
    dong: Optional[str] = Field(None, description="동")
    address: Optional[str] = Field(None, description="주소")
    lat: Optional[float] = Field(None, description="위도")
    lng: Optional[float] = Field(None, description="경도")

    developer: Optional[str] = Field(None, description="시공사/건설사")
    total_units: Optional[int] = Field(None, description="총 세대수")
    subscription_units: Optional[int] = Field(None, description="청약 세대수")

    # 일정
    subscription_start: Optional[date] = Field(None, description="청약 접수 시작일")
    subscription_end: Optional[date] = Field(None, description="청약 접수 마감일")
    announcement_date: Optional[date] = Field(None, description="당첨 발표일")
    move_in_date: Optional[date] = Field(None, description="입주 예정일")

    # 가격
    min_price: Optional[int] = Field(None, description="최소 분양가 (원)")
    max_price: Optional[int] = Field(None, description="최대 분양가 (원)")
    avg_price_per_m2: Optional[int] = Field(None, description="평균 평당가 (원/m2)")

    # 면적
    min_area_m2: Optional[float] = Field(None, description="최소 전용면적 (m2)")
    max_area_m2: Optional[float] = Field(None, description="최대 전용면적 (m2)")

    # 경쟁
    competition_rate: Optional[float] = Field(None, description="경쟁률")
    subscription_type: Optional[str] = Field(
        None, description="청약 유형 (일반, 특별공급 등)"
    )
    status: Optional[str] = Field(
        None, description="상태 (접수중, 마감, 당첨발표)"
    )

    # 메타
    source_url: Optional[str] = Field(None, description="원본 URL")
    source_id: Optional[str] = Field(None, description="소스 고유 ID")
    description: Optional[str] = Field(None, description="설명")
    created_at: Optional[datetime] = Field(None, description="등록일시")
    updated_at: Optional[datetime] = Field(None, description="수정일시")
