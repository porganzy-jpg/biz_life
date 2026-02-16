"""
공공데이터포털 수집기 (PublicDataReader wrapper)
실거래가 외 공공 데이터 수집
"""
import logging
from collectors.base_collector import BaseCollector

logger = logging.getLogger("homefinder.collector.public")


class PublicDataCollector(BaseCollector):
    name = "public_data"
    rate_limit_seconds = 1.0

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def collect(self, data_type: str = "apartment", **kwargs) -> dict:
        """공공데이터 수집 (확장 가능)"""
        if not self.api_key:
            logger.warning("PUBLIC_DATA_API_KEY not set")
            return {"fetched": 0, "new": 0, "updated": 0}

        # Placeholder for additional public data types
        # (빌라, 단독, 오피스텔 실거래가 등)
        logger.info(f"PublicData collect: {data_type}")
        return {"fetched": 0, "new": 0, "updated": 0}
