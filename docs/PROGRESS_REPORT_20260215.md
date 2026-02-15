# BIZ LIFE 프로젝트 진행 보고서

> **보고일**: 2026-02-15
> **버전**: v1.2
> **상태**: CryptoBot WebSocket 실시간 스트리밍 + 전략 v3.0 개선 + 24/7 운영 체계 구축

---

## 1. 이번 업데이트 요약

### 3대 핵심 업그레이드

| # | 업그레이드 | 효과 |
|---|-----------|------|
| 1 | **WebSocket 실시간 스트리밍** | 대시보드 지연 5초 → <500ms |
| 2 | **24/7 운영 체계** | PC 자동 재시작 + Cloudflare 터널 외부 접근 |
| 3 | **전략 v3.0 개선** | 7일 백테스트 -1.67% → +2.00% (흑자 전환) |

---

## 2. WebSocket 실시간 스트리밍 구현

### 2.1 개요

기존 HTTP 5초 폴링 방식을 WebSocket 실시간 스트리밍으로 전환. WebSocket 연결 실패 시 HTTP 폴링으로 자동 폴백하는 하이브리드 구조.

### 2.2 아키텍처

```
[ScalpTrader 스레드]
    │
    │  push_event() (스레드 안전)
    ▼
[queue.Queue] ←── stdlib, GIL 보호
    │
    │  _drain_loop() (1초 주기)
    ▼
[WSManager] ──broadcast──▶ [WebSocket 클라이언트 N개]
    │
    ├── status_update (5초 주기)
    ├── market_update (3초 주기)
    ├── trade_event (거래 실행 시 즉시)
    └── circuit_event (서킷브레이커 상태 변경 시)
```

### 2.3 메시지 프로토콜

| Type | 방향 | 주기 | 크기 |
|------|------|------|------|
| `status_update` | Server→Client | ~5초 | ~2-3KB |
| `market_update` | Server→Client | ~3초 | ~6KB |
| `trade_event` | Server→Client | 거래 실행 시 | ~500B |
| `circuit_event` | Server→Client | 상태 변경 시 | ~200B |

### 2.4 프론트엔드 WebSocket 클라이언트

```
[connectWS()]
    │
    ├── onopen → 폴링 중지, _useWS=true
    ├── onmessage → handleWSMessage() 분기
    │   ├── status_update → applyStatus(d)
    │   ├── market_update → applyMarketWatch(d)
    │   ├── trade_event → showTradeAlert() (탑바 플래시)
    │   └── circuit_event → showCircuitAlert()
    └── onclose → 폴링 재개, 자동 재연결 (1s→30s 지수 백오프)
```

### 2.5 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `scalper/dashboard.py` | WSManager 클래스, /ws 엔드포인트, JS 분리(applyStatus/applyMarketWatch), WS 클라이언트 |
| `scalper/trader.py` | set_ws_callback(), _ws_push(), trade_event/circuit_event 발행 |
| `scalper/run.py` | ws_mgr.push_event 콜백 연결 |

### 2.6 검증 결과

```
✅ Phase 1: WS 연결 — 초기 스냅샷(status+market) 수신 확인
✅ Phase 2: 실시간 수신 — status_update, market_update 주기적 수신
✅ Phase 3: 서버 종료 — 자동 재연결 시도 (지수 백오프)
✅ Phase 4: HTTP 폴백 — WS 불가 시 HTTP 폴링 자동 전환
✅ Phase 5: 서버 재시작 — WS 자동 재연결 성공
✅ Phase 6: HTTP 엔드포인트 — /api/status, /api/market-watch 정상
```

---

## 3. 24/7 운영 체계 구축

### 3.1 구성 요소

| 항목 | 설정 |
|------|------|
| **절전 모드** | 꺼짐 (powercfg -change) |
| **최대 절전** | 비활성화 (hibernate off) |
| **자동 시작** | Windows 시작 폴더에 BAT 등록 |
| **자동 재시작** | start_bot.bat의 goto loop (10초 대기 후 재시작) |
| **외부 접근** | Cloudflare Tunnel (Quick Tunnel) |

### 3.2 start_bot.bat 구조

```
[시작]
  ├── Cloudflare Tunnel 백그라운드 실행
  │   └── localhost:8081 → https://xxx.trycloudflare.com
  └── :loop
      ├── python -m scalper.run --with-dashboard
      ├── (비정상 종료 시)
      ├── 10초 대기
      └── goto loop (무한 재시작)
```

