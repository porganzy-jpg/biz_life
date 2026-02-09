"""
StockBot 뉴스 크롤러

네이버 금융, RSS 피드에서 종목 관련 뉴스를 수집합니다.
"""
import logging
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


class NewsCrawler:
    """뉴스 크롤러"""

    def __init__(self):
        self.cache = {}

    def fetch_naver_stock_news(self, symbol: str, stock_name: str, limit: int = 10) -> List[dict]:
        """
        네이버 금융 뉴스 크롤링

        실제 구현 시 aiohttp + BeautifulSoup으로 크롤링
        현재는 구조 설계 + 시뮬레이션
        """
        try:
            import aiohttp
            from bs4 import BeautifulSoup
            # 실제 크롤링 코드는 API 키/환경에 따라 구현
            # url = f"https://finance.naver.com/item/news.naver?code={symbol}"
        except ImportError:
            pass

        # 시뮬레이션 데이터
        return self._generate_sample_news(stock_name)

    def fetch_rss_news(self, keywords: List[str], limit: int = 20) -> List[dict]:
        """
        RSS 피드에서 뉴스 수집

        구글 뉴스, 한경, 매경 RSS
        """
        try:
            import feedparser
            feeds = [
                f"https://news.google.com/rss/search?q={kw}&hl=ko&gl=KR&ceid=KR:ko"
                for kw in keywords[:3]
            ]
            articles = []
            for feed_url in feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    for entry in feed.entries[:limit]:
                        articles.append({
                            "title": entry.get("title", ""),
                            "content": entry.get("summary", ""),
                            "date": entry.get("published", datetime.now().isoformat()),
                            "source": entry.get("source", {}).get("title", "RSS"),
                            "link": entry.get("link", ""),
                        })
                except Exception as e:
                    logger.debug(f"RSS 파싱 실패: {e}")
            return articles
        except ImportError:
            return self._generate_sample_news(keywords[0] if keywords else "주식")

    def fetch_all_news(self, symbol: str, stock_name: str) -> List[dict]:
        """모든 소스에서 뉴스 통합 수집"""
        news = []
        news.extend(self.fetch_naver_stock_news(symbol, stock_name))
        news.extend(self.fetch_rss_news([stock_name]))
        return news

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
