"""
듀얼 모멘텀 전략 (Gary Antonacci)

절대 모멘텀 + 상대 모멘텀 결합
- 절대 모멘텀: 자산 자체의 수익률 > 0 (안전자산 대비)
- 상대 모멘텀: 다른 자산 대비 우위
"""
import pandas as pd
import numpy as np
from base_strategy import BaseStockStrategy, StockSignal


class DualMomentumStrategy(BaseStockStrategy):
    """듀얼 모멘텀 전략"""

    name = "듀얼모멘텀"
    weight = 0.15

    def __init__(self, lookback: int = 60, risk_free_annual: float = 3.5):
        self.lookback = lookback
        # 일 단위 무위험 수익률 (한국 기준금리 기반)
        self.risk_free_daily = (1 + risk_free_annual / 100) ** (1 / 252) - 1

    def analyze(self, df: pd.DataFrame) -> StockSignal:
        if len(df) < self.lookback + 10:
            return StockSignal("HOLD", 50, "데이터 부족")

        close = df["close"]
        current = close.iloc[-1]
        past = close.iloc[-self.lookback]

        # 절대 모멘텀: 기간 수익률 vs 무위험 수익률
        actual_return = (current / past - 1)
        rf_return = self.risk_free_daily * self.lookback
        excess_return = actual_return - rf_return

        # 변동성 조정 수익률 (Sharpe 유사)
        daily_returns = close.pct_change().dropna().tail(self.lookback)
        volatility = daily_returns.std() * np.sqrt(252)
        sharpe_like = (actual_return * (252 / self.lookback)) / volatility if volatility > 0 else 0

        # 추세 강도 (ADX 대용 - 방향 일관성)
        up_days = (daily_returns > 0).sum()
        trend_consistency = up_days / len(daily_returns)

        # 종합 점수
        score = 50

        # 절대 모멘텀 (+/- 15점)
        if excess_return > 0:
            score += min(15, excess_return * 100)
        else:
            score += max(-15, excess_return * 100)

        # 샤프 비율 (+/- 15점)
        score += max(-15, min(15, sharpe_like * 7.5))

        # 추세 일관성 (+/- 10점)
        score += (trend_consistency - 0.5) * 20

        score = max(10, min(90, score))

        if score >= 65 and excess_return > 0:
            return StockSignal("BUY", round(score, 1),
                               f"듀얼모멘텀 BUY (초과수익:{excess_return*100:+.1f}% Sharpe:{sharpe_like:.1f})")
        elif score <= 35 or excess_return < -0.05:
            return StockSignal("SELL", round(score, 1),
                               f"듀얼모멘텀 SELL (초과수익:{excess_return*100:+.1f}%)")
        else:
            return StockSignal("HOLD", round(score, 1),
                               f"듀얼모멘텀 중립 (Sharpe:{sharpe_like:.1f})")
