# StockBot v3.7 - 프로젝트 현황

## 개요
한국 주식 자동매매 봇. **6대 전략 앙상블** (5전략 Z-score + ML예측) + **RSI(2) 급락 매수** + ATR 포지션 사이징 + 시장 국면 감지 + 서킷브레이커 + SQLite DB.
한국투자증권 API(mojito SDK) 연동, **멀티채널 알림** (Telegram/Discord/Email), 장 시간 자동 스케줄러.
yfinance 실시간 데이터 + 200만원 소규모 자본 최적화.

---

## 버전 이력

### v3.7 (2026-03-05) — 현재 버전
- **멀티채널 알림**: Telegram + Discord + Email 어댑터 패턴
  - AlertPriority enum: CRITICAL(전체), HIGH(Telegram+Discord), NORMAL(Telegram), LOW(Email+Telegram)
  - 기존 메서드 시그니처 100% 호환
  - env 미설정 채널 자동 비활성
- **포트폴리오 자동 리밸런싱**: execute_trades() 내 2.5단계
  - 단일종목 36% 초과 → 30%까지 초과분 매도
  - 섹터 55% 초과 → 50%까지 최대종목 축소
  - REBALANCE 액션으로 DB/알림 기록 (부분매도, 포지션 삭제 안 함)
- **기관/외국인 실제 수급 데이터**: 네이버 금융 크롤링
  - 20일 데이터, 10분 TTL 캐시, 0.3초 rate limiting
  - 5일/20일 외국인+기관 순매수 트렌드 기반 스코어링
  - 실패 시 기존 OBV 로직 폴백
- **실시간 호가 WebSocket 프레임워크**: opt-in 방식
  - asyncio + threading 별도 스레드 이벤트 루프
  - 자동 재연결 (exponential backoff, max 10회)
  - 30초 하트비트, 종목별 TickData deque 버퍼
  - KIS WebSocket 서브클래스 (API 키 필요)
- **ML 기반 종목 선정**: XGBoost 22피처 6번째 전략
  - Walk-forward validation (train 9개월, test 1개월)
  - 모델 없으면 50점(중립) → 5전략 가중치 재정규화
  - REGIME_WEIGHTS에 "ML예측": 0.15 추가

### v3.6 (2026-03-04)
- **RSI(2) 급락 매수 추가**: 앙상블과 독립적으로 작동하는 평균회귀 매수 신호
  - 매수 조건: RSI(2) < 10 AND 종가 > MA200
  - 청산: RSI(2) > 90 또는 7일 보유 후 시간기반 청산
  - 백테스트: +47.47% → **+50.25%** (+2.78%p), Sharpe 2.49 → 2.69
  - RSI(2) 거래 승률 87.5%, 순기여 +1,263,194원
- **코드 안정성 강화**: 개별 거래 try-except, ATR qty=0 경고, 2.5분 캐시

### v3.5 (2026-03-04)
- **ATR 기반 포지션 사이징**: 거래당 자본 2% 리스크 기반
  - 백테스트: +34.78% → **+45.98%** (+11.2%p), Sharpe 2.44 → 2.56

### v3.4 (2026-03-03)
- **ATR Chandelier Exit**: ATR x2 변동성 적응 트레일링 스탑

### v3.3 (2026-03-02)
- **뉴스 부스트 완전 제거**: 순수 퀀트가 모든 구간에서 우위
- **1년 풀백테스트 최적 설정 적용**: 익절 15%, 전량 매도

### v3.2 (2026-02-28)
- **Z-score 기반 스코어링 엔진 전면 교체**, 5개 크리티컬 버그 수정, 적응형 임계값

### v3.1 (2026-02-22)
- 5전략 통합 앙상블, 시장 국면 감지

---

## 백테스트 결과 요약

### 2025년 전체 (1~12월, 15종목)

| 순위 | 설정 | 수익률 | Sharpe | MDD | 매매수 | 승률 |
|:---:|------|------:|------:|-----:|------:|-----:|
| 1 | **v3.6 앙상블+RSI2+ATR** | **+50.25%** | **2.69** | **-8.36%** | 74 | 52.1% |
| 2 | v3.5 앙상블+ATR사이징 | +45.98% | 2.56 | -6.34% | 57 | 45.3% |
| 3 | v3.5 앙상블+균등분배 | +34.78% | 2.44 | -5.15% | 57 | 45.3% |

---

## 현재 매매 설정 (200만원 소자본 최적화)

| 항목 | 값 | 설명 |
|------|---|------|
| 최대 포지션 | 4개 | 소자본 집중 투자 |
| 종목당 최대 비중 | 30% | 1종목에 최대 60만원 |
| 섹터당 최대 비중 | 50% | 같은 업종 쏠림 방지 |
| 최소 현금 보유 | 15% | 30만원 이상 현금 유지 |
| **포지션 사이징** | **ATR 기반** | **거래당 자본 2% 리스크** |
| 손절 | -5% | 매수가 기준 자동 매도 |
| 익절 | +15% | 매수가 기준 전량 매도 |
| 트레일링 스탑 | ATR x2 | Chandelier Exit |
| **RSI(2) 급락 매수** | **RSI2<10 & MA200위** | **앙상블과 독립 작동** |
| **리밸런싱** | **자동** | **36%/55% 초과 시 자동 축소** |
| 매수 기준 점수 | 58점 이상 | 적응형 자동 조정 |
| 매매 주기 | 3분 | 자동 분석 사이클 간격 |

