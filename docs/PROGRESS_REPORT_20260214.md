# BIZ LIFE 프로젝트 진행 보고서

> **보고일**: 2026-02-14
> **버전**: v1.1
> **상태**: CryptoBot 대시보드 v2.0 대규모 업그레이드 완료

---

## 1. 이번 업데이트 요약

### CryptoBot 대시보드 v2.0 업그레이드

**목표**: 기존 대시보드의 Market Watch를 전문 트레이딩 대시보드 수준으로 업그레이드

**변경 파일**:
- `projects/04-crypto-trader/scalper/trader.py` — 백엔드 데이터 확장
- `projects/04-crypto-trader/scalper/dashboard.py` — 프론트엔드 전면 개편

**핵심 변경 사항**:

| 구분 | 기존 (v1) | 신규 (v2) |
|------|----------|----------|
| 메인 차트 | Chart.js 미니 라인차트 (80px) | **TradingView 캔들스틱** (300px) + BB/EMA/VWAP 오버레이 |
| 지표 차트 | 게이지 바만 | 게이지 바 + **RSI/StochRSI/Volume 서브차트** |
| 매매 조건 | 텍스트 시그널만 표시 | **전략별 조건 체크리스트** (✅/❌ + 앙상블 최종 판단) |
| Guide 탭 | 기본 전략 설명 | **실시간 상태 해석** + 앙상블 플로우차트 + 상세 초심자 가이드 |
| 차트 라이브러리 | Chart.js 단독 | Chart.js + **TradingView lightweight-charts v4** |

---

## 2. 상세 구현 내역

### 2.1 백엔드 데이터 확장 (trader.py)

#### A. OHLC + 지표 시계열 데이터 추가

`_compute_indicators()` 함수에 캔들스틱 및 서브차트용 60봉 시계열 데이터를 추가했습니다.

```
기존 데이터:
  chart_close, chart_time (미니 라인차트용)

추가된 데이터:
  ┌── 캔들스틱용 ──────────────────┐
  │ chart_open   : 시가 60봉 배열    │
  │ chart_high   : 고가 60봉 배열    │
  │ chart_low    : 저가 60봉 배열    │
  │ chart_volume : 거래량 60봉 배열   │
  │ chart_time_iso : ISO 타임스탬프  │
  └────────────────────────────────┘
  ┌── 지표 오버레이 시계열 ──────────┐
  │ chart_bb_upper/mid/lower : BB밴드 3선 │
  │ chart_ema3/ema8/ema21 : EMA 3선      │
  │ chart_vwap : VWAP 선                  │
  │ chart_rsi : RSI(7) 히스토리           │
  │ chart_stoch_k/d : StochRSI K/D 선    │
  │ chart_vol_avg : 평균 거래량           │
  └──────────────────────────────────────┘
```

**총 15개 시계열 배열** 추가 (각 60봉)

#### B. 매매 트리거 요약 (trigger_summary) 추가

`_build_trigger_summary()` 신규 함수를 추가하여 각 전략의 조건 충족 상태를 실시간으로 추적합니다.

```
trigger_summary 구조:
├── strategies[] — 4개 전략별 조건 상태
│   ├── RSI+BB (가중치 30%)
│   │   ├── RSI < 30         → ✅/❌ (현재: 28.5)
│   │   ├── BB%B < 15%       → ✅/❌ (현재: 12.3%)
│   │   └── RSI 반등 중      → ✅/❌ (상승/하락)
│   ├── VWAP+Volume (가중치 25%)
│   │   ├── 가격 > VWAP      → ✅/❌
│   │   ├── VWAP 상향돌파    → ✅/❌
│   │   └── 거래량 ≥ 1.5x   → ✅/❌
│   ├── StochRSI (가중치 25%)
│   │   ├── K or D < 25      → ✅/❌
│   │   └── K선 D선 상향교차  → ✅/❌
│   └── EMA Cross (가중치 20%)
│       ├── EMA3>EMA8 교차   → ✅/❌
│       └── 가격 > EMA21     → ✅/❌
└── ensemble — 앙상블 최종 판단
    ├── buy_votes / total_strategies
    ├── buy_weight (가중 신뢰도)
    ├── trend (up/down/neutral)
    └── final_signal (BUY/SELL/HOLD)
```

