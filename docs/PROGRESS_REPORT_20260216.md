# BIZ LIFE 프로젝트 진행 보고서

> **보고일**: 2026-02-16
> **버전**: v1.3
> **상태**: CryptoBot v4.0 동적마켓스캐너+적응형최적화 / HomeFinder v1.0 내 조건 검색

---

## 1. 이번 업데이트 요약

### 2대 핵심 신규 모듈

| # | 모듈 | 효과 |
|---|------|------|
| 1 | **동적 마켓 스캐너** | 고정 3개 → 거래량 Top 5 자동 선택 (1시간 주기) |
| 2 | **Walk-Forward 최적화** | 고정 파라미터 → 2시간마다 최적 설정 자동 탐색/적용 |

### 변경 범위

| 구분 | 파일 | 줄 수 |
|------|------|-------|
| **신규** | `scalper/market_scanner.py` | ~130줄 |
| **신규** | `scalper/optimizer.py` | ~230줄 |
| **수정** | `scalper/config.py` | +11줄 (신규 설정) |
| **수정** | `scalper/trader.py` | ~25줄 변경 (스캐너/옵티마이저 통합) |
| **수정** | `scalper/backtester.py` | ~10줄 변경 (ParamProfile 지원) |
| **수정** | `scalper/run.py` | ~15줄 변경 (CLI 플래그 추가) |
| **수정** | `scalper/dashboard.py` | ~20줄 변경 (대시보드 UI/API 확장) |
| **합계** | **7개 파일** | **~360줄 신규 + ~80줄 수정** |

---

## 2. 동적 마켓 스캐너 (MarketScanner)

### 2.1 문제점 (v3.0)

```
Before: config.MARKETS = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
→ 3개 마켓 고정, 거래량 많은 코인 놓침
→ XRP 거래량 급등 시에도 SOL/DOGE 등 기회 미포착
```

### 2.2 해결: 거래량 기반 동적 마켓 선택

```
[1시간 주기]
    │
    ▼
[pyupbit.get_tickers(fiat="KRW")] ── 전체 KRW 마켓 목록
    │
    ▼ (각 ticker별 24h 거래대금 조회, 0.1초 간격 rate limit)
[거래대금 상위 5개 선택] ── 최소 10억원 필터
    │
    ▼
[_active_markets 갱신] ── threading.Lock 보호
    │
    ▼
[trader._tick()] ── scanner.get_markets(positions)로 마켓 리스트 획득
```

### 2.3 핵심 설계

| 항목 | 설정 | 설명 |
|------|------|------|
| 스캔 주기 | 3600초 (1시간) | API 호출량 관리 |
| 상위 N개 | 5개 | 집중 분석 대상 |
| 최소 거래대금 | 10억 KRW | 유동성 필터 |
| Rate Limit | 0.1초/요청 | 업비트 API 제한 준수 |
| 오픈 포지션 보존 | 항상 | 마켓 교체 중 청산 보장 |
| 스레드 안전 | `threading.Lock` | `_active_markets` 보호 |

### 2.4 실제 테스트 결과 (2026-02-16 00:55)

```
스캔 완료 (31.6초):

순위  마켓        24h 거래대금
─────────────────────────────────────
 1   KRW-XRP     993,020,764,291 KRW  ← 선택
 2   KRW-ETH     240,489,117,174 KRW  ← 선택
 3   KRW-BTC     186,600,597,694 KRW  ← 선택
 4   KRW-DOGE     96,334,917,737 KRW  ← 선택
 5   KRW-SOL      75,867,827,589 KRW  ← 선택
 6   KRW-KITE     72,565,799,603 KRW
 7   KRW-IP       61,646,636,889 KRW
 8   KRW-QKC      57,465,860,155 KRW
 ...
```

**결과**: 기존 고정 3개(BTC, ETH, XRP)에서 거래량 기준 Top 5(XRP, ETH, BTC, DOGE, SOL)로 자동 확장.

### 2.5 오픈 포지션 보존 메커니즘

```python
# 시나리오: KRW-KITE 포지션 보유 중 스캐너가 Top 5 갱신
scanner.get_markets({"KRW-KITE": position})
# → ["KRW-XRP", "KRW-ETH", "KRW-BTC", "KRW-DOGE", "KRW-SOL", "KRW-KITE"]
#   ↑ Top 5                                                   ↑ 보존됨
```

