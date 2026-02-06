# CryptoBot - 암호화폐 자동매매 시스템

## 1. 프로젝트 개요

### 1.1 핵심 컨셉
24시간 코인 시장에서 등락률 높은 코인 단타 자동매매.
암호화폐 시장은 24시간 365일 운영되므로 사람이 모든 기회를 포착하기 어렵다.
변동성이 높은 코인을 자동으로 탐지하고, 기술적 분석 기반 단기 매매를 자동화하여
안정적인 수익을 추구한다.

### 1.2 문제 정의
- 24시간 시장 모니터링 불가능 (인간의 한계)
- 감정적 매매 (FOMO, 공포 매매) 방지 필요
- 고빈도 데이터 분석은 알고리즘이 인간보다 우월
- 다수의 코인을 동시에 모니터링하고 최적 진입점 포착 필요

### 1.3 목표
- 월 수익률: 5~15% (보수적 목표)
- 최대 손실률 (MDD): -10% 이내
- 승률: 55% 이상
- 수익/손실 비율 (R:R): 1.5:1 이상

---

## 2. 트레이딩 전략 (Trading Strategies)

### 2.1 변동성 돌파 전략 (Volatility Breakout)

```python
class VolatilityBreakoutStrategy:
    """래리 윌리엄스의 변동성 돌파 전략 변형"""

    def __init__(self, k_value: float = 0.5):
        self.k = k_value  # 변동성 계수 (0.4~0.6 최적)

    def calculate_target_price(self, df: pd.DataFrame) -> float:
        """목표 매수 가격 계산"""
        prev_high = df['high'].iloc[-2]
        prev_low = df['low'].iloc[-2]
        today_open = df['open'].iloc[-1]

        volatility_range = prev_high - prev_low
        target_price = today_open + (volatility_range * self.k)
        return target_price

    def should_buy(self, current_price: float, target_price: float) -> bool:
        """매수 신호 판단"""
        return current_price >= target_price

    def should_sell(self, position_entry: float, current_price: float) -> str:
        """매도 신호 판단"""
        profit_ratio = (current_price - position_entry) / position_entry

        if profit_ratio >= 0.03:     # 3% 이상 수익
            return 'TAKE_PROFIT'
        elif profit_ratio <= -0.015:  # 1.5% 이상 손실
            return 'STOP_LOSS'
        else:
            return 'HOLD'
```

### 2.2 볼린저밴드 + RSI 복합 전략

```python
class BollingerRSIStrategy:
    """볼린저밴드와 RSI를 결합한 평균 회귀 전략"""

    def __init__(self, bb_period=20, bb_std=2.0, rsi_period=14):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period

    def calculate_bollinger_bands(self, df: pd.DataFrame) -> dict:
        """볼린저밴드 계산"""
        sma = df['close'].rolling(window=self.bb_period).mean()
        std = df['close'].rolling(window=self.bb_period).std()

        return {
            'upper': sma + (std * self.bb_std),
            'middle': sma,
            'lower': sma - (std * self.bb_std),
        }

    def calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """RSI 계산"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def generate_signal(self, df: pd.DataFrame) -> str:
        """매매 신호 생성"""
        bb = self.calculate_bollinger_bands(df)
        rsi = self.calculate_rsi(df)

        current_price = df['close'].iloc[-1]
        current_rsi = rsi.iloc[-1]

        # 매수 조건: 가격이 하단 밴드 이하 + RSI 30 이하 (과매도)
        if current_price <= bb['lower'].iloc[-1] and current_rsi <= 30:
            return 'BUY'

        # 매도 조건: 가격이 상단 밴드 이상 + RSI 70 이상 (과매수)
        elif current_price >= bb['upper'].iloc[-1] and current_rsi >= 70:
            return 'SELL'

        return 'HOLD'
```

### 2.3 MACD 전략

```python
class MACDStrategy:
    """MACD 기반 추세 추종 전략"""

    def __init__(self, fast=12, slow=26, signal=9):
        self.fast_period = fast
        self.slow_period = slow
        self.signal_period = signal

    def calculate_macd(self, df: pd.DataFrame) -> dict:
        """MACD 계산"""
        ema_fast = df['close'].ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.slow_period, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram,
        }

    def generate_signal(self, df: pd.DataFrame) -> str:
        """매매 신호 생성"""
        macd = self.calculate_macd(df)

        # 골든크로스: MACD선이 시그널선을 상향 돌파
        if (macd['macd'].iloc[-2] < macd['signal'].iloc[-2] and
            macd['macd'].iloc[-1] > macd['signal'].iloc[-1]):
            return 'BUY'

        # 데드크로스: MACD선이 시그널선을 하향 돌파
        elif (macd['macd'].iloc[-2] > macd['signal'].iloc[-2] and
              macd['macd'].iloc[-1] < macd['signal'].iloc[-1]):
            return 'SELL'

        return 'HOLD'
```

