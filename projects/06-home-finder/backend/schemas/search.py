"""검색 조건 스키마"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from .common import PropertyType, AcquisitionType, SortOrder


class SearchCriteria(BaseModel):
    """다조건 검색 필터"""

    # 거래유형 (매매/전세/월세)
    transaction_type: Optional[str] = Field(
        None, description="거래유형: 매매, 전세, 월세"
    )

    # 가격 범위 (원) — 매매가 또는 보증금
    price_min: Optional[int] = Field(None, ge=0, description="최소 매매가/보증금 (원)")
    price_max: Optional[int] = Field(None, ge=0, description="최대 매매가/보증금 (원)")

    # 월세 범위
    monthly_rent_min: Optional[int] = Field(None, ge=0, description="최소 월세 (원)")
    monthly_rent_max: Optional[int] = Field(None, ge=0, description="최대 월세 (원)")

    # 면적 범위 (m2)
    area_min: Optional[float] = Field(None, gt=0, description="최소 전용면적 (m2)")
    area_max: Optional[float] = Field(None, gt=0, description="최대 전용면적 (m2)")

    # 지역 필터
    city: Optional[str] = Field(None, description="시/도")
    districts: Optional[List[str]] = Field(
        None, description="구 목록 (복수 선택 가능)"
    )
    dongs: Optional[List[str]] = Field(
        None, description="동 목록 (복수 선택 가능)"
    )

    # 매물 유형 필터
    property_types: Optional[List[PropertyType]] = Field(
        None, description="매물 유형 목록 (복수 선택 가능)"
    )
    acquisition_types: Optional[List[AcquisitionType]] = Field(
        None, description="취득 방법 목록 (복수 선택 가능)"
    )

    # 지하철 거리
    subway_max_distance: Optional[float] = Field(
        None, ge=0, description="지하철역 최대 거리 (m)"
    )

    # 스코어 기준
    score_min: Optional[float] = Field(
        None, ge=0, description="최소 종합 점수 (0~100)"
    )

    # 매물 상세 필터
    rooms_min: Optional[int] = Field(None, ge=0, description="최소 방 수")
    floor_min: Optional[int] = Field(None, description="최소 층")
    built_year_min: Optional[int] = Field(None, ge=1950, description="최소 건축년도")
    built_year_max: Optional[int] = Field(None, description="최대 건축년도")

    # 향 필터
    directions: Optional[List[str]] = Field(
        None, description="향 목록 (남향, 남동향 등 복수 선택 가능)"
    )

    # 토지 전용 필터
    property_category: Optional[str] = Field(
        None, description="매물 분류: 건물, 토지, 또는 None=전체"
    )
    land_uses: Optional[List[str]] = Field(
        None, description="지목 필터 (대, 전, 답, 잡종지 등)"
    )
    zoning_types: Optional[List[str]] = Field(
        None, description="용도지역 필터"
    )
    min_bcr: Optional[float] = Field(
        None, ge=0, description="최소 건폐율 (%)"
    )
    min_far: Optional[float] = Field(
        None, ge=0, description="최소 용적률 (%)"
    )
    road_frontage_types: Optional[List[str]] = Field(
        None, description="접도 상태 필터 (맹지, 4m미만, 4~6m, 6~8m, 8m이상)"
    )
    topography_types: Optional[List[str]] = Field(
        None, description="지형 필터 (평지, 완경사, 경사)"
    )

    # 세대수 필터
    min_total_units: Optional[int] = Field(
        None, ge=0, description="최소 세대수 (단지 기준)"
    )

    # 활성 여부
    is_active: Optional[int] = Field(
        None, ge=0, le=1, description="활성 여부 (0/1)"
    )

    # 정렬
    sort: SortOrder = Field(
        default=SortOrder.score_desc, description="정렬 순서"
    )

    # 페이지네이션
    page: int = Field(default=1, ge=1, description="페이지 번호")
    page_size: int = Field(default=20, ge=1, le=100, description="페이지당 항목 수")


class SavedSearchCreate(BaseModel):
    """저장된 검색조건 생성 요청"""

    name: str = Field(max_length=100, description="검색조건 이름")
    criteria: SearchCriteria = Field(description="검색 조건")
    alert_on_new: bool = Field(
        default=True, description="새 매물 알림 활성화"
    )
    alert_on_price_change: bool = Field(
        default=False, description="가격 변동 알림 활성화"
    )


class SavedSearchResponse(BaseModel):
    """저장된 검색조건 응답"""

    model_config = {"from_attributes": True}

    id: int = Field(description="저장된 검색 ID")
    name: str = Field(description="검색조건 이름")
    criteria_json: str = Field(description="검색 조건 JSON 문자열")
    alert_on_new: Optional[int] = Field(None, description="새 매물 알림 (0/1)")
    alert_on_price_change: Optional[int] = Field(
        None, description="가격 변동 알림 (0/1)"
    )
    last_matched_at: Optional[datetime] = Field(None, description="마지막 매칭 일시")
    match_count: Optional[int] = Field(None, description="매칭된 매물 수")
    created_at: Optional[datetime] = Field(None, description="생성일시")
    updated_at: Optional[datetime] = Field(None, description="수정일시")