---

## 3. Walk-Forward 적응형 최적화 (WalkForwardOptimizer)

### 3.1 문제점 (v3.0)

```
Before: 모든 파라미터 수동 고정
→ 시장 상태 변화 시 성과 하락
→ 최적 SL/TP/트레일링 비율이 시간에 따라 달라짐
→ 수동 튜닝 주기 = 수일~수주 (느림)
```

### 3.2 해결: 2시간 주기 자동 파라미터 최적화

```
[2시간 주기, 배경 스레드]
    │
    ▼
[과거 3일 데이터 로드] ── pyupbit, KRW-BTC + KRW-ETH
    │
    ▼
[12개 후보 프로필 생성]
    ├── 프로필 #1: 현재 default (baseline)
    ├── 프로필 #2: 이전 best (baseline)
    ├── 프로필 #3~12: 랜덤 생성 (합리적 범위 내)
    │
    ▼
[각 프로필로 백테스트 실행] ── Backtester 재활용
    │
    ▼
[스코어링: PF×0.4 + WR×0.3 - DD×0.3]
    │
    ▼
[최고 스코어 프로필 → config 모듈에 즉시 반영]
    │
    ▼
[다음 trader._tick()부터 새 설정으로 매매]
```

### 3.3 ParamProfile 데이터클래스

```python
@dataclass
class ParamProfile:
    candle_interval: str          # "minute3"
    min_ensemble_confidence: float  # 0.25 ~ 0.50
    entry_cooldown_bars: int       # 3 ~ 8
    risk_per_trade: float          # 0.005 ~ 0.02
    atr_stop_multiplier: float     # 1.5 ~ 3.0
    atr_tp_multiplier: float       # 2.5 ~ 5.0
    stop_loss_hard_cap: float      # 0.004 ~ 0.012
    take_profit_pct: float         # 0.005 ~ 0.015
    trailing_activate_pct: float   # 0.002 ~ 0.008
    trailing_stop_pct: float       # 0.001 ~ 0.004
    breakeven_after_bars: int      # 10 ~ 40
    weights: dict[str, float]      # Dirichlet 분포 (합=1)
```

| 메서드 | 기능 |
|--------|------|
| `from_config()` | 현재 config.py 값에서 프로필 생성 |
| `apply_to_config()` | 프로필 → `setattr(config, key, value)` 런타임 반영 |
| `summary()` | 대시보드 표시용 요약 딕셔너리 |

### 3.4 스코어링 함수

```
score = profit_factor_norm × 0.4
      + win_rate_norm     × 0.3
      - max_dd_penalty    × 0.3

where:
  profit_factor_norm = min(PF, 3.0) / 3.0    # 0~1 정규화
  win_rate_norm      = WR / 100               # 0~1 정규화
  max_dd_penalty     = min(DD%, 10%) / 10%    # 0~1 패널티
```

**설계 의도**:
- 수익성(PF)과 안정성(WR)을 균형있게 평가
- 과도한 드로다운(-DD)은 강하게 패널티
- PF가 3 이상이면 포화(over-fit 방지)

### 3.5 안전 장치

| 장치 | 설명 |
|------|------|
| **Default baseline** | 현재 config 값을 항상 후보에 포함 → 최소 현 수준 보장 |
| **Previous best** | 이전 최적 프로필도 baseline으로 포함 |
| **Config 복원** | 백테스트 후 원래 config 자동 복원 |
| **최소 거래 수 필터** | 3건 미만이면 스코어 -1 (과적합 방지) |
| **범위 제한** | 모든 파라미터에 합리적 min/max 설정 |
| **Dirichlet 가중치** | 전략 가중치 합 = 1.0 보장 (numpy.random.dirichlet) |

### 3.6 Backtester ParamProfile 통합

```python
# 기존 (v3.0)
bt = Backtester(initial_balance=1_000_000)

# 신규 (v4.0) — 프로필 적용 후 백테스트, 완료 시 자동 복원
bt = Backtester(initial_balance=1_000_000, param_profile=profile)
result = bt.run(market="KRW-BTC", days=3)
# → config는 자동으로 원래 값 복원됨
```

### 3.7 실제 테스트 결과 (2026-02-16 00:57)

