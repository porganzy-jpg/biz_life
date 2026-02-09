"""
VWAP + Volume Surge Breakout Strategy.

Buy:  최근 2봉 중 VWAP 상향돌파 + 현재 VWAP 위 유지 + 거래량 급등
Sell: 최근 2봉 중 VWAP 하향돌파 + 현재 VWAP 아래 유지 + 거래량 급등

허위 돌파 필터: 돌파 후 VWAP 위(아래) 유지 확인
"""
import pandas as pd

from .. import config
from .base import BaseScalpStrategy, ScalpSignal, SignalType


class VwapVolumeStrategy(BaseScalpStrategy):
    name = "vwap_volume"

    def analyze(self, df: pd.DataFrame) -> ScalpSignal:
        if not self._validate_df(df, min_rows=config.VWAP_PERIOD + 3):
            return self._hold("insufficient data")

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # VWAP calculation
        typical_price = (high + low + close) / 3
        cum_tp_vol = (typical_price * volume).rolling(window=config.VWAP_PERIOD).sum()
        cum_vol = volume.rolling(window=config.VWAP_PERIOD).sum()
        vwap = cum_tp_vol / cum_vol.replace(0, 1e-10)

        # Volume surge detection (최근 2봉 중 하나라도 급등)
        avg_volume = volume.rolling(window=config.VWAP_PERIOD).mean()
        volume_ratio = volume / avg_volume.replace(0, 1e-10)

        current_close = close.iloc[-1]
        prev_close = close.iloc[-2]
        prev2_close = close.iloc[-3]
        current_vwap = vwap.iloc[-1]
        prev_vwap = vwap.iloc[-2]
        prev2_vwap = vwap.iloc[-3]
        vol_ratio_now = volume_ratio.iloc[-1]
        vol_ratio_prev = volume_ratio.iloc[-2]

        if pd.isna(current_vwap) or pd.isna(vol_ratio_now):
            return self._hold("indicators not ready")

        # 최근 2봉 중 거래량 급등이 있었는지
        recent_surge = max(vol_ratio_now, vol_ratio_prev) >= config.VOLUME_SURGE_MULTIPLIER

        # BUY: 최근 2봉 내 상향돌파 + 현재 VWAP 위 유지
        recent_cross_up = (prev2_close <= prev2_vwap and prev_close > prev_vwap) or \
                          (prev_close <= prev_vwap and current_close > current_vwap)
        holding_above = current_close > current_vwap

        if recent_cross_up and holding_above and recent_surge:
            vr = max(vol_ratio_now, vol_ratio_prev)
            # VWAP 위 마진도 반영 (멀수록 확신)
            margin = (current_close - current_vwap) / current_vwap
            confidence = min(1.0, vr / (config.VOLUME_SURGE_MULTIPLIER * 2) + margin * 100)
            return ScalpSignal(
                signal=SignalType.BUY,
                strategy_name=self.name,
                confidence=max(0.3, confidence),
                reason=f"VWAP breakout up, vol={vr:.1f}x, margin={margin*100:.3f}%",
                metadata={"vwap": current_vwap, "vol_ratio": vr},
            )

        # SELL: 최근 2봉 내 하향돌파 + 현재 VWAP 아래 유지
        recent_cross_down = (prev2_close >= prev2_vwap and prev_close < prev_vwap) or \
                            (prev_close >= prev_vwap and current_close < current_vwap)
        holding_below = current_close < current_vwap

        if recent_cross_down and holding_below and recent_surge:
            vr = max(vol_ratio_now, vol_ratio_prev)
            margin = (current_vwap - current_close) / current_vwap
            confidence = min(1.0, vr / (config.VOLUME_SURGE_MULTIPLIER * 2) + margin * 100)
            return ScalpSignal(
                signal=SignalType.SELL,
                strategy_name=self.name,
                confidence=max(0.3, confidence),
                reason=f"VWAP breakdown, vol={vr:.1f}x, margin={margin*100:.3f}%",
                metadata={"vwap": current_vwap, "vol_ratio": vr},
            )

        return self._hold(f"no confirmed VWAP cross (vol={vol_ratio_now:.1f}x)")
