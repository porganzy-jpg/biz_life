"""
MACD 전략

전략 로직:
1. MACD 라인이 시그널 라인을 상향 돌파 (골든크로스) → 매수
2. MACD 라인이 시그널 라인을 하향 돌파 (데드크로스) → 매도
3. MACD 히스토그램의 크기로 신호 강도 판단

MACD = 단기 EMA(12) - 장기 EMA(26)
Signal = MACD의 EMA(9)
Histogram = MACD - Signal
"""
import pandas as pd
import ta

from base_strategy import BaseStrategy, Signal


class MACDStrategy(BaseStrategy):
    """MACD 전략"""

    def __init__(self, config: dict = None):
        default_config = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "histogram_threshold": 0,  # 히스토그램 최소 크기
        }
        merged_config = {**default_config, **(config or {})}
        super().__init__("MACD", merged_config)

    def analyze(self, df: pd.DataFrame, symbol: str) -> Signal:
        """MACD 분석"""
        if len(df) < self.config["slow_period"] + self.config["signal_period"] + 5:
            return Signal(Signal.HOLD, symbol, 0.0, "데이터 부족")

        df = df.copy()

        # MACD 계산
        macd_indicator = ta.trend.MACD(
            close=df["close"],
            window_fast=self.config["fast_period"],
            window_slow=self.config["slow_period"],
            window_sign=self.config["signal_period"]
        )
        df["macd"] = macd_indicator.macd()
        df["macd_signal"] = macd_indicator.macd_signal()
        df["macd_hist"] = macd_indicator.macd_diff()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        macd_val = latest["macd"]
        signal_val = latest["macd_signal"]
        hist_val = latest["macd_hist"]
        prev_macd = prev["macd"]
        prev_signal = prev["macd_signal"]

        # 골든크로스: MACD가 시그널을 상향 돌파
        if prev_macd <= prev_signal and macd_val > signal_val:
            confidence = min(1.0, abs(hist_val) / (latest["close"] * 0.001) * 0.5 + 0.5)
            return Signal(
                Signal.BUY, symbol, confidence,
                f"MACD골든크로스(MACD:{macd_val:,.0f} > Signal:{signal_val:,.0f}, Hist:{hist_val:,.0f})"
            )

        # 데드크로스: MACD가 시그널을 하향 돌파
        if prev_macd >= prev_signal and macd_val < signal_val:
            confidence = min(1.0, abs(hist_val) / (latest["close"] * 0.001) * 0.5 + 0.5)
            return Signal(
                Signal.SELL, symbol, confidence,
                f"MACD데드크로스(MACD:{macd_val:,.0f} < Signal:{signal_val:,.0f}, Hist:{hist_val:,.0f})"
            )

        # 추세 강도 표시
        trend = "상승추세" if macd_val > signal_val else "하락추세"
        return Signal(
            Signal.HOLD, symbol, 0.0,
            f"관망({trend}, MACD:{macd_val:,.0f}, Signal:{signal_val:,.0f})"
        )
