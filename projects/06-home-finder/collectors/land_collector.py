"""
국토교통부 토지 매매 실거래가 수집기
API: https://apis.data.go.kr/1613000/RTMSDataSvcLandTrade

목적: 서울 · 경기 · 송도(인천 연수구)에서 '내가 직접 집을 지을 수 있는 땅'만
      골라 실거래 데이터를 수집한다.

주의:
  - 공공데이터 API는 '실거래가(완료된 거래)'만 제공한다. '현재 호가/매물'은 없다.
    따라서 여기서 수집하는 데이터는 "어디에 어떤 성격의 땅이 얼마에 거래되는가"를
    보여주는 시장 지도이며, 지번(jibun)은 마스킹(예: 1**)되어 있다.
  - API 응답 필드는 영문 키(dealAmount, jimok, landUse, umdNm ...)이다.
    (구버전은 한글 키였으나 현재는 영문. 과거 코드가 한글 키로 파싱해 0건만 저장되던 버그를 수정.)
"""
import logging
import requests
import xmltodict
from datetime import datetime, date

from collectors.base_collector import BaseCollector
from database import SessionLocal
from models.transaction import TransactionHistory
from models.property import Property

logger = logging.getLogger("homefinder.collector.land")

API_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade"
KAKAO_GEOCODE_URL = "https://dapi.kakao.com/v2/local/search/address.json"

# ──────────── 대상 지역 (2026-07 API로 코드 실검증 완료) ────────────
# 서울 25개구 + 서울 근교 경기 + 송도(인천 연수구)
DISTRICT_CODES = {
    # ── 서울특별시 ──
    "종로구": "11110", "중구": "11140", "용산구": "11170",
    "성동구": "11200", "광진구": "11215", "동대문구": "11230",
    "중랑구": "11260", "성북구": "11290", "강북구": "11305",
    "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구": "11410", "마포구": "11440", "양천구": "11470",
    "강서구": "11500", "구로구": "11530", "금천구": "11545",
    "영등포구": "11560", "동작구": "11590", "관악구": "11620",
    "서초구": "11650", "강남구": "11680", "송파구": "11710",
    "강동구": "11740",
    # ── 경기도 (서울 근교 + 단독주택지 수요지) ──
    "하남시": "41450", "과천시": "41290", "광명시": "41210",
    "구리시": "41310", "남양주시": "41360", "의정부시": "41150",
    "성남시 분당구": "41135", "성남시 수정구": "41131", "성남시 중원구": "41133",
    "고양시 덕양구": "41281", "고양시 일산동구": "41285", "고양시 일산서구": "41287",
    "김포시": "41570", "파주시": "41480", "시흥시": "41390",
    "용인시 수지구": "41465", "용인시 기흥구": "41463", "용인시 처인구": "41461",
    "광주시": "41610", "양평군": "41830", "화성시": "41590",
    # ── 인천광역시 (송도) ──
    "인천 연수구": "28185",
}

# ──────────── 건축 가능성 판별 기준 ────────────
# 지목(jimok): 즉시 건축 가능한 지목
BUILDABLE_NOW_JIMOK = {"대", "대지", "잡종지", "공장용지", "학교용지", "창고용지", "주차장"}
# 지목: 전용/개발행위허가를 거치면 건축 가능 (농지·산지)
CONVERT_JIMOK = {"전", "답", "과수원", "목장용지", "임야", "염전"}
# 지목: 건축 불가 (필터에서 제외)
NON_BUILDABLE_JIMOK = {"도로", "구거", "하천", "제방", "묘지", "유지", "수도용지",
                       "철도용지", "공원", "체육용지", "종교용지", "사적지"}

# 용도지역(landUse): 부분 문자열이 포함되면 건축이 크게 제약됨 → 제외
RESTRICTED_LANDUSE = ("개발제한", "보전", "농림", "자연환경보전", "생산관리", "생산녹지")