### 2.4 이동평균선 전략

```python
class MovingAverageStrategy:
    """다중 이동평균선 기반 추세 전략"""

    def __init__(self):
        self.periods = {
            'short': 5,
            'medium': 20,
            'long': 60,
            'very_long': 120,
        }

    def calculate_mas(self, df: pd.DataFrame) -> dict:
        """이동평균선 계산"""
        return {
            name: df['close'].rolling(window=period).mean()
            for name, period in self.periods.items()
        }

    def generate_signal(self, df: pd.DataFrame) -> str:
        """정배열/역배열 기반 신호 생성"""
        mas = self.calculate_mas(df)
        latest = {name: ma.iloc[-1] for name, ma in mas.items()}

        # 정배열: 단기 > 중기 > 장기 > 초장기
        if (latest['short'] > latest['medium'] >
            latest['long'] > latest['very_long']):
            return 'STRONG_BUY'

        # 역배열: 단기 < 중기 < 장기 < 초장기
        elif (latest['short'] < latest['medium'] <
              latest['long'] < latest['very_long']):
            return 'STRONG_SELL'

        # 단기-중기 골든크로스
        elif (mas['short'].iloc[-2] < mas['medium'].iloc[-2] and
              mas['short'].iloc[-1] > mas['medium'].iloc[-1]):
            return 'BUY'

        return 'HOLD'
```

### 2.5 복합 전략 앙상블

```python
class StrategyEnsemble:
    """여러 전략의 신호를 종합하여 최종 결정"""

    def __init__(self):
        self.strategies = {
            'volatility': VolatilityBreakoutStrategy(),
            'bollinger_rsi': BollingerRSIStrategy(),
            'macd': MACDStrategy(),
            'moving_average': MovingAverageStrategy(),
        }
        self.weights = {
            'volatility': 0.3,
            'bollinger_rsi': 0.3,
            'macd': 0.2,
            'moving_average': 0.2,
        }

    def get_final_signal(self, df: pd.DataFrame) -> dict:
        """가중 투표 기반 최종 신호"""
        buy_score = 0
        sell_score = 0

        for name, strategy in self.strategies.items():
            signal = strategy.generate_signal(df)
            weight = self.weights[name]

            if signal in ('BUY', 'STRONG_BUY'):
                buy_score += weight * (1.5 if 'STRONG' in signal else 1.0)
            elif signal in ('SELL', 'STRONG_SELL'):
                sell_score += weight * (1.5 if 'STRONG' in signal else 1.0)

        if buy_score >= 0.6:
            return {'action': 'BUY', 'confidence': buy_score}
        elif sell_score >= 0.6:
            return {'action': 'SELL', 'confidence': sell_score}
        else:
            return {'action': 'HOLD', 'confidence': max(buy_score, sell_score)}
```

---

## 3. 리스크 관리 (Risk Management)

### 3.1 자금 관리 원칙
- **전체 투자금의 10% 이내**로 단일 포지션 진입
- 동시 보유 포지션: 최대 5개
- 일일 최대 손실: 전체 투자금의 3%
- 월간 최대 손실: 전체 투자금의 10%

### 3.2 손절 라인 (Stop Loss)
| 전략 | 손절 기준 | 비고 |
|------|----------|------|
| 변동성 돌파 | -1.5% | 빠른 손절 |
| 볼린저밴드+RSI | -2.0% | 중간 손절 |
| MACD | -2.5% | 추세 전환 확인 후 |
| 이동평균선 | -3.0% | 장기 추세 기반 |

### 3.3 익절 라인 (Take Profit)
| 전략 | 익절 기준 | 트레일링 스탑 |
|------|----------|--------------|
| 변동성 돌파 | +3.0% | 고점 대비 -1% |
| 볼린저밴드+RSI | +4.0% | 고점 대비 -1.5% |
| MACD | +5.0% | 고점 대비 -2% |
| 이동평균선 | +7.0% | 고점 대비 -2.5% |

