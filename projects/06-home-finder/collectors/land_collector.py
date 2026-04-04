"""
국토교통부 토지 매매 실거래가 수집기
API: https://apis.data.go.kr/1613000/RTMSDataSvcLandTrade
PublicDataReader가 토지를 지원하지 않으므로 직접 XML 파싱
"""
import logging
import requests
import xmltodict
from datetime import datetime, date
from collectors.base_collector import BaseCollector
from database import SessionLocal
from models.transaction import TransactionHistory

logger = logging.getLogger("homefinder.collector.land")

API_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade"

# 서울 + 경기 근교 시군구코드 (5자리)
DISTRICT_CODES = {
    "종로구": "11110", "중구": "11140", "용산구": "11170",
    "성동구": "11200", "광진구": "11215", "동대문구": "11230",
    "중랑구": "11260", "성북구": "11290", "강북구": "11305",
    "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구": "11410", "마포구": "11440", "양천구": "11470",
    "강서구": "11500", "구로구": "11530", "금천구": "11545",
    "영등포구": "11560", "동작구": "11590", "관악구": "11620",
    "서초구": "11650", "강남구": "11680", "송파구": "11710",
    "강동구": "11740",
    "하남시": "41450", "과천시": "41150", "광명시": "41210",
    "구리시": "41310", "남양주시": "41360",
    "성남시 분당구": "41135", "성남시 수정구": "41131", "성남시 중원구": "41133",
    "고양시 덕양구": "41281", "고양시 일산동구": "41285", "고양시 일산서구": "41287",
    "의정부시": "41820", "김포시": "41570", "파주시": "41480",
}


def _calc_year_months(months_back: int) -> list[str]:
    now = datetime.now()
    result = []
    for m in range(months_back):
        y = now.year
        mo = now.month - m
        while mo <= 0:
            mo += 12
            y -= 1
        result.append(f"{y}{mo:02d}")
    return result


class LandCollector(BaseCollector):
    name = "land"
    rate_limit_seconds = 1.5

    def __init__(self, api_key: str, target_districts: list):
        super().__init__()
        self.api_key = api_key
        self.target_districts = target_districts

    def collect(self, months_back: int = 2, **kwargs) -> dict:
        if not self.api_key:
            raise ValueError("PUBLIC_DATA_API_KEY not set")

        total_fetched = 0
        total_new = 0
        failures = 0

        district_codes = [
            (d, DISTRICT_CODES[d]) for d in self.target_districts if d in DISTRICT_CODES
        ]
        if not district_codes:
            district_codes = list(DISTRICT_CODES.items())

        year_months = _calc_year_months(months_back)
        total_attempts = len(district_codes) * len(year_months)

        for district_name, code in district_codes:
            for ym in year_months:
                try:
                    self._rate_limit()
                    items = self._fetch_api(code, ym)

                    if not items:
                        logger.debug(f"  {district_name}/{ym}: no data")
                        continue

                    fetched, new = self._save_transactions(items, district_name)
                    total_fetched += fetched
                    total_new += new
                    logger.info(f"  {district_name}/{ym}: fetched={fetched}, new={new}")

                except Exception as e:
                    failures += 1
                    logger.warning(f"  {district_name}/{ym} failed: {e}")
                    continue

        if failures == total_attempts and total_attempts > 0:
            raise RuntimeError(f"All {total_attempts} land API calls failed. Check API key activation.")

        return {"fetched": total_fetched, "new": total_new, "updated": 0, "failures": failures}

    def _fetch_api(self, lawd_cd: str, deal_ymd: str) -> list:
        """국토부 토지 실거래 API 직접 호출"""
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
        if result_code != "00":
            result_msg = header.get("resultMsg", "unknown")
            raise RuntimeError(f"API error code={result_code}, msg={result_msg}")

        body = response.get("body", {})
        items = body.get("items")
        if items is None:
            return []
        item_list = items.get("item", [])
        if isinstance(item_list, dict):
            item_list = [item_list]
        return item_list if item_list else []

    def _save_transactions(self, items: list, district_name: str) -> tuple:
        db = SessionLocal()
        fetched = len(items)
        new = 0

        try:
            for row in items:
                try:
                    year = int(row.get("년", 0) or 0)
                    month = int(row.get("월", 0) or 0)
                    day = int(row.get("일", 0) or 0)
                    if not all([year, month, day]):
                        continue
                    tx_date = date(year, month, day)

                    price_str = str(row.get("거래금액", "0")).replace(",", "").strip()
                    price_man = int(price_str) if price_str.isdigit() else 0
                    if price_man == 0:
                        continue
                    price_krw = price_man * 10000

                    area = float(row.get("거래면적", 0) or 0)
                    dong = str(row.get("법정동", "")).strip()
                    jibun = str(row.get("지번", "")).strip()
                    land_use = str(row.get("지목", "")).strip()

                    price_per_m2 = int(price_krw / area) if area > 0 else 0

                    # 중복 체크
                    existing = db.query(TransactionHistory).filter(
                        TransactionHistory.district == district_name,
                        TransactionHistory.dong == dong,
                        TransactionHistory.transaction_date == tx_date,
                        TransactionHistory.area_exclusive == area,
                        TransactionHistory.property_type == "토지",
                    ).first()
                    if existing:
                        continue

                    tx = TransactionHistory(
                        city="서울특별시" if district_name.endswith("구") else "경기도",
                        district=district_name,
                        dong=dong,
                        name=f"{dong} {jibun} ({land_use})",
                        address=f"{district_name} {dong} {jibun}",
                        transaction_date=tx_date,
                        price_krw=price_krw,
                        area_exclusive=area,
                        floor=None,
                        built_year=None,
                        property_type="토지",
                        price_per_m2=price_per_m2,
                        source="molit_land",
                    )
                    db.add(tx)
                    new += 1

                    if new > 0 and new % 500 == 0:
                        db.commit()

                except Exception as e:
                    logger.warning(f"Row parse error: {e}")
                    continue

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"DB commit failed for land {district_name}: {e}")
            raise
        finally:
            db.close()

        return fetched, new
