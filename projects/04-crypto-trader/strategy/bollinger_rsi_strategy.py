"""
볼린저밴드 + RSI 복합 전략

전략 로직:
1. 볼린저밴드 하단 돌파 + RSI 과매도(30 이하) → 매수 신호
2. 볼린저밴드 상단 돌파 + RSI 과매수(70 이상) → 매도 신호
3. 그 외 → 관망

이 전략은 "평균 회귀" 이론에 기반합니다.
가격이 극단적으로 벗어나면 다시 평균으로 돌아온다는 가정.
"""
import pandas as pd
import ta

from base_strategy import BaseStrategy, Signal


class BollingerRSIStrategy(BaseStrategy):
    """볼린저밴드 + RSI 복합 전략"""

    def __init__(self, config: dict = None):
        default_config = {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
        }
        merged_config = {**default_config, **(config or {})}
        super().__init__("BollingerBand+RSI", merged_config)

    def analyze(self, df: pd.DataFrame, symbol: str) -> Signal:
        """볼린저밴드 + RSI 분석"""
        if len(df) < self.config["bb_period"] + 5:
            return Signal(Signal.HOLD, symbol, 0.0, "데이터 부족")

        # 볼린저밴드 계산
        bb = ta.volatility.BollingerBands(
            close=df["close"],
            window=self.config["bb_period"],
            window_dev=self.config["bb_std"]
        )
        df = df.copy()
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_middle"] = bb.bollinger_mavg()
        df["bb_lower"] = bb.bollinger_lband()
        df["bb_pband"] = bb.bollinger_pband()  # %B 지표

        # RSI 계산
        rsi = ta.momentum.RSIIndicator(
            close=df["close"],
            window=self.config["rsi_period"]
        )
        df["rsi"] = rsi.rsi()

        # 최신 데이터 기준 판단
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        current_price = latest["close"]
        bb_lower = latest["bb_lower"]
        bb_upper = latest["bb_upper"]
        bb_middle = latest["bb_middle"]
        current_rsi = latest["rsi"]

        # 매수 조건: 가격이 볼린저밴드 하단 이하 + RSI 과매도
        if current_price <= bb_lower and current_rsi <= self.config["rsi_oversold"]:
            confidence = min(1.0, (self.config["rsi_oversold"] - current_rsi) / 20 + 0.5)
            return Signal(
                Signal.BUY, symbol, confidence,
                f"BB하단돌파({current_price:,.0f} <= {bb_lower:,.0f}) + RSI과매도({current_rsi:.1f})"
            )

        # 매도 조건: 가격이 볼린저밴드 상단 이상 + RSI 과매수
        if current_price >= bb_upper and current_rsi >= self.config["rsi_overbought"]:
            confidence = min(1.0, (current_rsi - self.config["rsi_overbought"]) / 20 + 0.5)
            return Signal(
                Signal.SELL, symbol, confidence,
                f"BB상단돌파({current_price:,.0f} >= {bb_upper:,.0f}) + RSI과매수({current_rsi:.1f})"
            )

        # 추가 매수 조건: RSI가 매우 낮고 볼린저밴드 중심선 이하
        if current_rsi <= 25 and current_price < bb_middle:
            return Signal(
                Signal.BUY, symbol, 0.6,
                f"RSI극과매도({current_rsi:.1f}) + BB중심선이하"
            )

        # 추가 매도 조건: RSI가 매우 높고 볼린저밴드 중심선 이상
        if current_rsi >= 75 and current_price > bb_middle:
            return Signal(
                Signal.SELL, symbol, 0.6,
                f"RSI극과매수({current_rsi:.1f}) + BB중심선이상"
            )

        return Signal(
            Signal.HOLD, symbol, 0.0,
            f"관망(RSI:{current_rsi:.1f}, Price:{current_price:,.0f}, BB:{bb_lower:,.0f}~{bb_upper:,.0f})"
        )
