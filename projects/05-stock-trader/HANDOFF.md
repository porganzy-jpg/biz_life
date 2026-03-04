# StockBot v3.6 - 노트북 이어서 작업 가이드

## 현재 상태 요약

**StockBot v3.6** — 한국 주식 자동매매 봇, 완성도 높음 (코드 100%, API 연동만 남음)

- 5대 퀀트 전략 앙상블 (Z-score + tanh 스코어링)
- **RSI(2) 급락 매수** (RSI2<10 & MA200위, 시간기반 청산, v3.6)
- **ATR 기반 포지션 사이징** (거래당 자본 2% 리스크, v3.5)
- 시장 국면(Regime) 자동 감지 + 전략 가중치 적응
- ATR x2 Chandelier Exit 트레일링 스탑 (v3.4)
- 서킷브레이커, 손절/익절 자동화
- 대시보드 (FastAPI, http://localhost:8082)
- SQLite DB, Telegram 알림
- 2025년 1년 백테스트: **+50.25%**, Sharpe 2.69, MDD -8.36%

---

## 남은 작업: KIS API 연동

### 1단계: 패키지 설치

```bash
cd ~/Desktop/biz_life/projects/05-stock-trader
pip install mojito2 yfinance pandas numpy ta python-dotenv fastapi uvicorn jinja2 aiohttp beautifulsoup4 feedparser schedule
```

### 2단계: .env 파일 생성

```bash
cp .env.example .env
```

`.env` 파일을 열어서 실제 값 입력:

```env
# === 한국투자증권 API ===
KIS_APP_KEY=발급받은_APP_KEY
KIS_APP_SECRET=발급받은_APP_SECRET
KIS_ACCOUNT_NO=계좌번호-01    # 예: 12345678-01
KIS_IS_PAPER=true              # 모의투자: true, 실전: false

# === 트레이딩 모드 (이중 안전장치) ===
TRADING_MODE=paper             # 반드시 paper로 시작!
LIVE_TRADING_CONFIRMED=false   # 실전 전환 시에만 true

# === 초기 자본 (원) ===
INITIAL_CAPITAL=2000000        # 200만원 (자본에 따라 설정 자동 조정)

# === Telegram 알림 (선택) ===
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

> **보안 주의**: `.env`는 `.gitignore`에 등록되어 있어 Git에 올라가지 않음. 안전합니다.

### 3단계: API 연결 테스트

```bash
cd trading-bot
python -c "
from broker_client import BrokerClient
client = BrokerClient(paper_trading=True)
print('연결 상태:', '성공' if client.broker else 'yfinance 전용 모드')
if client.broker:
    balance = client.get_balance()
    print('잔고:', balance)
    price = client.fetch_price('005930')
    print('삼성전자 현재가:', price)
"
```

### 4단계: 대시보드 실행

```bash
cd dashboard
python app.py
# → http://localhost:8082 접속
```

### 5단계: 자동매매 실행 (페이퍼 모드)

```bash
cd trading-bot
python trader.py
# 장 시간(09:00~15:30) 자동 매매 사이클 3분 간격
```

---

## 프로젝트 파일 구조

```
05-stock-trader/
├── strategy/                          # 퀀트 전략
│   ├── stock_selector.py              # [핵심] Z-score 앙상블 + 적응형 임계값
│   ├── base_strategy.py               # StockSignal + BaseStockStrategy ABC
│   ├── bollinger_strategy.py          # 볼린저밴드 %B (평균회귀)
│   ├── rsi_strategy.py                # RSI 과매수/과매도 (평균회귀)
│   ├── macd_strategy.py               # MACD 크로스 (추세추종)
│   ├── ma_strategy.py                 # 이동평균선 정배열 (추세추종)
│   ├── institutional_flow.py          # 기관수급 OBV (거래량)
│   ├── momentum_strategy.py           # 한국형 모멘텀 + 폭락가드
│   ├── dual_momentum.py               # 듀얼 모멘텀
│   ├── volatility_target.py           # 변동성 타겟팅
│   └── backtester.py                  # 백테스터
│
├── trading-bot/                       # 매매 실행
│   ├── trader.py                      # [핵심] StockTrader (RSI2 급락매수 + 앙상블)
│   ├── config.py                      # 설정 (자본별 자동 조정)
│   ├── broker_client.py               # 한투 API + yfinance 폴백
│   ├── data_provider.py               # yfinance 데이터 + 2.5분 TTL 캐시
│   ├── risk_manager.py                # ATR 포지션사이징, 섹터한도, 리밸런싱
│   ├── execution_engine.py            # TWAP/VWAP/Smart 주문 + 슬리피지 제어
│   ├── database.py                    # SQLite 거래/포지션/일일 기록
│   ├── circuit_breaker.py             # 일일-3%, 연속5패, 일20거래 차단
│   ├── alert_system.py                # Telegram 알림
│   ├── scheduler.py                   # 장시간 자동 스케줄러
│   ├── stock_analyzer.py              # 퀀트 분석기
│   └── volume_profile.py              # 거래량 프로필 (VWAP용)
│
├── dashboard/                         # 웹 대시보드
│   ├── app.py                         # FastAPI 대시보드 (포트 8082, RSI2 컬럼)
│   ├── backtest_portal.py             # 백테스트 포탈
│   ├── regime_detector.py             # 대시보드용 국면 감지
│   └── correlation_monitor.py         # 상관관계 모니터
│
├── news/                              # 뉴스 (v3.3에서 미사용)
│   ├── crawler.py                     # 네이버 금융 + RSS 크롤링
│   └── sentiment.py                   # 감성 분석 (제거됨)
│
├── strategy_lab.py                    # [v3.5] 3차원 전략 탐색 (31개 조합)
├── rsi2_crash_test.py                 # [v3.6] RSI(2) 급락매수 효과 검증
├── full_year_backtest.py              # 2025년 12설정 비교 테스트
├── news_boost_test.py                 # 뉴스 부스트 유/무 비교
├── v32_comparison_test.py             # v3.1 vs v3.2 비교
├── weekly_simulation.py               # 주간 시뮬레이션
├── strategy_comparison_test.py        # 전략 비교 테스트
├── .env.example                       # 환경변수 템플릿
├── .env                               # 실제 API 키 (Git 제외)
├── requirements.txt                   # 패키지 목록
├── stockbot.db                        # SQLite 거래 DB
├── HANDOFF.md                         # ← 이 파일
└── PROJECT_STATUS.md                  # 상세 프로젝트 현황
```

---

## 매매 전략

### 5대 전략 앙상블

| 전략 | 가중치 | 핵심 지표 |
|------|:------:|----------|
| 평균회귀 | 25% | RSI, 볼린저밴드 %B |
| 추세추종 | 20% | MACD, MA 정배열 |
| 한국형 모멘텀 | 20% | 20/60일 수익률, 폭락가드 |
| 거래량 | 20% | OBV, 거래량 비율 |
| 변동성 | 15% | 20/60일 변동성 비율 |

**국면별 자동 조정**: 상승장→추세↑, 하락장→평균회귀↑, 횡보장→거래량↑

**스코어링**: Z-score → tanh(0~100점) → 5전략 가중평균 → 적응형 임계값(75th/25th)

### RSI(2) 급락 매수 (v3.6)

- **매수**: RSI(2) < 10 AND 종가 > MA200 (극단적 과매도 + 장기 상승추세)
- **청산**: RSI(2) > 90 또는 7일 보유 후 시간기반 청산
- 앙상블과 독립적으로 작동 (별도 진입/청산 로직)
- DB에 entry_source 저장 → 포지션별 구분 청산
- 백테스트 승률 87.5%, PF 6.50

---

## 매매 설정 (200만원 소자본)

| 항목 | 값 |
|------|---|
| 최대 포지션 | 4개 |
| 종목당 최대 | 30% (60만원) |
| 섹터당 최대 | 50% |
| 현금 보유 | 최소 15% |
| **포지션 사이징** | **ATR 기반 (거래당 2% 리스크)** |
| 손절 | -5% |
| 익절 | +15% (전량 매도) |
| 트레일링 스탑 | ATR x2 Chandelier Exit |
| **RSI(2) 급락매수** | **RSI2<10 & MA200위 (v3.6)** |
| 매수 기준 | 58점+ (적응형 자동 조정) |
| 매매 주기 | 3분 |

---

## 안전 장치

1. **기본 페이퍼 모드**: `TRADING_MODE=paper`가 디폴트
2. **이중 확인**: live 전환에 env 변수 2개 + 콘솔 'CONFIRM' 입력
3. **서킷 브레이커**: 일일 -3%, 연속 5패, 일 20거래 시 자동 중단
4. **폭락 가드**: 20일 -25% 하락 종목 매수 차단
5. **소규모 주문 바이패스**: 5주 이하 시장가 직접 (TWAP 분할 안 함)
6. **개별 거래 예외 격리**: 1종목 오류 시 나머지 정상 실행 (v3.6)

---

## 데이터 흐름

```
[yfinance / mojito API]
        ↓
  DataProvider (2.5분 캐시)
        ↓
  BrokerClient (mojito 우선 → yfinance 폴백)
        ↓
  StockSelectorEnsemble (5전략 Z-score 앙상블)
  + RSI(2) 급락 감지 (v3.6)
        ↓
  RegimeDetector (국면 감지 → 가중치 조정)
        ↓
  StockTrader.run_cycle() (스캔 → 앙상블매수 → RSI2매수 → 매매실행)
        ↓
  ExecutionEngine (TWAP/VWAP/Smart + 슬리피지 제어)
        ↓
  RiskManager + CircuitBreaker (안전 장치)
        ↓
  TradeDB (SQLite 기록) + AlertSystem (Telegram)
```

---

## KIS API 참고

- **mojito2 SDK 사용** (`pip install mojito2`, `import mojito`)
- 모의투자 API와 실전투자 API 키가 다름 (별도 발급)
- `broker_client.py`에서 `mojito.KoreaInvestment(mock=True/False)`로 모드 전환
- API 키가 없으면 자동으로 yfinance 전용 시뮬레이션 모드로 동작
- 모의투자 API 제약: 일부 종목/시간대에 호가 조회 불가할 수 있음

---

## 실전 전환 체크리스트 (2주 이상 페이퍼 검증 후)

- [ ] 페이퍼 모드 2주+ 정상 동작 확인
- [ ] 백테스트 대비 실제 성과 비교
- [ ] 실전투자 API 키 발급 (한투 홈페이지)
- [ ] `.env` 수정:
  ```
  KIS_IS_PAPER=false
  TRADING_MODE=live
  LIVE_TRADING_CONFIRMED=true
  ```
- [ ] 콘솔에서 'CONFIRM' 입력
- [ ] Telegram 알림 설정 (실시간 모니터링)

---

## 향후 과제

- [ ] 실시간 호가 WebSocket 연동
- [ ] 기관/외국인 실제 수급 데이터
- [ ] 포트폴리오 자동 리밸런싱
- [ ] 머신러닝 종목 선정 모델
- [ ] 모바일 알림 확장

---

## 트러블슈팅

| 증상 | 해결 |
|------|------|
| `ModuleNotFoundError: mojito` | `pip install mojito2` |
| mojito 연결 실패 | API 키 확인, 모의투자/실전 키 구분 확인 |
| yfinance 데이터 없음 | 종목코드 확인 (.KS 자동 붙음), 네트워크 확인 |
| 대시보드 404 | `cd dashboard && python app.py` (reload=False 기본) |
| 매수 안 됨 | 점수 58점 미달, RSI2>10, 현금 부족, 서킷브레이커 확인 |
| `sys.path` 에러 | trader.py가 strategy/ 경로를 자동 추가함, 실행 위치 확인 |
