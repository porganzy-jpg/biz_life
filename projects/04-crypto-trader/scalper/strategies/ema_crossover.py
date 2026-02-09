"""
EMA(5/13) Crossover Trend Strategy.

Buy:  EMA5 crosses above EMA13 AND price above EMA50
Sell: EMA5 crosses below EMA13 AND price below EMA50
"""
import pandas as pd

from .. import config
from .base import BaseScalpStrategy, ScalpSignal, SignalType


class EmaCrossoverStrategy(BaseScalpStrategy):
    name = "ema_cross"

    def analyze(self, df: pd.DataFrame) -> ScalpSignal:
        if not self._validate_df(df, min_rows=config.EMA_TREND + 5):
            return self._hold("insufficient data")

        close = df["close"]

        ema_fast = close.ewm(span=config.EMA_FAST, adjust=False).mean()
        ema_slow = close.ewm(span=config.EMA_SLOW, adjust=False).mean()
        ema_trend = close.ewm(span=config.EMA_TREND, adjust=False).mean()

        fast_now = ema_fast.iloc[-1]
        fast_prev = ema_fast.iloc[-2]
        slow_now = ema_slow.iloc[-1]
        slow_prev = ema_slow.iloc[-2]
        trend_now = ema_trend.iloc[-1]
        current_close = close.iloc[-1]

        if pd.isna(fast_now) or pd.isna(trend_now):
            return self._hold("indicators not ready")

        above_trend = current_close > trend_now
        below_trend = current_close < trend_now

        # BUY: EMA5 crosses above EMA13 + above EMA50
        golden_cross = fast_prev <= slow_prev and fast_now > slow_now
        if golden_cross and above_trend:
            spread = (fast_now - slow_now) / slow_now
            confidence = min(1.0, spread * 500)
            return ScalpSignal(
                signal=SignalType.BUY,
                strategy_name=self.name,
                confidence=max(0.3, confidence),
                reason=f"EMA golden cross, above EMA{config.EMA_TREND}",
                metadata={"ema_fast": fast_now, "ema_slow": slow_now, "ema_trend": trend_now},
            )

        # SELL: EMA5 crosses below EMA13 + below EMA50
        dead_cross = fast_prev >= slow_prev and fast_now < slow_now
        if dead_cross and below_trend:
            spread = (slow_now - fast_now) / slow_now
            confidence = min(1.0, spread * 500)
            return ScalpSignal(
                signal=SignalType.SELL,
                strategy_name=self.name,
                confidence=max(0.3, confidence),
                reason=f"EMA dead cross, below EMA{config.EMA_TREND}",
                metadata={"ema_fast": fast_now, "ema_slow": slow_now, "ema_trend": trend_now},
            )

        return self._hold(f"EMA5={fast_now:.0f}, EMA13={slow_now:.0f}, trend={'up' if above_trend else 'down'}")
