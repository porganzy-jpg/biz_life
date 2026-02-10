"""
모멘텀 전략

최근 N개월 수익률 기반 모멘텀 스코어링
강한 모멘텀 종목 매수, 약한 모멘텀 종목 매도
"""
import pandas as pd
import numpy as np
from base_strategy import BaseStockStrategy, StockSignal


class MomentumStrategy(BaseStockStrategy):
    """모멘텀 전략 (1개월/3개월/6개월 수익률 기반)"""

    name = "모멘텀"
    weight = 0.20

    def __init__(self, short_period: int = 20, mid_period: int = 60, long_period: int = 120):
        self.short_period = short_period
        self.mid_period = mid_period
        self.long_period = long_period

    def analyze(self, df: pd.DataFrame) -> StockSignal:
        if len(df) < self.long_period:
            return StockSignal("HOLD", 50, "데이터 부족")

        close = df["close"]
        current = close.iloc[-1]

        # 각 기간별 수익률
        ret_short = (current / close.iloc[-self.short_period] - 1) * 100 if len(df) >= self.short_period else 0
        ret_mid = (current / close.iloc[-self.mid_period] - 1) * 100 if len(df) >= self.mid_period else 0
        ret_long = (current / close.iloc[-self.long_period] - 1) * 100 if len(df) >= self.long_period else 0

        # 가중 모멘텀 점수 (최근 기간에 더 높은 가중치)
        momentum_score = ret_short * 0.5 + ret_mid * 0.3 + ret_long * 0.2

        # 점수 변환 (0~100)
        # 모멘텀 +20% 이상이면 80점, -20% 이하면 20점
        score = 50 + momentum_score * 1.5
        score = max(10, min(90, score))

        # 가속도 체크 (최근 모멘텀이 중기보다 강한지)
        accelerating = ret_short > ret_mid / (self.mid_period / self.short_period)

        if score >= 65:
            reason = f"강한 모멘텀 (1M:{ret_short:+.1f}% 3M:{ret_mid:+.1f}%)"
            if accelerating:
                reason += " 가속중"
                score = min(90, score + 5)
            return StockSignal("BUY", round(score, 1), reason)
        elif score <= 35:
            return StockSignal("SELL", round(score, 1),
                               f"약한 모멘텀 (1M:{ret_short:+.1f}% 3M:{ret_mid:+.1f}%)")
        else:
            return StockSignal("HOLD", round(score, 1),
                               f"중립 모멘텀 (1M:{ret_short:+.1f}%)")
