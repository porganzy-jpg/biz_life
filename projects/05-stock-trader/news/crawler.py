"""
StockBot 뉴스 크롤러 v2.0

네이버 금융, Google News RSS에서 실제 뉴스 수집
"""
import logging
import re
import time
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


class NewsCrawler:
    """뉴스 크롤러"""

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5분 캐시
        self._session = None

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

    def fetch_naver_stock_news(self, symbol: str, stock_name: str, limit: int = 15) -> List[dict]:
        """네이버 금융 종목 뉴스 크롤링"""
        cache_key = f"naver_{symbol}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        articles = []
        session = self._get_session()
        if not session:
            return self._generate_sample_news(stock_name)

        try:
            from bs4 import BeautifulSoup

            url = f"https://finance.naver.com/item/news_news.naver?code={symbol}&page=1"
            resp = session.get(url, timeout=10)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")

            rows = soup.select("table.type5 tbody tr")
            for row in rows[:limit]:
                title_tag = row.select_one("td.title a")
                date_tag = row.select_one("td.date")
                source_tag = row.select_one("td.info")

                if title_tag and date_tag:
                    title = title_tag.get_text(strip=True)
                    if not title:
                        continue
                    articles.append({
                        "title": title,
                        "content": title,
                        "date": date_tag.get_text(strip=True),
                        "source": source_tag.get_text(strip=True) if source_tag else "네이버금융",
                        "link": "https://finance.naver.com" + title_tag.get("href", ""),
                    })

            if articles:
                self._set_cache(cache_key, articles)
                logger.info(f"네이버 뉴스 {len(articles)}건 수집: {stock_name}")
                return articles

        except ImportError:
            logger.debug("beautifulsoup4 미설치, 시뮬레이션 데이터 사용")
        except Exception as e:
            logger.warning(f"네이버 뉴스 크롤링 실패 [{stock_name}]: {e}")

        return self._generate_sample_news(stock_name)

    def fetch_rss_news(self, keywords: List[str], limit: int = 20) -> List[dict]:
        """RSS 피드에서 뉴스 수집 (Google News + 한경 + 매경)"""
        cache_key = f"rss_{'_'.join(keywords[:2])}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        articles = []
        try:
            import feedparser

            # Google News (한국어)
            for kw in keywords[:2]:
                feed_url = f"https://news.google.com/rss/search?q={kw}+주식&hl=ko&gl=KR&ceid=KR:ko"
                try:
                    feed = feedparser.parse(feed_url)
                    for entry in feed.entries[:limit // 2]:
                        title = entry.get("title", "")
                        # Google News 제목에서 소스 분리
                        parts = title.rsplit(" - ", 1)
                        clean_title = parts[0] if len(parts) > 1 else title
                        source = parts[1] if len(parts) > 1 else "Google News"

                        articles.append({
                            "title": clean_title,
                            "content": entry.get("summary", ""),
                            "date": entry.get("published", datetime.now().isoformat()),
                            "source": source,
                            "link": entry.get("link", ""),
                        })
                except Exception as e:
                    logger.debug(f"RSS 파싱 실패 [{kw}]: {e}")

            # 한국경제 RSS
            try:
                feed = feedparser.parse("https://www.hankyung.com/feed/finance")
                for entry in feed.entries[:5]:
                    articles.append({
                        "title": entry.get("title", ""),
                        "content": entry.get("summary", ""),
                        "date": entry.get("published", ""),
                        "source": "한국경제",
                        "link": entry.get("link", ""),
                    })
            except Exception:
                pass

            if articles:
                self._set_cache(cache_key, articles)
                logger.info(f"RSS 뉴스 {len(articles)}건 수집: {keywords}")

        except ImportError:
            logger.debug("feedparser 미설치")

        return articles

    def fetch_market_news(self, limit: int = 20) -> List[dict]:
        """시장 전반 뉴스 (KOSPI, 경제)"""
        return self.fetch_rss_news(["코스피", "한국경제", "금리"], limit)

    def fetch_all_news(self, symbol: str, stock_name: str) -> List[dict]:
        """모든 소스에서 뉴스 통합 수집"""
        news = []
        news.extend(self.fetch_naver_stock_news(symbol, stock_name))
        news.extend(self.fetch_rss_news([stock_name]))

        # 중복 제거 (제목 기준)
        seen = set()
        unique = []
        for n in news:
            key = n["title"][:30]
            if key not in seen:
                seen.add(key)
                unique.append(n)
        return unique

    def _get_cache(self, key: str):
        if key in self.cache:
            data, ts = self.cache[key]
            if time.time() - ts < self.cache_ttl:
                return data
            del self.cache[key]
        return None

    def _set_cache(self, key: str, data):
        self.cache[key] = (data, time.time())

    def _generate_sample_news(self, stock_name: str) -> List[dict]:
        """시뮬레이션용 샘플 뉴스"""
        templates = [
            ("{name} 분기 실적 시장 예상 상회...매출 전년比 15% 증가", "긍정"),
            ("{name} 신규 사업 진출 가시화...AI 분야 대규모 투자 발표", "긍정"),
            ("{name} 외국인 순매수 지속...3거래일 연속 매집", "긍정"),
            ("{name} 목표가 상향 조정...증권사 '비중확대' 의견", "긍정"),
            ("{name} 단기 조정 가능성...기술적 저항선 도달", "중립"),
            ("{name} 업종 전반 약세 속 혼조...관망세 지속", "중립"),
        ]

        news = []
        for template, sentiment in templates:
            title = template.format(name=stock_name)
            news.append({
                "title": title,
                "content": title,
                "date": datetime.now().isoformat(),
                "source": "시뮬레이션",
                "sentiment_hint": sentiment,
            })
        return news
