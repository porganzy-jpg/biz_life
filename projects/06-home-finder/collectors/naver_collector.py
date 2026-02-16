"""
네이버부동산 매물 스크래퍼
레이트리밋: 3초/건 (보수적)
"""
import logging
import json
from typing import Optional
from collectors.base_collector import BaseCollector
from database import SessionLocal
from models.property import Property

logger = logging.getLogger("homefinder.collector.naver")

# Naver Real Estate API endpoints (unofficial)
NAVER_API_BASE = "https://new.land.naver.com/api"


class NaverCollector(BaseCollector):
    name = "naver"
    rate_limit_seconds = 3.0
    max_retries = 2

    def __init__(self, target_districts: list):
        super().__init__()
        self.target_districts = target_districts

    def collect(self, **kwargs) -> dict:
        """네이버부동산 매물 수집"""
        import requests

        total_fetched = 0
        total_new = 0

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://new.land.naver.com/",
        }

        # District -> Naver region codes
        region_codes = self._get_region_codes()

        for district, code in region_codes.items():
            if self.target_districts and district not in self.target_districts:
                continue

            try:
                self._rate_limit()
                # Naver apartment listing API
                url = f"{NAVER_API_BASE}/articles/complex"
                params = {
                    "cortarNo": code,
                    "realEstateType": "APT:ABYG:JGC",  # 아파트, 빌라, 주거용오피스텔
                    "tradeType": "A1",  # 매매
                    "page": 1,
                    "articleState": "",
                }

                resp = self._retry(requests.get, url, params=params,
                                    headers=headers, timeout=10)
                if resp.status_code != 200:
                    logger.warning(f"Naver API {resp.status_code} for {district}")
                    continue

                data = resp.json()
                articles = data.get("articleList", [])
                total_fetched += len(articles)

                new = self._save_articles(articles, district)
                total_new += new

            except Exception as e:
                logger.warning(f"Naver collect failed for {district}: {e}")
                continue

        return {"fetched": total_fetched, "new": total_new, "updated": 0}

    def _save_articles(self, articles: list, district: str) -> int:
        """네이버 매물을 DB에 저장"""
        db = SessionLocal()
        new = 0

        try:
            for art in articles:
                source_id = str(art.get("articleNo", ""))
                if not source_id:
                    continue

                # Check duplicate
                existing = db.query(Property).filter(
                    Property.source == "naver",
                    Property.source_id == source_id,
                ).first()
                if existing:
                    continue

                # Parse price (만원 -> 원)
                deal_price = str(art.get("dealOrWarrantPrc", "0")).replace(",", "")
                try:
                    price_man = int(deal_price)
                except ValueError:
                    price_man = 0
                price_krw = price_man * 10000

                area = float(art.get("area2", 0) or 0)
                area_supply = float(art.get("area1", 0) or 0)
                price_per_m2 = int(price_krw / area) if area > 0 else 0

                # Map property type
                re_type = art.get("realEstateTypeName", "아파트")
                type_map = {
                    "아파트": "아파트", "빌라": "빌라", "오피스텔": "오피스텔",
                    "연립다세대": "빌라", "단독/다가구": "단독",
                }
                prop_type = type_map.get(re_type, "아파트")

                prop = Property(
                    source="naver",
                    source_id=source_id,
                    property_type=prop_type,
                    acquisition_type="매매",
                    city="서울특별시",
                    district=district,
                    dong=art.get("dong", ""),
                    address=art.get("articleName", ""),
                    detail_address=art.get("detailAddress", ""),
                    lat=float(art.get("latitude", 0) or 0) or None,
                    lng=float(art.get("longitude", 0) or 0) or None,
                    price_krw=price_krw,
                    price_per_m2=price_per_m2,
                    area_m2=area,
                    area_supply_m2=area_supply,
                    floor=int(art.get("floorInfo", "0").split("/")[0] or 0) if "/" in str(art.get("floorInfo", "")) else None,
                    direction=art.get("direction", ""),
                    complex_name=art.get("complexName", ""),
                    source_url=f"https://new.land.naver.com/houses?articleNo={source_id}",
                    description=art.get("articleFeatureDesc", ""),
                )
                db.add(prop)
                new += 1

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Save naver articles error: {e}")
        finally:
            db.close()

        return new

    def _get_region_codes(self) -> dict:
        """네이버 지역코드 매핑"""
        return {
            "마포구": "1144000000", "용산구": "1117000000",
            "성동구": "1120000000", "광진구": "1121500000",
            "영등포구": "1156000000", "동작구": "1159000000",
            "강동구": "1174000000", "은평구": "1138000000",
            "강서구": "1150000000", "노원구": "1135000000",
            "강남구": "1168000000", "서초구": "1165000000",
            "송파구": "1171000000",
        }
