"""
네이버부동산 스크래퍼 (Naver Real Estate Scraper)

Naver Real Estate (land.naver.com) unofficial API scraper.
Uses httpx for async-friendly HTTP requests.
Implements rate limiting to avoid being blocked.
Falls back to realistic mock data if the real API is unavailable.
"""
import asyncio
import logging
import time
import random
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger("homefinder.scraper.naver")

# Naver Real Estate API base URL (unofficial)
NAVER_API_BASE = "https://new.land.naver.com/api"

# Standard browser-like headers required by Naver
NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://new.land.naver.com/",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

# Seoul district -> Naver cortarNo code mapping
DISTRICT_CODES: Dict[str, str] = {
    "마포구": "1144000000",
    "용산구": "1117000000",
    "성동구": "1120000000",
    "광진구": "1121500000",
    "영등포구": "1156000000",
    "동작구": "1159000000",
    "강동구": "1174000000",
    "은평구": "1138000000",
    "강서구": "1150000000",
    "노원구": "1135000000",
    "강남구": "1168000000",
    "서초구": "1165000000",
    "송파구": "1171000000",
    "종로구": "1111000000",
    "중구": "1114000000",
    "동대문구": "1123000000",
    "중랑구": "1126000000",
    "서대문구": "1141000000",
    "양천구": "1147000000",
    "구로구": "1153000000",
    "금천구": "1154500000",
    "관악구": "1162000000",
    "강북구": "1130500000",
    "도봉구": "1132000000",
    "성북구": "1129000000",
}

# Property type mapping from Naver to our schema
NAVER_TYPE_MAP: Dict[str, str] = {
    "아파트": "아파트",
    "오피스텔": "오피스텔",
    "빌라": "빌라",
    "연립다세대": "빌라",
    "단독/다가구": "단독",
    "전원주택": "전원주택",
    "타운하우스": "타운하우스",
    "토지": "토지",
}

# Naver realEstateType codes
NAVER_APT_TYPES = "APT:ABYG:JGC"  # 아파트, 빌라/연립, 주거용 오피스텔
NAVER_LAND_TYPES = "LAND"  # 토지


