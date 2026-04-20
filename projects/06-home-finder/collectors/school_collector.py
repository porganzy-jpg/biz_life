"""
학교 데이터 수집기 (NEIS 학교정보 API + 시드 데이터)

NEIS Open API: https://open.neis.go.kr/hub/schoolInfo
10개 대상 구의 초등/중학/고등학교 정보를 수집하고,
특정 좌표 주변 학교 검색 기능을 제공한다.
"""
import logging
import math
import os
from typing import List, Optional

import requests

from collectors.base_collector import BaseCollector

logger = logging.getLogger("homefinder.collector.school")

# ---------------------------------------------------------------------------
# NEIS API config
# ---------------------------------------------------------------------------
NEIS_BASE_URL = "https://open.neis.go.kr/hub/schoolInfo"
ATPT_OE_CD_SEOUL = "B10"  # 서울특별시교육청 시도교육청코드

# 학교종류 코드 매핑
SCHOOL_TYPE_MAP = {
    "초등학교": "초등",
    "중학교": "중학",
    "고등학교": "고등",
    "특수학교": "특수",
    "방송통신중학교": "중학",
    "방송통신고등학교": "고등",
}

# 대상 10개 구
TARGET_DISTRICTS = [
    "마포구", "용산구", "성동구", "광진구", "영등포구",
    "동작구", "강동구", "은평구", "강서구", "노원구",
]