### 3.4 분산 투자
- 시가총액 상위 20개 코인 중 선별
- 섹터 분산: DeFi, Layer1, Layer2, Meme 등
- 거래소 분산: Upbit 60%, Binance 40%
- 전략 분산: 4개 전략 병행 운용

### 3.5 비상 정지 조건 (Circuit Breaker)

```python
class CircuitBreaker:
    """비상 정지 시스템"""

    def __init__(self, config: dict):
        self.max_daily_loss_pct = config.get('max_daily_loss', 0.03)
        self.max_monthly_loss_pct = config.get('max_monthly_loss', 0.10)
        self.max_consecutive_losses = config.get('max_consecutive_losses', 5)

    def should_stop(self, performance: dict) -> tuple[bool, str]:
        if performance['daily_pnl_pct'] <= -self.max_daily_loss_pct:
            return True, "일일 최대 손실 도달"

        if performance['monthly_pnl_pct'] <= -self.max_monthly_loss_pct:
            return True, "월간 최대 손실 도달"

        if performance['consecutive_losses'] >= self.max_consecutive_losses:
            return True, "연속 손실 한도 도달"

        return False, ""
```

---

## 4. 기술 아키텍처 (Technical Architecture)

### 4.1 전체 시스템 구성

```
[Data Collector]
    │ - ccxt (거래소 API)
    │ - WebSocket (실시간 시세)
    │
    ▼
[Data Pipeline]
    │ - pandas (데이터 처리)
    │ - ta-lib (기술적 지표)
    │ - Redis (실시간 캐시)
    │
    ▼
[Strategy Engine]
    │ - 4개 전략 병렬 실행
    │ - 앙상블 투표
    │ - Risk Manager
    │
    ▼
[Order Executor]
    │ - Upbit API
    │ - Binance API
    │ - 주문 실행 / 체결 확인
    │
    ▼
[Dashboard (FastAPI + React)]
    │ - 실시간 수익률
    │ - 포지션 현황
    │ - 전략 성과 분석
    │
    ▼
[Alert System]
    │ - Telegram Bot
    │ - Slack Webhook
    │ - Email
```

### 4.2 기술 스택 상세

| 구성 요소 | 기술 | 버전/사양 |
|----------|------|----------|
| 언어 | Python | 3.11+ |
| 거래소 연동 | ccxt | 최신 |
| 데이터 처리 | pandas, numpy | 최신 |
| 기술적 분석 | ta-lib, pandas-ta | 최신 |
| 백엔드 API | FastAPI | 0.100+ |
| 프론트엔드 | React + Recharts | 18+ |
| 데이터베이스 | PostgreSQL | 15+ |
| 캐시 | Redis | 7.x |
| 태스크 큐 | Celery + Redis | 최신 |
| 모니터링 | Prometheus + Grafana | 최신 |
| 알림 | python-telegram-bot | 최신 |
| 서버 | AWS EC2 (t3.medium) | 또는 로컬 서버 |

### 4.3 ccxt 기반 거래소 연동

```python
import ccxt

class ExchangeConnector:
    """ccxt를 활용한 거래소 통합 연동"""

    def __init__(self, exchange_id: str, api_key: str, secret: str):
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })

    def get_ohlcv(self, symbol: str, timeframe: str = '1h',
                   limit: int = 200) -> pd.DataFrame:
        """OHLCV 데이터 조회"""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv,
                         columns=['timestamp', 'open', 'high', 'low',
                                  'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def place_order(self, symbol: str, side: str, amount: float,
                    order_type: str = 'market') -> dict:
        """주문 실행"""
        if order_type == 'market':
            return self.exchange.create_market_order(symbol, side, amount)
        elif order_type == 'limit':
            price = self.exchange.fetch_ticker(symbol)['last']
            return self.exchange.create_limit_order(
                symbol, side, amount, price
            )

    def get_balance(self) -> dict:
        """잔고 조회"""
        balance = self.exchange.fetch_balance()
        return {
            'total': balance['total'],
            'free': balance['free'],
            'used': balance['used'],
        }
```

---

## 5. Upbit API 연동

### 5.1 Upbit 특화 기능

