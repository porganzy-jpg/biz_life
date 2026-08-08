"""
투자 심사 엔진 — 입력 스키마

사용자가 아는 만큼만 넣으면 되도록 대부분 Optional로 두고,
빠진 값은 `resolve()` 단계에서 시장 데이터·기준값으로 추정해 채운다.
어떤 값이 실측이고 어떤 값이 추정인지 `assumptions`에 남겨
리포트에서 신뢰도를 표시할 수 있게 한다.
"""
from dataclasses import dataclass, field
from typing import Optional

from appraisal import constants as C


@dataclass
class RentRoll:
    """임차 현황 — 상가 가치의 근원"""
    monthly_rent_krw: int = 0          # 월 임대료 (부가세 별도)
    deposit_krw: int = 0               # 보증금
    monthly_maintenance_krw: int = 0   # 월 관리비 (임차인 부담분은 수입 아님)
    is_vacant: bool = False            # 공실 여부
    lease_end_year: Optional[int] = None  # 계약 만료 (임대차 안정성)
    tenant_business: Optional[str] = None  # 업종 (예: 편의점, 학원)


@dataclass
class PropertyInput:
    """심사 대상 물건"""
    # ── 필수 ──
    address: str
    asking_price_krw: int                      # 희망 매수가 (호가/제시가)
    asset_type: str = C.ASSET_COMMERCIAL_UNIT

    # ── 물건 제원 ──
    area_m2: Optional[float] = None            # 전용면적
    land_area_m2: Optional[float] = None       # 대지지분 (건물 통매입 시 대지면적)
    floor: Optional[int] = None
    built_year: Optional[int] = None
    building_name: Optional[str] = None

    # ── 수익 ──
    rent: RentRoll = field(default_factory=RentRoll)

    # ── 입지/상권 ──
    cap_grade: Optional[str] = None            # A~D. 미입력 시 상권 데이터로 추정
    is_first_floor: Optional[bool] = None      # 1층 여부 (임대료 결정력 큼)
    is_corner: bool = False                    # 코너/양면 노출
    road_width_m: Optional[float] = None       # 접도 폭

    # ── 특이사항 (자유 입력) ──
    notes: str = ""

    # ── 자금 계획 (미입력 시 프로파일 기본값) ──
    ltv: Optional[float] = None
    loan_rate: Optional[float] = None
    holding_years: Optional[int] = None
    required_return: Optional[float] = None

    # ── 추정 근거 기록 ──
    assumptions: dict = field(default_factory=dict)

    def note_assumption(self, key: str, value, source: str):
        """추정으로 채운 값과 그 근거를 기록한다."""
        self.assumptions[key] = {"value": value, "source": source}

    @property
    def price_per_m2(self) -> Optional[int]:
        if self.area_m2 and self.area_m2 > 0:
            return int(self.asking_price_krw / self.area_m2)
        return None

    @property
    def building_age(self) -> Optional[int]:
        from datetime import date
        if self.built_year:
            return date.today().year - self.built_year
        return None

    def is_commercial(self) -> bool:
        return self.asset_type in (C.ASSET_COMMERCIAL_UNIT, C.ASSET_COMMERCIAL_BLDG)
