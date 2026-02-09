"""
이동평균선 전략

전략 로직:
1. 단기 이평선(5)이 장기 이평선(20)을 상향 돌파 (골든크로스) → 매수
2. 단기 이평선이 장기 이평선을 하향 돌파 (데드크로스) → 매도
3. 60일선과 120일선을 추세 필터로 사용

정배열(5>20>60>120): 강한 상승 추세
역배열(5<20<60<120): 강한 하락 추세
"""
import pandas as pd

from base_strategy import BaseStrategy, Signal


class MovingAverageStrategy(BaseStrategy):
    """이동평균선 전략"""

    def __init__(self, config: dict = None):
        default_config = {
            "ma_short": 5,
            "ma_mid": 20,
            "ma_long": 60,
            "ma_very_long": 120,
        }
        merged_config = {**default_config, **(config or {})}
        super().__init__("MovingAverage", merged_config)

    def analyze(self, df: pd.DataFrame, symbol: str) -> Signal:
        """이동평균선 분석"""
        if len(df) < self.config["ma_very_long"] + 5:
            return Signal(Signal.HOLD, symbol, 0.0, "데이터 부족")

        df = df.copy()
        df["ma_short"] = df["close"].rolling(window=self.config["ma_short"]).mean()
        df["ma_mid"] = df["close"].rolling(window=self.config["ma_mid"]).mean()
        df["ma_long"] = df["close"].rolling(window=self.config["ma_long"]).mean()
        df["ma_vlong"] = df["close"].rolling(window=self.config["ma_very_long"]).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        ma_s = latest["ma_short"]
        ma_m = latest["ma_mid"]
        ma_l = latest["ma_long"]
        ma_vl = latest["ma_vlong"]
        prev_s = prev["ma_short"]
        prev_m = prev["ma_mid"]

        # 골든크로스: 단기선이 중기선 상향 돌파
        if prev_s <= prev_m and ma_s > ma_m:
            # 정배열에 가까울수록 높은 신뢰도
            if ma_s > ma_m > ma_l:
                confidence = 0.85
                reason = f"골든크로스(정배열근접) MA5:{ma_s:,.0f} > MA20:{ma_m:,.0f} > MA60:{ma_l:,.0f}"
            else:
                confidence = 0.65
                reason = f"골든크로스 MA5:{ma_s:,.0f} > MA20:{ma_m:,.0f}"
            return Signal(Signal.BUY, symbol, confidence, reason)

        # 데드크로스: 단기선이 중기선 하향 돌파
        if prev_s >= prev_m and ma_s < ma_m:
            if ma_s < ma_m < ma_l:
                confidence = 0.85
                reason = f"데드크로스(역배열근접) MA5:{ma_s:,.0f} < MA20:{ma_m:,.0f} < MA60:{ma_l:,.0f}"
            else:
                confidence = 0.65
                reason = f"데드크로스 MA5:{ma_s:,.0f} < MA20:{ma_m:,.0f}"
            return Signal(Signal.SELL, symbol, confidence, reason)

        # 완전 정배열
        if ma_s > ma_m > ma_l > ma_vl:
            return Signal(Signal.BUY, symbol, 0.55, f"정배열 유지 MA5>MA20>MA60>MA120")

        # 완전 역배열
        if ma_s < ma_m < ma_l < ma_vl:
            return Signal(Signal.SELL, symbol, 0.55, f"역배열 유지 MA5<MA20<MA60<MA120")

        return Signal(
            Signal.HOLD, symbol, 0.0,
            f"관망(MA5:{ma_s:,.0f}, MA20:{ma_m:,.0f}, MA60:{ma_l:,.0f})"
        )
