"""
이동평균선 전략 (주식용)
"""
import pandas as pd
from base_strategy import BaseStockStrategy, StockSignal


class MAStockStrategy(BaseStockStrategy):
    def __init__(self):
        super().__init__("MovingAverage", weight=0.20)

    def analyze(self, df: pd.DataFrame) -> StockSignal:
        if len(df) < 125:
            return StockSignal(StockSignal.HOLD, 50, "데이터 부족")

        df = df.copy()
        df["ma5"] = df["close"].rolling(5).mean()
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma60"] = df["close"].rolling(60).mean()
        df["ma120"] = df["close"].rolling(120).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        ma5, ma20, ma60, ma120 = latest["ma5"], latest["ma20"], latest["ma60"], latest["ma120"]

        # 골든크로스 (5일선 > 20일선 돌파)
        if prev["ma5"] <= prev["ma20"] and ma5 > ma20:
            if ma5 > ma60:
                return StockSignal(StockSignal.BUY, 80, "MA 골든크로스(정배열)")
            return StockSignal(StockSignal.BUY, 70, "MA 골든크로스")

        # 데드크로스
        if prev["ma5"] >= prev["ma20"] and ma5 < ma20:
            return StockSignal(StockSignal.SELL, 25, "MA 데드크로스")

        # 정배열
        if ma5 > ma20 > ma60 > ma120:
            return StockSignal(StockSignal.BUY, 65, "완전 정배열")

        # 역배열
        if ma5 < ma20 < ma60 < ma120:
            return StockSignal(StockSignal.SELL, 30, "완전 역배열")

        return StockSignal(StockSignal.HOLD, 50, "MA 혼조")
