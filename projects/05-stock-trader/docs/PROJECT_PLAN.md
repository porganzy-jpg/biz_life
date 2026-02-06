# StockBot - 뉴스 크롤링 + 퀀트 분석 기반 주식 자동매매

## 1. 프로젝트 개요

### 1.1 핵심 컨셉
뉴스 크롤링 + 퀀트 분석 기반 중장기 주식 자동매매.
뉴스와 공시 정보를 실시간으로 수집하여 감성 분석(Sentiment Analysis)을 수행하고,
기술적 분석(Technical Analysis) + 기관/외국인 수급 데이터를 결합하여
중장기 관점의 주식 자동매매를 실행한다.

### 1.2 문제 정의
- 주식 시장 정보 과잉: 수많은 뉴스/공시 중 유의미한 정보 선별 어려움
- 감정적 매매 방지: 뉴스에 의한 공포/탐욕 매매 자동화로 해결
- 기관/외국인 수급 분석의 어려움: 데이터 수집 및 해석 자동화
- 퀀트 분석의 진입 장벽: 비전문가도 활용 가능한 시스템 구축

### 1.3 투자 철학
- **중장기 투자**: 최소 보유 기간 1주 ~ 최대 6개월
- **뉴스 기반 선별 + 기술적 분석 기반 타이밍**
- **기관/외국인 수급이 뒷받침되는 종목 우선**
- **분산 투자**: 10~20 종목 포트폴리오 운용

---

## 2. 퀀트 전략 (Quant Strategies)

### 2.1 볼린저밴드 전략

```python
class BollingerBandStrategy:
    """볼린저밴드 기반 매매 전략"""

    def __init__(self, period: int = 20, num_std: float = 2.0):
        self.period = period
        self.num_std = num_std

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """볼린저밴드 계산"""
        df['bb_middle'] = df['close'].rolling(window=self.period).mean()
        df['bb_std'] = df['close'].rolling(window=self.period).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * self.num_std)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * self.num_std)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        return df

    def generate_signal(self, df: pd.DataFrame) -> str:
        df = self.calculate(df)
        current = df.iloc[-1]

        # 하단밴드 터치 + 밴드폭 축소 후 확대 시작 → 매수
        if (current['close'] <= current['bb_lower'] and
            df['bb_width'].iloc[-1] > df['bb_width'].iloc[-2]):
            return 'BUY'

        # 상단밴드 돌파 후 되돌림 시작 → 매도
        elif (current['close'] >= current['bb_upper'] and
              df['close'].iloc[-1] < df['close'].iloc[-2]):
            return 'SELL'

        return 'HOLD'
```

### 2.2 RSI 전략

```python
class RSIStrategy:
    """RSI (Relative Strength Index) 기반 전략"""

    def __init__(self, period: int = 14,
                 oversold: float = 30, overbought: float = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def generate_signal(self, df: pd.DataFrame) -> str:
        rsi = self.calculate_rsi(df)
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        # RSI가 과매도 영역에서 반등 시작 → 매수
        if prev_rsi < self.oversold and current_rsi > self.oversold:
            return 'BUY'

        # RSI가 과매수 영역에서 하락 시작 → 매도
        elif prev_rsi > self.overbought and current_rsi < self.overbought:
            return 'SELL'

        return 'HOLD'
```

### 2.3 MACD 전략

```python
class MACDStockStrategy:
    """주식용 MACD 전략 (일봉/주봉 기반)"""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df['ema_fast'] = df['close'].ewm(span=self.fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.slow, adjust=False).mean()
        df['macd'] = df['ema_fast'] - df['ema_slow']
        df['macd_signal'] = df['macd'].ewm(
            span=self.signal, adjust=False
        ).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        return df

    def generate_signal(self, df: pd.DataFrame) -> str:
        df = self.calculate(df)

        # MACD 히스토그램 양전환 (골든크로스)
        if (df['macd_hist'].iloc[-2] < 0 and
            df['macd_hist'].iloc[-1] > 0):
            return 'BUY'

        # MACD 히스토그램 음전환 (데드크로스)
        elif (df['macd_hist'].iloc[-2] > 0 and
              df['macd_hist'].iloc[-1] < 0):
            return 'SELL'

        return 'HOLD'
```