```
Optimizer: 5 profiles × KRW-BTC × 3일 (52.4초)

프로필 #3 (random):
  Trades: 2 (W:1, L:1), WR: 50%, PnL: +2,624 KRW (+0.26%)
  PF: 3.49, MaxDD: 0.82%
  Exit: breakeven_stop(1), trailing_stop(1)

프로필 #5 (random):
  Trades: 2 (W:1, L:1), WR: 50%, PnL: +1,370 KRW (+0.14%)
  PF: 1.83, MaxDD: 0.82%

→ Default 프로필이 best로 선택 (안정적 baseline)
```

---

## 4. 대시보드 + CLI 업데이트

### 4.1 대시보드 신규 UI 요소

```
┌─────────────────────────────────────────────────────┐
│  Balance   Today PnL   Fees   WinRate   Trades   CB │  ← 기존
├─────────────────────────────────────────────────────┤
│  Active Markets (Scanner)    │  Optimizer Status     │  ← NEW
│  XRP, ETH, BTC, DOGE, SOL   │  Score: 0.23 (#3)    │
│  Last scan: 45m ago | Top 5  │  SL:0.7% TP:0.8%    │
└─────────────────────────────────────────────────────┘
```

### 4.2 API 응답 확장

**`GET /api/status` 신규 필드**:

| 필드 | 타입 | 설명 |
|------|------|------|
| `active_markets` | `list[str]` | 현재 스캔 중인 마켓 리스트 |
| `scanner_status` | `dict` | 스캐너 상태 (enabled, last_scan, top_n, volumes) |
| `optimizer_status` | `dict` | 옵티마이저 상태 (enabled, run_count, best_score, profile) |

**`GET /api/runtime` 신규 필드**:

| 필드 | 타입 | 설명 |
|------|------|------|
| `markets` | `list[str]` | 동적 활성 마켓 (기존: 고정 config.MARKETS) |
| `static_markets` | `list[str]` | 원래 config.MARKETS (참조용) |
| `scanner_status` | `dict` | 스캐너 상세 상태 |
| `optimizer_status` | `dict` | 옵티마이저 상세 상태 |

### 4.3 CLI 신규 플래그

```bash
# v4.0 전체 기능 (기본)
python -m scalper.run --with-dashboard

# 스캐너 비활성 (고정 마켓 사용)
python -m scalper.run --with-dashboard --no-scanner

# 옵티마이저 비활성 (고정 파라미터 사용)
python -m scalper.run --with-dashboard --no-optimizer

# v3.0 호환 모드 (스캐너 + 옵티마이저 모두 비활성)
python -m scalper.run --with-dashboard --no-scanner --no-optimizer

# 백테스트 (스캐너/옵티마이저 자동 비활성)
python -m scalper.run --backtest
```

---

## 5. 데이터 흐름도 (v4.0 최종)

```
[업비트 API]
    │
    ├──▶ [MarketScanner] ── 1시간 주기 ── ← NEW
    │     ├── pyupbit.get_tickers(fiat="KRW")
    │     ├── 24h 거래대금 상위 5개 선택
    │     └── _active_markets 갱신
    │
    ▼ (동적 마켓 리스트, 3분봉 120개)
[ScalpTrader._tick()] ── 5초 루프 ──
    │
    ├──▶ [EnsembleStrategy.analyze()]
    │     ├── 4개 전략 독립 분석
    │     ├── 투표 집계 (≥2 전략 동의)
    │     ├── 추세 필터 (EMA50 기울기 + 가격 위치)
    │     ├── 변동성 레짐 필터
    │     └── 캔들 확인 필터 (약세봉 차단)
    │
    ├──▶ [RiskManager] ── 파라미터는 Optimizer가 동적 조정 ──
    │     ├── ATR 기반 SL (0.3~0.7% → 동적 최적화)
    │     ├── ATR 기반 TP (0.6~0.8% → 동적 최적화)
    │     ├── 트레일링 스탑 (활성/추적 비율 → 동적 최적화)
    │     └── 손익분기 스탑
    │
    ├──▶ [WalkForwardOptimizer] ── 2시간 주기, 배경 스레드 ── ← NEW
    │     ├── 과거 3일 데이터로 12개 프로필 백테스트
    │     ├── 스코어링: PF×0.4 + WR×0.3 - DD×0.3
    │     └── 최적 프로필 → config 런타임 반영
    │
    ├──▶ [queue.Queue] → [WSManager] → [WebSocket 클라이언트]
    │
    └──▶ [FastAPI 대시보드]
          ├── /ws (WebSocket 실시간)
          ├── /api/status (+ active_markets, optimizer_status)
          ├── /api/market-watch (동적 마켓 분석)
          └── http://localhost:8081
```

