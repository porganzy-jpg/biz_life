"""
청약홈 스크래퍼
레이트리밋: 3초/건
"""
import logging
from datetime import datetime
from collectors.base_collector import BaseCollector
from database import SessionLocal
from models.subscription import SubscriptionOpportunity

logger = logging.getLogger("homefinder.collector.subscription")

APPLYHOME_URL = "https://www.applyhome.co.kr"


class SubscriptionCollector(BaseCollector):
    name = "subscription"
    rate_limit_seconds = 3.0

    def __init__(self, target_cities: list):
        super().__init__()
        self.target_cities = target_cities

    def collect(self, **kwargs) -> dict:
        """청약 정보 수집"""
        import requests
        from bs4 import BeautifulSoup

        total_fetched = 0
        total_new = 0
        db = SessionLocal()

        try:
            self._rate_limit()

            # Fetch current subscription listings
            url = f"{APPLYHOME_URL}/co/coa/selectNoticeList.do"
            resp = self._retry(requests.get, url, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"ApplyHome fetch failed: {resp.status_code}")
                return {"fetched": 0, "new": 0, "updated": 0}

            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select("table tbody tr")

            for row in rows:
                try:
                    cols = row.select("td")
                    if len(cols) < 6:
                        continue

                    name = cols[1].get_text(strip=True)
                    if not name:
                        continue

                    # Filter by target cities
                    location = cols[2].get_text(strip=True)
                    is_target = any(c in location for c in self.target_cities)
                    if not is_target:
                        continue

                    # 개별 청약 공고 링크 생성
                    link_tag = cols[1].select_one("a")
                    detail_href = link_tag.get("href", "") if link_tag else ""
                    source_id = f"sub_{name}_{cols[3].get_text(strip=True)}"

                    # Check duplicate
                    existing = db.query(SubscriptionOpportunity).filter(
                        SubscriptionOpportunity.source_id == source_id
                    ).first()
                    if existing:
                        total_fetched += 1
                        continue

                    # Parse dates
                    start_text = cols[3].get_text(strip=True)
                    end_text = cols[4].get_text(strip=True)
                    start_date = self._parse_date(start_text)
                    end_date = self._parse_date(end_text)

                    # Parse district from location
                    district = ""
                    for d in ["마포구", "용산구", "성동구", "광진구", "영등포구",
                              "동작구", "강동구", "은평구", "강서구", "노원구"]:
                        if d in location:
                            district = d
                            break

                    sub = SubscriptionOpportunity(
                        name=name,
                        city=location.split(" ")[0] if " " in location else "서울특별시",
                        district=district,
                        address=location,
                        subscription_start=start_date,
                        subscription_end=end_date,
                        status="접수중" if end_date and end_date >= datetime.now().date() else "마감",
                        source_id=source_id,
                        source_url=f"{APPLYHOME_URL}{detail_href}" if detail_href else f"{APPLYHOME_URL}/co/coa/selectNoticeInfo.do?noticeId={source_id}",
                    )
                    db.add(sub)
                    total_new += 1
                    total_fetched += 1

                except Exception as e:
                    logger.debug(f"Sub row parse error: {e}")
                    continue

            db.commit()
        finally:
            db.close()

        return {"fetched": total_fetched, "new": total_new, "updated": 0}

    def _parse_date(self, text: str):
        """날짜 파싱"""
        if not text:
            return None
        for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(text.strip()[:10], fmt).date()
            except ValueError:
                continue
        return None