### 2.4 이동평균선 전략

```python
class StockMAStrategy:
    """주식 이동평균선 전략 (5일, 20일, 60일, 120일)"""

    def __init__(self):
        self.periods = {
            'ma5': 5,      # 단기 (1주)
            'ma20': 20,    # 중기 (1개월)
            'ma60': 60,    # 장기 (3개월)
            'ma120': 120,  # 반기 (6개월)
        }

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        for name, period in self.periods.items():
            df[name] = df['close'].rolling(window=period).mean()
        return df

    def generate_signal(self, df: pd.DataFrame) -> str:
        df = self.calculate(df)
        current = df.iloc[-1]

        # 정배열 전환 (단기 > 중기 > 장기) → 강한 매수
        if (current['ma5'] > current['ma20'] > current['ma60']):
            # 추가 조건: 거래량 증가
            vol_avg = df['volume'].rolling(20).mean().iloc[-1]
            if current['volume'] > vol_avg * 1.5:
                return 'STRONG_BUY'
            return 'BUY'

        # 역배열 전환 (단기 < 중기 < 장기) → 매도
        elif (current['ma5'] < current['ma20'] < current['ma60']):
            return 'SELL'

        return 'HOLD'
```

### 2.5 기관수급 분석

```python
class InstitutionalFlowAnalyzer:
    """기관/외국인 수급 분석"""

    def __init__(self):
        self.weight_foreign = 0.4     # 외국인 비중
        self.weight_institution = 0.3  # 기관 비중
        self.weight_pension = 0.3      # 연기금 비중

    def analyze_flow(self, flow_data: pd.DataFrame) -> dict:
        """수급 분석 (최근 5일, 20일 기준)"""
        recent_5d = flow_data.tail(5)
        recent_20d = flow_data.tail(20)

        # 5일 누적 순매수 금액 (억원)
        foreign_5d = recent_5d['foreign_net_buy'].sum()
        inst_5d = recent_5d['institution_net_buy'].sum()
        pension_5d = recent_5d['pension_net_buy'].sum()

        # 20일 누적 순매수 금액
        foreign_20d = recent_20d['foreign_net_buy'].sum()
        inst_20d = recent_20d['institution_net_buy'].sum()
        pension_20d = recent_20d['pension_net_buy'].sum()

        # 가중 수급 점수
        score_5d = (
            foreign_5d * self.weight_foreign +
            inst_5d * self.weight_institution +
            pension_5d * self.weight_pension
        )
        score_20d = (
            foreign_20d * self.weight_foreign +
            inst_20d * self.weight_institution +
            pension_20d * self.weight_pension
        )

        return {
            'flow_score_5d': score_5d,
            'flow_score_20d': score_20d,
            'foreign_trend': 'BUY' if foreign_5d > 0 else 'SELL',
            'institution_trend': 'BUY' if inst_5d > 0 else 'SELL',
            'pension_trend': 'BUY' if pension_5d > 0 else 'SELL',
            'is_consensus': (foreign_5d > 0 and inst_5d > 0),
        }

    def generate_signal(self, flow_data: pd.DataFrame) -> str:
        analysis = self.analyze_flow(flow_data)

        # 외국인 + 기관 동시 순매수 (5일 기준) → 매수
        if (analysis['is_consensus'] and
            analysis['flow_score_5d'] > 0 and
            analysis['flow_score_20d'] > 0):
            return 'BUY'

        # 외국인 + 기관 동시 순매도 → 매도
        elif (analysis['foreign_trend'] == 'SELL' and
              analysis['institution_trend'] == 'SELL'):
            return 'SELL'

        return 'HOLD'
```

---

## 3. 뉴스 크롤링 및 감성 분석 (News Crawling & Sentiment Analysis)

### 3.1 뉴스 소스

| 소스 | 수집 방법 | 주기 |
|------|----------|------|
| 네이버 금융 뉴스 | Web Scraping (BeautifulSoup) | 5분 |
| 다음 금융 뉴스 | Web Scraping | 5분 |
| 한국경제 | RSS Feed | 10분 |
| 매일경제 | RSS Feed | 10분 |
| DART 공시 | Open API | 실시간 |
| 증권사 리포트 | RSS / API | 1시간 |