---

## 6. 테스트 결과 (전체 4개 테스트 통과)

### Test 1: MarketScanner 실시간 API

| 항목 | 결과 |
|------|------|
| 초기값 = config.MARKETS | PASS |
| 실제 API 스캔 → Top 5 선택 | PASS (XRP, ETH, BTC, DOGE, SOL) |
| 오픈 포지션 보존 (KRW-SHIB 추가) | PASS |
| 재스캔 방지 (interval 캐시) | PASS |

### Test 2: WalkForwardOptimizer 수동 최적화

| 항목 | 결과 |
|------|------|
| 초기 상태 (run_count=0, score=0) | PASS |
| 5개 프로필 백테스트 (~52초) | PASS |
| best_score 갱신 + config 적용 | PASS |
| 설정값 정상 범위 확인 | PASS |

### Test 3: v3 호환성 (--no-scanner --no-optimizer)

| 항목 | 결과 |
|------|------|
| scanner=None, optimizer=None | PASS |
| status에서 disabled 상태 | PASS |
| 백테스트 정상 실행 (v3 동일) | PASS |

### Test 4: Trader 통합 (Scanner + Optimizer + tick)

| 항목 | 결과 |
|------|------|
| 초기화 (scanner + optimizer 모두 생성) | PASS |
| get_status() 신규 필드 3개 존재 | PASS |
| _tick() 3회 실행: **5개 동적 마켓** 모두 스캔 | PASS |
| market_watch에 5개 마켓 분석 결과 | PASS |

```
_tick() 결과:
  KRW-XRP: price=2,253, signal=HOLD, trend=down
  KRW-ETH: price=2,975,000, signal=HOLD, trend=down
  KRW-BTC: price=102,025,000, signal=HOLD, trend=down
  KRW-DOGE: price=159, signal=HOLD, trend=down
  KRW-SOL: price=129,200, signal=HOLD, trend=down
```

---

## 7. 파일 구조 (v4.0)

```
04-crypto-trader/
├── scalper/                          # 핵심 스캘핑 엔진 (v4.0)
│   ├── __init__.py
│   ├── config.py                     # 전체 설정 + 스캐너/옵티마이저 설정 (수정)
│   ├── trader.py                     # ScalpTrader + Scanner/Optimizer 통합 (수정)
│   ├── market_scanner.py             # 동적 마켓 스캐너 (신규)
│   ├── optimizer.py                  # Walk-Forward 최적화 + ParamProfile (신규)
│   ├── dashboard.py                  # FastAPI 대시보드 + 신규 UI (수정)
│   ├── run.py                        # CLI + --no-scanner/--no-optimizer (수정)
│   ├── backtester.py                 # 백테스터 + ParamProfile 지원 (수정)
│   ├── risk_manager.py               # ATR 리스크 관리
│   ├── circuit_breaker.py            # 서킷브레이커
│   ├── upbit_client.py               # 업비트 API 클라이언트
│   ├── alert_system.py               # 텔레그램/콘솔 알림
│   └── strategies/                   # 4가지 매매 전략
│       ├── base.py
│       ├── rsi_bb_scalp.py
│       ├── vwap_volume.py
│       ├── stochastic_rsi.py
│       ├── ema_crossover.py
│       └── ensemble.py
├── start_bot.bat
├── monitor.py
└── docs/PROJECT_PLAN.md
```

---

## 8. 실행 방법 (v4.0)

```bash
cd projects/04-crypto-trader

# v4.0 전체 (봇 + 대시보드 + 스캐너 + 옵티마이저)
python -m scalper.run --with-dashboard

# v3.0 호환 (스캐너/옵티마이저 비활성)
python -m scalper.run --with-dashboard --no-scanner --no-optimizer

# 스캐너만 비활성 (고정 마켓 + 옵티마이저)
python -m scalper.run --with-dashboard --no-scanner

# 백테스트 (스캐너/옵티마이저 자동 비활성)
python -m scalper.run --backtest --market KRW-BTC --days 7

# 24/7 자동 실행
start_bot.bat
```

---

## 9. 버전 히스토리

