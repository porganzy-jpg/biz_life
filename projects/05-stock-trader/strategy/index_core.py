"""
지수 코어 전략 (v4.0) — 절충형: 고정 보유 + 리스크 오버레이

2026-10 재검증 결과 종목선정 신호는 베타 헤지 후 알파가 없었음.
수익의 원천은 시장 자체이므로, 코어를 지수 ETF로 두고 하락 국면 비중만 줄인다.

목표 비중 = BLEND × 1.0 (항상 보유)
          + (1 - BLEND) × [종가 > MA120] × min(1, VOL_TARGET / 20일 실현변동성)

KODEX200 2009-09~2026-10 백테스트 (리밸런스 밴드 10%p, 비용 편도 0.05%):
  CAGR 10.2% / MDD -24.8% / Sharpe 0.55  (단순 보유: 11.8% / -40.8% / 0.50)
"""
import numpy as np
import pandas as pd

SYMBOL = "069500"          # KODEX 200
SYMBOL_NAME = "KODEX 200"
BLEND = 0.5                # 항상 보유하는 비율 (절충형)
MA_WINDOW = 120
VOL_WINDOW = 20
VOL_TARGET = 0.15          # 연환산 목표 변동성
REBALANCE_BAND = 0.10      # 목표 비중과 10%p 넘게 벌어지면 리밸런스
TRADING_DAYS = 245
MIN_HISTORY = MA_WINDOW + 1


def overlay_weight(close: pd.Series) -> pd.Series:
    """리스크 오버레이 비중 (0~1): 추세 필터 × 변동성 타깃"""
    trend_ok = (close > close.rolling(MA_WINDOW).mean()).astype(float)
    realized = close.pct_change().rolling(VOL_WINDOW).std() * np.sqrt(TRADING_DAYS)
    vol_scale = (VOL_TARGET / realized).clip(upper=1.0)
    return (trend_ok * vol_scale).where(realized.notna() & close.rolling(MA_WINDOW).mean().notna())


def target_weight(close: pd.Series, blend: float = BLEND) -> pd.Series:
    """일자별 목표 비중 (0~1). 당일 종가 기준 → 다음 거래일에 집행"""
    return blend + (1 - blend) * overlay_weight(close)


def latest_target(close: pd.Series, blend: float = BLEND) -> dict:
    """가장 최근 종가 기준 목표 비중과 판단 근거"""
    if len(close) < MIN_HISTORY:
        raise ValueError(f"가격 이력 부족: {len(close)}일 (최소 {MIN_HISTORY}일)")
    ma = close.rolling(MA_WINDOW).mean().iloc[-1]
    realized = close.pct_change().rolling(VOL_WINDOW).std().iloc[-1] * np.sqrt(TRADING_DAYS)
    return {
        "date": close.index[-1],
        "close": float(close.iloc[-1]),
        "ma120": float(ma),
        "trend_ok": bool(close.iloc[-1] > ma),
        "realized_vol": float(realized),
        "target": float(target_weight(close, blend).iloc[-1]),
    }


def needs_rebalance(current_w: float, target_w: float) -> bool:
    """
    현재 비중을 목표 비중으로 맞추는 주문을 낼지 결정한다.
    백테스트(index_core_backtest.py)와 실행기(index_core_trader.py)가 공통으로 사용.

    Args:
        current_w: 현재 보유 비중 (0~1, 가격 변동으로 목표에서 떠 있음)
        target_w:  오늘 종가 기준 목표 비중 (0~1, 최소 BLEND)

    Returns:
        True면 목표 비중까지 매매, False면 그대로 둔다.

    참고 (2010~2026, 단순 절대값 밴드):
        밴드 0%p  → 연 158회 매매, MDD -25.6%
        밴드 5%p  → 연 15회,       MDD -25.4%
        밴드 10%p → 연 12회,       MDD -24.8%  ← Sharpe 최고
        밴드 20%p → 연 9회,        MDD -30.6%  (하락 대응 지연)

    비대칭 밴드(축소 3~5%p / 확대 10~15%p)도 비교했으나 CAGR·Sharpe·MDD 모두 대칭 10%p 이하
    → 가장 단순한 대칭 밴드 채택 (2009~2017 / 2018~ 두 구간 모두 동등 이상)
    """
    return abs(target_w - current_w) > REBALANCE_BAND