### 3.2 뉴스 크롤러

```python
import aiohttp
from bs4 import BeautifulSoup
import feedparser

class NewsCrawler:
    """금융 뉴스 크롤러"""

    def __init__(self):
        self.sources = {
            'naver_finance': 'https://finance.naver.com/news/',
            'hankyung': 'https://www.hankyung.com/feed/finance',
            'mk': 'https://www.mk.co.kr/rss/30100041/',
        }

    async def crawl_naver_stock_news(self, stock_code: str) -> list:
        """네이버 종목 뉴스 크롤링"""
        url = (f"https://finance.naver.com/item/news.naver"
               f"?code={stock_code}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, 'html.parser')
        articles = []

        for item in soup.select('.type5 tbody tr'):
            title_tag = item.select_one('.title a')
            date_tag = item.select_one('.date')
            if title_tag and date_tag:
                articles.append({
                    'title': title_tag.text.strip(),
                    'url': title_tag['href'],
                    'date': date_tag.text.strip(),
                    'source': 'naver',
                })

        return articles

    async def crawl_dart_disclosure(self, corp_code: str) -> list:
        """DART 공시 크롤링"""
        url = "https://opendart.fss.or.kr/api/list.json"
        params = {
            'crtfc_key': self.dart_api_key,
            'corp_code': corp_code,
            'bgn_de': self._get_date_n_days_ago(30),
            'page_count': 20,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()

        return data.get('list', [])
```

### 3.3 감성 분석 엔진

```python
from transformers import pipeline
from openai import OpenAI

class SentimentAnalyzer:
    """뉴스 감성 분석 엔진"""

    def __init__(self):
        # KoBERT 기반 감성 분석 (한국어 특화)
        self.ko_sentiment = pipeline(
            "sentiment-analysis",
            model="snunlp/KR-FinBert-SC"
        )
        self.openai_client = OpenAI()

    def analyze_with_kobert(self, text: str) -> dict:
        """KoBERT 기반 빠른 감성 분석"""
        result = self.ko_sentiment(text[:512])
        return {
            'label': result[0]['label'],    # 긍정/부정/중립
            'score': result[0]['score'],     # 신뢰도
        }

    def analyze_with_llm(self, articles: list,
                          stock_name: str) -> dict:
        """LLM 기반 정밀 감성 분석"""
        articles_text = "\n".join(
            [f"- {a['title']} ({a['date']})" for a in articles[:20]]
        )

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": """당신은 한국 주식 시장 전문 애널리스트입니다.
주어진 뉴스 제목들을 분석하여 해당 종목에 대한 투자 의견을 제시하세요."""
            }, {
                "role": "user",
                "content": f"""
종목: {stock_name}
최근 뉴스:
{articles_text}

다음 형식으로 분석해 주세요:
1. 전반적 감성: (매우긍정/긍정/중립/부정/매우부정)
2. 감성 점수: (-100 ~ +100)
3. 핵심 이슈: (1~3가지)
4. 투자 시사점: (1~2문장)
"""
            }],
            temperature=0.3,
        )

        return self._parse_llm_response(response.choices[0].message.content)

    def get_overall_sentiment(self, stock_code: str,
                               stock_name: str) -> dict:
        """종합 감성 점수 산출"""
        # 뉴스 수집
        articles = self.crawler.crawl_naver_stock_news(stock_code)

        # 개별 뉴스 감성 분석 (KoBERT)
        sentiments = []
        for article in articles[:30]:
            result = self.analyze_with_kobert(article['title'])
            sentiments.append(result)

        # 긍정/부정 비율 계산
        positive = sum(1 for s in sentiments if s['label'] == 'positive')
        negative = sum(1 for s in sentiments if s['label'] == 'negative')
        total = len(sentiments)

        # LLM 정밀 분석
        llm_analysis = self.analyze_with_llm(articles, stock_name)

        return {
            'kobert_score': (positive - negative) / total * 100
                            if total > 0 else 0,
            'llm_analysis': llm_analysis,
            'news_count': total,
            'positive_ratio': positive / total if total > 0 else 0,
        }
```

---

## 4. 종목 선정 알고리즘 (Stock Selection Algorithm)