```python
import jwt
import uuid
import hashlib
import requests
from urllib.parse import urlencode

class UpbitTrader:
    """Upbit 거래소 전용 트레이더"""

    BASE_URL = "https://api.upbit.com/v1"

    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key

    def _create_token(self, query: dict = None) -> str:
        """JWT 토큰 생성"""
        payload = {
            'access_key': self.access_key,
            'nonce': str(uuid.uuid4()),
        }
        if query:
            query_string = urlencode(query).encode()
            m = hashlib.sha512()
            m.update(query_string)
            payload['query_hash'] = m.hexdigest()
            payload['query_hash_alg'] = 'SHA512'

        return jwt.encode(payload, self.secret_key)

    def get_top_volatile_coins(self, top_n: int = 10) -> list:
        """등락률 상위 코인 조회"""
        url = f"{self.BASE_URL}/market/all"
        markets = requests.get(url).json()

        krw_markets = [m['market'] for m in markets
                       if m['market'].startswith('KRW-')]

        tickers_url = f"{self.BASE_URL}/ticker"
        params = {'markets': ','.join(krw_markets)}
        tickers = requests.get(tickers_url, params=params).json()

        # 등락률 기준 정렬
        sorted_tickers = sorted(
            tickers,
            key=lambda x: abs(x['signed_change_rate']),
            reverse=True
        )

        return sorted_tickers[:top_n]

    def buy_market_order(self, market: str, price: float) -> dict:
        """시장가 매수 (KRW 기준)"""
        query = {
            'market': market,
            'side': 'bid',
            'price': str(price),
            'ord_type': 'price',  # 시장가 매수
        }
        headers = {"Authorization": f"Bearer {self._create_token(query)}"}
        return requests.post(
            f"{self.BASE_URL}/orders", json=query, headers=headers
        ).json()

    def sell_market_order(self, market: str, volume: float) -> dict:
        """시장가 매도 (수량 기준)"""
        query = {
            'market': market,
            'side': 'ask',
            'volume': str(volume),
            'ord_type': 'market',  # 시장가 매도
        }
        headers = {"Authorization": f"Bearer {self._create_token(query)}"}
        return requests.post(
            f"{self.BASE_URL}/orders", json=query, headers=headers
        ).json()
```

---

## 6. Binance API 연동

### 6.1 Binance 특화 기능

```python
from binance.client import Client as BinanceClient

class BinanceTrader:
    """Binance 거래소 전용 트레이더"""

    def __init__(self, api_key: str, api_secret: str):
        self.client = BinanceClient(api_key, api_secret)

    def get_volatile_pairs(self, quote: str = 'USDT',
                            top_n: int = 10) -> list:
        """변동성 높은 거래쌍 조회"""
        tickers = self.client.get_ticker()
        usdt_tickers = [
            t for t in tickers
            if t['symbol'].endswith(quote)
            and float(t['quoteVolume']) > 1000000  # 최소 거래량 필터
        ]

        sorted_tickers = sorted(
            usdt_tickers,
            key=lambda x: abs(float(x['priceChangePercent'])),
            reverse=True
        )

        return sorted_tickers[:top_n]

    def place_oco_order(self, symbol: str, side: str, quantity: float,
                         price: float, stop_price: float,
                         stop_limit_price: float) -> dict:
        """OCO 주문 (익절 + 손절 동시 설정)"""
        return self.client.create_oco_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=str(price),
            stopPrice=str(stop_price),
            stopLimitPrice=str(stop_limit_price),
            stopLimitTimeInForce='GTC',
        )
```

---

## 7. 백테스팅 프레임워크 (Backtesting Framework)

### 7.1 백테스트 엔진

```python
class BacktestEngine:
    """전략 백테스팅 엔진"""

    def __init__(self, initial_capital: float = 10_000_000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = []
        self.trades = []
        self.equity_curve = []

    def run(self, strategy, data: pd.DataFrame) -> dict:
        """백테스트 실행"""
        for i in range(len(data)):
            current_data = data.iloc[:i+1]
            signal = strategy.generate_signal(current_data)

            if signal == 'BUY' and not self.positions:
                self._open_position(data.iloc[i], 'LONG')
            elif signal == 'SELL' and self.positions:
                self._close_position(data.iloc[i])

            self.equity_curve.append(self._calculate_equity(data.iloc[i]))

        return self._generate_report()

    def _generate_report(self) -> dict:
        """성과 리포트 생성"""
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['pnl'] > 0]

        return {
            'total_return': (self.capital - self.initial_capital)
                            / self.initial_capital * 100,
            'total_trades': total_trades,
            'win_rate': len(winning_trades) / total_trades * 100
                        if total_trades > 0 else 0,
            'max_drawdown': self._calculate_mdd(),
            'sharpe_ratio': self._calculate_sharpe(),
            'avg_profit': np.mean([t['pnl'] for t in winning_trades])
                          if winning_trades else 0,
            'avg_loss': np.mean([t['pnl'] for t in self.trades
                                 if t['pnl'] <= 0]) or 0,
        }
```