class NaverRealEstateScraper:
    """
    Scraper for Naver Real Estate (land.naver.com).

    Supports searching apartments, land properties, and fetching
    detailed property/complex information.

    All methods return standardized dicts matching our PropertyCreate schema.
    If the real API is unavailable, falls back to mock data.
    """

    def __init__(self, rate_limit_sec: float = 2.0, timeout: float = 15.0):
        """
        Args:
            rate_limit_sec: Minimum seconds between HTTP requests.
            timeout: HTTP request timeout in seconds.
        """
        self.rate_limit_sec = rate_limit_sec
        self.timeout = timeout
        self._last_request_time: float = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=NAVER_HEADERS,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_sec:
            wait_time = self.rate_limit_sec - elapsed
            # Add small jitter to avoid pattern detection
            wait_time += random.uniform(0.1, 0.5)
            await asyncio.sleep(wait_time)
        self._last_request_time = time.time()

    async def _request(
        self, url: str, params: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Make a rate-limited HTTP GET request.

        Returns parsed JSON dict on success, None on failure.
        """
        await self._rate_limit()
        client = await self._get_client()

        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Naver rate limited (429). Backing off 30s...")
                await asyncio.sleep(30)
                return None
            else:
                logger.warning(
                    "Naver API returned %d for %s", response.status_code, url
                )
                return None
        except httpx.TimeoutException:
            logger.warning("Naver API timeout for %s", url)
            return None
        except httpx.HTTPError as e:
            logger.warning("Naver API HTTP error: %s", e)
            return None
        except Exception as e:
            logger.error("Naver API unexpected error: %s", e)
            return None

    # ──────────── Public API Methods ────────────

    async def search_apartments(
        self,
        district: str,
        dong: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Search apartment listings in a district.

        Args:
            district: Seoul district name (e.g., "마포구")
            dong: Optional dong-level filter
            price_min: Minimum price in 만원 (10,000 KRW)
            price_max: Maximum price in 만원 (10,000 KRW)
            page: Page number (1-based)

        Returns:
            List of raw article dicts from Naver API,
            or mock data if API is unavailable.
        """
        cortar_no = DISTRICT_CODES.get(district)
        if not cortar_no:
            logger.warning("Unknown district: %s", district)
            return []

        params = {
            "cortarNo": cortar_no,
            "realEstateType": NAVER_APT_TYPES,
            "tradeType": "A1",  # 매매
            "page": page,
            "articleState": "",
        }

        if price_min is not None:
            params["priceMin"] = str(price_min)
        if price_max is not None:
            params["priceMax"] = str(price_max)

        url = f"{NAVER_API_BASE}/articles/complex"
        data = await self._request(url, params)

        if data and "articleList" in data:
            articles = data["articleList"]
            # Filter by dong if specified
            if dong:
                articles = [
                    a for a in articles
                    if dong in (a.get("dong", "") or "")
                ]
            logger.info(
                "Naver search_apartments: district=%s, found=%d articles",
                district, len(articles),
            )
            return articles

        # Fallback to mock data
        logger.info(
            "Naver API unavailable for %s, returning mock data", district
        )
        return self._generate_mock_apartments(district, dong)

    async def search_land(
        self,
        district: str,
        dong: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search land property listings in a district.

        Args:
            district: Seoul district name (e.g., "마포구")
            dong: Optional dong-level filter

        Returns:
            List of raw article dicts from Naver API,
            or mock data if API is unavailable.
        """
        cortar_no = DISTRICT_CODES.get(district)
        if not cortar_no:
            logger.warning("Unknown district for land search: %s", district)
            return []

        params = {
            "cortarNo": cortar_no,
            "realEstateType": NAVER_LAND_TYPES,
            "tradeType": "A1",
            "page": 1,
            "articleState": "",
        }

        url = f"{NAVER_API_BASE}/articles/complex"
        data = await self._request(url, params)

        if data and "articleList" in data:
            articles = data["articleList"]
            if dong:
                articles = [
                    a for a in articles
                    if dong in (a.get("dong", "") or "")
                ]
            logger.info(
                "Naver search_land: district=%s, found=%d articles",
                district, len(articles),
            )
            return articles

        logger.info(
            "Naver land API unavailable for %s, returning mock data", district
        )
        return self._generate_mock_land(district, dong)

    async def get_property_detail(
        self, article_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get full property details for a specific article.

        Args:
            article_id: Naver article number

        Returns:
            Full article detail dict, or None if unavailable.
        """
        url = f"{NAVER_API_BASE}/articles/{article_id}"
        params = {"complexNo": ""}
        data = await self._request(url, params)

        if data and "articleDetail" in data:
            return data["articleDetail"]

        # Try alternate endpoint
        url_alt = f"{NAVER_API_BASE}/articles/{article_id}?complexNo="
        data_alt = await self._request(url_alt)
        if data_alt and "articleDetail" in data_alt:
            return data_alt["articleDetail"]

        return None

    async def get_complex_info(
        self, complex_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get apartment complex information.

        Args:
            complex_id: Naver complex ID

        Returns:
            Complex info dict, or None if unavailable.
        """
        url = f"{NAVER_API_BASE}/complexes/overview/{complex_id}"
        data = await self._request(url)

        if data:
            return data

        # Alternate endpoint
        url_alt = f"{NAVER_API_BASE}/complexes/{complex_id}"
        data_alt = await self._request(url_alt)
        return data_alt

    async def get_price_history(
        self, complex_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get price trend data for an apartment complex.

        Args:
            complex_id: Naver complex ID

        Returns:
            List of price trend data points, or None if unavailable.
        """
        url = f"{NAVER_API_BASE}/complexes/{complex_id}/prices"
        params = {
            "complexNo": complex_id,
            "tradeType": "A1",
            "year": 5,
        }
        data = await self._request(url, params)

        if data and "prices" in data:
            return data["prices"]

        return None

    # ──────────── Mock Data Generators ────────────

    def _generate_mock_apartments(
        self, district: str, dong: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate realistic mock apartment data for testing."""
        mock_complexes = {
            "마포구": [
                ("래미안마포리버웰", "아현동", 37.5520, 126.9560, 126000, 84.97, 114.81, "2015", "12/20"),
                ("마포프레스티지자이", "신공덕동", 37.5435, 126.9505, 118000, 84.92, 113.98, "2018", "8/15"),
                ("마포래미안푸르지오", "염리동", 37.5455, 126.9435, 135000, 59.91, 84.98, "2014", "15/25"),
            ],
            "용산구": [
                ("래미안첼리투스", "이촌동", 37.5168, 126.9730, 250000, 84.94, 114.93, "2020", "10/35"),
                ("이촌래미안", "이촌동", 37.5190, 126.9700, 190000, 114.92, 149.94, "2001", "5/15"),
                ("용산시티파크", "한강로2가", 37.5310, 126.9640, 170000, 101.78, 134.95, "2006", "22/34"),
            ],
            "성동구": [
                ("서울숲트리마제", "성수동1가", 37.5474, 127.0452, 225000, 115.87, 149.99, "2019", "25/35"),
                ("금호어울림", "금호동3가", 37.5550, 127.0120, 80000, 59.97, 84.95, "2005", "8/15"),
                ("옥수하이츠", "옥수동", 37.5430, 127.0180, 105000, 84.87, 114.95, "1999", "12/18"),
            ],
        }

        complexes = mock_complexes.get(district, [
            ("샘플아파트1", "중앙동", 37.5500, 127.0000, 90000, 84.0, 112.0, "2010", "7/15"),
            ("샘플아파트2", "역삼동", 37.5550, 127.0050, 110000, 59.0, 84.0, "2015", "10/20"),
        ])

        articles = []
        for i, (name, dong_name, lat, lng, price, area2, area1, built, floor_info) in enumerate(complexes):
            if dong and dong not in dong_name:
                continue
            article_no = f"MOCK_{district}_{i+1:04d}"
            articles.append({
                "articleNo": article_no,
                "articleName": name,
                "realEstateTypeName": "아파트",
                "tradeTypeName": "매매",
                "dealOrWarrantPrc": str(price),
                "area1": area1,
                "area2": area2,
                "direction": random.choice(["남향", "남동향", "남서향", "동향"]),
                "floorInfo": floor_info,
                "dong": dong_name,
                "latitude": lat,
                "longitude": lng,
                "complexName": name,
                "buildingName": "",
                "articleFeatureDesc": f"{name} {dong_name} 매매 {price}만원",
                "articleConfirmYmd": "20250101",
                "buildYear": built,
                "_mock": True,
            })

        return articles

    def _generate_mock_land(
        self, district: str, dong: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate realistic mock land data for testing."""
        mock_lands = {
            "마포구": [
                ("상암동 토지", "상암동", 37.5780, 126.8920, 85000, 230.5, "대", "제2종일반주거지역"),
                ("연남동 건축부지", "연남동", 37.5660, 126.9250, 120000, 180.0, "대", "제1종일반주거지역"),
            ],
            "은평구": [
                ("진관동 전원주택부지", "진관동", 37.6380, 126.9200, 45000, 330.0, "대", "제1종일반주거지역"),
                ("수색동 토지", "수색동", 37.5820, 126.8980, 95000, 200.0, "대", "제2종일반주거지역"),
            ],
        }

        lands = mock_lands.get(district, [
            ("샘플토지", "중앙동", 37.5500, 127.0000, 50000, 250.0, "대", "제2종일반주거지역"),
        ])

        articles = []
        for i, (name, dong_name, lat, lng, price, area, land_use, zoning) in enumerate(lands):
            if dong and dong not in dong_name:
                continue
            article_no = f"MOCK_LAND_{district}_{i+1:04d}"
            articles.append({
                "articleNo": article_no,
                "articleName": name,
                "realEstateTypeName": "토지",
                "tradeTypeName": "매매",
                "dealOrWarrantPrc": str(price),
                "area1": area,
                "area2": area,
                "direction": "",
                "floorInfo": "",
                "dong": dong_name,
                "latitude": lat,
                "longitude": lng,
                "complexName": "",
                "articleFeatureDesc": f"{name} {area}m2 {zoning}",
                "landUse": land_use,
                "zoningType": zoning,
                "_mock": True,
            })

        return articles