### 4.1 다단계 필터링

```python
class StockSelector:
    """퀀트 기반 종목 선정"""

    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.flow_analyzer = InstitutionalFlowAnalyzer()

    def select_stocks(self, universe: list) -> list:
        """투자 종목 선정 (다단계 필터링)"""
        candidates = []

        for stock in universe:
            score = self._calculate_total_score(stock)
            if score['total'] >= 70:  # 70점 이상만 선정
                candidates.append({
                    'code': stock['code'],
                    'name': stock['name'],
                    'score': score,
                })

        # 점수 상위 20종목 선정
        candidates.sort(key=lambda x: x['score']['total'], reverse=True)
        return candidates[:20]

    def _calculate_total_score(self, stock: dict) -> dict:
        """종합 점수 계산 (100점 만점)"""

        # 1단계: 기술적 분석 점수 (30점)
        tech_score = self._technical_score(stock)

        # 2단계: 뉴스 감성 점수 (25점)
        sentiment_score = self._sentiment_score(stock)

        # 3단계: 기관/외국인 수급 점수 (25점)
        flow_score = self._flow_score(stock)

        # 4단계: 펀더멘털 점수 (20점)
        fundamental_score = self._fundamental_score(stock)

        total = tech_score + sentiment_score + flow_score + fundamental_score

        return {
            'technical': tech_score,
            'sentiment': sentiment_score,
            'flow': flow_score,
            'fundamental': fundamental_score,
            'total': total,
        }

    def _technical_score(self, stock: dict) -> float:
        """기술적 분석 점수 (최대 30점)"""
        score = 0
        df = stock['price_data']

        # 볼린저밴드 하단 근접 (+10)
        bb = BollingerBandStrategy()
        if bb.generate_signal(df) == 'BUY':
            score += 10

        # RSI 과매도 반등 (+10)
        rsi = RSIStrategy()
        if rsi.generate_signal(df) == 'BUY':
            score += 10

        # MACD 골든크로스 (+10)
        macd = MACDStockStrategy()
        if macd.generate_signal(df) == 'BUY':
            score += 10

        return score

    def _sentiment_score(self, stock: dict) -> float:
        """뉴스 감성 점수 (최대 25점)"""
        sentiment = self.sentiment_analyzer.get_overall_sentiment(
            stock['code'], stock['name']
        )

        # KoBERT 점수 (0~15)
        kobert = max(0, min(15, (sentiment['kobert_score'] + 100) / 200 * 15))

        # LLM 분석 점수 (0~10)
        llm = max(0, min(10,
                         (sentiment['llm_analysis']['score'] + 100) / 200 * 10))

        return kobert + llm

    def _flow_score(self, stock: dict) -> float:
        """수급 점수 (최대 25점)"""
        analysis = self.flow_analyzer.analyze_flow(stock['flow_data'])

        score = 0
        if analysis['foreign_trend'] == 'BUY':
            score += 10
        if analysis['institution_trend'] == 'BUY':
            score += 8
        if analysis['pension_trend'] == 'BUY':
            score += 7

        return score

    def _fundamental_score(self, stock: dict) -> float:
        """펀더멘털 점수 (최대 20점)"""
        fund = stock['fundamental']
        score = 0

        # PER 적정 (5~15배) → +5
        if 5 <= fund.get('per', 0) <= 15:
            score += 5

        # PBR 1 이하 → +5
        if 0 < fund.get('pbr', 0) <= 1.0:
            score += 5

        # ROE 10% 이상 → +5
        if fund.get('roe', 0) >= 10:
            score += 5

        # 영업이익 증가율 양수 → +5
        if fund.get('operating_profit_growth', 0) > 0:
            score += 5

        return score
```

---

## 5. 리스크 관리 (Risk Management)

### 5.1 손절/익절 라인 설정

| 구분 | 기준 | 비고 |
|------|------|------|
| 기본 손절 | -5% | 매수가 대비 |
| 강화 손절 | -3% | 시장 하락 국면 시 |
| 기본 익절 | +10% | 1차 부분 매도 (50%) |
| 추가 익절 | +20% | 2차 부분 매도 (30%) |
| 트레일링 스탑 | 고점 대비 -5% | 나머지 20% 물량 |