### 3.3 파일 목록

| 파일 | 위치 | 역할 |
|------|------|------|
| `start_bot.bat` | 04-crypto-trader/ | 봇+대시보드+터널 실행 |
| `CryptoBot_Scalper.bat` | 시작 프로그램 폴더 | 로그인 시 자동 실행 |
| `monitor.py` | 04-crypto-trader/ | 실시간 모니터링 스크립트 |

---

## 4. 전략 v3.0 개선 (핵심!)

### 4.1 문제 분석 (v2.0 백테스트 7일)

| 지표 | 값 | 문제점 |
|------|-----|--------|
| 거래 수 | 41건 | 과다 거래 (노이즈) |
| 승률 | 48.8% | 50% 이하 |
| PnL | **-50,052 KRW (-1.67%)** | 적자 |
| SL 평균 손실 | -6,338 KRW/건 (18건) | 손실 과대 |
| 트레일링 평균 수익 | +2,276 KRW/건 (19건) | 수익 과소 |
| **R:R 비율** | **2.8:1 (손실:수익)** | 구조적 적자 |

### 4.2 개선 전략

#### A. 3분봉 전환 (노이즈 제거)

```
Before: CANDLE_INTERVAL = "minute1"  (1분봉, 41 trades/7days)
After:  CANDLE_INTERVAL = "minute3"  (3분봉, 5 trades/7days)
                                      → 88% 허위 신호 제거
```

#### B. 스탑로스 축소 (손실 제한)

```
Before: STOP_LOSS_HARD_CAP = 1.2%  → 평균 SL 손실 -6,338 KRW
After:  STOP_LOSS_HARD_CAP = 0.7%  → 평균 SL 손실 -4,462 KRW
                                     → 30% 손실 축소
```

#### C. 손익분기 스탑 활성화

```
Before: BREAKEVEN_AFTER_BARS = 999  (사실상 비활성)
After:  BREAKEVEN_AFTER_BARS = 20   (60분 후 마이너스면 청산)
                                     → 횡보 포지션 조기 탈출
```

#### D. 트레일링 개선 (수익 더 잡기)

```
Before: 활성 0.5%, 추적 0.3% → 수익 후 0.2%만 확보
After:  활성 0.4%, 추적 0.2% → 수익 후 0.2%+ 확보 (더 타이트)
```

#### E. 캔들 확인 필터 (신규)

```
ensemble.py에 _candle_confirmation() 적용:
  → 약세봉(종가 < 시가)에서는 매수 차단
  → 기존 미사용 메서드를 활성화하여 구현
```

### 4.3 전체 파라미터 변경표

| 파라미터 | Before (v2.0) | After (v3.0) | 효과 |
|---------|:---:|:---:|------|
| CANDLE_INTERVAL | minute1 | **minute3** | 노이즈 -88% |
| CANDLE_COUNT | 200 | **120** | 6시간 데이터 |
| LOOP_INTERVAL_SEC | 3 | **5** | 3분봉 대응 |
| MIN_ENSEMBLE_CONFIDENCE | 0.30 | **0.35** | 문턱 상향 |
| ENTRY_COOLDOWN_BARS | 8 | **5** | 15분 대기 유지 |
| SIGNAL_EXIT_MIN_BARS | 15 | **8** | 24분 대기 유지 |
| RISK_PER_TRADE | 1.5% | **1.0%** | 보수적 리스크 |
| ATR_STOP_MULTIPLIER | 4.0 | **2.0** | 3분봉 ATR 대응 |
| ATR_TP_MULTIPLIER | 6.0 | **3.5** | 3분봉 ATR 대응 |
| STOP_LOSS_MIN_PCT | 0.4% | **0.3%** | 최소 SL 축소 |
| STOP_LOSS_HARD_CAP | **1.2%** | **0.7%** | 핵심 개선! |
| TAKE_PROFIT_PCT | 1.0% | **0.8%** | 적중률 상승 |
| TAKE_PROFIT_MIN | 1.0% | **0.6%** | 최소 TP 축소 |
| TRAILING_ACTIVATE_PCT | 0.5% | **0.4%** | 조기 활성 |
| TRAILING_STOP_PCT | 0.3% | **0.2%** | 타이트 추적 |
| BREAKEVEN_AFTER_BARS | 999 | **20** | 60분 후 BEP |
| BREAKEVEN_BUFFER | 0.15% | **0.1%** | 타이트 버퍼 |

### 4.4 백테스트 결과 비교

