# StockBot v3.7 - 노트북 이어서 작업 가이드

## 현재 상태 요약

**StockBot v3.7** — 한국 주식 자동매매 봇, 프로덕션 완성도 높음

- 6대 전략 앙상블 (5전략 Z-score + ML예측 XGBoost)
- **RSI(2) 급락 매수** (RSI2<10 & MA200위, 시간기반 청산)
- **ATR 기반 포지션 사이징** (거래당 자본 2% 리스크)
- **멀티채널 알림** (Telegram + Discord + Email, 우선순위별)
- **포트폴리오 자동 리밸런싱** (단일종목 36%/섹터 55% 초과 시)
- **기관/외국인 수급 데이터** (네이버 금융 크롤링)
- **실시간 호가 WebSocket** 프레임워크 (opt-in)
- 시장 국면(Regime) 자동 감지 + 전략 가중치 적응
- ATR x2 Chandelier Exit 트레일링 스탑
- 대시보드 (FastAPI, http://localhost:8082)
- SQLite DB + 서킷브레이커
- 2025년 1년 백테스트: **+50.25%**, Sharpe 2.69, MDD -8.36%

---

## 설치 및 실행

### 1단계: 패키지 설치

```bash
cd ~/Desktop/biz_life/projects/05-stock-trader
pip install -r requirements.txt
```

### 2단계: 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어서 실제 API 키 입력
```

### 3단계: ML 모델 학습 (선택)

```bash
python ml_train.py
# → trading-bot/models/stock_selector_xgb.pkl 생성
# 모델 없이도 정상 동작 (5전략 앙상블로 폴백)
```

### 4단계: 대시보드 실행

```bash
cd dashboard
python app.py
# → http://localhost:8082
```

### 5단계: 자동매매 (페이퍼 모드)

```bash
cd trading-bot
python trader.py
# 장 시간(09:00~15:30) 자동 매매 사이클 3분 간격
```

---

## v3.7 신규 기능 설정

### 멀티채널 알림
`.env`에 추가:
```env
# Discord (webhook URL만 설정하면 활성화)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Email (SMTP 정보 설정하면 활성화)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=app_password
ALERT_EMAIL_TO=recipient@email.com
```
미설정 채널은 자동 비활성. 기존 Telegram만 사용해도 OK.

### WebSocket 활성화 (선택)
```python
# trader.py 또는 커스텀 스크립트에서:
trader.client.enable_websocket(WATCHLIST)
```
기본은 폴링 모드. API 키 없으면 NotImplementedError (정상).

### ML 모델
```bash
python ml_train.py  # yfinance 2년 데이터로 학습
```
모델 파일이 없으면 5전략 앙상블만 사용 (v3.6과 동일).

---

## 파일 구조

```
05-stock-trader/
├── strategy/
│   └── stock_selector.py         # [v3.7] 6전략 앙상블 (ML + 수급)
├── trading-bot/
│   ├── trader.py                 # [v3.7] StockTrader (리밸런싱)
│   ├── config.py                 # [v3.7] 설정 (Discord/Email)
│   ├── broker_client.py          # [v3.7] API + WebSocket
│   ├── data_provider.py          # [v3.7] yfinance + WS 브릿지
│   ├── risk_manager.py           # [v3.7] 리밸런싱
│   ├── alert_system.py           # [v3.7] 멀티채널 알림
│   ├── websocket_client.py       # [v3.7] WebSocket 프레임워크
│   ├── ml_model.py               # [v3.7] ML 종목 선정
│   └── models/                   # [v3.7] 학습 모델 (.pkl)
├── news/
│   ├── crawler.py                # 뉴스 크롤러
│   └── institutional_crawler.py  # [v3.7] 기관/외국인 수급
├── dashboard/
│   └── app.py                    # [v3.7] 대시보드
├── ml_train.py                   # [v3.7] ML 학습 스크립트
├── .env.example                  # [v3.7] 환경변수 템플릿
├── .gitignore                    # [v3.7] ML 모델 제외
└── requirements.txt              # [v3.7] xgboost, websockets
```

---

## 매매 전략

### 6대 전략 앙상블 (v3.7)

| 전략 | 가중치 | 핵심 지표 |
|------|:------:|----------|
| 평균회귀 | ~22% | RSI, 볼린저밴드 %B |
| 추세추종 | ~20% | MACD, MA 정배열 |
| 한국형 모멘텀 | ~15% | 20/60일 수익률, 폭락가드 |
| 거래량 | ~20% | OBV, 기관/외국인 수급 |
| 변동성 | ~13% | 20/60일 변동성 비율 |
| ML예측 | 15% | XGBoost 22피처 |

**국면별 자동 조정**: 상승장→추세+ML↑, 하락장→평균회귀+변동성↑

### RSI(2) 급락 매수 (v3.6)
- **매수**: RSI(2) < 10 AND 종가 > MA200
- **청산**: RSI(2) > 90 또는 7일 보유
- 앙상블과 독립, 87.5% 승률

---

## 안전 장치

1. **기본 페이퍼 모드**: `TRADING_MODE=paper`
2. **이중 확인**: live 전환에 env 2개 + 콘솔 'CONFIRM'
3. **서킷 브레이커**: 일일 -3%, 연속 5패, 일 20거래
4. **자동 리밸런싱**: 단일종목 36%/섹터 55% 초과 시 축소 (v3.7)
5. **폭락 가드**: 20일 -25% 하락 종목 매수 차단
6. **멀티채널 알림**: CRITICAL → 전 채널 동시 발송 (v3.7)

---

## 데이터 흐름

```
[yfinance / mojito API / WebSocket(opt-in)]
        ↓
  DataProvider (2.5분 캐시 / WS 즉시 업데이트)
        ↓
  BrokerClient (WS 0순위 → mojito → yfinance)
        ↓
  StockSelectorEnsemble (6전략 앙상블)
  + InstitutionalCrawler (기관/외국인 수급)
  + MLStockPredictor (XGBoost 22피처)
  + RSI(2) 급락 감지
        ↓
  RegimeDetector → 가중치 조정
        ↓
  StockTrader.run_cycle()
    1. 청산 (손절/익절/트레일링)
    2. 퀀트 매도
    2.5. 리밸런싱 (단일종목/섹터)
    3. 앙상블 매수
    4. RSI(2) 급락매수
        ↓
  ExecutionEngine + RiskManager + CircuitBreaker
        ↓
  TradeDB (SQLite) + AlertSystem (Telegram/Discord/Email)
```

---

## 향후 과제

- [ ] 한국투자증권 실전 API 키 발급 및 연동
- [ ] Paper Trading 2주 이상 실전 검증
- [ ] ML 모델 정기 재학습 파이프라인
- [ ] 대시보드에 수급/ML 서브스코어 표시

---

## 트러블슈팅

| 증상 | 해결 |
|------|------|
| `ModuleNotFoundError: mojito` | `pip install mojito2` |
| `ModuleNotFoundError: xgboost` | `pip install xgboost scikit-learn joblib` |
| ML 모델 없음 경고 | 정상. `python ml_train.py`로 학습 또는 5전략으로 동작 |
| Discord 알림 안 옴 | `.env`에 `DISCORD_WEBHOOK_URL` 확인 |
| WebSocket 연결 실패 | API 키 필요. 기본 폴링 모드로 정상 동작 |
| 수급 데이터 없음 | 네이버 금융 접속 불가 시 OBV 폴백 (정상) |
| 매수 안 됨 | 점수 58점 미달, 서킷브레이커, 현금 부족 확인 |
