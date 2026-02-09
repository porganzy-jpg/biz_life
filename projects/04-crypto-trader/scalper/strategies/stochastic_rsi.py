"""
Stochastic RSI Momentum Strategy.

Buy:  K(5) golden crosses D(3) in oversold zone (<20)
Sell: K(5) dead crosses D(3) in overbought zone (>80)
"""
import pandas as pd

from .. import config
from .base import BaseScalpStrategy, ScalpSignal, SignalType


class StochasticRsiStrategy(BaseScalpStrategy):
    name = "stoch_rsi"

    def analyze(self, df: pd.DataFrame) -> ScalpSignal:
        min_rows = config.STOCH_RSI_PERIOD + config.STOCH_K_PERIOD + config.STOCH_D_PERIOD + 5
        if not self._validate_df(df, min_rows=min_rows):
            return self._hold("insufficient data")

        close = df["close"]

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta.clip(upper=0))
        avg_gain = gain.rolling(window=config.STOCH_RSI_PERIOD, min_periods=config.STOCH_RSI_PERIOD).mean()
        avg_loss = loss.rolling(window=config.STOCH_RSI_PERIOD, min_periods=config.STOCH_RSI_PERIOD).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))

        # Stochastic RSI
        rsi_min = rsi.rolling(window=config.STOCH_RSI_PERIOD).min()
        rsi_max = rsi.rolling(window=config.STOCH_RSI_PERIOD).max()
        rsi_range = rsi_max - rsi_min
        stoch_rsi = ((rsi - rsi_min) / rsi_range.replace(0, 1e-10)) * 100

        # K and D lines
        k_line = stoch_rsi.rolling(window=config.STOCH_K_PERIOD).mean()
        d_line = k_line.rolling(window=config.STOCH_D_PERIOD).mean()

        k_now = k_line.iloc[-1]
        k_prev = k_line.iloc[-2]
        d_now = d_line.iloc[-1]
        d_prev = d_line.iloc[-2]

        if pd.isna(k_now) or pd.isna(d_now) or pd.isna(k_prev) or pd.isna(d_prev):
            return self._hold("indicators not ready")

        # BUY: K crosses above D in oversold zone
        golden_cross = k_prev <= d_prev and k_now > d_now
        in_oversold = k_now < config.STOCH_OVERSOLD or d_now < config.STOCH_OVERSOLD

        if golden_cross and in_oversold:
            confidence = min(1.0, (config.STOCH_OVERSOLD - min(k_now, d_now)) / config.STOCH_OVERSOLD)
            return ScalpSignal(
                signal=SignalType.BUY,
                strategy_name=self.name,
                confidence=max(0.3, confidence),
                reason=f"StochRSI golden cross (K={k_now:.1f}, D={d_now:.1f}) in oversold",
                metadata={"k": k_now, "d": d_now},
            )

        # SELL: K crosses below D in overbought zone
        dead_cross = k_prev >= d_prev and k_now < d_now
        in_overbought = k_now > config.STOCH_OVERBOUGHT or d_now > config.STOCH_OVERBOUGHT

        if dead_cross and in_overbought:
            confidence = min(1.0, (max(k_now, d_now) - config.STOCH_OVERBOUGHT) / (100 - config.STOCH_OVERBOUGHT))
            return ScalpSignal(
                signal=SignalType.SELL,
                strategy_name=self.name,
                confidence=max(0.3, confidence),
                reason=f"StochRSI dead cross (K={k_now:.1f}, D={d_now:.1f}) in overbought",
                metadata={"k": k_now, "d": d_now},
            )

        return self._hold(f"K={k_now:.1f}, D={d_now:.1f}")