# 용도지역 → (건폐율%, 용적률%) 표준값 (서울/수도권 기준, 부분 문자열 매칭)
ZONING_BCR_FAR = {
    "제1종전용주거": (50, 100), "제2종전용주거": (50, 120),
    "제1종일반주거": (60, 150), "제2종일반주거": (60, 200),
    "제3종일반주거": (50, 250),
    "준주거": (60, 400),
    "중심상업": (60, 1000), "일반상업": (60, 800),
    "근린상업": (60, 600), "유통상업": (60, 600),
    "준공업": (60, 400), "일반공업": (60, 350), "전용공업": (60, 300),
    "계획관리": (40, 100), "보전관리": (20, 80),
    "자연녹지": (20, 80), "보전녹지": (20, 80),
}


def _calc_year_months(months_back: int) -> list:
    now = datetime.now()
    result = []
    for m in range(months_back):
        y, mo = now.year, now.month - m
        while mo <= 0:
            mo += 12
            y -= 1
        result.append(f"{y}{mo:02d}")
    return result


def _city_from_sgg_code(sgg_code: str) -> str:
    prefix = str(sgg_code)[:2]
    return {"11": "서울특별시", "28": "인천광역시", "41": "경기도"}.get(prefix, "기타")


def _bcr_far_for(land_use: str):
    """용도지역 문자열에서 (건폐율, 용적률) 추정. 못 찾으면 (None, None)."""
    for key, (bcr, far) in ZONING_BCR_FAR.items():
        if key in land_use:
            return bcr, far
    return None, None


def classify_buildability(jimok: str, land_use: str, share_type: str) -> dict:
    """
    한 필지가 '내가 집을 지을 수 있는 땅'인지 분류한다.

    반환: {
      "buildable": bool,     # 수집 대상 여부 (False면 저장 안 함)
      "tier": str,           # "즉시가능" | "전용필요"
      "reason": str,         # 제외/등급 사유 (한 줄)
    }

    핵심 판단:
      1. 지분거래("지분")는 필지 일부만 취득 → 단독 건축 불가 → 제외
      2. 도로/하천/묘지 등 건축 불가 지목 → 제외
      3. 개발제한구역(그린벨트)·보전·농림 용도지역 → 제외
      4. 대/잡종지 = 즉시가능, 전/답/임야 = 전용필요
    """
    jimok = (jimok or "").strip()
    land_use = (land_use or "").strip()
    share_type = (share_type or "").strip()

    if share_type == "지분":
        return {"buildable": False, "tier": None, "reason": "지분거래(단독 건축 불가)"}
    if jimok in NON_BUILDABLE_JIMOK:
        return {"buildable": False, "tier": None, "reason": f"건축 불가 지목({jimok})"}
    if any(k in land_use for k in RESTRICTED_LANDUSE):
        return {"buildable": False, "tier": None, "reason": f"건축 제약 용도지역({land_use})"}

    if jimok in BUILDABLE_NOW_JIMOK:
        return {"buildable": True, "tier": "즉시가능", "reason": f"{jimok}/{land_use}"}
    if jimok in CONVERT_JIMOK:
        return {"buildable": True, "tier": "전용필요", "reason": f"{jimok} 전용허가 필요/{land_use}"}
    # 알 수 없는 지목: 보수적으로 전용필요로 분류하되 포함
    return {"buildable": True, "tier": "전용필요", "reason": f"{jimok or '지목미상'}/{land_use}"}