| 버전 | 날짜 | 주요 변경 |
|------|------|----------|
| v1.0 | 2026-02-09 | 4전략 앙상블 + ATR 리스크 + 서킷브레이커 + 백테스터 |
| v2.0 | 2026-02-14 | 대시보드 v2 (TradingView 차트 + 체크리스트 + Guide) |
| v2.5 | 2026-02-15 | WebSocket 실시간 + 24/7 운영 체계 + 전략 v3.0 |
| **v4.0** | **2026-02-16** | **동적 마켓 스캐너 + Walk-Forward 최적화 엔진** |

---

## 10. 향후 계획

### 완료됨 (이번 업데이트)
- [x] 동적 마켓 스캐너 (거래량 Top 5 자동 선택)
- [x] Walk-Forward 적응형 최적화 (2시간 주기 자동 튜닝)
- [x] ParamProfile 기반 런타임 설정 교체
- [x] Backtester ParamProfile 통합
- [x] 대시보드 Active Markets + Optimizer Status 표시
- [x] CLI --no-scanner / --no-optimizer 플래그
- [x] v3.0 완전 호환 (플래그로 비활성 가능)

### 단기 (1~2주)
- [ ] 실전 거래 결과 추적 (최소 7일 라이브 데이터 수집)
- [ ] 옵티마이저 결과 로깅 (프로필 변경 이력 저장)
- [ ] Cloudflare Named Tunnel 설정 (고정 URL)
- [ ] 텔레그램 알림 연동

### 중기 (1개월)
- [ ] 실전 API 키 연동 (소액 실전 테스트)
- [ ] 다중 시간프레임 분석 (3분 + 15분 확인)
- [ ] 옵티마이저 결과 대시보드 차트 (파라미터 변화 추이)
- [ ] 마켓별 개별 최적화 프로필

---

## 11. HomeFinder v1.0 — "내 조건 검색" 페이지 구축

### 11.1 배경

HomeFinder는 실거주 주택 구매를 위한 부동산 검색·분석 플랫폼으로, 160건 매물과 4차원 채점 데이터가 축적되어 있었으나 사용자가 세부 조건을 동적으로 조정하며 실시간 결과를 확인할 수 있는 UI가 없었음. 이를 해결하기 위해 "내 조건 검색" 페이지를 신규 구축.

### 11.2 구현 내용

#### 수정/신규 파일 (5개)

| 구분 | 파일 | 변경 |
|------|------|------|
| **신규** | `templates/my_search.html` | 검색 페이지 전체 (~350줄) |
| **수정** | `backend/schemas/search.py` | `directions`, `min_total_units` 필드 추가 |
| **수정** | `backend/api/v1/search.py` | 향 필터, 세대수 필터(Complex JOIN), 서브점수 응답 추가 |
| **수정** | `main.py` | `GET /search` 라우트 추가 |
| **수정** | `templates/base.html` | 네비바에 "내 조건" 메뉴 추가 |

#### 검색 페이지 구성

```
┌──────────────────────────────────────────────────────────┐
│  HomeFinder  대시보드  [내 조건]  지도  후보관리  지역분석  │
├────────────┬─────────────────────────────────────────────┤
│ 조건 설정   │  🔍 검색 결과  160건                        │
│            │  ┌─ 💰8~15억  📍마포,용산  🚇500m ────┐    │
│ 예산 범위   │  │                                    │    │
│ [8억]~[15억]│  │ ● 84  용산파크타워                  │    │
│            │  │      용산구 문배동 · 아파트           │    │
│ 대상 지역   │  │      🚇신용산 188m  🏢22층  📅19년   │    │
│ ☑마포 ☑용산 │  │      위치 85  가격 80  매물 86  지역 86│    │
│ □성동 □광진 │  │                                    │    │
│            │  │ ● 77  공덕자이                      │    │
│ 역세권 거리  │  │      마포구 공덕동 · 아파트           │    │
│ ●───── 500m │  │      🚇공덕 72m  🏢11층  📅10년     │    │
│            │  │      위치 66  가격 76  매물 96  지역 78│    │
│ 건물 연식   │  └────────────────────────────────────┘    │
│ ●───── 제한없음│                                         │
│            │  [이전] 1 2 3 [다음]                       │
│ 향          │                                           │
│ ☑남향 ☑남동향│                                           │
│            │                                           │
│ [🔍 검색]   │                                           │
│ [저장][불러오기]│                                         │
└────────────┴─────────────────────────────────────────────┘
```

