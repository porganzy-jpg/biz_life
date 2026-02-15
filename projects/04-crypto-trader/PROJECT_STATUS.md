# CryptoBot - 프로젝트 현황

**최종 업데이트**: 2026-02-16

## 개요
암호화폐 자동매매 스캘핑 봇. 4가지 전략의 앙상블 가중 투표로 매매 신호를 생성하고, ATR 기반 리스크 관리 + 서킷브레이커 + WebSocket 실시간 대시보드를 통합한 트레이딩 엔진. v4.0에서 동적 마켓 스캐너와 Walk-Forward 적응형 최적화를 추가.

## 기술 스택
- **Backend**: Python 3.13, FastAPI
- **거래소 연동**: pyupbit (업비트 REST API)
- **기술적 분석**: pandas, numpy, ta
- **대시보드**: FastAPI + 인라인 HTML/JS (TradingView lightweight-charts)
- **실시간 통신**: WebSocket (자동 재연결 + HTTP 폴백)
- **외부 접근**: Cloudflare Tunnel

## 실행 방법
```bash
cd projects/04-crypto-trader

# v4.0 전체 (봇 + 대시보드 + 스캐너 + 옵티마이저)
python -m scalper.run --with-dashboard
# → http://localhost:8081 (WS: ws://localhost:8081/ws)

# v3.0 호환 (스캐너/옵티마이저 비활성)
python -m scalper.run --with-dashboard --no-scanner --no-optimizer

# 대시보드만 (봇 별도 시작)
python -m scalper.run --dashboard

# 봇만 (대시보드 없이)
python -m scalper.run

# 백테스트 (스캐너/옵티마이저 자동 비활성)
python -m scalper.run --backtest

# 24/7 자동 실행 (Windows)
start_bot.bat
```

