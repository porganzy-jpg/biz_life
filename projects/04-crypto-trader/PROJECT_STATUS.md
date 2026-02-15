# CryptoBot - 프로젝트 현황

**최종 업데이트**: 2026-02-15

## 개요
암호화폐 자동매매 스캘핑 봇. 4가지 전략의 앙상블 가중 투표로 매매 신호를 생성하고, ATR 기반 리스크 관리 + 서킷브레이커 + WebSocket 실시간 대시보드를 통합한 트레이딩 엔진.

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

# 봇 + 대시보드 + WebSocket (권장)
python -m scalper.run --with-dashboard
# → http://localhost:8081 (WS: ws://localhost:8081/ws)

# 대시보드만 (봇 별도 시작)
python -m scalper.run --dashboard

# 봇만 (대시보드 없이)
python -m scalper.run

# 백테스트
python -m scalper.run --backtest

# 24/7 자동 실행 (Windows)
start_bot.bat
```

## 핵심 파일 구조
```
04-crypto-trader/
├── scalper/                        # 핵심 스캘핑 엔진 (v3.0)
│   ├── __init__.py
│   ├── config.py                   # 모든 설정값 (3분봉, ATR, SL/TP 등)
│   ├── trader.py                   # ScalpTrader (메인 트레이딩 루프)
│   ├── dashboard.py                # FastAPI 대시보드 + WebSocket
│   ├── run.py                      # CLI 진입점 (argparse)
│   ├── backtester.py               # 백테스터 (실데이터/합성데이터)
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
| GET | `/api/status` | 봇 상태 (잔고, 매매수, 승률) |
| GET | `/api/market-watch` | 3개 마켓 실시간 분석 |
| GET | `/api/history` | 매매 이력 (필터, 페이지네이션) |
| GET | `/api/performance` | 기간별 성과 통계 |
| POST | `/api/bot/start` | 봇 시작 |
| POST | `/api/bot/stop` | 봇 정지 |
| **WS** | **`/ws`** | **WebSocket 실시간 스트리밍** |

## 4개 전략 앙상블 (스캘퍼 v3.0)

| 전략 | 기본 가중치 | 설명 |
|------|:-:|------|
| RSI + Bollinger Band | 30% | BB%B + RSI 과매수/과매도 반등 |
| VWAP + Volume | 25% | VWAP 돌파 + 거래량 서지 |
| Stochastic RSI | 25% | StochRSI K/D 골든크로스 |
| EMA Crossover | 20% | EMA3/8 크로스 + EMA21 추세 |

## 리스크 관리 시스템
- **ATR 기반 동적 SL/TP**: 시장 변동성에 따라 자동 조절
- **트레일링 스탑**: +0.4% 수익 시 활성, 고점 대비 -0.2% 시 청산
- **손익분기 스탑**: 60분 경과 후 마이너스면 청산
- **서킷브레이커**: 일일 손실 3%, 연속 4패, 시간당 20건 제한
- **캔들 확인 필터**: 약세봉에서 매수 차단

---

## 대시보드 v2.0 (2026-02-14)

### 주요 기능
- **캔들스틱 차트**: TradingView lightweight-charts v4 기반 OHLC + BB/EMA/VWAP 오버레이
- **서브차트 3종**: RSI(7), StochRSI K/D, Volume + 서지 라인
- **매매 조건 체크리스트**: 4개 전략별 조건 충족 상태 실시간 표시 (✅/❌)
- **앙상블 판단 패널**: 투표 수, 가중 신뢰도, 추세 상태, 최종 시그널
- **Guide 탭**: 실시간 상태 해석, 앙상블 플로우차트, 상세 초심자 가이드

---

## WebSocket 실시간 스트리밍 (2026-02-15)

### 개요
HTTP 5초 폴링 → WebSocket 실시간 스트리밍(<500ms)으로 전환. 연결 실패 시 HTTP 폴링으로 자동 폴백.

### 메시지 타입
| Type | 주기 | 내용 |
|------|------|------|
| `status_update` | 5초 | 잔고, 매매수, 승률 등 |
| `market_update` | 3초 | 3개 마켓 지표, 차트 데이터 |
| `trade_event` | 즉시 | 매수/매도 실행 알림 |
| `circuit_event` | 즉시 | 서킷브레이커 상태 변경 |

### 스레드 안전성
- `queue.Queue`(stdlib): 동기 trader 스레드 → 비동기 WS drain loop
- `asyncio.Task`로 1초 주기 drain, 주기적 status/market push

---

## 전략 v3.0 개선 (2026-02-15)

### 문제: v2.0 백테스트 7일 = -1.67% 적자
- 1분봉 → 41건 과다 거래 (노이즈)
- SL 평균 손실 -6,338 KRW > 트레일링 평균 수익 +2,276 KRW
- R:R 비율 2.8:1 (손실:수익)

### 해결: 5대 개선

| 개선 | Before | After | 효과 |
|------|:---:|:---:|------|
| 3분봉 전환 | minute1 | **minute3** | 노이즈 -88% |
| SL 하드캡 | 1.2% | **0.7%** | 손실 -30% |
| BEP 스탑 | 비활성 | **60분** | 횡보 탈출 |
| 트레일링 | 0.5%/0.3% | **0.4%/0.2%** | 수익 확보 |
| 캔들 필터 | 없음 | **약세봉 차단** | 허위 진입 감소 |

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

## 향후 과제
- [ ] 실전 API 키 연동 (소액 테스트)
- [ ] Cloudflare Named Tunnel (고정 URL)
- [ ] 텔레그램 알림 연동
- [ ] 다중 시간프레임 분석 (3분 + 15분)
- [ ] 백테스트 결과 차트 대시보드 통합
- [ ] 다중 거래소 지원