#### C. _analyze_market() 연동

`_analyze_market()` 메서드에서 `trigger_summary`를 계산하여 `_last_market_analysis` 캐시에 포함시킵니다. 대시보드가 `/api/market-watch` API를 호출하면 이 데이터가 함께 전달됩니다.

---

### 2.2 프론트엔드 대시보드 전면 업그레이드 (dashboard.py)

#### A. 차트 라이브러리 추가

```html
<!-- 기존 -->
<script src="chart.js@4.4.1"></script>

<!-- 추가 -->
<script src="lightweight-charts@4.1.1"></script>
```

TradingView lightweight-charts v4는 금융 차트 전문 라이브러리로, 프로 수준의 캔들스틱 차트를 제공합니다. Chart.js는 Performance/Strategy 탭에서 계속 사용합니다.

#### B. Market Watch 확장형 카드 시스템

기존 고정형 카드 → **클릭하면 확장되는 상세 패널** 구조로 변경:

```
[접힌 상태] (기존과 유사)
┌─────────────────────────────────┐
│ KRW-BTC         Uptrend         │
│ 102,548,000 KRW  Ensemble: HOLD │
│ ═══ 미니 라인차트 (80px) ═══     │
│ rsi_bb: HOLD  vwap: HOLD  ...   │
│ ▐ RSI(7) ════░══════════▌  45.2 │
│ ▐ BB%B  ═░═════════════▌  12.3  │
│        클릭하면 상세 차트 열기      │
└─────────────────────────────────┘

[확장 상태] (전체 너비 차지)
┌─────────────────────────────────────────────────┐
│ KRW-BTC                              Uptrend    │
│ 102,548,000 KRW                Ensemble: HOLD   │
│ ═══ 미니 라인차트 ═══                              │
│ rsi_bb: HOLD  vwap: HOLD  stoch: HOLD  ema: HOLD│
│ ▐ 게이지 바들 ▌                                    │
│                                                   │
│ ┌─── 캔들스틱 메인 차트 (300px) ─────────────────┐ │
│ │  ╱╲                                            │ │
│ │ ╱  ╲  ╱╲  ── BB상단 (보라점선)                  │ │
│ │╱    ╲╱  ╲ ── EMA3 (주황) EMA8 (노랑)           │ │
│ │          ╲── EMA21 (파랑)                       │ │
│ │           ── VWAP (연초록)                       │ │
│ │            ── BB하단 (보라점선)                   │ │
│ └─────────────────────────────────────────────── │ │
│                                                   │
│ ┌ RSI(7) ─┐ ┌ StochRSI ─┐ ┌ Volume ──┐          │
│ │ ──70──  │ │ ──75──    │ │ █ █ █ █  │          │
│ │ ~~~~~   │ │  K ───    │ │ █ █ █ █  │          │
│ │ ──30──  │ │  D ---    │ │ ─1.5x─   │          │
│ │ 100px   │ │ ──25──    │ │ 80px     │          │
│ └─────────┘ └──────────┘ └──────────┘          │
│                                                   │
│ ┌─── 매매 조건 체크리스트 ────────────────────────┐ │
│ │ RSI+BB (가중치 30%)                             │ │
│ │  ✅ RSI < 30 (현재: 28.5)                       │ │
│ │  ✅ BB%B < 15% (현재: 12.3%)                    │ │
│ │  ❌ RSI 반등 중 (하락 중)                        │ │
│ │  → 2/3 충족, 미발동                              │ │
│ │                                                 │ │
│ │ VWAP+Volume (25%) | StochRSI (25%) | EMA (20%) │ │
│ │   ... (각 전략별 조건 표시)                       │ │
│ │                                                 │ │
│ │ ┌── 앙상블 최종 판단 ──────────────────┐         │ │
│ │ │ BUY 투표: 1/4 전략 (최소 2개 필요)    │         │ │
│ │ │ 가중 신뢰도: 0.18 (최소 0.30 필요)    │         │ │
│ │ │ 추세: 상승중 ✅                       │         │ │
│ │ │ → ⚪ HOLD (매수 조건 부족)            │         │ │
│ │ └──────────────────────────────────── │         │ │
│ └─────────────────────────────────────────────── │ │
└─────────────────────────────────────────────────┘
```

