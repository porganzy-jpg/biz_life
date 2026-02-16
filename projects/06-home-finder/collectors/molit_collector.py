"""
국토교통부 실거래가 수집기 (PublicDataReader)
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from collectors.base_collector import BaseCollector
from database import SessionLocal
from models.transaction import TransactionHistory

logger = logging.getLogger("homefinder.collector.molit")


class MolitCollector(BaseCollector):
    name = "molit"
    rate_limit_seconds = 1.0

    def __init__(self, api_key: str, target_districts: list):
        super().__init__()
        self.api_key = api_key
        self.target_districts = target_districts

    def collect(self, months_back: int = 1, **kwargs) -> dict:
        """실거래가 수집"""
        try:
            import PublicDataReader as pdr
        except ImportError:
            logger.error("PublicDataReader not installed. pip install PublicDataReader")
            return {"fetched": 0, "new": 0, "updated": 0}

        if not self.api_key:
            logger.warning("PUBLIC_DATA_API_KEY not set, skipping")
            return {"fetched": 0, "new": 0, "updated": 0}

        api = pdr.TransactionPrice(self.api_key)

        # Collect for each month
        total_fetched = 0
        total_new = 0

        now = datetime.now()
        for m in range(months_back):
            target_date = now - timedelta(days=30 * m)
            year_month = target_date.strftime("%Y%m")

            for district_code in self._get_district_codes():
                try:
                    self._rate_limit()
                    df = api.get_data(
                        property_type="아파트",
                        trade_type="매매",
                        sigungu_code=district_code,
                        year_month=year_month,
                    )

                    if df is None or df.empty:
                        continue

                    fetched, new = self._save_transactions(df, district_code)
                    total_fetched += fetched
                    total_new += new

                except Exception as e:
                    logger.warning(f"Failed to fetch {district_code}/{year_month}: {e}")
                    continue

        return {"fetched": total_fetched, "new": total_new, "updated": 0}

    def _save_transactions(self, df, district_code: str) -> tuple:
        """DataFrame을 DB에 저장"""
        db = SessionLocal()
        fetched = len(df)
        new = 0

        try:
            for _, row in df.iterrows():
                try:
                    # Parse transaction date
                    year = int(row.get("년", 0))
                    month = int(row.get("월", 0))
                    day = int(row.get("일", 0))
                    if not all([year, month, day]):
                        continue
                    tx_date = datetime(year, month, day).date()

                    # Parse price (만원 -> 원)
                    price_str = str(row.get("거래금액", "0")).replace(",", "").strip()
                    price_man = int(price_str) if price_str.isdigit() else 0
                    price_krw = price_man * 10000

                    area = float(row.get("전용면적", 0) or 0)
                    floor_val = int(row.get("층", 0) or 0)
                    built = int(row.get("건축년도", 0) or 0)
                    name = str(row.get("아파트", row.get("단지명", "")))
                    dong = str(row.get("법정동", ""))
                    district = str(row.get("시군구", ""))

                    price_per_m2 = int(price_krw / area) if area > 0 else 0

                    tx = TransactionHistory(
                        city="서울특별시",
                        district=district,
                        dong=dong,
                        name=name,
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
                except Exception as e:
                    logger.debug(f"Row parse error: {e}")
                    continue

            db.commit()
        finally:
            db.close()

        return fetched, new

    def _get_district_codes(self) -> list:
        """대상 지역 법정동코드"""
        code_map = {
            "마포구": "11440", "용산구": "11170", "성동구": "11200",
            "광진구": "11215", "영등포구": "11560", "동작구": "11590",
            "강동구": "11740", "은평구": "11380", "강서구": "11500",
            "노원구": "11350", "강남구": "11680", "서초구": "11650",
            "송파구": "11710",
        }
        codes = []
        for d in self.target_districts:
            if d in code_map:
                codes.append(code_map[d])
        return codes if codes else list(code_map.values())