### 5.2 포트폴리오 리스크 관리

```python
class PortfolioRiskManager:
    """포트폴리오 리스크 관리"""

    def __init__(self, total_capital: float):
        self.total_capital = total_capital
        self.max_single_position = 0.10  # 종목당 최대 10%
        self.max_sector_weight = 0.30    # 섹터당 최대 30%
        self.max_positions = 20          # 최대 보유 종목 수
        self.cash_reserve = 0.20         # 최소 현금 비중 20%

    def validate_order(self, order: dict,
                        portfolio: dict) -> tuple[bool, str]:
        """주문 유효성 검증"""

        # 종목당 최대 비중 체크
        position_weight = order['amount'] / self.total_capital
        if position_weight > self.max_single_position:
            return False, f"종목 비중 초과: {position_weight:.1%}"

        # 섹터 비중 체크
        sector = order['sector']
        sector_weight = self._get_sector_weight(portfolio, sector)
        if sector_weight + position_weight > self.max_sector_weight:
            return False, f"섹터 비중 초과: {sector}"

        # 최대 종목 수 체크
        if len(portfolio['positions']) >= self.max_positions:
            return False, "최대 보유 종목 수 초과"

        # 현금 비중 체크
        available_cash = portfolio['cash'] - order['amount']
        cash_ratio = available_cash / self.total_capital
        if cash_ratio < self.cash_reserve:
            return False, f"최소 현금 비중 미달: {cash_ratio:.1%}"

        return True, "OK"

    def rebalance_signal(self, portfolio: dict) -> list:
        """리밸런싱 신호 생성 (월 1회)"""
        signals = []

        for position in portfolio['positions']:
            current_weight = position['value'] / self.total_capital

            # 비중 초과 종목 → 일부 매도
            if current_weight > self.max_single_position * 1.5:
                signals.append({
                    'action': 'REDUCE',
                    'code': position['code'],
                    'reason': f"비중 초과 ({current_weight:.1%})",
                })

            # 손절 라인 도달 종목 → 전량 매도
            if position['return_pct'] <= -0.05:
                signals.append({
                    'action': 'STOP_LOSS',
                    'code': position['code'],
                    'reason': f"손절 ({position['return_pct']:.1%})",
                })

        return signals
```

### 5.3 시장 상황별 전략 조절

| 시장 상황 | 판단 기준 | 전략 조절 |
|----------|----------|----------|
| 상승장 | KOSPI 20일선 위 + 양봉 | 공격적: 현금 20%, 종목 80% |
| 횡보장 | KOSPI 20일선 횡보 | 균형: 현금 40%, 종목 60% |
| 하락장 | KOSPI 20일선 아래 + 음봉 | 방어적: 현금 60%, 종목 40% |
| 급락장 | KOSPI -3% 이상 하락 | 안전: 현금 80%, 종목 20% |

---

## 6. 기술 아키텍처 (Technical Architecture)

### 6.1 전체 시스템 구성

```
[뉴스 크롤러 (Scrapy/aiohttp)]
    │ - 네이버/다음 금융 뉴스
    │ - DART 공시
    │ - 증권사 리포트
    │
    ▼
[감성 분석 엔진]
    │ - KR-FinBERT (한국어 금융 특화)
    │ - GPT-4o-mini (정밀 분석)
    │
    ▼
[퀀트 분석 엔진]
    │ - 볼린저밴드, RSI, MACD, 이동평균선
    │ - 기관/외국인 수급 분석
    │ - 펀더멘털 분석 (PER, PBR, ROE)
    │
    ▼
[종목 선정 엔진]
    │ - 다단계 필터링
    │ - 종합 점수 산출
    │ - 포트폴리오 최적화
    │
    ▼
[주문 실행 엔진]
    │ - 한국투자증권 API
    │ - 키움증권 API (QV OpenAPI+)
    │
    ▼
[대시보드 (FastAPI + React)]
    │ - 포트폴리오 현황
    │ - 종목 선정 이유
    │ - 뉴스 감성 분석 결과
    │
    ▼
[알림 시스템]
    │ - Telegram Bot
    │ - 카카오톡 알림
```