class LandCollector(BaseCollector):
    name = "land"
    rate_limit_seconds = 1.2

    def __init__(self, api_key: str, target_districts: list = None, kakao_key: str = ""):
        super().__init__()
        self.api_key = api_key
        self.target_districts = target_districts or []
        self.kakao_key = kakao_key
        self._geo_cache = {}  # (city, district, dong) -> (lat, lng)

    def collect(self, months_back: int = 6, **kwargs) -> dict:
        if not self.api_key:
            raise ValueError("PUBLIC_DATA_API_KEY not set")

        total_fetched = 0   # API에서 받은 원본 건수
        total_new = 0       # 신규 저장된 건축가능 매물(Property)
        total_skipped = 0   # 건축 불가로 제외
        failures = 0
        # 마스킹된 지번 탓에 배치 내 source_id가 겹칠 수 있어 메모리에서도 중복 제거
        self._seen_ids = set()

        # 대상 구 결정: 지정이 있으면 교집합, 없으면 전체
        if self.target_districts:
            district_codes = [(d, DISTRICT_CODES[d]) for d in self.target_districts
                              if d in DISTRICT_CODES]
            if not district_codes:
                district_codes = list(DISTRICT_CODES.items())
        else:
            district_codes = list(DISTRICT_CODES.items())

        year_months = _calc_year_months(months_back)
        total_attempts = len(district_codes) * len(year_months)

        for district_name, code in district_codes:
            for ym in year_months:
                try:
                    self._rate_limit()
                    items = self._fetch_api(code, ym)
                    if not items:
                        continue
                    fetched, new, skipped = self._save(items)
                    total_fetched += fetched
                    total_new += new
                    total_skipped += skipped
                    logger.info(f"  {district_name}/{ym}: fetched={fetched}, "
                                f"buildable_new={new}, skipped={skipped}")
                except Exception as e:
                    failures += 1
                    logger.warning(f"  {district_name}/{ym} failed: {e}")
                    continue

        if failures == total_attempts and total_attempts > 0:
            raise RuntimeError(
                f"All {total_attempts} land API calls failed. Check API key activation.")

        logger.info(f"[land] 완료: 원본 {total_fetched}건 중 건축가능 신규 {total_new}건 저장, "
                    f"{total_skipped}건 제외(지분/불가지목/제약용도)")
        return {"fetched": total_fetched, "new": total_new,
                "updated": 0, "skipped": total_skipped, "failures": failures}

    def _fetch_api(self, lawd_cd: str, deal_ymd: str) -> list:
        params = {
            "serviceKey": self.api_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "numOfRows": "1000",
            "pageNo": "1",
        }
        resp = self._retry(requests.get, API_URL, params=params, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"API {resp.status_code}")

        data = xmltodict.parse(resp.text)
        response = data.get("response")
        if not response:
            raise RuntimeError("Unexpected XML: missing <response>")

        header = response.get("header", {})
        result_code = header.get("resultCode", "")
        # 정상 코드: "00"(구버전) 또는 "000"(신버전)
        if result_code not in ("00", "000"):
            raise RuntimeError(f"API error code={result_code}, "
                               f"msg={header.get('resultMsg', 'unknown')}")

        items = (response.get("body", {}) or {}).get("items")
        if not items:
            return []
        item_list = items.get("item", [])
        if isinstance(item_list, dict):
            item_list = [item_list]
        return item_list or []

    def _geocode(self, city: str, district: str, dong: str):
        """동(洞) 단위 근사 좌표. 지번이 마스킹되어 정확 지오코딩 불가 → 동 중심 좌표."""
        key = (city, district, dong)
        if key in self._geo_cache:
            return self._geo_cache[key]
        lat = lng = None
        if self.kakao_key and dong:
            try:
                # "인천 연수구 옥련동" / "서울 강남구 개포동" 형태로 질의
                query = f"{district} {dong}".strip()
                r = requests.get(
                    KAKAO_GEOCODE_URL,
                    headers={"Authorization": f"KakaoAK {self.kakao_key}"},
                    params={"query": query, "size": 1},
                    timeout=8,
                )
                if r.status_code == 200:
                    docs = r.json().get("documents", [])
                    if docs:
                        lng = float(docs[0]["x"])
                        lat = float(docs[0]["y"])
            except Exception as e:
                logger.debug(f"geocode fail {district} {dong}: {e}")
        self._geo_cache[key] = (lat, lng)
        return lat, lng

    def _save(self, items: list) -> tuple:
        """건축 가능 필지만 Property(토지 매물) + TransactionHistory(실거래)에 저장."""
        db = SessionLocal()
        fetched = len(items)
        new = 0
        skipped = 0
        try:
            for row in items:
                try:
                    year = int(row.get("dealYear", 0) or 0)
                    month = int(row.get("dealMonth", 0) or 0)
                    day = int(row.get("dealDay", 0) or 0)
                    if not all([year, month, day]):
                        continue
                    tx_date = date(year, month, day)

                    price_str = str(row.get("dealAmount", "0")).replace(",", "").strip()
                    price_man = int(price_str) if price_str.isdigit() else 0
                    if price_man == 0:
                        continue
                    price_krw = price_man * 10000

                    area = float(row.get("dealArea", 0) or 0)
                    dong = str(row.get("umdNm", "")).strip()
                    jibun = str(row.get("jibun", "")).strip()
                    jimok = str(row.get("jimok", "")).strip()
                    land_use = str(row.get("landUse", "")).strip()  # 용도지역
                    share_type = str(row.get("shareDealingType", "")).strip()
                    deal_gbn = str(row.get("dealingGbn", "")).strip()  # 중개거래/직거래
                    sgg_cd = str(row.get("sggCd", "")).strip()
                    sgg_nm = str(row.get("sggNm", "")).strip()  # 예: "연수구", "용인시 수지구"

                    # ── 건축 가능성 판별 ──
                    verdict = classify_buildability(jimok, land_use, share_type)
                    if not verdict["buildable"]:
                        skipped += 1
                        continue

                    city = _city_from_sgg_code(sgg_cd)
                    district = sgg_nm or "미상"
                    price_per_m2 = int(price_krw / area) if area > 0 else 0
                    bcr, far = _bcr_far_for(land_use)
                    tier = verdict["tier"]

                    # 중복 방지용 안정적 source_id (마스킹 지번 + 거래일 + 면적 + 가격)
                    source_id = (f"molitland_{sgg_cd}_{dong}_{jibun}_"
                                 f"{year}{month:02d}{day:02d}_{area}_{price_man}")

                    # 배치 내 중복(같은 source_id) 제거 — 커밋 전이라 DB 조회로는 못 잡음
                    if source_id in self._seen_ids:
                        continue
                    self._seen_ids.add(source_id)

                    # ── 1) 실거래 이력 (TransactionHistory) ──
                    exists_tx = db.query(TransactionHistory).filter(
                        TransactionHistory.district == district,
                        TransactionHistory.dong == dong,
                        TransactionHistory.transaction_date == tx_date,
                        TransactionHistory.area_exclusive == area,
                        TransactionHistory.price_krw == price_krw,
                        TransactionHistory.property_type == "토지",
                    ).first()
                    if not exists_tx:
                        db.add(TransactionHistory(
                            city=city, district=district, dong=dong,
                            name=f"{dong} {jibun} ({jimok})",
                            address=f"{district} {dong} {jibun}",
                            transaction_date=tx_date,
                            price_krw=price_krw, area_exclusive=area,
                            property_type="토지", price_per_m2=price_per_m2,
                            source="molit_land",
                        ))

                    # ── 2) 토지 매물 카드 (Property) ──
                    exists_prop = db.query(Property).filter(
                        Property.source == "molit_land",
                        Property.source_id == source_id,
                    ).first()
                    if exists_prop:
                        continue

                    lat, lng = self._geocode(city, district, dong)
                    desc = (f"실거래 {year}.{month} · {jimok}/{land_use} · "
                            f"{deal_gbn or '거래'} · 건축:{tier} · {area:.0f}㎡")

                    db.add(Property(
                        source="molit_land",
                        source_id=source_id,
                        property_type="토지",
                        acquisition_type="매매",
                        transaction_type="매매",
                        city=city, district=district, dong=dong,
                        address=f"{district} {dong} {jibun}",
                        lat=lat, lng=lng,
                        price_krw=price_krw, price_per_m2=price_per_m2,
                        area_m2=round(area, 2),
                        land_use=jimok,           # 지목
                        zoning_type=land_use,     # 용도지역
                        building_coverage_ratio=bcr,
                        floor_area_ratio=far,
                        road_frontage=None,       # API 미제공
                        topography=None,          # API 미제공
                        source_url="https://rt.molit.go.kr/",
                        description=desc,
                        is_active=1,
                    ))
                    new += 1

                    if new % 200 == 0:
                        db.commit()

                except Exception as e:
                    logger.warning(f"Row parse error: {e}")
                    continue

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"DB commit failed for land: {e}")
            raise
        finally:
            db.close()

        return fetched, new, skipped
