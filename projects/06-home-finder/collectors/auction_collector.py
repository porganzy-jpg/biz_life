"""
법원경매 스크래퍼
레이트리밋: 5초/건 (보수적)
"""
import logging
from datetime import datetime, date
from collectors.base_collector import BaseCollector
from database import SessionLocal
from models.auction import AuctionListing

logger = logging.getLogger("homefinder.collector.auction")

AUCTION_URL = "https://www.courtauction.go.kr"


class AuctionCollector(BaseCollector):
    name = "auction"
    rate_limit_seconds = 5.0
    max_retries = 2

    def __init__(self, target_districts: list):
        super().__init__()
        self.target_districts = target_districts

    def collect(self, **kwargs) -> dict:
        """법원경매 물건 수집"""
        import requests
        from bs4 import BeautifulSoup

        total_fetched = 0
        total_new = 0
        db = SessionLocal()

        try:
            # Court auction search by region
            for district in self.target_districts:
                try:
                    self._rate_limit()

                    # Search auction listings
                    search_url = f"{AUCTION_URL}/RetrieveRealEstMulDetailList.laf"
                    params = {
                        "bubwLocGubun": "1",  # 서울
                        "jiwonNm": "서울중앙지방법원",
                        "sidoCode": "11",
                        "siguCode": self._get_sigu_code(district),
                        "realVowel": "",
                        "mvRealGbnCode": "01",  # 주거용
                        "page": 1,
                    }

                    resp = self._retry(requests.get, search_url, params=params, timeout=15)
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, "lxml")
                    rows = soup.select("table.Ltbl_list tbody tr")

                    for row in rows:
                        try:
                            cols = row.select("td")
                            if len(cols) < 8:
                                continue

                            case_num = cols[0].get_text(strip=True)
                            if not case_num:
                                continue

                            # Check duplicate
                            existing = db.query(AuctionListing).filter(
                                AuctionListing.case_number == case_num
                            ).first()
                            if existing:
                                total_fetched += 1
                                continue

                            address = cols[3].get_text(strip=True)
                            appraisal_text = cols[5].get_text(strip=True).replace(",", "")
                            min_bid_text = cols[6].get_text(strip=True).replace(",", "")
                            date_text = cols[7].get_text(strip=True)

                            appraisal = int(appraisal_text) if appraisal_text.isdigit() else 0
                            min_bid = int(min_bid_text) if min_bid_text.isdigit() else 0
                            discount = ((appraisal - min_bid) / appraisal * 100) if appraisal > 0 else 0

                            auction_date = None
                            if date_text:
                                try:
                                    auction_date = datetime.strptime(date_text[:10], "%Y-%m-%d").date()
                                except ValueError:
                                    pass

                            listing = AuctionListing(
                                case_number=case_num,
                                court="서울중앙지방법원",
                                city="서울특별시",
                                district=district,
                                address=address,
                                property_type="아파트",
                                appraisal_price=appraisal,
                                minimum_bid=min_bid,
                                discount_rate=round(discount, 1),
                                auction_date=auction_date,
                                auction_status="진행중",
                                source_url=f"{AUCTION_URL}/RetrieveRealEstCar498Detail.laf?saession={case_num}",
                            )
                            db.add(listing)
                            total_new += 1
                            total_fetched += 1
                        except Exception as e:
                            logger.debug(f"Row parse error: {e}")
                            continue

                except Exception as e:
                    logger.warning(f"Auction fetch failed for {district}: {e}")
                    continue

            db.commit()
        finally:
            db.close()

        return {"fetched": total_fetched, "new": total_new, "updated": 0}

    def _get_sigu_code(self, district: str) -> str:
        codes = {
            "마포구": "440", "용산구": "170", "성동구": "200",
            "광진구": "215", "영등포구": "560", "동작구": "590",
            "강동구": "740", "은평구": "380", "강서구": "500",
            "노원구": "350",
        }
        return codes.get(district, "")
