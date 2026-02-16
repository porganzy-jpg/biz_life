"""후보 매물 스키마"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from .common import CandidateStatus


class CandidateCreate(BaseModel):
    """후보 매물 생성 요청"""

    property_id: int = Field(description="매물 ID (properties.id)")
    auction_id: Optional[int] = Field(None, description="경매 ID (선택)")
    subscription_id: Optional[int] = Field(None, description="청약 ID (선택)")

    status: CandidateStatus = Field(
        default=CandidateStatus.발견, description="파이프라인 상태"
    )
    priority: int = Field(
        default=3, ge=1, le=5, description="우선순위 (1=최고, 5=최저)"
    )
    tags: Optional[str] = Field(None, max_length=200, description="태그 (쉼표 구분)")
    pros: Optional[str] = Field(None, description="장점")
    cons: Optional[str] = Field(None, description="단점")


class CandidateUpdate(BaseModel):
    """후보 매물 수정 요청 (부분 업데이트)"""

    status: Optional[CandidateStatus] = Field(None, description="파이프라인 상태")
    priority: Optional[int] = Field(
        None, ge=1, le=5, description="우선순위 (1=최고, 5=최저)"
    )
    rating: Optional[int] = Field(
        None, ge=1, le=5, description="방문 후 평점 (1~5)"
    )

    visit_date: Optional[datetime] = Field(None, description="방문 일시")
    visit_notes: Optional[str] = Field(None, description="방문 메모")
    decision: Optional[str] = Field(
        None, max_length=20, description="결정 (보류, 탈락, 최종후보)"
    )
    decision_reason: Optional[str] = Field(None, description="결정 사유")

    tags: Optional[str] = Field(None, max_length=200, description="태그 (쉼표 구분)")
    pros: Optional[str] = Field(None, description="장점")
    cons: Optional[str] = Field(None, description="단점")


class CandidateResponse(BaseModel):
    """후보 매물 상세 응답"""

    model_config = {"from_attributes": True}

    id: int = Field(description="후보 ID")
    property_id: Optional[int] = Field(None, description="매물 ID")
    auction_id: Optional[int] = Field(None, description="경매 ID")
    subscription_id: Optional[int] = Field(None, description="청약 ID")

    status: str = Field(description="파이프라인 상태")
    priority: Optional[int] = Field(None, description="우선순위")
    rating: Optional[int] = Field(None, description="방문 후 평점")

    visit_date: Optional[datetime] = Field(None, description="방문 일시")
    visit_notes: Optional[str] = Field(None, description="방문 메모")
    decision: Optional[str] = Field(None, description="결정")
    decision_reason: Optional[str] = Field(None, description="결정 사유")

    tags: Optional[str] = Field(None, description="태그")
    pros: Optional[str] = Field(None, description="장점")
    cons: Optional[str] = Field(None, description="단점")

    created_at: Optional[datetime] = Field(None, description="등록일시")
    updated_at: Optional[datetime] = Field(None, description="수정일시")


class CandidateStatusCount(BaseModel):
    """파이프라인 상태별 건수"""

    status: str = Field(description="상태명")
    count: int = Field(default=0, description="건수")


class CandidatePipeline(BaseModel):
    """후보 매물 파이프라인 요약 (상태별 건수)"""

    total: int = Field(default=0, description="전체 후보 수")
    status_counts: List[CandidateStatusCount] = Field(
        default_factory=list, description="상태별 건수 목록"
    )
    발견: int = Field(default=0, description="발견 상태 건수")
    조사: int = Field(default=0, description="조사 상태 건수")
    관심: int = Field(default=0, description="관심 상태 건수")
    방문예정: int = Field(default=0, description="방문예정 상태 건수")
    방문완료: int = Field(default=0, description="방문완료 상태 건수")
    결정: int = Field(default=0, description="결정 상태 건수")
