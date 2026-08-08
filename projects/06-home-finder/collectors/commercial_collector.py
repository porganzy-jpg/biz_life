"""
국토교통부 상업업무용 부동산 매매 실거래가 수집기

상가 밸류에이션의 두 축 중 '거래사례비교법'을 떠받치는 데이터.
(나머지 한 축인 수익환원법은 임대료 데이터가 필요하며, 국토부는 상가 임대차를
공개하지 않으므로 한국부동산원 임대동향조사로 별도 보강한다.)

⚠️ 이 API는 공공데이터포털에서 **별도 활용신청**이 필요하다.
   아파트/토지 신청만으로는 403이 떨어진다.
   신청: https://www.data.go.kr → "국토교통부_상업업무용 부동산 매매 신고 자료"

컬럼명은 PublicDataReader 버전에 따라 한글/영문이 갈릴 수 있어
후보 목록으로 방어적으로 해석한다. (토지 수집기에서 실제로 겪었던 문제)
"""
import logging
from datetime import date, datetime

from collectors.base_collector import BaseCollector
from collectors.molit_collector import DISTRICT_CODES, _calc_year_months
from database import SessionLocal
from models.transaction import TransactionHistory

logger = logging.getLogger("homefinder.commercial")

SOURCE = "molit_commercial"
PROPERTY_TYPE = "상업업무용"

# 컬럼명 후보 — 앞에서부터 먼저 존재하는 것을 쓴다
FIELD_CANDIDATES = {
    "dong":        ["법정동", "umdNm", "법정동명"],
    "district":    ["시군구", "sggNm"],
    "jibun":       ["지번", "jibun"],
    "price":       ["거래금액", "dealAmount"],
    "build_year":  ["건축년도", "buildYear"],
    "year":        ["계약년도", "년", "dealYear"],
    "month":       ["계약월", "월", "dealMonth"],
    "day":         ["계약일", "일", "dealDay"],
    "bldg_area":   ["건물면적", "buildingAr", "건축물면적"],
    "land_area":   ["대지면적", "plottageAr"],
    "floor":       ["층", "floor"],
    "usage":       ["건물주용도", "buildingUse", "주용도"],
    "zoning":      ["용도지역", "landUse"],
    "bldg_type":   ["유형", "buildingType"],   # 집합 / 일반
    "cancel":      ["해제여부", "cdealType"],
}


def _pick(row, keys, default=None):
    """후보 컬럼명 중 실제 존재하는 값을 반환"""
    for k in keys:
        if k in row and row[k] not in (None, "", " "):
            return row[k]
    return default


def _to_int(value, default=0) -> int:
    """'1,250' / ' 1250 ' / 1250.0 → 1250"""
    if value is None:
        return default
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError):
        return default


def _to_float(value, default=None):
    if value is None:
        return default
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return default