#### C. 캔들스틱 메인 차트 상세

TradingView lightweight-charts로 구현한 메인 차트의 오버레이:

| 오버레이 | 색상 | 스타일 | 용도 |
|---------|------|--------|------|
| 캔들스틱 | 초록(양봉)/빨강(음봉) | 실선 | OHLC 가격 |
| BB 상단/하단 | 보라색 40% | 점선 | 볼린저밴드 범위 |
| BB 중앙선 | 보라색 30% | 파선 | 20봉 이동평균 |
| EMA 3 | 주황색 | 실선 | 단기 추세 |
| EMA 8 | 노란색 | 실선 | 중기 추세 |
| EMA 21 | 파란색 | 실선 | 장기 추세 |
| VWAP | 연초록 60% | 파선 | 거래량가중평균가 |

#### D. 서브차트 3종

Chart.js로 구현한 서브차트:

| 서브차트 | 높이 | 내용 | 임계선 |
|---------|------|------|--------|
| RSI(7) | 100px | 보라색 RSI 라인 | 30(초록점선), 70(빨강점선) |
| StochRSI | 100px | K선(파랑) + D선(주황점선) | 25(초록점선), 75(빨강점선) |
| Volume | 80px | 막대(파랑/노랑서지) | 1.5x 평균(노랑점선) |

#### E. Guide 탭 대폭 확장

**새로 추가된 섹션들:**

1. **실시간 상태 해석** (guide-live)
   - 각 코인별 "왜 지금 매매를 안 하는지" 실시간 설명
   - 예: "KRW-BTC — HOLD — 전략 동의 부족 (0/2개), 추세 비상승 (횡보)"
   - 5초마다 자동 업데이트

2. **앙상블 투표 플로우차트** (guide-flow)
   - 7단계 의사결정 과정을 텍스트 기반 플로우차트로 시각화
   - 각 단계별 YES/NO 분기와 HOLD 사유 표시

3. **전략별 상세 설명 강화**
   - 기존: 매수/매도 조건만 나열
   - 추가: 신뢰도 계산 공식, 조건 충족 필요 개수, 가중치 명시

4. **상세 차트 읽는 법**
   - 캔들스틱 색상 의미, 각 오버레이 선 설명
   - 서브차트별 읽는 법 (RSI/StochRSI/Volume)

5. **매매 조건 체크리스트 읽는 법**
   - ✅/❌ 의미, 전략별→앙상블 판단 흐름 설명

---

## 3. 기술 아키텍처

### 3.1 데이터 흐름도

```
[업비트 API]
    │
    ▼ (1분봉 200개)
[ScalpTrader._analyze_market()]
    │
    ├──▶ [EnsembleStrategy.analyze()] ──▶ 4개 전략 시그널 + 투표
    │
    ├──▶ [_compute_indicators()] ──▶ 게이지 값 + 15개 시계열 배열
    │
    ├──▶ [_build_trigger_summary()] ──▶ 조건 체크리스트 + 앙상블 판단
    │
    └──▶ _last_market_analysis 캐시에 저장
              │
              ▼
[FastAPI /api/market-watch] ──▶ JSON 응답
              │
              ▼
[브라우저 JavaScript (5초 폴링)]
    │
    ├──▶ lightweight-charts: 캔들스틱 + 오버레이
    ├──▶ Chart.js: RSI/StochRSI/Volume 서브차트
    ├──▶ DOM: 게이지 바 + 트리거 체크리스트
    └──▶ DOM: Guide 실시간 상태 해석
```

### 3.2 API 응답 구조 변경

`GET /api/market-watch` 응답의 `indicators` 필드가 확장되었습니다:

