# StockBot v3.8 - 완전 가이드

## 현재 상태 요약

**StockBot v3.8** — 한국 주식 자동매매 봇, 논문 기반 전략 + 실전 안전성 강화

- **6대 전략 앙상블** (5전략 Z-score + ML예측) + **Piotroski F-Score 필터**
- **펀더멘털 분석기 v2.0** (F-Score 9항목, GP/A, PER/PBR/ROE 섹터 상대평가)
- **에러 추적기** (연속 실패 감지 → 자동 매매 중단 + 알림)
- **주문 체결 확인** (ACK polling, 부분 체결 추적)
- **포지션 동기화 검증** (API vs DB 불일치 감지)
- **일일 DB 백업** (7일 보관, 장 시작 전 자동)
- **QA 검증 35/35 통과** (중복주문, 서킷브레이커, 엣지케이스 등)
- RSI(2) 급락 매수 (RSI2<10 & MA200위, 시간기반 청산)
- ATR 기반 포지션 사이징 (거래당 자본 2% 리스크)
- 멀티채널 알림 (Telegram + Discord + Email, 우선순위별)
- 포트폴리오 자동 리밸런싱 (단일종목 36%/섹터 55% 초과 시)
- 기관/외국인 수급 데이터 (네이버 금융 크롤링)
- 시장 국면(Regime) 자동 감지 + 전략 가중치 적응
- ATR x2 Chandelier Exit 트레일링 스탑
- 대시보드 (FastAPI, http://localhost:8082)
- SQLite DB + 서킷브레이커 (일일 주문 금액 한도)
- **2025년 백테스트: +75.35%, Sharpe 3.47, MDD -8.05% (200만원 기준)**

---

## 설치 및 실행 (다운받으면 바로 사용)

### 1단계: 패키지 설치

```bash
cd ~/Desktop/biz_life/projects/05-stock-trader
pip install -r requirements.txt
```

### 2단계: 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어서 아래 항목 입력:
```

```env
# === 필수: 한국투자증권 API ===
KIS_APP_KEY=발급받은_APP_KEY
KIS_APP_SECRET=발급받은_APP_SECRET
KIS_ACCOUNT_NO=계좌번호-01
KIS_IS_PAPER=true           # true=모의투자, false=실전

# === 매매 모드 (기본: 안전한 페이퍼) ===
TRADING_MODE=paper           # paper 또는 live
LIVE_TRADING_CONFIRMED=false # live일 때 이것도 true여야 실전 매매
INITIAL_CAPITAL=2000000      # 초기 자본 (원)

# === 알림 (선택, 설정한 것만 활성화) ===
TELEGRAM_BOT_TOKEN=텔레그램_봇_토큰
TELEGRAM_CHAT_ID=텔레그램_채팅_ID
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### 3단계: 백테스트로 성능 확인

```bash
# v3.8 전략 조합별 비교 백테스트
python v38_backtest.py

# QA 검증 테스트 (35개 안전성 테스트)
python qa_test.py
```

### 4단계: 페이퍼 트레이딩 시작

```bash
cd trading-bot
python trader.py
# → 장 시간(09:00~15:30) 자동 매매, 3분 간격 사이클
# → API 키 없어도 yfinance 데이터로 시뮬레이션 가능
```

### 5단계: 대시보드 (선택)

```bash
cd dashboard
python app.py
# → http://localhost:8082
```

---

## v3.8 핵심 변경사항 (논문 기반)

### 백테스트 검증 결과

| 설정 | 수익률 | Sharpe | MDD | 승률 |
|------|--------|--------|-----|------|
| **v3.8 기술적앙상블+F-Score필터** | **+75.35%** | **3.47** | -8.05% | 55.9% |
| v3.8 펀더멘털 가중치 10% | +45.11% | 2.36 | -13.82% | 45.5% |
| v3.8 + Half-Kelly | +28.47% | 2.34 | -6.79% | 49.1% |

**핵심 발견**: 펀더멘털은 "가중치"가 아니라 "필터"로 쓸 때 최적
- 기술적 앙상블 가중치는 v3.7 그대로 유지
- F-Score<4 종목만 매수 차단 (Piotroski 2000 논문)
- 이 조합이 수익률과 Sharpe 모두 최고

### 적용된 논문/전략

| 논문 | 적용 방식 |
|------|----------|
| **Piotroski F-Score (2000)** | 9항목 퀄리티 체크 → F-Score<4 매수 차단 |
| **Novy-Marx GP/A (2013)** | 영업이익률 기반 수익 퀄리티 분석 |
| **Park et al. (2024) 한국 반전효과** | 한국형 모멘텀에 이미 반영 (reversal 60%) |
| **Asness Value+Momentum (2013)** | 가치+모멘텀 앙상블 결합 (자연 헤지) |
| **Carver ATR 사이징** | ATR 기반 포지션 사이징 (거래당 2% 리스크) |

### 미적용 (한국 시장에서 비효과적)

- 전통적 12개월 모멘텀 (Jegadeesh-Titman) — 한국에서 실패 확인
- Fama-French RMW/CMA — 한국에서 단독 효과 미약
- Full Kelly 사이징 — 수익률 과도 하락 (백테스트 확인)

---

## 파일 구조

```
05-stock-trader/
├── strategy/
│   ├── stock_selector.py            # [v3.8] 6전략 앙상블 + F-Score 필터
│   ├── fundamental_analyzer.py      # [v3.8 신규] 펀더멘털 v2.0 (F-Score, GP/A)
│   ├── base_strategy.py             # 전략 ABC
│   └── backtester.py                # 전략 백테스터
├── trading-bot/
│   ├── trader.py                    # [v3.8] 메인 트레이더 (에러추적, DB백업, 포지션검증)
│   ├── config.py                    # [v3.8] 설정 (주문 금액 한도 추가)
│   ├── broker_client.py             # [v3.8] API + 체결확인 + 부분체결
│   ├── error_tracker.py             # [v3.8 신규] 에러 추적 및 연속 실패 감지
│   ├── circuit_breaker.py           # [v3.8] 서킷브레이커 (주문금액한도, 트립이력)
│   ├── risk_manager.py              # [v3.7] 포트폴리오 리스크
│   ├── alert_system.py              # [v3.7] 멀티채널 알림
│   ├── execution_engine.py          # [v3.7] 스마트 주문 (TWAP/VWAP)
│   ├── data_provider.py             # [v3.7] yfinance 데이터
│   ├── database.py                  # DB 영속성
│   ├── scheduler.py                 # 장 시간 스케줄러
│   ├── regime_detector.py           # 시장 국면 감지
│   ├── websocket_client.py          # WebSocket (opt-in)
│   ├── ml_model.py                  # ML 종목 선정 (XGBoost)
│   └── models/                      # 학습 모델 (.pkl)
├── news/
│   ├── crawler.py                   # 뉴스 크롤러
│   └── institutional_crawler.py     # 기관/외국인 수급
├── dashboard/
│   └── app.py                       # 대시보드 (FastAPI)
├── v38_backtest.py                  # [v3.8 신규] 8가지 전략 조합 백테스트
├── qa_test.py                       # [v3.8 신규] 35개 QA 검증 테스트
├── v37_backtest.py                  # v3.7 백테스트
├── full_year_backtest.py            # 2025년 전체 백테스트
├── requirements.txt                 # 의존성 패키지
├── .env.example                     # 환경변수 템플릿
└── HANDOFF.md                       # 이 파일
```

---

## 매매 전략

### 6대 전략 앙상블 (가중치 = 국면별 자동 조정)

| 전략 | BULL | BEAR | SIDEWAYS | 핵심 지표 |
|------|:----:|:----:|:--------:|----------|
| 추세추종 | 25% | 13% | 17% | MACD tanh, MA 정배열 |
| 평균회귀 | 13% | 25% | 22% | RSI Z-score, 볼린저밴드 |
| 한국형모멘텀 | 17% | 8% | 12% | 20일 반전, 60일 모멘텀, 폭락가드 |
| 거래량 | 17% | 17% | 22% | OBV, 기관/외국인 수급 |
| 변동성 | 13% | 22% | 12% | 20/60일 변동성 비율 |
| ML예측 | 15% | 15% | 15% | XGBoost 22피처 (없으면 자동 제외) |

### Piotroski F-Score 필터 (v3.8)
- 9항목 바이너리 체크: ROA양수, CFO양수, ROA개선, 어크루얼, 부채감소, 유동비율, 희석없음, 마진개선, 회전율개선
- **F-Score < 4 → 매수 차단** (퀄리티 필터)
- 경고 3개 이상 → 추가 차단 (적자, 고부채, PER과도 등)

### RSI(2) 급락 매수
- **매수**: RSI(2) < 10 AND 종가 > MA200
- **청산**: RSI(2) > 90 또는 7일 보유 또는 -5% 손절
- 2025년 백테스트 승률: 88.9%

---

## 안전 장치 (7중 방어)

1. **기본 페이퍼 모드**: `TRADING_MODE=paper` (기본값)
2. **이중 확인**: live 전환에 env 2개 + 콘솔 'CONFIRM' 입력
3. **서킷 브레이커**: 일일 -3%, 연속 5패, 일 20거래, **일일 주문 금액 한도(자본x2)**
4. **에러 추적기**: API 연속 실패 → 자동 매매 중단 + 즉시 알림
5. **F-Score 필터**: 퀄리티 낮은 종목 매수 원천 차단
6. **주문 체결 확인**: 실전 주문 후 30초 polling, 부분 체결 추적
7. **포지션 동기화**: 매일 장 전 API vs DB 비교, 불일치 시 알림

---

## 데이터 흐름

```
[yfinance / mojito API / WebSocket(opt-in)]
        |
  DataProvider (2.5분 캐시)
        |
  BrokerClient (WS → mojito → yfinance 폴백)
        |
  +-- StockSelectorEnsemble (6전략 앙상블)
  +-- FundamentalAnalyzer (F-Score 필터)    ← v3.8
  +-- InstitutionalCrawler (기관/외국인)
  +-- MLStockPredictor (XGBoost)
  +-- RSI(2) 급락 감지
        |
  RegimeDetector → 가중치 조정
        |
  StockTrader.run_cycle()
    0. 에러 추적기 체크 (halt 여부)          ← v3.8
    1. 청산 (손절/익절/트레일링)
    2. 퀀트 매도
    2.5. 리밸런싱 (단일종목/섹터)
    3. 앙상블 매수 (F-Score<4 차단)          ← v3.8
    4. RSI(2) 급락매수
        |
  ExecutionEngine (TWAP/VWAP/시장가)
  + 체결 확인 polling                        ← v3.8
  + RiskManager + CircuitBreaker
        |
  TradeDB (SQLite, 일일 자동 백업)           ← v3.8
  + AlertSystem (Telegram/Discord/Email)
  + ErrorTracker (연속 실패 감지)             ← v3.8
```

---

## QA 검증 현황

35개 테스트 전체 통과 (`python qa_test.py`):

| 카테고리 | 항목 | 결과 |
|----------|------|------|
| 중복 주문 방지 | 3건 | PASS |
| 잔고/수량 방어 | 2건 | PASS |
| 서킷브레이커 | 4건 | PASS |
| 미보유 매도 방어 | 2건 | PASS |
| 리스크 매니저 | 3건 | PASS |
| 펀더멘털 필터 | 5건 | PASS |
| 에러 추적기 | 3건 | PASS |
| 레이스 조건 | 2건 | PASS |
| 가격 엣지 케이스 | 2건 | PASS |
| 주문 체결 확인 | 3건 | PASS |
| DB 안전성 | 2건 | PASS |
| 실행 엔진 | 3건 | PASS |
| F-Score 통합 | 1건 | PASS |

---

## 향후 과제

- [ ] 한국투자증권 실전 API 키 연동 (`pip install mojito2` → `.env` 설정)
- [ ] Paper Trading 2주 이상 실전 데이터 검증
- [ ] ML 모델 정기 재학습 파이프라인
- [ ] 대시보드에 F-Score/펀더멘털 점수 표시
- [ ] HMM 기반 시장 국면 감지 업그레이드 (hmmlearn)

---

## 트러블슈팅

| 증상 | 해결 |
|------|------|
| `ModuleNotFoundError: mojito` | `pip install mojito2` |
| `ModuleNotFoundError: xgboost` | `pip install xgboost scikit-learn joblib` |
| ML 모델 없음 경고 | 정상. 5전략 앙상블로 자동 폴백 |
| 펀더멘털 데이터 없음 | yfinance 접속 불가 시 F-Score 필터 비활성 (정상 동작) |
| Discord 알림 안 옴 | `.env`에 `DISCORD_WEBHOOK_URL` 확인 |
| 에러 추적기 알림 폭주 | 1시간 내 동일 카테고리 중복 알림 자동 차단됨 |
| 매수 안 됨 | 점수 58점 미달, F-Score<4, 서킷브레이커, 현금 부족 확인 |
| 포지션 불일치 경고 | 장 전 API vs DB 비교 결과. 수동 매매 했으면 정상 |