class CommercialCollector(BaseCollector):
    name = "commercial"
    rate_limit_seconds = 1.0

    def __init__(self, api_key: str, target_districts: list = None):
        super().__init__()
        self.api_key = api_key
        self.target_districts = target_districts or []

    def collect(self, months_back: int = 6, **kwargs) -> dict:
        """
        상업업무용 부동산 매매 실거래 수집.

        Args:
            months_back: 과거 몇 개월치 (기본 6개월 — 상가는 거래량이 적어
                         아파트보다 긴 기간을 봐야 비교군이 형성된다)
        """
        try:
            import PublicDataReader as pdr
        except ImportError:
            raise RuntimeError("PublicDataReader not installed. pip install PublicDataReader")

        if not self.api_key:
            raise ValueError("PUBLIC_DATA_API_KEY not set. Check .env file.")

        api = pdr.TransactionPrice(self.api_key)

        district_codes = [
            (d, DISTRICT_CODES[d]) for d in self.target_districts if d in DISTRICT_CODES
        ] or list(DISTRICT_CODES.items())

        year_months = _calc_year_months(months_back)
        total_attempts = len(district_codes) * len(year_months)

        total_fetched = total_new = failures = 0
        empty_responses = 0

        for district_name, code in district_codes:
            for ym in year_months:
                try:
                    df = self._retry(
                        api.get_data,
                        property_type=PROPERTY_TYPE,
                        trade_type="매매",
                        sigungu_code=code,
                        year_month=ym,
                    )
                    if df is None or df.empty:
                        empty_responses += 1
                        continue

                    fetched, new = self._save(df, district_name)
                    total_fetched += fetched
                    total_new += new
                    logger.info(f"  {district_name}/{ym}: fetched={fetched}, new={new}")

                except Exception as e:
                    failures += 1
                    logger.warning(f"  {district_name}/{ym} failed: {e}")
                    continue

        # 전건 실패 = 키/권한 문제. 조용히 0건으로 넘기면 안 된다.
        if failures == total_attempts and total_attempts > 0:
            raise RuntimeError(
                f"All {total_attempts} API calls failed. "
                f"상업업무용 API는 별도 활용신청이 필요합니다 (403). "
                f"data.go.kr에서 '국토교통부_상업업무용 부동산 매매 신고 자료' 신청 후 재시도하세요."
            )

        # PublicDataReader는 403을 예외로 던지지 않고 빈 DataFrame을 돌려준다.
        # 그래서 "전건 빈 응답"을 실패로 승격시키지 않으면 권한 문제가
        # '성공 0건'으로 위장된다 — 토지 수집기에서 실제로 당했던 함정이다.
        # 단, 단일 구/단일 월 조회는 거래가 없어 비어 있을 수 있으므로 3건 이상일 때만 승격.
        if total_fetched == 0 and empty_responses == total_attempts and total_attempts >= 3:
            raise RuntimeError(
                f"{total_attempts}건 호출이 모두 빈 응답입니다. "
                f"상업업무용 API 활용신청이 승인되지 않았을 가능성이 큽니다(403은 빈 응답으로 위장됨). "
                f"data.go.kr에서 '국토교통부_상업업무용 부동산 매매 신고 자료' 승인 여부를 확인하세요."
            )
        if total_fetched == 0 and empty_responses == total_attempts:
            logger.warning(
                f"  API 호출 {total_attempts}건 모두 빈 응답 — "
                f"권한 미승인(403) 또는 해당 기간 거래 없음"
            )

        return {
            "fetched": total_fetched,
            "new": total_new,
            "updated": 0,
            "failures": failures,
            "empty": empty_responses,
        }

    def _save(self, df, district_name: str) -> tuple[int, int]:
        """DataFrame → TransactionHistory 적재"""
        db = SessionLocal()
        fetched = new = 0
        try:
            for _, row in df.iterrows():
                r = row.to_dict()
                fetched += 1

                # 해제된 거래는 제외 (계약 취소분이 시세를 왜곡한다)
                if str(_pick(r, FIELD_CANDIDATES["cancel"], "")).strip() in ("O", "o", "Y"):
                    continue

                # 거래금액은 만원 단위로 온다
                price_manwon = _to_int(_pick(r, FIELD_CANDIDATES["price"]))
                if price_manwon <= 0:
                    continue
                price_krw = price_manwon * 10_000

                y = _to_int(_pick(r, FIELD_CANDIDATES["year"]))
                m = _to_int(_pick(r, FIELD_CANDIDATES["month"]))
                d = _to_int(_pick(r, FIELD_CANDIDATES["day"]), 1)
                if not (y and m):
                    continue
                try:
                    tx_date = date(y, m, max(1, min(d, 28)))
                except ValueError:
                    continue

                dong = str(_pick(r, FIELD_CANDIDATES["dong"], "")).strip()
                jibun = str(_pick(r, FIELD_CANDIDATES["jibun"], "")).strip()
                bldg_area = _to_float(_pick(r, FIELD_CANDIDATES["bldg_area"]))
                usage = str(_pick(r, FIELD_CANDIDATES["usage"], "")).strip()
                bldg_type = str(_pick(r, FIELD_CANDIDATES["bldg_type"], "")).strip()

                # 중복 방지: 같은 날짜·동·금액·면적이면 동일 거래로 본다
                exists = db.query(TransactionHistory.id).filter(
                    TransactionHistory.source == SOURCE,
                    TransactionHistory.district == district_name,
                    TransactionHistory.dong == dong,
                    TransactionHistory.transaction_date == tx_date,
                    TransactionHistory.price_krw == price_krw,
                    TransactionHistory.area_exclusive == bldg_area,
                ).first()
                if exists:
                    continue

                tx = TransactionHistory(
                    city="서울특별시" if district_name in DISTRICT_CODES and
                         DISTRICT_CODES[district_name].startswith("11") else "경기도",
                    district=district_name,
                    dong=dong,
                    name=f"{usage} {bldg_type}".strip() or "상업업무용",
                    address=f"{district_name} {dong} {jibun}".strip(),
                    transaction_date=tx_date,
                    price_krw=price_krw,
                    area_exclusive=bldg_area,
                    floor=_to_int(_pick(r, FIELD_CANDIDATES["floor"]), None) or None,
                    built_year=_to_int(_pick(r, FIELD_CANDIDATES["build_year"]), None) or None,
                    property_type=PROPERTY_TYPE,
                    price_per_m2=int(price_krw / bldg_area) if bldg_area else None,
                    trade_type="매매",
                    source=SOURCE,
                )
                db.add(tx)
                new += 1

                if new % 500 == 0:
                    db.commit()

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        return fetched, new
