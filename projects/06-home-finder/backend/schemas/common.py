"""공통 Enum 정의"""
from enum import Enum


class PropertyType(str, Enum):
    """매물 유형"""
    아파트 = "아파트"
    빌라 = "빌라"
    단독 = "단독"
    전원주택 = "전원주택"
    타운하우스 = "타운하우스"
    오피스텔 = "오피스텔"
    토지 = "토지"


class AcquisitionType(str, Enum):
    """취득 방법"""
    매매 = "매매"
    경매 = "경매"
    청약 = "청약"


class CandidateStatus(str, Enum):
    """후보 매물 파이프라인 상태"""
    발견 = "발견"
    조사 = "조사"
    관심 = "관심"
    방문예정 = "방문예정"
    방문완료 = "방문완료"
    결정 = "결정"


class DataSource(str, Enum):
    """데이터 소스"""
    naver = "naver"
    molit = "molit"
    kb = "kb"
    auction = "auction"
    subscription = "subscription"
    manual = "manual"


class SortOrder(str, Enum):
    """정렬 순서"""
    price_asc = "price_asc"
    price_desc = "price_desc"
    score_desc = "score_desc"
    newest = "newest"
    area_desc = "area_desc"