### 7.2 백테스트 실행 예시

```python
# 백테스트 실행
engine = BacktestEngine(initial_capital=10_000_000)  # 1천만원

# Upbit BTC/KRW 1시간봉 데이터 로드
data = exchange.get_ohlcv('KRW-BTC', '1h', limit=720)  # 30일

# 볼린저밴드+RSI 전략 테스트
strategy = BollingerRSIStrategy()
result = engine.run(strategy, data)

print(f"총 수익률: {result['total_return']:.2f}%")
print(f"총 거래 횟수: {result['total_trades']}")
print(f"승률: {result['win_rate']:.1f}%")
print(f"최대 낙폭 (MDD): {result['max_drawdown']:.2f}%")
print(f"샤프 비율: {result['sharpe_ratio']:.2f}")
```

---

## 8. 성과 추적 및 개선 사이클 (Performance Tracking)

### 8.1 실시간 대시보드 지표
- 총 자산 및 수익률 (일/주/월)
- 포지션별 미실현 손익
- 전략별 성과 비교
- 거래 체결 히스토리
- 리스크 지표 (MDD, Sharpe, Sortino)

### 8.2 주간 리뷰 프로세스
1. **성과 분석**: 주간 수익률, 승률, 평균 손익비 검토
2. **전략 평가**: 각 전략의 기여도 분석
3. **파라미터 튜닝**: 성과 부진 전략의 파라미터 조정
4. **시장 환경 분석**: 현재 시장이 횡보/상승/하락 중 어느 구간인지
5. **전략 가중치 조정**: 시장 환경에 맞게 전략 비중 변경

### 8.3 월간 개선 사이클
- 새로운 전략 아이디어 백테스트
- 기존 전략 파라미터 최적화 (Grid Search)
- 슬리피지/수수료 반영 정확도 개선
- 비상 정지 기준 재검토

### 8.4 알림 설정

```python
class AlertSystem:
    """텔레그램 기반 알림 시스템"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send_trade_alert(self, trade: dict):
        """거래 체결 알림"""
        message = f"""
{'매수' if trade['side'] == 'BUY' else '매도'} 체결 알림

코인: {trade['symbol']}
가격: {trade['price']:,.0f}원
수량: {trade['amount']:.4f}
전략: {trade['strategy']}
현재 수익률: {trade['total_return']:.2f}%
"""
        await self._send_telegram(message)

    async def send_daily_report(self, report: dict):
        """일일 리포트"""
        message = f"""
일일 리포트 ({report['date']})

총 자산: {report['total_equity']:,.0f}원
일일 수익률: {report['daily_return']:.2f}%
거래 횟수: {report['trade_count']}건
승률: {report['win_rate']:.1f}%
"""
        await self._send_telegram(message)
```

---

## 9. 운영 주의사항

### 9.1 법적 고려사항
- 국내 거래소 (Upbit): 원화 입출금 가능, 특금법 준수
- 해외 거래소 (Binance): 해외 금융계좌 신고 의무 (5,000만원 이상)
- 가상자산 소득세: 250만원 초과 수익 시 22% 과세 (시행 시기 확인 필요)

### 9.2 보안 수칙
- API Key는 환경변수로 관리 (.env 파일)
- API Key 권한: 주문만 허용, 출금 권한 비활성화
- IP 화이트리스트 설정
- 2FA (2단계 인증) 필수 활성화

### 9.3 서버 운영
- 24시간 무중단 운영 (AWS EC2 또는 전용 서버)
- 서버 헬스체크: 5분마다 상태 점검
- 장애 시 즉시 모든 포지션 정리 (안전 모드)
- 일 1회 자동 로그 백업

---

## 10. KPI 및 성과 지표

- **월간 수익률**: 5~15% (목표)
- **최대 낙폭 (MDD)**: -10% 이내
- **승률**: 55% 이상
- **수익/손실 비율**: 1.5:1 이상
- **샤프 비율**: 1.5 이상
- **일 평균 거래 횟수**: 5~20회
- **시스템 가동률**: 99.9% 이상