```json
{
  "KRW-BTC": {
    "market": "KRW-BTC",
    "price": 102548000,
    "trend": "up",
    "ensemble_signal": "HOLD",
    "strategy_signals": [...],
    "indicators": {
      "rsi": 45.2,
      "bb_pctb": 0.523,
      "stoch_k": 62.1,
      "stoch_d": 58.3,
      "chart_open": [102300000, ...],      // NEW: 60개
      "chart_high": [102600000, ...],      // NEW: 60개
      "chart_low": [102100000, ...],       // NEW: 60개
      "chart_volume": [0.8523, ...],       // NEW: 60개
      "chart_rsi": [42.1, 43.5, ...],     // NEW: 60개
      "chart_bb_upper": [103200000, ...],  // NEW: 60개
      "chart_bb_mid": [102500000, ...],    // NEW: 60개
      "chart_bb_lower": [101800000, ...],  // NEW: 60개
      "chart_ema3": [102550000, ...],      // NEW: 60개
      "chart_ema8": [102480000, ...],      // NEW: 60개
      "chart_ema21": [102350000, ...],     // NEW: 60개
      "chart_vwap": [102420000, ...],      // NEW: 60개
      "chart_stoch_k": [55.2, ...],       // NEW: 60개
      "chart_stoch_d": [52.8, ...],       // NEW: 60개
      "chart_vol_avg": [0.6234, ...],     // NEW: 60개
      ...
    },
    "trigger_summary": {                   // NEW: 전체 신규
      "strategies": [
        {
          "name": "RSI+BB",
          "weight": 30,
          "conditions": [
            {"label": "RSI < 30", "met": false, "current": "현재: 45.2"},
            ...
          ],
          "met_count": 1,
          "total_count": 3,
          "would_fire": false
        },
        ...
      ],
      "ensemble": {
        "buy_votes": 0,
        "total_strategies": 4,
        "min_agreement": 2,
        "buy_weight": 0,
        "min_confidence": 0.3,
        "trend": "up",
        "final_signal": "HOLD",
        "final_reason": "No consensus..."
      }
    }
  }
}
```

---

## 4. 앙상블 투표 시스템 상세 작동 원리

### 4.1 전체 흐름

```
[1단계] 4개 전략 독립 분석
  각 전략이 1분봉 데이터를 받아 BUY / SELL / HOLD 판단
  RSI+BB (30%) │ VWAP+Vol (25%) │ StochRSI (25%) │ EMA Cross (20%)
        ↓               ↓               ↓               ↓

[2단계] 쿨다운 체크
  마지막 거래 후 8분(=8사이클×60초) 경과했는가?
  → YES: 다음 단계  → NO: HOLD (쿨다운 대기)

[3단계] 변동성 레짐 체크
  현재 ATR이 최근 60분 ATR 분포의 20~90 퍼센타일 범위인가?
  → YES: 다음 단계  → NO: HOLD (변동성 부적합)

[4단계] 투표 집계
  BUY 투표 수 ≥ 2개? (MIN_AGREEMENT)
  → YES: 다음 단계  → NO: HOLD (합의 부족)

[5단계] 신뢰도 검증
  가중 합산 신뢰도 = Σ(가중치 × 개별 신뢰도)
  이 값이 ≥ 0.30?
  → YES: 다음 단계  → NO: HOLD (신뢰도 부족)

[6단계] 추세 필터 - EMA50 기울기
  EMA(50) 최근 10봉 기울기 > +0.03%?
  → YES: 다음 단계  → NO: HOLD (하락/횡보 추세)

[7단계] 가격 위치 필터
  현재 가격 > EMA(50)?
  → YES: ✅ BUY 실행!  → NO: HOLD (가격이 추세선 아래)
```

### 4.2 개별 전략 매수 조건 상세

#### 전략 1: RSI + Bollinger Band (rsi_bb) — 가중치 30%

**원리**: 가격이 통계적으로 "너무 싸다"는 구간에서 반등이 시작될 때 매수

| 조건 | 임계값 | 현재 예시 | 설명 |
|------|--------|----------|------|
| RSI < 30 | RSI_OVERSOLD=30 | RSI=28.5 ✅ | 최근 7분간 하락 압도적 |
| BB%B < 15% | 0.15 | BB%B=12.3% ✅ | 볼린저밴드 하단 근처 |
| RSI 반등 중 | prev_rsi < cur_rsi | 26→28.5 ✅ | 하락 멈추고 상승 시작 |

