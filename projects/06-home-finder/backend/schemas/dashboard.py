"""대시보드 스키마"""
from typing import Optional, List

from pydantic import BaseModel, Field

from .candidate import CandidatePipeline


class PriceStats(BaseModel):
    """가격 통계"""

    avg_price_krw: Optional[int] = Field(None, description="평균 매매가 (원)")
    median_price_krw: Optional[int] = Field(None, description="중앙값 매매가 (원)")
    min_price_krw: Optional[int] = Field(None, description="최저 매매가 (원)")
    max_price_krw: Optional[int] = Field(None, description="최고 매매가 (원)")
    avg_price_per_m2: Optional[int] = Field(None, description="평균 평당가 (원/m2)")


class TopCandidate(BaseModel):
    """상위 후보 매물 요약"""

    candidate_id: int = Field(description="후보 ID")
    property_id: Optional[int] = Field(None, description="매물 ID")
    complex_name: Optional[str] = Field(None, description="단지명")
    district: Optional[str] = Field(None, description="구")
    dong: Optional[str] = Field(None, description="동")
    price_krw: Optional[int] = Field(None, description="매매가 (원)")
    area_m2: Optional[float] = Field(None, description="전용면적 (m2)")
    score_composite: Optional[float] = Field(None, description="종합 점수")
    status: Optional[str] = Field(None, description="파이프라인 상태")
    priority: Optional[int] = Field(None, description="우선순위")


class DashboardSummary(BaseModel):
    """대시보드 종합 요약"""

    # 건수
    total_properties: int = Field(default=0, description="전체 매물 수")
    active_properties: int = Field(default=0, description="활성 매물 수")
    total_auctions: int = Field(default=0, description="전체 경매 물건 수")
    active_auctions: int = Field(default=0, description="진행중 경매 수")
    total_subscriptions: int = Field(default=0, description="전체 청약 수")
    active_subscriptions: int = Field(default=0, description="접수중 청약 수")

    # 후보 파이프라인
    pipeline: CandidatePipeline = Field(
        default_factory=CandidatePipeline,
        description="후보 매물 파이프라인 현황"
    )

    # 상위 후보
    top_candidates: List[TopCandidate] = Field(
        default_factory=list, description="상위 후보 매물 목록"
    )

    # 가격 통계
    price_stats: Optional[PriceStats] = Field(
        None, description="활성 매물 가격 통계"
    )

    # 최근 활동
    new_properties_7d: int = Field(
        default=0, description="최근 7일 신규 매물 수"
    )
    new_candidates_7d: int = Field(
        default=0, description="최근 7일 신규 후보 수"
    )
    saved_search_count: int = Field(
        default=0, description="저장된 검색조건 수"
    )


class MapMarker(BaseModel):
    """지도 마커 데이터"""

    id: int = Field(description="매물 ID")
    lat: float = Field(description="위도")
    lng: float = Field(description="경도")
    price_krw: Optional[int] = Field(None, description="매매가 (원)")
    score_composite: Optional[float] = Field(None, description="종합 점수")
    color: str = Field(
        default="blue",
        description="마커 색상 (점수 기반: red=높음, orange=중간, blue=보통, gray=낮음)"
    )
    label: Optional[str] = Field(None, description="마커 라벨 (단지명 또는 주소)")
    property_type: Optional[str] = Field(None, description="매물 유형")
    acquisition_type: Optional[str] = Field(None, description="취득 방법")
    is_candidate: bool = Field(
        default=False, description="후보 매물 여부"
    )
