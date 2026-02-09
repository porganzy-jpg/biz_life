"""
RSI(7) + Bollinger Band(20) Mean Reversion Scalping Strategy.

Buy:  RSI 과매도권 + BB 하단 근접 + RSI 반등 확인
Sell: RSI 과매수권 + BB 상단 근접 + RSI 하락 확인
"""
import pandas as pd

from .. import config
from .base import BaseScalpStrategy, ScalpSignal, SignalType


class RsiBbScalpStrategy(BaseScalpStrategy):
    name = "rsi_bb"

    def analyze(self, df: pd.DataFrame) -> ScalpSignal:
        if not self._validate_df(df, min_rows=config.BB_PERIOD + 5):
            return self._hold("insufficient data")

        close = df["close"]

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta.clip(upper=0))
        avg_gain = gain.rolling(window=config.RSI_PERIOD, min_periods=config.RSI_PERIOD).mean()
        avg_loss = loss.rolling(window=config.RSI_PERIOD, min_periods=config.RSI_PERIOD).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))

        # Bollinger Bands
        bb_mid = close.rolling(window=config.BB_PERIOD).mean()
        bb_std = close.rolling(window=config.BB_PERIOD).std()
        bb_upper = bb_mid + config.BB_STD_DEV * bb_std
        bb_lower = bb_mid - config.BB_STD_DEV * bb_std

        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        current_close = close.iloc[-1]
        current_upper = bb_upper.iloc[-1]
        current_lower = bb_lower.iloc[-1]
        bb_mid_now = bb_mid.iloc[-1]

        if pd.isna(current_rsi) or pd.isna(current_lower) or pd.isna(prev_rsi):
            return self._hold("indicators not ready")

        # BB %B 위치 (0=하단, 1=상단)
        bb_width = current_upper - current_lower
        bb_pctb = (current_close - current_lower) / bb_width if bb_width > 0 else 0.5

        # BUY: RSI 과매도 + BB 하단 근접 + RSI 반등 시작
        rsi_oversold = current_rsi < config.RSI_OVERSOLD
        near_bb_lower = bb_pctb < 0.15  # BB 하단 15% 이내
        rsi_recovering = current_rsi > prev_rsi  # RSI 반등 확인

        if rsi_oversold and near_bb_lower and rsi_recovering:
            confidence = min(1.0, (config.RSI_OVERSOLD - current_rsi) / config.RSI_OVERSOLD + 0.2)
            return ScalpSignal(
                signal=SignalType.BUY,
                strategy_name=self.name,
                confidence=confidence,
                reason=f"RSI={current_rsi:.1f} recovering, BB%B={bb_pctb:.2f}",
                metadata={"rsi": current_rsi, "bb_pctb": bb_pctb, "close": current_close},
            )

        # SELL: RSI 과매수 + BB 상단 근접 + RSI 하락 시작
        rsi_overbought = current_rsi > config.RSI_OVERBOUGHT
        near_bb_upper = bb_pctb > 0.85  # BB 상단 85% 이상
        rsi_declining = current_rsi < prev_rsi  # RSI 하락 확인

        if rsi_overbought and near_bb_upper and rsi_declining:
            confidence = min(1.0, (current_rsi - config.RSI_OVERBOUGHT) / (100 - config.RSI_OVERBOUGHT) + 0.2)
            return ScalpSignal(
                signal=SignalType.SELL,
                strategy_name=self.name,
                confidence=confidence,
                reason=f"RSI={current_rsi:.1f} declining, BB%B={bb_pctb:.2f}",
                metadata={"rsi": current_rsi, "bb_pctb": bb_pctb, "close": current_close},
            )

        return self._hold(f"RSI={current_rsi:.1f}, BB%B={bb_pctb:.2f}")