**3개 모두 충족 시 BUY**. 신뢰도 = min(1.0, (30-RSI)/30 + 0.2)

#### 전략 2: VWAP + Volume (vwap_volume) — 가중치 25%

**원리**: 거래량 급등과 함께 기관 기준선(VWAP)을 돌파하면 강한 추세 시작

| 조건 | 임계값 | 현재 예시 | 설명 |
|------|--------|----------|------|
| VWAP 상향돌파 | 최근 2봉 내 | 돌파! ✅ | 가격이 VWAP 아래→위로 |
| VWAP 위 유지 | close > VWAP | 위 ✅ | 돌파 후 유지 확인 |
| 거래량 ≥ 1.5x | VOL_SURGE=1.5 | 2.1x ✅ | 평균의 1.5배 이상 |

**3개 모두 충족 시 BUY**. 신뢰도 = max(0.3, min(1.0, vol_ratio/3 + margin×100))

#### 전략 3: Stochastic RSI (stoch_rsi) — 가중치 25%

**원리**: RSI의 RSI에서 과매도 구간 골든크로스를 포착

| 조건 | 임계값 | 현재 예시 | 설명 |
|------|--------|----------|------|
| K or D < 25 | STOCH_OVERSOLD=25 | K=18.5 ✅ | 과매도 구간 진입 |
| K선 D선 상향교차 | K_prev≤D_prev, K_now>D_now | 교차! ✅ | 골든크로스 |

**2개 모두 충족 시 BUY**. 신뢰도 = max(0.3, min(1.0, (25-min(K,D))/25))

#### 전략 4: EMA Crossover (ema_cross) — 가중치 20%

**원리**: 단기 이동평균이 중기를 돌파하며 추세 전환 확인

| 조건 | 임계값 | 현재 예시 | 설명 |
|------|--------|----------|------|
| EMA3 > EMA8 교차 | fast_prev≤slow_prev, fast_now>slow_now | 교차! ✅ | 골든크로스 |
| 가격 > EMA21 | close > EMA(21) | 위 ✅ | 중기 상승추세 확인 |

**2개 모두 충족 시 BUY**. 신뢰도 = max(0.3, min(1.0, (EMA3-EMA8)/EMA8 × 500))

### 4.3 가중 투표 계산 예시

```
상황: BTC 1분봉 분석 결과

  rsi_bb     → BUY (confidence=0.72)   가중치=30%
  vwap_volume → BUY (confidence=0.55)   가중치=25%
  stoch_rsi  → HOLD (confidence=0)      가중치=25%
  ema_cross  → BUY (confidence=0.45)    가중치=20%

투표 집계:
  BUY 투표: 3개 ≥ 2개 (MIN_AGREEMENT) ✅
  가중 신뢰도 = 0.30×0.72 + 0.25×0.55 + 0.20×0.45
             = 0.216 + 0.1375 + 0.09
             = 0.4435 ≥ 0.30 ✅

추세 필터:
  EMA50 기울기: +0.05% (상승) ✅
  가격 > EMA50: YES ✅

결과: ✅ BUY 실행! (신뢰도 0.44, 3/4 전략 동의)
```

---

## 5. 대시보드 v2.0 기능 목록

### 5.1 Real-time 탭

| 기능 | 설명 | 업데이트 주기 |
|------|------|-------------|
| Summary Cards | 잔고, 일일PnL, 수수료, 승률, 총매매, 서킷브레이커 | 5초 |
| Market Watch 카드 | 가격, 추세, 앙상블 시그널, 전략 시그널 | 5초 |
| 지표 게이지 바 | RSI, BB%B, StochRSI K, Volume, EMA, VWAP | 5초 |
| **캔들스틱 차트** (NEW) | OHLC + BB/EMA/VWAP 오버레이 | 5초 |
| **RSI 서브차트** (NEW) | RSI(7) 라인 + 30/70 임계선 | 5초 |
| **StochRSI 서브차트** (NEW) | K/D 라인 + 25/75 임계선 | 5초 |
| **Volume 서브차트** (NEW) | 거래량 막대 + 서지 라인 | 5초 |
| **조건 체크리스트** (NEW) | 전략별 ✅/❌ + 앙상블 판단 | 5초 |
| Open Positions | 포지션 상세 (진입가, 현재가, PnL, SL/TP) | 5초 |

