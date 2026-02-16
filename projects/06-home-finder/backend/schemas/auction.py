"""경매 스키마"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuctionResponse(BaseModel):
    """경매 물건 상세 응답"""

    model_config = {"from_attributes": True}

    id: int = Field(description="경매 ID")
    case_number: str = Field(description="사건번호")
    court: Optional[str] = Field(None, description="법원")

    # 위치
    city: Optional[str] = Field(None, description="시/도")
    district: Optional[str] = Field(None, description="구")
    dong: Optional[str] = Field(None, description="동")
    address: Optional[str] = Field(None, description="주소")
    lat: Optional[float] = Field(None, description="위도")
    lng: Optional[float] = Field(None, description="경도")

    # 매물 정보
    property_type: Optional[str] = Field(None, description="매물 유형")
    area_m2: Optional[float] = Field(None, description="면적 (m2)")
    floor: Optional[int] = Field(None, description="층")
    built_year: Optional[int] = Field(None, description="건축년도")

    # 가격 (할인율 중심)
    appraisal_price: Optional[int] = Field(None, description="감정가 (원)")
    minimum_bid: Optional[int] = Field(None, description="최저입찰가 (원)")
    current_bid_round: Optional[int] = Field(None, description="현재 입찰 회차")
    discount_rate: Optional[float] = Field(
        None, description="감정가 대비 할인율 (%) - 할인율이 높을수록 저렴"
    )

    # 경매 진행
    auction_date: Optional[date] = Field(None, description="경매일")
    auction_status: Optional[str] = Field(
        None, description="경매 상태 (진행중, 낙찰, 유찰, 취하)"
    )

    # 리스크 분석
    risk_level: Optional[str] = Field(None, description="리스크 수준 (낮음, 보통, 높음)")
    risk_notes: Optional[str] = Field(None, description="권리분석 메모")
    occupancy_status: Optional[str] = Field(None, description="점유 현황")

    # 메타
    source_url: Optional[str] = Field(None, description="원본 URL")
    description: Optional[str] = Field(None, description="물건 설명")
    created_at: Optional[datetime] = Field(None, description="등록일시")
    updated_at: Optional[datetime] = Field(None, description="수정일시")


class AuctionDeal(BaseModel):
    """경매 할인 거래 요약 (할인율 중심 뷰)"""

    id: int = Field(description="경매 ID")
    case_number: str = Field(description="사건번호")
    district: Optional[str] = Field(None, description="구")
    dong: Optional[str] = Field(None, description="동")
    address: Optional[str] = Field(None, description="주소")
    property_type: Optional[str] = Field(None, description="매물 유형")
    area_m2: Optional[float] = Field(None, description="면적 (m2)")

    appraisal_price: Optional[int] = Field(None, description="감정가 (원)")
    minimum_bid: Optional[int] = Field(None, description="최저입찰가 (원)")
    discount_rate: Optional[float] = Field(
        None, description="감정가 대비 할인율 (%)"
    )
    current_bid_round: Optional[int] = Field(None, description="현재 입찰 회차")
    estimated_market_price: Optional[int] = Field(
        None, description="추정 시세 (원) - 주변 실거래가 기반"
    )
    estimated_profit_rate: Optional[float] = Field(
        None, description="예상 수익률 (%) - (시세 - 최저입찰가) / 최저입찰가"
    )

    auction_date: Optional[date] = Field(None, description="경매일")
    auction_status: Optional[str] = Field(None, description="경매 상태")
    risk_level: Optional[str] = Field(None, description="리스크 수준")
