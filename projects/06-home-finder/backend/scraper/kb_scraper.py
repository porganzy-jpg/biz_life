"""
KB부동산 스크래퍼 (KB Real Estate Price Scraper)

Lighter scraper focused on KB market price data for scoring.
Uses httpx for async HTTP requests with rate limiting.
Falls back to mock data if real API is unavailable.
"""
import asyncio
import logging
import time
import random
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger("homefinder.scraper.kb")

# KB Real Estate API endpoints (unofficial/public)
KB_API_BASE = "https://data-api.kbland.kr"

KB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://kbland.kr/",
}

# KB region code mapping for Seoul districts
KB_REGION_CODES: Dict[str, str] = {
    "서울": "1100000000",
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
}


class KBRealEstateScraper:
    """
    Scraper for KB Real Estate market price data.

    Focused on price indices and trend data used in property scoring.
    Lighter than the Naver scraper -- does not scrape individual listings.
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
                headers=KB_HEADERS,
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
            wait_time += random.uniform(0.1, 0.3)
            await asyncio.sleep(wait_time)
        self._last_request_time = time.time()

    async def _request(
        self, url: str, params: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make a rate-limited HTTP GET request."""
        await self._rate_limit()
        client = await self._get_client()

        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("KB rate limited (429). Backing off 30s...")
                await asyncio.sleep(30)
                return None
            else:
                logger.warning(
                    "KB API returned %d for %s", response.status_code, url
                )
                return None
        except httpx.TimeoutException:
            logger.warning("KB API timeout for %s", url)
            return None
        except httpx.HTTPError as e:
            logger.warning("KB API HTTP error: %s", e)
            return None
        except Exception as e:
            logger.error("KB API unexpected error: %s", e)
            return None

    # ──────────── Public API Methods ────────────

    async def get_market_prices(
        self, district: str
    ) -> Dict[str, Any]:
        """
        Get KB market price index data for a district.

        Args:
            district: District name (e.g., "마포구")

        Returns:
            Dict with price index info:
            {
                "district": str,
                "avg_price_index": float,
                "change_rate_monthly": float,
                "change_rate_yearly": float,
                "avg_price_per_m2": int,
                "data_points": List[Dict],
            }
        """
        region_code = KB_REGION_CODES.get(district)
        if not region_code:
            logger.warning("Unknown KB region: %s", district)
            return self._mock_market_prices(district)

        url = f"{KB_API_BASE}/bfmstat/weekMnthlyHus498702"
        params = {
            "월간주간구분코드": "01",
            "매매전세코드": "01",
            "부동산구분코드": "01",
            "지역코드": region_code,
        }

        data = await self._request(url, params)

        if data and "dataBody" in data:
            try:
                body = data["dataBody"]
                data_list = body if isinstance(body, list) else body.get("data", [])

                if data_list:
                    latest = data_list[-1] if isinstance(data_list, list) else {}
                    prev = data_list[-2] if isinstance(data_list, list) and len(data_list) > 1 else {}
                    year_ago = data_list[-12] if isinstance(data_list, list) and len(data_list) > 12 else {}

                    current_val = float(latest.get("매매지수", latest.get("index", 100)))
                    prev_val = float(prev.get("매매지수", prev.get("index", 100))) if prev else current_val
                    year_val = float(year_ago.get("매매지수", year_ago.get("index", 100))) if year_ago else current_val

                    monthly_change = ((current_val - prev_val) / prev_val * 100) if prev_val else 0
                    yearly_change = ((current_val - year_val) / year_val * 100) if year_val else 0

                    points = []
                    for item in (data_list[-12:] if isinstance(data_list, list) else []):
                        points.append({
                            "date": item.get("날짜", item.get("date", "")),
                            "index": float(item.get("매매지수", item.get("index", 0))),
                            "change": float(item.get("증감률", item.get("change", 0))),
                        })

                    return {
                        "district": district,
                        "avg_price_index": current_val,
                        "change_rate_monthly": round(monthly_change, 2),
                        "change_rate_yearly": round(yearly_change, 2),
                        "avg_price_per_m2": 0,
                        "data_points": points,
                    }
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("KB data parse error for %s: %s", district, e)

        logger.info("KB API unavailable for %s, returning mock data", district)
        return self._mock_market_prices(district)

    async def get_price_trends(
        self, complex_name: str
    ) -> Dict[str, Any]:
        """
        Get price trend data for a named apartment complex.

        Args:
            complex_name: Name of the apartment complex

        Returns:
            Dict with trend data:
            {
                "complex_name": str,
                "trend_direction": str,  "상승" | "하락" | "보합"
                "avg_price_change_pct": float,
                "recent_transactions": List[Dict],
            }
        """
        # KB does not have a direct complex search by name in their public API.
        # In practice, you would search by complex code, but here we try
        # the name-based search endpoint.
        url = f"{KB_API_BASE}/bfmstat/complexPriceSearch"
        params = {"complexName": complex_name}

        data = await self._request(url, params)

        if data and "dataBody" in data:
            try:
                body = data["dataBody"]
                items = body if isinstance(body, list) else body.get("data", [])

                if items:
                    recent = items[-6:] if isinstance(items, list) else []
                    changes = []
                    for item in recent:
                        chg = float(item.get("증감률", item.get("change_pct", 0)))
                        changes.append(chg)

                    avg_change = sum(changes) / len(changes) if changes else 0

                    if avg_change > 0.5:
                        direction = "상승"
                    elif avg_change < -0.5:
                        direction = "하락"
                    else:
                        direction = "보합"

                    transactions = []
                    for item in recent:
                        transactions.append({
                            "date": item.get("날짜", item.get("date", "")),
                            "price": int(item.get("매매가", item.get("price", 0))),
                            "change_pct": float(item.get("증감률", item.get("change_pct", 0))),
                        })

                    return {
                        "complex_name": complex_name,
                        "trend_direction": direction,
                        "avg_price_change_pct": round(avg_change, 2),
                        "recent_transactions": transactions,
                    }
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("KB trend parse error for %s: %s", complex_name, e)

        logger.info("KB trends unavailable for %s, returning mock data", complex_name)
        return self._mock_price_trends(complex_name)

    # ──────────── Mock Data Generators ────────────

    def _mock_market_prices(self, district: str) -> Dict[str, Any]:
        """Generate realistic mock KB market price data."""
        # Base index values per district (realistic as of 2024-2025)
        base_indices = {
            "마포구": 105.2, "용산구": 112.8, "성동구": 108.5,
            "광진구": 103.7, "영등포구": 101.3, "동작구": 99.8,
            "강동구": 107.1, "은평구": 95.4, "강서구": 97.2,
            "노원구": 88.6, "강남구": 118.5, "서초구": 115.3,
            "송파구": 113.7,
        }

        base = base_indices.get(district, 100.0)

        points = []
        for i in range(12):
            month_idx = base + random.uniform(-2.0, 2.0) + (i * 0.3)
            points.append({
                "date": f"2025-{(i+1):02d}",
                "index": round(month_idx, 1),
                "change": round(random.uniform(-0.5, 0.8), 2),
            })

        return {
            "district": district,
            "avg_price_index": round(base + random.uniform(-1.0, 3.0), 1),
            "change_rate_monthly": round(random.uniform(-0.3, 0.5), 2),
            "change_rate_yearly": round(random.uniform(-2.0, 5.0), 2),
            "avg_price_per_m2": 0,
            "data_points": points,
            "_mock": True,
        }

    def _mock_price_trends(self, complex_name: str) -> Dict[str, Any]:
        """Generate realistic mock price trend data."""
        direction = random.choice(["상승", "보합", "하락"])
        avg_change = {
            "상승": random.uniform(0.5, 3.0),
            "보합": random.uniform(-0.5, 0.5),
            "하락": random.uniform(-3.0, -0.5),
        }[direction]

        transactions = []
        for i in range(6):
            transactions.append({
                "date": f"2025-{(i+1):02d}",
                "price": random.randint(80000, 200000) * 10000,
                "change_pct": round(avg_change + random.uniform(-0.5, 0.5), 2),
            })

        return {
            "complex_name": complex_name,
            "trend_direction": direction,
            "avg_price_change_pct": round(avg_change, 2),
            "recent_transactions": transactions,
            "_mock": True,
        }