### 5.2 Performance 탭

| 기능 | 설명 |
|------|------|
| 기간 필터 | Today / 7 Days / 30 Days / All Time |
| 통계 카드 | 총PnL, 승률, Profit Factor, MDD, 수수료, 최고/최저 거래 |
| Equity Curve | 누적 PnL 꺽은선 차트 |
| Daily PnL | 일별 PnL 막대 차트 |
| Exit Types | 종료 유형별 도넛 차트 |

### 5.3 Strategy 탭

| 기능 | 설명 |
|------|------|
| Weight Radar | 4개 전략 가중치 레이더 차트 |
| Strategy Table | 전략별 가중치, 거래수, 승수, 승률, EMA 승률 |

### 5.4 Trade History 탭

| 기능 | 설명 |
|------|------|
| 필터 | 마켓별, 종료유형별 필터링 |
| 페이지네이션 | 50건 단위 페이징 |
| CSV 내보내기 | 필터 적용된 거래 내역 CSV 다운로드 |

### 5.5 Guide 탭 (대폭 확장)

| 기능 | 설명 |
|------|------|
| **실시간 상태 해석** (NEW) | "왜 지금 매매를 안 하는지" 코인별 실시간 설명 |
| **앙상블 플로우차트** (NEW) | 7단계 의사결정 과정 시각화 |
| 전략별 상세 설명 (강화) | 신뢰도 공식, 조건 개수, 가중치 명시 |
| **상세 차트 읽는 법** (NEW) | 캔들스틱/서브차트 읽는 법 |
| **체크리스트 읽는 법** (NEW) | 트리거 조건 체크리스트 해석 가이드 |
| 손절/익절 시스템 (강화) | 시그널 매도, 수수료 정보 추가 |
| 게이지 바 읽는 법 | 기존 유지 |

---

## 6. 검증 결과

### 6.1 구문 검증
```
✅ trader.py: AST 파싱 성공
✅ dashboard.py: AST 파싱 성공
✅ scalper.dashboard import 성공
✅ scalper.trader._compute_indicators import 성공
✅ scalper.trader._build_trigger_summary import 성공
```

### 6.2 실행 검증
```
✅ python -m scalper.run --dashboard → 서버 시작 성공 (port 8081)
✅ POST /api/bot/start → 봇 시작 성공
✅ GET /api/market-watch → 3개 마켓 데이터 정상 수신
✅ OHLC 캔들 데이터: 60봉씩 정상 (BTC, ETH, XRP)
✅ 지표 시계열: RSI, BB, EMA, VWAP, StochRSI, VolAvg 각 60개
✅ trigger_summary: 4개 전략, 조건 충족 상태 정상
✅ 앙상블 판단: 투표, 추세, 최종 시그널 정상
✅ 서버 에러 없음 (전체 200 OK)
```

### 6.3 API 데이터 크기
- 기존 market-watch 응답: ~2KB/마켓
- 신규 market-watch 응답: ~8KB/마켓 (시계열 데이터 포함)
- 총 3마켓 기준: ~24KB/응답 (5초 폴링, 네트워크 부담 미미)

---

## 7. 향후 계획

### 즉시 (이번 주)
- [ ] 대시보드 실제 사용 피드백 수집
- [ ] 차트 성능 최적화 (데이터 diff 업데이트)

### 단기 (1~2주)
- [ ] WebSocket 실시간 스트리밍 (5초 폴링 → 실시간)
- [ ] 차트 시간범위 선택 (5분/15분/1시간)
- [ ] 백테스트 결과 차트 통합

### 중기 (1개월)
- [ ] 모바일 반응형 최적화
- [ ] 다크/라이트 테마 전환
- [ ] 알림 설정 UI

---

*본 보고서는 2026-02-14 CryptoBot 대시보드 v2.0 업그레이드 작업을 기록한 것입니다.*
