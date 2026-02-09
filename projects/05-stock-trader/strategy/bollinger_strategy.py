"""
볼린저밴드 전략 (주식용)
"""
import pandas as pd
from base_strategy import BaseStockStrategy, StockSignal


class BollingerStrategy(BaseStockStrategy):
    def __init__(self, period: int = 20, std: float = 2.0):
        super().__init__("Bollinger", weight=0.15)
        self.period = period
        self.std = std

    def analyze(self, df: pd.DataFrame) -> StockSignal:
        if len(df) < self.period + 5:
            return StockSignal(StockSignal.HOLD, 50, "데이터 부족")

        df = df.copy()
        df["bb_ma"] = df["close"].rolling(self.period).mean()
        df["bb_std"] = df["close"].rolling(self.period).std()
        df["bb_upper"] = df["bb_ma"] + self.std * df["bb_std"]
        df["bb_lower"] = df["bb_ma"] - self.std * df["bb_std"]
        df["bb_pband"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

        latest = df.iloc[-1]
        pband = latest["bb_pband"]

        if pband <= 0.1:
            return StockSignal(StockSignal.BUY, 85, f"BB 하단 ({pband:.2f})")
        elif pband >= 0.9:
            return StockSignal(StockSignal.SELL, 15, f"BB 상단 ({pband:.2f})")
        else:
            score = 50 + (0.5 - pband) * 50
            return StockSignal(StockSignal.HOLD, score, f"BB %B={pband:.2f}")