### 6.2 한국투자증권 API 연동

```python
import mojito  # 한국투자증권 Python SDK

class KISTrader:
    """한국투자증권 API 트레이더"""

    def __init__(self, api_key: str, api_secret: str,
                 acc_no: str, mock: bool = True):
        self.broker = mojito.KoreaInvestment(
            api_key=api_key,
            api_secret=api_secret,
            acc_no=acc_no,
            mock=mock,  # True: 모의투자, False: 실전투자
        )

    def get_price(self, stock_code: str) -> dict:
        """현재가 조회"""
        return self.broker.fetch_price(stock_code)

    def get_daily_price(self, stock_code: str,
                         period: str = 'D') -> pd.DataFrame:
        """일별 시세 조회"""
        resp = self.broker.fetch_ohlcv(
            symbol=stock_code,
            timeframe=period,
            adj_price=True,
        )
        return pd.DataFrame(resp['output2'])

    def buy(self, stock_code: str, qty: int,
            price: int = 0) -> dict:
        """매수 주문"""
        if price == 0:
            # 시장가 매수
            return self.broker.create_market_buy_order(
                symbol=stock_code,
                quantity=qty,
            )
        else:
            # 지정가 매수
            return self.broker.create_limit_buy_order(
                symbol=stock_code,
                price=price,
                quantity=qty,
            )

    def sell(self, stock_code: str, qty: int,
             price: int = 0) -> dict:
        """매도 주문"""
        if price == 0:
            return self.broker.create_market_sell_order(
                symbol=stock_code,
                quantity=qty,
            )
        else:
            return self.broker.create_limit_sell_order(
                symbol=stock_code,
                price=price,
                quantity=qty,
            )

    def get_balance(self) -> dict:
        """잔고 조회"""
        return self.broker.fetch_balance()
```

### 6.3 키움증권 API 연동

```python
class KiwoomTrader:
    """키움증권 QV OpenAPI+ 트레이더"""

    def __init__(self):
        # 키움 OpenAPI+는 Windows COM 기반
        # pykiwoom 라이브러리 사용
        from pykiwoom.kiwoom import Kiwoom
        self.kiwoom = Kiwoom()
        self.kiwoom.CommConnect(block=True)

    def get_stock_info(self, code: str) -> dict:
        """종목 정보 조회"""
        return {
            'name': self.kiwoom.GetMasterCodeName(code),
            'price': self.kiwoom.GetCommRealData(code, 10),
            'volume': self.kiwoom.GetCommRealData(code, 15),
        }

    def get_daily_data(self, code: str, count: int = 120) -> pd.DataFrame:
        """일봉 데이터 조회"""
        df = self.kiwoom.block_request(
            "opt10081",
            종목코드=code,
            기준일자="",
            수정주가구분=1,
            output="주식일봉차트조회",
            next=0,
        )
        return df.head(count)

    def send_order(self, order_type: int, code: str,
                    qty: int, price: int, hoga: str) -> int:
        """주문 전송
        order_type: 1=신규매수, 2=신규매도, 3=매수취소, 4=매도취소
        hoga: '00'=지정가, '03'=시장가
        """
        return self.kiwoom.SendOrder(
            "주문",          # 사용자 구분명
            "0101",          # 화면번호
            self.account,    # 계좌번호
            order_type,      # 주문유형
            code,            # 종목코드
            qty,             # 수량
            price,           # 가격
            hoga,            # 호가유형
            "",              # 원주문번호
        )

    def get_holding_stocks(self) -> list:
        """보유 종목 조회"""
        df = self.kiwoom.block_request(
            "opw00018",
            계좌번호=self.account,
            비밀번호="",
            비밀번호입력매체구분="00",
            조회구분=1,
            output="계좌평가잔고개별합산",
            next=0,
        )
        return df.to_dict('records')
```

---

## 7. Paper Trading -> 실전 전환 (Paper Trading First)

### 7.1 Paper Trading 단계

