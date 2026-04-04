"""
StockBot 기관/외국인 수급 크롤러 v3.7

네이버 금융에서 외국인/기관 순매수 데이터 크롤링.
news/crawler.py 패턴 재사용 (세션, 캐시, 폴백).
"""
import logging
import time
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

# 캐시 TTL: 10분
CACHE_TTL_SEC = 600
# 요청 간격: 0.3초
RATE_LIMIT_SEC = 0.3


class InstitutionalCrawler:
    """네이버 금융 기관/외국인 수급 크롤러"""

    def __init__(self, cache_ttl: int = CACHE_TTL_SEC):
        self._cache = {}  # {symbol: (data, timestamp)}
        self._cache_ttl = cache_ttl
        self._session = None
        self._last_request_time = 0

    def _get_session(self):
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
                self._session.headers.update({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
            except ImportError:
                return None
        return self._session

    def _rate_limit(self):
        """요청 간 최소 0.3초 간격 유지"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < RATE_LIMIT_SEC:
            time.sleep(RATE_LIMIT_SEC - elapsed)
        self._last_request_time = time.time()

    def _get_cache(self, symbol: str) -> Optional[list]:
        if symbol in self._cache:
            data, ts = self._cache[symbol]
            if time.time() - ts < self._cache_ttl:
                return data
            del self._cache[symbol]
        return None

    def _set_cache(self, symbol: str, data: list):
        self._cache[symbol] = (data, time.time())

    def fetch_flow_data(self, symbol: str, pages: int = 2) -> List[dict]:
        """
        네이버 금융 외국인/기관 순매수 데이터 크롤링.

        URL: https://finance.naver.com/item/frgn.naver?code={code}
        20일 데이터 (2페이지 크롤링)

        Args:
            symbol: 종목코드 (예: "005930")
            pages: 크롤링 페이지 수 (기본 2 → 약 20일)

        Returns:
            [{date, inst_net, frgn_net, frgn_holding_pct}, ...]
            최신 날짜가 첫 번째.
        """
        cached = self._get_cache(symbol)
        if cached is not None:
            return cached

        session = self._get_session()
        if not session:
            logger.debug("requests 미설치, 수급 데이터 사용 불가")
            return []

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.debug("beautifulsoup4 미설치, 수급 데이터 사용 불가")
            return []

        all_rows = []
        for page in range(1, pages + 1):
            try:
                self._rate_limit()
                url = (
                    f"https://finance.naver.com/item/frgn.naver"
                    f"?code={symbol}&page={page}"
                )
                resp = session.get(url, timeout=10)
                resp.encoding = "euc-kr"
                soup = BeautifulSoup(resp.text, "html.parser")

                # 테이블 파싱
                table = soup.select_one("table.type2")
                if not table:
                    continue

                rows = table.select("tr")
                for row in rows:
                    cols = row.select("td")
                    if len(cols) < 9:
                        continue

                    try:
                        date_text = cols[0].get_text(strip=True)
                        if not date_text or len(date_text) < 8:
                            continue

                        # 기관 순매수 (6번째 열)
                        inst_text = cols[5].get_text(strip=True).replace(",", "").replace("+", "")
                        # 외국인 순매수 (8번째 열)
                        frgn_text = cols[7].get_text(strip=True).replace(",", "").replace("+", "")
                        # 외국인 보유율 (9번째 열)
                        holding_text = cols[8].get_text(strip=True).replace("%", "")

                        inst_net = int(inst_text) if inst_text and inst_text != "-" else 0
                        frgn_net = int(frgn_text) if frgn_text and frgn_text != "-" else 0
                        frgn_holding = float(holding_text) if holding_text else 0

                        all_rows.append({
                            "date": date_text,
                            "inst_net": inst_net,
                            "frgn_net": frgn_net,
                            "frgn_holding_pct": frgn_holding,
                        })
                    except (ValueError, IndexError):
                        continue

            except Exception as e:
                logger.warning(f"수급 크롤링 실패 [{symbol}] page={page}: {e}")
                break

        if all_rows:
            self._set_cache(symbol, all_rows)
            logger.debug(f"수급 데이터 {len(all_rows)}일 수집: {symbol}")

        return all_rows

    def get_flow_score(self, symbol: str) -> Optional[dict]:
        """
        수급 데이터 기반 스코어 계산.

        Returns:
            {
                "score": float (33~67 범위, 50=중립),
                "frgn_5d": int (5일 외국인 순매수 합계),
                "inst_5d": int (5일 기관 순매수 합계),
                "frgn_20d": int (20일 외국인 순매수 합계),
                "inst_20d": int (20일 기관 순매수 합계),
                "frgn_trend": str ("매수"/"매도"/"중립"),
                "inst_trend": str ("매수"/"매도"/"중립"),
            }
            or None if data unavailable.
        """
        data = self.fetch_flow_data(symbol)
        if not data or len(data) < 5:
            return None

        # 5일/20일 순매수 합계
        frgn_5d = sum(d["frgn_net"] for d in data[:5])
        inst_5d = sum(d["inst_net"] for d in data[:5])
        frgn_20d = sum(d["frgn_net"] for d in data[:20])
        inst_20d = sum(d["inst_net"] for d in data[:20])

        # 트렌드 판단
        frgn_trend = "매수" if frgn_5d > 0 else "매도" if frgn_5d < 0 else "중립"
        inst_trend = "매수" if inst_5d > 0 else "매도" if inst_5d < 0 else "중립"

        # 점수 계산 (+22/-17점 범위 → 33~67로 매핑)
        score = 50.0

        # 5일 단기 트렌드 (더 높은 가중치)
        if frgn_5d > 0 and inst_5d > 0:
            score += 12  # 외국인+기관 동시 매수
        elif frgn_5d > 0:
            score += 7   # 외국인만 매수
        elif inst_5d > 0:
            score += 5   # 기관만 매수
        elif frgn_5d < 0 and inst_5d < 0:
            score -= 10  # 동시 매도
        elif frgn_5d < 0:
            score -= 7   # 외국인만 매도
        elif inst_5d < 0:
            score -= 4   # 기관만 매도

        # 20일 장기 트렌드
        if frgn_20d > 0 and inst_20d > 0:
            score += 10
        elif frgn_20d > 0:
            score += 5
        elif inst_20d > 0:
            score += 4
        elif frgn_20d < 0 and inst_20d < 0:
            score -= 7
        elif frgn_20d < 0:
            score -= 5
        elif inst_20d < 0:
            score -= 3

        score = max(33, min(67, score))

        return {
            "score": round(score, 1),
            "frgn_5d": frgn_5d,
            "inst_5d": inst_5d,
            "frgn_20d": frgn_20d,
            "inst_20d": inst_20d,
            "frgn_trend": frgn_trend,
            "inst_trend": inst_trend,
        }
