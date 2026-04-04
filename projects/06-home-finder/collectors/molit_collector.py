"""
국토교통부 아파트매매 실거래가 수집기 (PublicDataReader)
API: https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev
"""
import logging
from datetime import datetime, date
from collectors.base_collector import BaseCollector
from database import SessionLocal
from models.transaction import TransactionHistory

logger = logging.getLogger("homefinder.collector.molit")

# 서울 전체 25개구 + 경기도 근교 시군구코드
DISTRICT_CODES = {
    # ── 서울특별시 (25개구) ──
    "종로구": "11110", "중구": "11140", "용산구": "11170",
    "성동구": "11200", "광진구": "11215", "동대문구": "11230",
    "중랑구": "11260", "성북구": "11290", "강북구": "11305",
    "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구": "11410", "마포구": "11440", "양천구": "11470",
    "강서구": "11500", "구로구": "11530", "금천구": "11545",
    "영등포구": "11560", "동작구": "11590", "관악구": "11620",
    "서초구": "11650", "강남구": "11680", "송파구": "11710",
    "강동구": "11740",
    # ── 경기도 근교 ──
    "하남시": "41450", "과천시": "41150", "광명시": "41210",
    "구리시": "41310", "남양주시": "41360",
    "성남시 분당구": "41135", "성남시 수정구": "41131", "성남시 중원구": "41133",
    "고양시 덕양구": "41281", "고양시 일산동구": "41285", "고양시 일산서구": "41287",
    "의정부시": "41150", "김포시": "41570", "파주시": "41480",
}


def _calc_year_months(months_back: int) -> list[str]:
    """정확한 년월 목록 생성 (timedelta 대신 직접 계산)"""
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


class MolitCollector(BaseCollector):
    name = "molit"
    rate_limit_seconds = 1.0

    def __init__(self, api_key: str, target_districts: list):
        super().__init__()
        self.api_key = api_key
        self.target_districts = target_districts

    def collect(self, months_back: int = 3, **kwargs) -> dict:
        """
        실거래가 수집
        Args:
            months_back: 과거 몇 개월치 수집 (기본 3개월)
        """
        try:
            import PublicDataReader as pdr
        except ImportError:
            raise RuntimeError("PublicDataReader not installed. pip install PublicDataReader")

        if not self.api_key:
            raise ValueError("PUBLIC_DATA_API_KEY not set. Check .env file.")

        api = pdr.TransactionPrice(self.api_key)

        total_fetched = 0
        total_new = 0
        failures = 0

        # 대상 구 코드 목록 (지정된 구가 없으면 전체)
        district_codes = [
            (d, DISTRICT_CODES[d]) for d in self.target_districts if d in DISTRICT_CODES
        ]
        if not district_codes:
            district_codes = list(DISTRICT_CODES.items())

        # 정확한 년월 계산
        year_months = _calc_year_months(months_back)

        total_attempts = len(district_codes) * len(year_months)

        for district_name, code in district_codes:
            for ym in year_months:
                try:
                    self._rate_limit()
                    df = self._retry(
                        api.get_data,
                        property_type="아파트",
                        trade_type="매매",
                        sigungu_code=code,
                        year_month=ym,
                    )

                    if df is None or df.empty:
                        logger.debug(f"  {district_name}/{ym}: no data")
                        continue

                    fetched, new = self._save_transactions(df, district_name)
                    total_fetched += fetched
                    total_new += new
                    logger.info(f"  {district_name}/{ym}: fetched={fetched}, new={new}")

                except Exception as e:
                    failures += 1
                    logger.warning(f"  {district_name}/{ym} failed: {e}")
                    continue

        # 전부 실패한 경우 에러로 처리
        if failures == total_attempts and total_attempts > 0:
            raise RuntimeError(
                f"All {total_attempts} API calls failed. "
                f"Check API key validity and network connectivity."
            )

        if failures > 0:
            logger.warning(f"  {failures}/{total_attempts} API calls failed")

        return {"fetched": total_fetched, "new": total_new, "updated": 0, "failures": failures}

    def _save_transactions(self, df, district_name: str) -> tuple:
        """DataFrame → DB 저장 (중복 체크 포함)"""
        db = SessionLocal()
        fetched = len(df)
        new = 0
        parse_failures = 0

        try:
            for _, row in df.iterrows():
                try:
                    # 해제 거래 제외
                    if row.get("해제여부") == "O":
                        continue

                    year = int(row.get("계약년도", 0) or 0)
                    month = int(row.get("계약월", 0) or 0)
                    day = int(row.get("계약일", 0) or 0)
                    if not all([year, month, day]):
                        continue
                    tx_date = date(year, month, day)

                    # 가격 (만원 → 원)
                    price_str = str(row.get("거래금액", "0")).replace(",", "").strip()
                    price_man = int(price_str) if price_str.isdigit() else 0
                    if price_man == 0:
                        continue
                    price_krw = price_man * 10000

                    area = float(row.get("전용면적", 0) or 0)
                    floor_val = int(row.get("층", 0) or 0)
                    built = int(row.get("건축년도", 0) or 0)
                    name = str(row.get("단지명", "")).strip()
                    dong = str(row.get("법정동", "")).strip()
                    jibun = str(row.get("지번", "")).strip()

                    price_per_m2 = int(price_krw / area) if area > 0 else 0

                    # 중복 체크 (같은 단지+날짜+층+면적)
                    existing = db.query(TransactionHistory).filter(
                        TransactionHistory.name == name,
                        TransactionHistory.transaction_date == tx_date,
                        TransactionHistory.floor == floor_val,
                        TransactionHistory.area_exclusive == area,
                    ).first()
                    if existing:
                        continue

                    tx = TransactionHistory(
                        city="서울특별시",
                        district=district_name,
                        dong=dong,
                        name=name,
                        address=f"서울특별시 {district_name} {dong} {jibun}",
                        transaction_date=tx_date,
                        price_krw=price_krw,
                        area_exclusive=area,
                        floor=floor_val,
                        built_year=built,
                        property_type="아파트",
                        price_per_m2=price_per_m2,
                        source="molit",
                    )
                    db.add(tx)
                    new += 1

                    # 500건 단위 배치 커밋
                    if new > 0 and new % 500 == 0:
                        db.commit()

                except Exception as e:
                    parse_failures += 1
                    logger.warning(f"Row parse error in {district_name}: {e}")
                    continue

            db.commit()

            if parse_failures > 0:
                failure_rate = parse_failures / fetched * 100
                if failure_rate > 90:
                    logger.error(
                        f"CRITICAL: {failure_rate:.0f}% of rows failed to parse for {district_name}. "
                        f"API schema may have changed. ({parse_failures}/{fetched} rows)"
                    )
                else:
                    logger.warning(f"{district_name}: {parse_failures}/{fetched} rows failed to parse")

        except Exception as e:
            db.rollback()
            logger.error(f"DB commit failed for {district_name}: {e}")
            raise  # BaseCollector.run()이 실패로 기록하도록 전파
        finally:
            db.close()

        return fetched, new