def _api_key() -> str:
    """NEIS_API_KEY 우선, 없으면 PUBLIC_DATA_API_KEY 사용"""
    return os.getenv("NEIS_API_KEY", "") or os.getenv("PUBLIC_DATA_API_KEY", "")


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 간 거리(m)를 Haversine 공식으로 계산"""
    R = 6_371_000  # 지구 반경(m)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# In-memory school storage  (list[dict])
# ---------------------------------------------------------------------------
_schools: List[dict] = []


def _get_schools() -> List[dict]:
    """현재 메모리에 있는 학교 목록 반환 (비어있으면 시드 로딩)"""
    if not _schools:
        _schools.extend(_SEED_SCHOOLS)
    return _schools


# ---------------------------------------------------------------------------
# SchoolCollector
# ---------------------------------------------------------------------------
class SchoolCollector(BaseCollector):
    """NEIS 학교정보 API를 이용한 학교 데이터 수집기"""

    name = "school"
    rate_limit_seconds = 0.5  # NEIS API는 초당 5회까지 허용

    def __init__(self, api_key: Optional[str] = None, target_districts: Optional[list] = None):
        super().__init__()
        self.api_key = api_key or _api_key()
        self.target_districts = target_districts or TARGET_DISTRICTS

    # ------------------------------------------------------------------
    # collect: BaseCollector 인터페이스 구현
    # ------------------------------------------------------------------
    def collect(self, **kwargs) -> dict:
        """
        대상 구의 학교 정보를 NEIS API에서 수집하여 메모리에 저장한다.

        API 키가 없으면 시드 데이터로 대체.

        Returns:
            {"fetched": int, "new": int, "updated": int}
        """
        if not self.api_key:
            logger.warning(
                "NEIS_API_KEY / PUBLIC_DATA_API_KEY not set — loading seed data only"
            )
            return self._load_seed()

        total_fetched = 0
        total_new = 0

        for district in self.target_districts:
            try:
                schools = self._fetch_district(district)
                total_fetched += len(schools)

                for s in schools:
                    if not self._already_exists(s):
                        _schools.append(s)
                        total_new += 1

            except Exception as e:
                logger.warning(f"Failed to fetch schools for {district}: {e}")
                continue

        # 시드 데이터 중 API에서 빠진 것 보충
        self._backfill_seed()

        logger.info(
            f"School collect complete: fetched={total_fetched}, "
            f"new={total_new}, total_in_memory={len(_schools)}"
        )
        return {"fetched": total_fetched, "new": total_new, "updated": 0}

    # ------------------------------------------------------------------
    # NEIS API 호출
    # ------------------------------------------------------------------
    def _fetch_district(self, district: str) -> List[dict]:
        """특정 구의 학교 목록을 NEIS API에서 가져온다."""
        results: List[dict] = []
        page = 1
        page_size = 100

        while True:
            params = {
                "KEY": self.api_key,
                "Type": "json",
                "pIndex": page,
                "pSize": page_size,
                "ATPT_OFCDC_SC_CODE": ATPT_OE_CD_SEOUL,
                "LCTN_SC_NM": "서울특별시",
                "ORG_RDNMA": district,  # 도로명주소에 구 이름 포함
            }

            resp = self._retry(self._do_request, params)
            if resp is None:
                break

            rows = self._parse_response(resp)
            if not rows:
                break

            for row in rows:
                school = self._row_to_dict(row, district)
                if school:
                    results.append(school)

            # 페이지 끝 판단
            if len(rows) < page_size:
                break
            page += 1

        return results

    def _do_request(self, params: dict) -> Optional[dict]:
        """단일 HTTP 요청"""
        resp = requests.get(NEIS_BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _parse_response(data: dict) -> List[dict]:
        """NEIS JSON 응답에서 row 리스트 추출"""
        if not data:
            return []

        # NEIS 에러 응답 처리
        if "RESULT" in data:
            code = data["RESULT"].get("CODE", "")
            if code == "INFO-200":
                # 데이터 없음 (해당 조건)
                return []
            if code != "INFO-000":
                logger.debug(f"NEIS API: {data['RESULT']}")
                return []

        try:
            return data["schoolInfo"][1]["row"]
        except (KeyError, IndexError, TypeError):
            return []

    @staticmethod
    def _row_to_dict(row: dict, fallback_district: str = "") -> Optional[dict]:
        """NEIS API row를 내부 학교 dict로 변환"""
        name = row.get("SCHUL_NM", "").strip()
        if not name:
            return None

        kind_raw = row.get("SCHUL_KND_SC_NM", "")
        school_type = SCHOOL_TYPE_MAP.get(kind_raw, "")
        if not school_type:
            return None  # 관심 대상이 아닌 학교종류

        address = row.get("ORG_RDNMA", "") or row.get("ORG_FAXNO", "")
        lat = _safe_float(row.get("LCTN_SC_LA"))  # 위도 (일부 응답에 포함)
        lng = _safe_float(row.get("LCTN_SC_LO"))  # 경도

        # 구 이름 추출 (주소에서)
        district = fallback_district
        for d in TARGET_DISTRICTS:
            if d in address:
                district = d
                break

        return {
            "name": name,
            "type": school_type,           # 초등 / 중학 / 고등
            "address": address,
            "lat": lat,
            "lng": lng,
            "district": district,
            "source": "neis_api",
        }

    # ------------------------------------------------------------------
    # 시드 데이터 관련
    # ------------------------------------------------------------------
    def _load_seed(self) -> dict:
        """시드 데이터를 메모리에 로딩"""
        new = 0
        for s in _SEED_SCHOOLS:
            if not self._already_exists(s):
                _schools.append(s)
                new += 1
        return {"fetched": len(_SEED_SCHOOLS), "new": new, "updated": 0}

    def _backfill_seed(self):
        """API 결과에 누락된 시드 학교를 보충"""
        for s in _SEED_SCHOOLS:
            if not self._already_exists(s):
                _schools.append(s)

    @staticmethod
    def _already_exists(school: dict) -> bool:
        """이름 + 구로 중복 확인"""
        for existing in _schools:
            if (
                existing["name"] == school["name"]
                and existing["district"] == school["district"]
            ):
                return True
        return False

    # ------------------------------------------------------------------
    # 주변 학교 검색 (클래스 메서드)
    # ------------------------------------------------------------------
    @classmethod
    def get_nearby_schools(
        cls,
        lat: float,
        lng: float,
        radius_m: float = 1000,
        school_type: Optional[str] = None,
    ) -> List[dict]:
        """
        특정 좌표 주변 학교 목록을 반환한다.

        Args:
            lat: 위도
            lng: 경도
            radius_m: 검색 반경 (미터, 기본 1000m)
            school_type: 필터 — "초등", "중학", "고등" (None이면 전체)

        Returns:
            거리순 정렬된 학교 dict 리스트.
            각 dict에 "distance_m" 필드가 추가된다.
        """
        schools = _get_schools()
        nearby: List[dict] = []

        for s in schools:
            s_lat = s.get("lat", 0)
            s_lng = s.get("lng", 0)
            if not s_lat or not s_lng:
                continue

            if school_type and s.get("type") != school_type:
                continue

            dist = _haversine(lat, lng, s_lat, s_lng)
            if dist <= radius_m:
                entry = {**s, "distance_m": round(dist)}
                nearby.append(entry)

        nearby.sort(key=lambda x: x["distance_m"])
        return nearby

    @classmethod
    def get_school_summary(cls, lat: float, lng: float, radius_m: float = 1000) -> dict:
        """
        좌표 주변 학교 요약 정보를 반환한다.

        Returns:
            {
                "total": int,
                "elementary": int,   # 초등
                "middle": int,       # 중학
                "high": int,         # 고등
                "nearest": {...} or None,
                "schools": [...]
            }
        """
        nearby = cls.get_nearby_schools(lat, lng, radius_m)
        return {
            "total": len(nearby),
            "elementary": sum(1 for s in nearby if s["type"] == "초등"),
            "middle": sum(1 for s in nearby if s["type"] == "중학"),
            "high": sum(1 for s in nearby if s["type"] == "고등"),
            "nearest": nearby[0] if nearby else None,
            "schools": nearby,
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _safe_float(val) -> float:
    """안전한 float 변환, 실패 시 0.0"""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Seed data: 10개 대상 구의 대표 학교들
# ---------------------------------------------------------------------------
_SEED_SCHOOLS: List[dict] = [
    # ===== 마포구 =====
    {"name": "서울마포초등학교", "type": "초등", "address": "서울특별시 마포구 백범로 23", "lat": 37.5413, "lng": 126.9465, "district": "마포구", "source": "seed"},
    {"name": "서울염리초등학교", "type": "초등", "address": "서울특별시 마포구 만리재로 14길 16", "lat": 37.5445, "lng": 126.9510, "district": "마포구", "source": "seed"},
    {"name": "서울용강초등학교", "type": "초등", "address": "서울특별시 마포구 토정로 32길 20", "lat": 37.5390, "lng": 126.9418, "district": "마포구", "source": "seed"},
    {"name": "서강중학교", "type": "중학", "address": "서울특별시 마포구 신촌로 176", "lat": 37.5559, "lng": 126.9368, "district": "마포구", "source": "seed"},
    {"name": "마포중학교", "type": "중학", "address": "서울특별시 마포구 월드컵북로 396", "lat": 37.5678, "lng": 126.9087, "district": "마포구", "source": "seed"},
    {"name": "서울여자고등학교", "type": "고등", "address": "서울특별시 마포구 만리재로 68", "lat": 37.5437, "lng": 126.9541, "district": "마포구", "source": "seed"},
    {"name": "숭문고등학교", "type": "고등", "address": "서울특별시 마포구 백범로 71", "lat": 37.5460, "lng": 126.9488, "district": "마포구", "source": "seed"},

    # ===== 용산구 =====
    {"name": "서울원효초등학교", "type": "초등", "address": "서울특별시 용산구 원효로97길 15", "lat": 37.5349, "lng": 126.9640, "district": "용산구", "source": "seed"},
    {"name": "서울이촌초등학교", "type": "초등", "address": "서울특별시 용산구 이촌로 72길 16", "lat": 37.5218, "lng": 126.9710, "district": "용산구", "source": "seed"},
    {"name": "서울보광초등학교", "type": "초등", "address": "서울특별시 용산구 보광로 117", "lat": 37.5285, "lng": 126.9940, "district": "용산구", "source": "seed"},
    {"name": "용산중학교", "type": "중학", "address": "서울특별시 용산구 녹사평대로 66", "lat": 37.5348, "lng": 126.9870, "district": "용산구", "source": "seed"},
    {"name": "한강중학교", "type": "중학", "address": "서울특별시 용산구 이촌로 64길 43", "lat": 37.5200, "lng": 126.9688, "district": "용산구", "source": "seed"},
    {"name": "용산고등학교", "type": "고등", "address": "서울특별시 용산구 한남대로 22", "lat": 37.5288, "lng": 126.9912, "district": "용산구", "source": "seed"},
    {"name": "중경고등학교", "type": "고등", "address": "서울특별시 용산구 이태원로 183", "lat": 37.5340, "lng": 126.9920, "district": "용산구", "source": "seed"},

    # ===== 성동구 =====
    {"name": "서울행당초등학교", "type": "초등", "address": "서울특별시 성동구 행당로 105", "lat": 37.5575, "lng": 127.0370, "district": "성동구", "source": "seed"},
    {"name": "서울옥수초등학교", "type": "초등", "address": "서울특별시 성동구 옥수동 228", "lat": 37.5410, "lng": 127.0150, "district": "성동구", "source": "seed"},
    {"name": "서울성수초등학교", "type": "초등", "address": "서울특별시 성동구 성수이로 10길 23", "lat": 37.5442, "lng": 127.0560, "district": "성동구", "source": "seed"},
    {"name": "성동중학교", "type": "중학", "address": "서울특별시 성동구 왕십리로 130", "lat": 37.5565, "lng": 127.0410, "district": "성동구", "source": "seed"},
    {"name": "무학중학교", "type": "중학", "address": "서울특별시 성동구 마조로 42", "lat": 37.5616, "lng": 127.0210, "district": "성동구", "source": "seed"},
    {"name": "한양대학교사범대학부속고등학교", "type": "고등", "address": "서울특별시 성동구 행당로 107", "lat": 37.5578, "lng": 127.0375, "district": "성동구", "source": "seed"},
    {"name": "성수고등학교", "type": "고등", "address": "서울특별시 성동구 성수이로7길 22", "lat": 37.5435, "lng": 127.0545, "district": "성동구", "source": "seed"},

    # ===== 광진구 =====
    {"name": "서울광장초등학교", "type": "초등", "address": "서울특별시 광진구 광나루로 410", "lat": 37.5482, "lng": 127.0940, "district": "광진구", "source": "seed"},
    {"name": "서울구의초등학교", "type": "초등", "address": "서울특별시 광진구 아차산로 410", "lat": 37.5388, "lng": 127.0870, "district": "광진구", "source": "seed"},
    {"name": "광남중학교", "type": "중학", "address": "서울특별시 광진구 능동로 40길 27", "lat": 37.5475, "lng": 127.0790, "district": "광진구", "source": "seed"},
    {"name": "대원중학교", "type": "중학", "address": "서울특별시 광진구 용마산로 23길 16", "lat": 37.5530, "lng": 127.0860, "district": "광진구", "source": "seed"},
    {"name": "대원외국어고등학교", "type": "고등", "address": "서울특별시 광진구 용마산로 22", "lat": 37.5535, "lng": 127.0855, "district": "광진구", "source": "seed"},
    {"name": "광양고등학교", "type": "고등", "address": "서울특별시 광진구 광나루로 26길 20", "lat": 37.5460, "lng": 127.0935, "district": "광진구", "source": "seed"},

    # ===== 영등포구 =====
    {"name": "서울영등포초등학교", "type": "초등", "address": "서울특별시 영등포구 영등포로 32길 18", "lat": 37.5165, "lng": 126.9060, "district": "영등포구", "source": "seed"},
    {"name": "서울여의도초등학교", "type": "초등", "address": "서울특별시 영등포구 여의도동 43", "lat": 37.5265, "lng": 126.9250, "district": "영등포구", "source": "seed"},
    {"name": "서울당산초등학교", "type": "초등", "address": "서울특별시 영등포구 당산로 41길 11", "lat": 37.5340, "lng": 126.9020, "district": "영등포구", "source": "seed"},
    {"name": "영등포중학교", "type": "중학", "address": "서울특별시 영등포구 도림로 109", "lat": 37.5100, "lng": 126.8975, "district": "영등포구", "source": "seed"},
    {"name": "여의도중학교", "type": "중학", "address": "서울특별시 영등포구 여의도동 43-1", "lat": 37.5270, "lng": 126.9260, "district": "영등포구", "source": "seed"},
    {"name": "여의도고등학교", "type": "고등", "address": "서울특별시 영등포구 여의공원로 101", "lat": 37.5275, "lng": 126.9240, "district": "영등포구", "source": "seed"},
    {"name": "영등포고등학교", "type": "고등", "address": "서울특별시 영등포구 도림로 105", "lat": 37.5095, "lng": 126.8970, "district": "영등포구", "source": "seed"},

    # ===== 동작구 =====
    {"name": "서울상도초등학교", "type": "초등", "address": "서울특별시 동작구 상도로 61길 80", "lat": 37.5018, "lng": 126.9430, "district": "동작구", "source": "seed"},
    {"name": "서울노량진초등학교", "type": "초등", "address": "서울특별시 동작구 노량진로 10길 36", "lat": 37.5120, "lng": 126.9412, "district": "동작구", "source": "seed"},
    {"name": "서울흑석초등학교", "type": "초등", "address": "서울특별시 동작구 흑석로 84", "lat": 37.5085, "lng": 126.9610, "district": "동작구", "source": "seed"},
    {"name": "상도중학교", "type": "중학", "address": "서울특별시 동작구 상도로 37길 44", "lat": 37.5010, "lng": 126.9410, "district": "동작구", "source": "seed"},
    {"name": "동작중학교", "type": "중학", "address": "서울특별시 동작구 사당로 16길 27", "lat": 37.4928, "lng": 126.9550, "district": "동작구", "source": "seed"},
    {"name": "중앙대학교사범대학부속고등학교", "type": "고등", "address": "서울특별시 동작구 흑석로 84", "lat": 37.5080, "lng": 126.9605, "district": "동작구", "source": "seed"},
    {"name": "보성고등학교", "type": "고등", "address": "서울특별시 동작구 상도로 61길 5", "lat": 37.5005, "lng": 126.9420, "district": "동작구", "source": "seed"},

    # ===== 강동구 =====
    {"name": "서울강동초등학교", "type": "초등", "address": "서울특별시 강동구 천호대로 168길 35", "lat": 37.5460, "lng": 127.1270, "district": "강동구", "source": "seed"},
    {"name": "서울명일초등학교", "type": "초등", "address": "서울특별시 강동구 명일로 55", "lat": 37.5525, "lng": 127.1440, "district": "강동구", "source": "seed"},
    {"name": "서울한산초등학교", "type": "초등", "address": "서울특별시 강동구 고덕로 39길 36", "lat": 37.5570, "lng": 127.1530, "district": "강동구", "source": "seed"},
    {"name": "강동중학교", "type": "중학", "address": "서울특별시 강동구 양재대로 1579", "lat": 37.5465, "lng": 127.1275, "district": "강동구", "source": "seed"},
    {"name": "명일중학교", "type": "중학", "address": "서울특별시 강동구 명일로 47", "lat": 37.5520, "lng": 127.1435, "district": "강동구", "source": "seed"},
    {"name": "배재고등학교", "type": "고등", "address": "서울특별시 강동구 고덕로 22길 43", "lat": 37.5560, "lng": 127.1520, "district": "강동구", "source": "seed"},
    {"name": "한영고등학교", "type": "고등", "address": "서울특별시 강동구 동남로 73길 29", "lat": 37.5300, "lng": 127.1280, "district": "강동구", "source": "seed"},

    # ===== 은평구 =====
    {"name": "서울녹번초등학교", "type": "초등", "address": "서울특별시 은평구 통일로 684", "lat": 37.6035, "lng": 126.9300, "district": "은평구", "source": "seed"},
    {"name": "서울응암초등학교", "type": "초등", "address": "서울특별시 은평구 은평로 25", "lat": 37.5990, "lng": 126.9218, "district": "은평구", "source": "seed"},
    {"name": "서울구산초등학교", "type": "초등", "address": "서울특별시 은평구 갈현로 11길 40", "lat": 37.6120, "lng": 126.9140, "district": "은평구", "source": "seed"},
    {"name": "은평중학교", "type": "중학", "address": "서울특별시 은평구 불광로 68", "lat": 37.6120, "lng": 126.9270, "district": "은평구", "source": "seed"},
    {"name": "신사중학교", "type": "중학", "address": "서울특별시 은평구 진흥로 73", "lat": 37.6160, "lng": 126.9170, "district": "은평구", "source": "seed"},
    {"name": "은평고등학교", "type": "고등", "address": "서울특별시 은평구 불광로 38", "lat": 37.6108, "lng": 126.9255, "district": "은평구", "source": "seed"},
    {"name": "대성고등학교", "type": "고등", "address": "서울특별시 은평구 녹번동 산24", "lat": 37.6050, "lng": 126.9310, "district": "은평구", "source": "seed"},

    # ===== 강서구 =====
    {"name": "서울가양초등학교", "type": "초등", "address": "서울특별시 강서구 가양대로 8길 76", "lat": 37.5610, "lng": 126.8560, "district": "강서구", "source": "seed"},
    {"name": "서울등촌초등학교", "type": "초등", "address": "서울특별시 강서구 등촌로 13나길 28", "lat": 37.5515, "lng": 126.8648, "district": "강서구", "source": "seed"},
    {"name": "서울화곡초등학교", "type": "초등", "address": "서울특별시 강서구 화곡로 58길 38", "lat": 37.5440, "lng": 126.8395, "district": "강서구", "source": "seed"},
    {"name": "가양중학교", "type": "중학", "address": "서울특별시 강서구 양천로 47길 62", "lat": 37.5605, "lng": 126.8570, "district": "강서구", "source": "seed"},
    {"name": "등촌중학교", "type": "중학", "address": "서울특별시 강서구 등촌로 19길 26", "lat": 37.5510, "lng": 126.8655, "district": "강서구", "source": "seed"},
    {"name": "명덕고등학교", "type": "고등", "address": "서울특별시 강서구 화곡로 64길 41", "lat": 37.5445, "lng": 126.8410, "district": "강서구", "source": "seed"},
    {"name": "강서고등학교", "type": "고등", "address": "서울특별시 강서구 가로공원로 78길 68", "lat": 37.5580, "lng": 126.8480, "district": "강서구", "source": "seed"},

    # ===== 노원구 =====
    {"name": "서울상계초등학교", "type": "초등", "address": "서울특별시 노원구 동일로 204길 27", "lat": 37.6540, "lng": 127.0615, "district": "노원구", "source": "seed"},
    {"name": "서울중계초등학교", "type": "초등", "address": "서울특별시 노원구 한글비석로 200", "lat": 37.6430, "lng": 127.0710, "district": "노원구", "source": "seed"},
    {"name": "서울공릉초등학교", "type": "초등", "address": "서울특별시 노원구 공릉로 43길 25", "lat": 37.6260, "lng": 127.0730, "district": "노원구", "source": "seed"},
    {"name": "상계중학교", "type": "중학", "address": "서울특별시 노원구 상계로 5", "lat": 37.6545, "lng": 127.0620, "district": "노원구", "source": "seed"},
    {"name": "중계중학교", "type": "중학", "address": "서울특별시 노원구 한글비석로 205", "lat": 37.6435, "lng": 127.0705, "district": "노원구", "source": "seed"},
    {"name": "대진고등학교", "type": "고등", "address": "서울특별시 노원구 동일로 214길 32", "lat": 37.6555, "lng": 127.0630, "district": "노원구", "source": "seed"},
    {"name": "서라벌고등학교", "type": "고등", "address": "서울특별시 노원구 노해로 371", "lat": 37.6505, "lng": 127.0605, "district": "노원구", "source": "seed"},
]
