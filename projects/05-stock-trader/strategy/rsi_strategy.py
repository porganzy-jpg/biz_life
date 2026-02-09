"""
RSI 전략 (주식용)
"""
import pandas as pd
from base_strategy import BaseStockStrategy, StockSignal


class RSIStrategy(BaseStockStrategy):
    def __init__(self, period: int = 14):
        super().__init__("RSI", weight=0.20)
        self.period = period

    def analyze(self, df: pd.DataFrame) -> StockSignal:
        if len(df) < self.period + 5:
            return StockSignal(StockSignal.HOLD, 50, "데이터 부족")

        df = df.copy()
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.period).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        rsi = df["rsi"].iloc[-1]

        if rsi <= 30:
            score = 80 + (30 - rsi)
            return StockSignal(StockSignal.BUY, min(score, 100), f"RSI 과매도 ({rsi:.1f})")
        elif rsi >= 70:
            score = 20 - (rsi - 70)
            return StockSignal(StockSignal.SELL, max(score, 0), f"RSI 과매수 ({rsi:.1f})")
        else:
            return StockSignal(StockSignal.HOLD, 50, f"RSI={rsi:.1f}")