## 핵심 파일 구조
```
04-crypto-trader/
├── scalper/                        # 핵심 스캘핑 엔진 (v4.0)
│   ├── __init__.py
│   ├── config.py                   # 전체 설정 (3분봉, ATR, SL/TP, 스캐너, 옵티마이저)
│   ├── trader.py                   # ScalpTrader (메인 루프 + Scanner/Optimizer 통합)
│   ├── market_scanner.py           # 동적 마켓 스캐너 (v4.0 신규)
│   ├── optimizer.py                # Walk-Forward 최적화 + ParamProfile (v4.0 신규)
│   ├── dashboard.py                # FastAPI 대시보드 + WebSocket
│   ├── run.py                      # CLI 진입점 (--no-scanner, --no-optimizer)
│   ├── backtester.py               # 백테스터 (ParamProfile 지원)
│   ├── risk_manager.py             # ATR 기반 리스크 관리
│   ├── circuit_breaker.py          # 서킷브레이커
│   ├── upbit_client.py             # 업비트 API 클라이언트
│   ├── alert_system.py             # 텔레그램/콘솔 알림
│   └── strategies/                 # 4가지 매매 전략
│       ├── base.py                 # 전략 공통 인터페이스
│       ├── rsi_bb_scalp.py         # RSI + 볼린저밴드
│       ├── vwap_volume.py          # VWAP + 거래량
│       ├── stochastic_rsi.py       # 스토캐스틱 RSI
│       ├── ema_crossover.py        # EMA 크로스오버
│       └── ensemble.py             # 앙상블 투표 시스템
├── start_bot.bat                   # 24/7 자동 실행 스크립트
├── monitor.py                      # 실시간 모니터링
├── strategy/                       # 레거시 전략 모듈
├── trading-bot/                    # 레거시 트레이더
├── dashboard/                      # 레거시 대시보드
└── docs/PROJECT_PLAN.md
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 대시보드 UI (SPA) |
| GET | `/api/status` | 봇 상태 (잔고, 매매수, 승률, **활성 마켓, 옵티마이저**) |
| GET | `/api/market-watch` | 동적 마켓 실시간 분석 |
| GET | `/api/trades/history` | 매매 이력 (필터, 페이지네이션) |
| GET | `/api/trades/stats` | 기간별 성과 통계 |
| GET | `/api/runtime` | 런타임 정보 (**스캐너/옵티마이저 상태 포함**) |
| POST | `/api/bot/start` | 봇 시작 |
| POST | `/api/bot/stop` | 봇 정지 |
| POST | `/api/bot/halt` | 수동 서킷브레이커 |
| POST | `/api/bot/resume` | 서킷브레이커 해제 |
| **WS** | **`/ws`** | **WebSocket 실시간 스트리밍** |

---

## v4.0 동적 마켓 스캐너 (2026-02-16)

### 개요
고정 3개 마켓(BTC, ETH, XRP) 대신 **거래량 상위 5개 KRW 마켓을 1시간마다 자동 선택**.

### 설정

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| `DYNAMIC_MARKETS_ENABLED` | True | 스캐너 활성화 |
| `SCANNER_TOP_N` | 5 | 상위 5개 마켓 |
| `SCANNER_INTERVAL_SEC` | 3600 | 1시간 주기 |
| `SCANNER_MIN_VOLUME_KRW` | 10억 | 최소 24h 거래대금 |

### 동작
1. `pyupbit.get_tickers(fiat="KRW")`로 전체 KRW 마켓 조회
2. 각 ticker의 24h 거래대금 확인 (0.1초 rate limit)
3. 10억 KRW 이상 중 Top 5 선택
4. 오픈 포지션 마켓은 항상 보존 (교체 중 청산 보장)

### 테스트 결과 (실제 데이터)
```
Top 5: KRW-XRP(993B), KRW-ETH(240B), KRW-BTC(187B), KRW-DOGE(96B), KRW-SOL(76B)
```

---

## v4.0 Walk-Forward 최적화 (2026-02-16)

### 개요
2시간마다 과거 3일 데이터로 **12개 파라미터 조합을 백테스트**, 최고 성과 설정을 런타임에 자동 적용.

### 설정

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| `OPTIMIZER_ENABLED` | True | 옵티마이저 활성화 |
| `OPTIMIZER_INTERVAL_SEC` | 7200 | 2시간 주기 |
| `OPTIMIZER_LOOKBACK_DAYS` | 3 | 과거 3일 데이터 |
| `OPTIMIZER_N_PROFILES` | 12 | 테스트할 프로필 수 |
| `OPTIMIZER_MARKETS` | BTC, ETH | 최적화 대상 (속도) |

### ParamProfile 최적화 범위

| 파라미터 | 범위 | 설명 |
|---------|------|------|
| `min_ensemble_confidence` | 0.25 ~ 0.50 | 앙상블 문턱 |
| `risk_per_trade` | 0.5% ~ 2.0% | 거래당 리스크 |
| `stop_loss_hard_cap` | 0.4% ~ 1.2% | SL 하드캡 |
| `take_profit_pct` | 0.5% ~ 1.5% | TP 비율 |
| `trailing_activate_pct` | 0.2% ~ 0.8% | 트레일링 활성 |
| `trailing_stop_pct` | 0.1% ~ 0.4% | 트레일링 추적 |
| `weights` | Dirichlet(2,2,2,2) | 전략 가중치 |

### 스코어링
```
score = PF×0.4 + WR×0.3 - DD×0.3
```

---

## 4개 전략 앙상블 (스캘퍼 v3.0)

| 전략 | 기본 가중치 | 설명 |
|------|:-:|------|
| RSI + Bollinger Band | 30% | BB%B + RSI 과매수/과매도 반등 |
| VWAP + Volume | 25% | VWAP 돌파 + 거래량 서지 |
| Stochastic RSI | 25% | StochRSI K/D 골든크로스 |
| EMA Crossover | 20% | EMA3/8 크로스 + EMA21 추세 |

**참고**: v4.0 옵티마이저가 가중치를 Dirichlet 분포로 자동 조정

## 리스크 관리 시스템
- **ATR 기반 동적 SL/TP**: 시장 변동성에 따라 자동 조절 (옵티마이저가 배율 최적화)
- **트레일링 스탑**: +0.4% 수익 시 활성, 고점 대비 -0.2% 시 청산 (동적 최적화)
- **손익분기 스탑**: 60분 경과 후 마이너스면 청산
- **서킷브레이커**: 일일 손실 3%, 연속 4패, 시간당 20건 제한
- **캔들 확인 필터**: 약세봉에서 매수 차단

---

## 대시보드 v2.0 (2026-02-14)

### 주요 기능
- **캔들스틱 차트**: TradingView lightweight-charts v4 기반 OHLC + BB/EMA/VWAP 오버레이
- **서브차트 3종**: RSI(7), StochRSI K/D, Volume + 서지 라인
- **매매 조건 체크리스트**: 4개 전략별 조건 충족 상태 실시간 표시
- **앙상블 판단 패널**: 투표 수, 가중 신뢰도, 추세 상태, 최종 시그널
- **Active Markets 패널**: 스캐너 선택 마켓 + 마지막 스캔 시간 (v4.0 신규)
- **Optimizer Status 패널**: 최적화 스코어 + 현재 프로필 요약 (v4.0 신규)
- **Guide 탭**: 실시간 상태 해석, 앙상블 플로우차트, 상세 초심자 가이드

---

## WebSocket 실시간 스트리밍 (2026-02-15)

### 메시지 타입
| Type | 주기 | 내용 |
|------|------|------|
| `status_update` | 5초 | 잔고, 매매수, 승률, **활성 마켓, 옵티마이저** |
| `market_update` | 3초 | 동적 마켓 지표, 차트 데이터 |
| `trade_event` | 즉시 | 매수/매도 실행 알림 |
| `circuit_event` | 즉시 | 서킷브레이커 상태 변경 |

---

## 전략 v3.0 개선 (2026-02-15)

### 결과: 14일 백테스트 = +6.11% 흑자

| 지표 | v2.0 (7일) | v3.0 (14일) |
|------|:-:|:-:|
| 거래 수 | 41 | 11 |
| 승률 | 48.8% | **72.7%** |
| PnL | -50,052 KRW | **+61,122 KRW** |
| 연환산 | - | **~159%** |

---

## 24/7 운영 체계 (2026-02-15)

| 항목 | 설정 |
|------|------|
| 절전 모드 | 비활성화 |
| 자동 시작 | Windows 시작 폴더 등록 |
| 자동 재시작 | start_bot.bat (10초 대기 후 재시작) |
| 외부 접근 | Cloudflare Tunnel (Quick Tunnel) |

---

## 버전 히스토리

| 버전 | 날짜 | 주요 변경 |
|------|------|----------|
| v1.0 | 2026-02-09 | 4전략 앙상블 + ATR 리스크 + 서킷브레이커 + 백테스터 |
| v2.0 | 2026-02-14 | 대시보드 v2 (TradingView 차트 + 체크리스트 + Guide) |
| v2.5 | 2026-02-15 | WebSocket 실시간 + 24/7 운영 체계 + 전략 v3.0 |
| **v4.0** | **2026-02-16** | **동적 마켓 스캐너 + Walk-Forward 최적화 엔진** |

---

## 주요 기능 체크리스트
- [x] 4가지 기술적 분석 전략 (RSI+BB, VWAP, StochRSI, EMA)
- [x] 가중 투표 앙상블 시스템 + 자동 가중치 조정
- [x] ATR 기반 리스크 관리 (동적 SL/TP/트레일링)
- [x] 손익분기 스탑 (60분 경과 보호)
- [x] 캔들 확인 필터 (약세봉 차단)
- [x] 서킷브레이커 (일일 손실 / 연속 손실 / 과다 거래)
- [x] 페이퍼 트레이딩 모드
- [x] 실데이터 백테스팅 엔진 (pyupbit 자동 페이지네이션)
- [x] 웹 대시보드 v2.0 (TradingView 캔들스틱 + 체크리스트)
- [x] WebSocket 실시간 스트리밍 (자동 재연결 + HTTP 폴백)
- [x] 24/7 운영 체계 (자동 재시작 + Cloudflare Tunnel)
- [x] **동적 마켓 스캐너** (거래량 Top N 자동 선택)
- [x] **Walk-Forward 최적화** (2시간 주기 자동 파라미터 튜닝)
- [x] **ParamProfile 런타임 설정 교체** (백테스터 통합)

## 향후 과제
- [ ] 실전 API 키 연동 (소액 테스트)
- [ ] 옵티마이저 결과 로깅 (프로필 변경 이력)
- [ ] Cloudflare Named Tunnel (고정 URL)
- [ ] 텔레그램 알림 연동
- [ ] 다중 시간프레임 분석 (3분 + 15분)
- [ ] 마켓별 개별 최적화 프로필
- [ ] 다중 거래소 지원