#### 필터 항목 (10개)

| 필터 | UI 타입 | API 파라미터 |
|------|---------|-------------|
| 예산 범위 | 숫자 입력 (억 단위) | `price_min`, `price_max` |
| 대상 지역 | 체크박스 (10개 구) | `districts` |
| 전용면적 | 숫자 입력 (㎡) | `area_min`, `area_max` |
| 역세권 거리 | 슬라이더 (0~2000m) | `subway_max_distance` |
| 건물 연식 | 슬라이더 (신축~40년) | `built_year_min` |
| 최소 층수 | 숫자 입력 | `floor_min` |
| 향 | 체크박스 (6종) | `directions` ← **신규** |
| 최소 세대수 | 숫자 입력 | `min_total_units` ← **신규** |
| 최소 점수 | 슬라이더 (0~100) | `score_min` |
| 정렬 기준 | 셀렉트 (5종) | `sort` |

#### 결과 카드 정보

각 매물 카드에 표시되는 정보:
- **종합 점수** (원형 배지, 색상: 초록≥70 / 파랑≥45 / 회색)
- 단지명, 구·동, 매물유형
- 가격 (억 단위), 전용면적
- 최근접 역 이름 + 거리(m), 층수, 연식, 향, 방수
- **서브점수 바**: 위치 / 가격 / 매물 / 지역 (4개 진행바)
- 후보 추가(+) 버튼 → 칸반 파이프라인 연동

#### 조건 저장/불러오기

- **저장**: 조건명 입력 + 새 매물 알림 옵션 → `POST /api/v1/search/saved`
- **불러오기**: 저장된 조건 목록 표시 → 클릭 시 필터 자동 적용 + 즉시 검색
- **삭제**: 저장된 조건 개별 삭제 가능

### 11.3 테스트 결과

| 테스트 | 결과 |
|--------|------|
| 기본 검색 (필터 없음) | 160건 전체 표시, 점수순 정렬 ✅ |
| 마포+용산, 역세권 800m, 남향 | 160→10건 필터링 ✅ |
| 8~15억, 마포+용산, 500m, 남향+남동향 | 160→6건 필터링 ✅ |
| 남향 필터 단독 | 42건 ✅ |
| 가격 낮은순 정렬 | 정상 (상계주공 5.5억부터) ✅ |
| 조건 저장 ("마포용산 역세권 남향") | DB 저장 성공 ✅ |
| 필터 초기화 → 불러오기 → 적용 | 조건 복원 + 6건 재검색 ✅ |
| 서브점수 시각화 | 위치/가격/매물/지역 바 정상 표시 ✅ |

### 11.4 HomeFinder 전체 현황

| 항목 | 수치 |
|------|------|
| 파일 수 | 90개+ |
| DB 모델 | 14개 (Property, Complex, Candidate, SavedSearch 등) |
| API 엔드포인트 | 10개 |
| 페이지 | 7개 (대시보드, 내 조건, 지도, 후보관리, 지역분석, 매물상세, API문서) |
| 시드 데이터 | 매물 160건, 지하철역 193개, 공원 16개, 한강접근점 11개 |
| 데이터 수집기 | 5개 (네이버, 국토부, 경매, 청약, KB지수) |
| 채점 차원 | 4개 (위치 35% + 가격 25% + 매물 20% + 지역 20%) |

### 11.5 실행 방법

```bash
cd projects/06-home-finder
python main.py
# → http://localhost:8006         (대시보드)
# → http://localhost:8006/search  (내 조건 검색)
# → http://localhost:8006/map     (지도)
# → http://localhost:8006/candidates (후보관리)
```

### 11.6 HomeFinder 향후 계획

- [ ] 실제 네이버 부동산 크롤링 연동 (API키 설정 후)
- [ ] 카카오맵 연동 (검색 결과 지도 표시)
- [ ] 매물 상세페이지 고도화 (시세 차트, 주변 인프라)
- [ ] 비교 기능 (2~3개 매물 나란히 비교)
- [ ] 텔레그램 알림 (새 매물 + 가격 변동)

---

*본 보고서는 2026-02-16 CryptoBot v4.0 동적 마켓 스캐너 + Walk-Forward 적응형 최적화 엔진 구축 및 HomeFinder v1.0 "내 조건 검색" 페이지 구축 작업을 기록한 것입니다.*
