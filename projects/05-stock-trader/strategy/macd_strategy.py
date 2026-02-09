"""
MACD 전략 (주식용)
"""
import pandas as pd
from base_strategy import BaseStockStrategy, StockSignal


class MACDStockStrategy(BaseStockStrategy):
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__("MACD", weight=0.20)
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def analyze(self, df: pd.DataFrame) -> StockSignal:
        if len(df) < self.slow + self.signal + 5:
            return StockSignal(StockSignal.HOLD, 50, "데이터 부족")

        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.fast).mean()
        df["ema_slow"] = df["close"].ewm(span=self.slow).mean()
        df["macd"] = df["ema_fast"] - df["ema_slow"]
        df["macd_signal"] = df["macd"].ewm(span=self.signal).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # 골든크로스
        if prev["macd"] <= prev["macd_signal"] and latest["macd"] > latest["macd_signal"]:
            return StockSignal(StockSignal.BUY, 80, "MACD 골든크로스")

        # 데드크로스
        if prev["macd"] >= prev["macd_signal"] and latest["macd"] < latest["macd_signal"]:
            return StockSignal(StockSignal.SELL, 20, "MACD 데드크로스")

        if latest["macd_hist"] > 0:
            return StockSignal(StockSignal.HOLD, 60, "MACD 상승추세")
        else:
            return StockSignal(StockSignal.HOLD, 40, "MACD 하락추세")