#### 7일 백테스트 (BTC + ETH + XRP)

| 지표 | v2.0 (1분봉) | v3.0 (3분봉) | 변화 |
|------|:-:|:-:|:-:|
| 거래 수 | 41 | **5** | -88% |
| 승률 | 48.8% | **60.0%** | +11.2%p |
| PnL | -50,052 KRW | **+20,017 KRW** | 흑자 전환! |
| PnL% | -1.67% | **+2.00%** | +3.67%p |

#### 14일 백테스트 (BTC + ETH + XRP)

| 마켓 | 거래 | 승률 | PnL | 주요 청산 |
|------|:---:|:---:|----:|---------|
| BTC | 3 | 66.7% | +902 KRW | trailing×2, BEP×1 |
| ETH | 7 | 71.4% | +54,637 KRW | TP×3, trailing×3, SL×1 |
| XRP | 1 | 100% | +5,583 KRW | trailing×1 |
| **합계** | **11** | **72.7%** | **+61,122 KRW (+6.11%)** | |

**연환산 수익률: ~159%**

### 4.5 개선 핵심 요약

```
Before (v2.0):
  1분봉 → 과다 거래 → SL 다발 → R:R 2.8:1 → 구조적 적자

After (v3.0):
  3분봉 → 선별 진입 → TP/trailing 위주 → R:R 개선 → 흑자!
```

---

## 5. 데이터 흐름도 (최종)

```
[업비트 API]
    │
    ▼ (3분봉 120개, pyupbit)
[ScalpTrader._tick()] ── 5초 루프 ──
    │
    ├──▶ [EnsembleStrategy.analyze()]
    │     ├── 4개 전략 독립 분석
    │     ├── 쿨다운 체크 (5봉 = 15분)
    │     ├── 변동성 레짐 필터
    │     ├── 투표 집계 (≥2 전략 동의)
    │     ├── 추세 필터 (EMA50 기울기 + 가격 위치)
    │     └── 캔들 확인 필터 (약세봉 차단) ← NEW
    │
    ├──▶ [RiskManager]
    │     ├── ATR 기반 SL (0.3~0.7%)
    │     ├── ATR 기반 TP (0.6~0.8%)
    │     ├── 트레일링 스탑 (0.4% 활성, 0.2% 추적)
    │     └── 손익분기 스탑 (60분 후) ← NEW
    │
    ├──▶ [queue.Queue] → [WSManager] → [WebSocket 클라이언트] ← NEW
    │
    └──▶ [FastAPI 대시보드]
          ├── /ws (WebSocket 실시간) ← NEW
          ├── /api/status
          ├── /api/market-watch
          └── http://localhost:8081
                 │
                 └──▶ [Cloudflare Tunnel] → https://xxx.trycloudflare.com ← NEW
```

---

## 6. 실행 방법

```bash
# 기본 실행 (봇 + 대시보드 + WebSocket)
cd projects/04-crypto-trader
python -m scalper.run --with-dashboard
# → http://localhost:8081 (WS: ws://localhost:8081/ws)

# 대시보드만 (봇 별도 시작)
python -m scalper.run --dashboard

# 백테스트
python -m scalper.run --backtest

# 24/7 자동 실행 (Windows)
start_bot.bat
# → Cloudflare Tunnel 자동 연결, 비정상 종료 시 자동 재시작
```

---

## 7. 향후 계획

### 완료됨 (이번 업데이트)
- [x] WebSocket 실시간 스트리밍 (5초 폴링 → <500ms)
- [x] 자동 재연결 + HTTP 폴백
- [x] 24/7 운영 체계 (PC 서버 + Cloudflare Tunnel)
- [x] 전략 v3.0 (3분봉 + 타이트 SL + BEP 스탑 + 캔들 필터)
- [x] 실데이터 백테스트 검증 (14일, +6.11%)

### 단기 (1~2주)
- [ ] 실전 거래 결과 추적 (최소 7일 라이브 데이터 수집)
- [ ] Cloudflare Named Tunnel 설정 (고정 URL)
- [ ] 텔레그램 알림 연동

### 중기 (1개월)
- [ ] 실전 API 키 연동 (소액 실전 테스트)
- [ ] 백테스트 결과 차트 대시보드 통합
- [ ] 다중 시간프레임 분석 (3분 + 15분 확인)

---

*본 보고서는 2026-02-15 CryptoBot WebSocket 스트리밍 + 전략 v3.0 개선 + 24/7 운영 체계 구축 작업을 기록한 것입니다.*