```
Phase 1: 백테스트 (4주)
    └── 과거 2년치 데이터로 전략 검증
    └── 수익률, MDD, 승률 확인
    └── 파라미터 최적화

Phase 2: Paper Trading (8주)
    └── 한국투자증권 모의투자 계좌 사용 (mock=True)
    └── 실시간 시장에서 가상 매매 실행
    └── 실전과 동일한 조건 (수수료, 슬리피지 반영)

Phase 3: 소액 실전 (4주)
    └── 실전 계좌 전환 (mock=False)
    └── 투자금 100만원으로 소규모 운용
    └── 시스템 안정성 검증

Phase 4: 점진적 증액 (지속)
    └── 성과 확인 후 월 단위로 투자금 증액
    └── 최대 투자금: 총 자산의 30% 이내
```

### 7.2 Paper Trading 성과 기준

| 지표 | 최소 기준 | 목표 기준 | 미달 시 조치 |
|------|----------|----------|-------------|
| 월간 수익률 | +2% | +5% | 전략 재검토 |
| 승률 | 50% | 60% | 진입 조건 강화 |
| MDD | -8% 이내 | -5% 이내 | 손절 라인 조정 |
| 샤프 비율 | 1.0 이상 | 1.5 이상 | 전략 조합 변경 |

### 7.3 실전 전환 체크리스트
- [ ] Paper Trading 8주 이상 운용 완료
- [ ] 월간 수익률 최소 기준 2개월 연속 달성
- [ ] MDD -8% 이내 유지
- [ ] 시스템 장애 0건 (8주간)
- [ ] 주문 실행 정확도 99.9% 이상
- [ ] 슬리피지 평균 0.1% 이내
- [ ] 리스크 관리 시스템 정상 작동 확인
- [ ] 비상 정지(Circuit Breaker) 테스트 완료

---

## 8. 운영 스케줄

### 8.1 일일 운영 스케줄 (한국 주식 시장)

| 시간 | 작업 | 자동/수동 |
|------|------|----------|
| 07:00 | 뉴스 크롤링 및 감성 분석 시작 | 자동 |
| 08:00 | 전일 수급 데이터 수집 | 자동 |
| 08:30 | 종목 선정 알고리즘 실행 | 자동 |
| 08:50 | 매수 예정 종목 리스트 텔레그램 알림 | 자동 |
| 09:00 | 장 시작 - 주문 실행 시작 | 자동 |
| 09:00~15:30 | 실시간 모니터링 + 손절/익절 실행 | 자동 |
| 15:30 | 장 마감 - 일일 성과 정리 | 자동 |
| 16:00 | 일일 리포트 텔레그램 발송 | 자동 |
| 19:00 | DART 공시 크롤링 (장 마감 후 공시) | 자동 |

### 8.2 주간/월간 작업
- **매주 토요일**: 주간 성과 리뷰, 전략 파라미터 점검
- **매월 1일**: 월간 성과 리포트, 전략 가중치 재조정
- **매분기**: 포트폴리오 리밸런싱, 유니버스 재선정

---

## 9. 대시보드 설계

### 9.1 메인 대시보드 구성 요소
- **포트폴리오 총 가치**: 실시간 자산 현황
- **수익률 차트**: 일별/주별/월별 수익률 그래프
- **보유 종목 리스트**: 종목명, 수량, 평균단가, 현재가, 수익률
- **오늘의 매매**: 당일 체결 내역
- **뉴스 감성 히트맵**: 종목별 뉴스 감성 점수 시각화
- **수급 현황**: 기관/외국인 매매 동향

### 9.2 종목 상세 페이지
- 차트 (일봉/주봉 + 기술적 지표 오버레이)
- 뉴스 타임라인 (감성 분석 결과 포함)
- 수급 추이 (5일/20일/60일)
- 종목 선정 점수 내역
- 매매 이력

---

## 10. KPI 및 성과 지표

- **연간 수익률**: KOSPI 수익률 + 10%p 초과 (목표)
- **월간 수익률**: 3~8% (안정적 수익)
- **최대 낙폭 (MDD)**: -10% 이내
- **승률**: 55% 이상
- **샤프 비율**: 1.5 이상
- **종목 선정 적중률**: 60% 이상 (매수 후 +5% 도달)
- **뉴스 감성 분석 정확도**: 75% 이상
- **시스템 가동률**: 99.5% 이상 (장중)
- **Paper Trading → 실전 전환 성공률**: 목표 기준 달성 후 전환
