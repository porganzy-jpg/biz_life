"""매물 스키마"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .common import PropertyType, AcquisitionType, DataSource


class PropertyCreate(BaseModel):
    """매물 생성 요청"""

    source: DataSource = Field(description="데이터 소스")
    property_type: PropertyType = Field(description="매물 유형 (아파트, 빌라 등)")
    acquisition_type: AcquisitionType = Field(
        default=AcquisitionType.매매, description="취득 방법 (매매, 경매, 청약)"
    )

    # 위치
    city: Optional[str] = Field(None, max_length=30, description="시/도")
    district: Optional[str] = Field(None, max_length=30, description="구")
    dong: Optional[str] = Field(None, max_length=30, description="동")
    address: Optional[str] = Field(None, max_length=200, description="주소")
    detail_address: Optional[str] = Field(None, max_length=200, description="상세주소")
    lat: Optional[float] = Field(None, description="위도")
    lng: Optional[float] = Field(None, description="경도")

    # 가격
    price_krw: Optional[int] = Field(None, ge=0, description="매매가 (원)")
    price_per_m2: Optional[int] = Field(None, ge=0, description="평당가 (원/m2)")

    # 매물 상세
    area_m2: Optional[float] = Field(None, gt=0, description="전용면적 (m2)")
    area_supply_m2: Optional[float] = Field(None, gt=0, description="공급면적 (m2)")
    floor: Optional[int] = Field(None, description="층")
    total_floors: Optional[int] = Field(None, ge=1, description="총 층수")
    rooms: Optional[int] = Field(None, ge=0, description="방 수")
    bathrooms: Optional[int] = Field(None, ge=0, description="화장실 수")
    direction: Optional[str] = Field(None, max_length=20, description="향 (남향, 남동향 등)")
    built_year: Optional[int] = Field(None, ge=1950, description="건축년도")
    maintenance_fee: Optional[int] = Field(None, ge=0, description="관리비 (만원)")

    # 단지 정보
    complex_name: Optional[str] = Field(None, max_length=100, description="단지명")
    complex_id: Optional[int] = Field(None, description="단지 ID")

    # 토지 전용
    land_use: Optional[str] = Field(None, max_length=30, description="지목 (대, 전, 답, 임야, 잡종지)")
    zoning_type: Optional[str] = Field(None, max_length=50, description="용도지역")
    building_coverage_ratio: Optional[float] = Field(None, ge=0, le=100, description="건폐율 (%)")
    floor_area_ratio: Optional[float] = Field(None, ge=0, description="용적률 (%)")
    road_frontage: Optional[str] = Field(None, max_length=50, description="접도 상태")
    topography: Optional[str] = Field(None, max_length=30, description="지형")

    # 메타
    source_url: Optional[str] = Field(None, max_length=500, description="원본 URL")
    source_id: Optional[str] = Field(None, max_length=100, description="소스 고유 ID")
    description: Optional[str] = Field(None, description="매물 설명")


class PropertyUpdate(BaseModel):
    """매물 수정 요청 (부분 업데이트)"""

    property_type: Optional[PropertyType] = Field(None, description="매물 유형")
    acquisition_type: Optional[AcquisitionType] = Field(None, description="취득 방법")

    city: Optional[str] = Field(None, max_length=30, description="시/도")
    district: Optional[str] = Field(None, max_length=30, description="구")
    dong: Optional[str] = Field(None, max_length=30, description="동")
    address: Optional[str] = Field(None, max_length=200, description="주소")
    detail_address: Optional[str] = Field(None, max_length=200, description="상세주소")
    lat: Optional[float] = Field(None, description="위도")
    lng: Optional[float] = Field(None, description="경도")

    price_krw: Optional[int] = Field(None, ge=0, description="매매가 (원)")
    price_per_m2: Optional[int] = Field(None, ge=0, description="평당가 (원/m2)")

    area_m2: Optional[float] = Field(None, gt=0, description="전용면적 (m2)")
    area_supply_m2: Optional[float] = Field(None, gt=0, description="공급면적 (m2)")
    floor: Optional[int] = Field(None, description="층")
    total_floors: Optional[int] = Field(None, ge=1, description="총 층수")
    rooms: Optional[int] = Field(None, ge=0, description="방 수")
    bathrooms: Optional[int] = Field(None, ge=0, description="화장실 수")
    direction: Optional[str] = Field(None, max_length=20, description="향")
    built_year: Optional[int] = Field(None, ge=1950, description="건축년도")
    maintenance_fee: Optional[int] = Field(None, ge=0, description="관리비 (만원)")

    complex_name: Optional[str] = Field(None, max_length=100, description="단지명")
    complex_id: Optional[int] = Field(None, description="단지 ID")

    # 토지 전용
    land_use: Optional[str] = Field(None, max_length=30, description="지목")
    zoning_type: Optional[str] = Field(None, max_length=50, description="용도지역")
    building_coverage_ratio: Optional[float] = Field(None, ge=0, le=100, description="건폐율 (%)")
    floor_area_ratio: Optional[float] = Field(None, ge=0, description="용적률 (%)")
    road_frontage: Optional[str] = Field(None, max_length=50, description="접도 상태")
    topography: Optional[str] = Field(None, max_length=30, description="지형")

    source_url: Optional[str] = Field(None, max_length=500, description="원본 URL")
    description: Optional[str] = Field(None, description="매물 설명")
    is_active: Optional[int] = Field(None, ge=0, le=1, description="활성 여부 (0/1)")


class PropertyResponse(BaseModel):
    """매물 상세 응답"""

    model_config = {"from_attributes": True}

    id: int = Field(description="매물 ID")
    source: str = Field(description="데이터 소스")
    property_type: str = Field(description="매물 유형")
    acquisition_type: str = Field(description="취득 방법")

    # 위치
    city: Optional[str] = Field(None, description="시/도")
    district: Optional[str] = Field(None, description="구")
    dong: Optional[str] = Field(None, description="동")
    address: Optional[str] = Field(None, description="주소")
    detail_address: Optional[str] = Field(None, description="상세주소")
    lat: Optional[float] = Field(None, description="위도")
    lng: Optional[float] = Field(None, description="경도")

    # 가격
    price_krw: Optional[int] = Field(None, description="매매가 (원)")
    price_per_m2: Optional[int] = Field(None, description="평당가 (원/m2)")

    # 매물 상세
    area_m2: Optional[float] = Field(None, description="전용면적 (m2)")
    area_supply_m2: Optional[float] = Field(None, description="공급면적 (m2)")
    floor: Optional[int] = Field(None, description="층")
    total_floors: Optional[int] = Field(None, description="총 층수")
    rooms: Optional[int] = Field(None, description="방 수")
    bathrooms: Optional[int] = Field(None, description="화장실 수")
    direction: Optional[str] = Field(None, description="향")
    built_year: Optional[int] = Field(None, description="건축년도")
    maintenance_fee: Optional[int] = Field(None, description="관리비 (만원)")

    # 단지 정보
    complex_name: Optional[str] = Field(None, description="단지명")
    complex_id: Optional[int] = Field(None, description="단지 ID")

    # 토지 전용
    land_use: Optional[str] = Field(None, description="지목")
    zoning_type: Optional[str] = Field(None, description="용도지역")
    building_coverage_ratio: Optional[float] = Field(None, description="건폐율 (%)")
    floor_area_ratio: Optional[float] = Field(None, description="용적률 (%)")
    road_frontage: Optional[str] = Field(None, description="접도 상태")
    topography: Optional[str] = Field(None, description="지형")

    # 스코어
    score_location: Optional[float] = Field(None, description="입지 점수")
    score_price: Optional[float] = Field(None, description="가격 점수")
    score_property: Optional[float] = Field(None, description="매물 자체 점수")
    score_area: Optional[float] = Field(None, description="지역 점수")
    score_composite: Optional[float] = Field(None, description="종합 점수")

    # 주변 인프라
    nearest_subway_name: Optional[str] = Field(None, description="최근접 지하철역")
    nearest_subway_distance: Optional[float] = Field(None, description="지하철역 거리 (m)")
    nearest_subway_lines: Optional[str] = Field(None, description="지하철 노선")
    nearest_park_name: Optional[str] = Field(None, description="최근접 공원")
    nearest_park_distance: Optional[float] = Field(None, description="공원 거리 (m)")
    nearest_river_distance: Optional[float] = Field(None, description="하천 거리 (m)")

    # 메타
    source_url: Optional[str] = Field(None, description="원본 URL")
    source_id: Optional[str] = Field(None, description="소스 고유 ID")
    description: Optional[str] = Field(None, description="매물 설명")
    is_active: Optional[int] = Field(None, description="활성 여부")
    created_at: Optional[datetime] = Field(None, description="등록일시")
    updated_at: Optional[datetime] = Field(None, description="수정일시")
    scored_at: Optional[datetime] = Field(None, description="스코어링 일시")


class PropertyBrief(BaseModel):
    """매물 목록용 간략 응답"""

    model_config = {"from_attributes": True}

    id: int = Field(description="매물 ID")
    property_type: str = Field(description="매물 유형")
    acquisition_type: str = Field(description="취득 방법")
    district: Optional[str] = Field(None, description="구")
    dong: Optional[str] = Field(None, description="동")
    address: Optional[str] = Field(None, description="주소")
    complex_name: Optional[str] = Field(None, description="단지명")
    price_krw: Optional[int] = Field(None, description="매매가 (원)")
    area_m2: Optional[float] = Field(None, description="전용면적 (m2)")
    floor: Optional[int] = Field(None, description="층")
    rooms: Optional[int] = Field(None, description="방 수")
    built_year: Optional[int] = Field(None, description="건축년도")
    score_composite: Optional[float] = Field(None, description="종합 점수")
    nearest_subway_name: Optional[str] = Field(None, description="최근접 지하철역")
    nearest_subway_distance: Optional[float] = Field(None, description="지하철역 거리 (m)")
    # 토지 전용
    land_use: Optional[str] = Field(None, description="지목")
    zoning_type: Optional[str] = Field(None, description="용도지역")
    building_coverage_ratio: Optional[float] = Field(None, description="건폐율 (%)")
    floor_area_ratio: Optional[float] = Field(None, description="용적률 (%)")
    road_frontage: Optional[str] = Field(None, description="접도 상태")
    topography: Optional[str] = Field(None, description="지형")
    is_active: Optional[int] = Field(None, description="활성 여부")
    created_at: Optional[datetime] = Field(None, description="등록일시")