---

## 6대 전략 앙상블 (v3.7)

| 전략 | 가중치 | 원리 | 핵심 지표 |
|------|:------:|------|----------|
| 평균회귀 | ~22% | 많이 빠진 건 오르고 많이 오른 건 빠진다 | RSI, 볼린저밴드 %B |
| 추세추종 | ~20% | 오르는 주식은 계속 오른다 | MACD, MA 정배열 |
| 한국형 모멘텀 | ~15% | 급등주 단기 역전 + 폭락 가드 | 20/60일 수익률 |
| 거래량 | ~20% | 거래량은 주가의 연료 (기관/외국인 수급) | OBV, 네이버 수급 |
| 변동성 | ~13% | 변동 축소=안정, 확대=위험 | 20/60일 변동성 비율 |
| **ML예측** | **15%** | **XGBoost 22피처 종합 예측** | **학습 모델 (.pkl)** |

※ ML 모델 미설치 시 5전략 가중치 자동 재정규화 (v3.6과 동일 동작)

---

## 파일 구조

```
05-stock-trader/
├── strategy/
│   ├── stock_selector.py        # [v3.7] 6전략 앙상블 (ML예측 + 수급 하이브리드)
│   ├── base_strategy.py         # StockSignal + BaseStockStrategy ABC
│   ├── bollinger_strategy.py    # 볼린저밴드 %B
│   ├── rsi_strategy.py          # RSI 과매수/과매도
│   ├── macd_strategy.py         # MACD 크로스
│   ├── ma_strategy.py           # 이동평균선 정배열
│   ├── institutional_flow.py    # 기관수급 (OBV 기반)
│   ├── momentum_strategy.py     # 한국형 모멘텀
│   └── backtester.py            # 백테스터
├── trading-bot/
│   ├── trader.py                # [v3.7] StockTrader (리밸런싱 + 멀티알림)
│   ├── config.py                # [v3.7] 설정 (Discord/Email 추가)
│   ├── broker_client.py         # [v3.7] 한투 API + WebSocket + yfinance
│   ├── data_provider.py         # [v3.7] yfinance + WebSocket 브릿지
│   ├── risk_manager.py          # [v3.7] ATR사이징 + 리밸런싱
│   ├── alert_system.py          # [v3.7] 멀티채널 알림 (Telegram/Discord/Email)
│   ├── websocket_client.py      # [v3.7] WebSocket 프레임워크
│   ├── ml_model.py              # [v3.7] ML 종목 선정 (XGBoost)
│   ├── models/                  # [v3.7] 학습된 모델 저장소
│   │   └── .gitkeep
│   ├── execution_engine.py      # 스마트 주문 (TWAP/VWAP/Smart)
│   ├── database.py              # SQLite DB 영속성
│   ├── circuit_breaker.py       # 서킷브레이커
│   └── scheduler.py             # 장 시간 자동 스케줄러
├── dashboard/
│   ├── app.py                   # [v3.7] 대시보드
│   └── ...
├── news/
│   ├── crawler.py               # 네이버 금융 + RSS 크롤링
│   └── institutional_crawler.py # [v3.7] 기관/외국인 수급 크롤러
├── ml_train.py                  # [v3.7] ML 학습 스크립트
├── .env.example                 # [v3.7] 환경변수 (Discord/Email 추가)
├── .gitignore                   # [v3.7] ML 모델 제외
├── requirements.txt             # [v3.7] xgboost, websockets 추가
├── HANDOFF.md
└── PROJECT_STATUS.md            # ← 이 파일
```

---

## 안전 장치
1. **기본값 페이퍼 모드**: `TRADING_MODE=paper`가 디폴트
2. **이중 확인**: live 전환에 env 변수 2개 + 콘솔 CONFIRM 입력 필요
3. **서킷 브레이커**: 일일 -3%, 연속 5패, 일 20거래 초과 시 자동 중단
4. **손절/익절**: -5% 손절, +15% 익절, ATR x2 Chandelier Exit
5. **자동 리밸런싱**: 단일종목 36%/섹터 55% 초과 시 자동 축소 (v3.7)
6. **현금 보유**: 최소 15% 현금 유지
7. **멀티채널 알림**: CRITICAL 이벤트는 전 채널 동시 발송 (v3.7)
8. **폭락 가드**: 20일 -25% 이상 하락 종목 매수 차단
9. **소규모 주문 바이패스**: 5주 이하 직접 시장가 주문

---

## 향후 과제
- [x] ~~모바일 알림 확장 (멀티채널)~~ → v3.7 완료
- [x] ~~포트폴리오 자동 리밸런싱~~ → v3.7 완료
- [x] ~~기관/외국인 실제 수급 데이터~~ → v3.7 완료
- [x] ~~실시간 호가 WebSocket 연동~~ → v3.7 완료
- [x] ~~머신러닝 기반 종목 선정 모델~~ → v3.7 완료
- [ ] 한국투자증권 실전 API 키 발급 및 연동
- [ ] Paper Trading 2주 이상 실전 검증
- [ ] ML 모델 정기 재학습 파이프라인
- [ ] 대시보드에 수급/ML 서브스코어 표시
