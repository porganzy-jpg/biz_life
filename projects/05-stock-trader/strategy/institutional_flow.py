"""
기관/외국인 수급 분석

실제 구현 시에는 KRX 데이터나 증권사 API에서 수급 데이터를 받아오나,
현재는 거래량 기반 프록시 분석을 수행합니다.
"""
import pandas as pd
import numpy as np
from base_strategy import BaseStockStrategy, StockSignal


class InstitutionalFlowStrategy(BaseStockStrategy):
    """기관/외국인 수급 분석 전략"""

    def __init__(self):
        super().__init__("InstitutionalFlow", weight=0.25)

    def analyze(self, df: pd.DataFrame) -> StockSignal:
        if len(df) < 25:
            return StockSignal(StockSignal.HOLD, 50, "데이터 부족")

        df = df.copy()

        # 거래량 이동평균
        df["vol_ma5"] = df["volume"].rolling(5).mean()
        df["vol_ma20"] = df["volume"].rolling(20).mean()

        # 가격-거래량 상관관계 (OBV 유사)
        df["price_change"] = df["close"].pct_change()
        df["obv"] = (np.sign(df["price_change"]) * df["volume"]).cumsum()
        df["obv_ma5"] = df["obv"].rolling(5).mean()

        # 체결강도 프록시 (가격 위치 기반)
        df["candle_body"] = (df["close"] - df["open"]) / (df["high"] - df["low"] + 1)

        latest = df.iloc[-1]
        score = 50.0
        reasons = []

        # 1. 거래량 급증 + 상승 = 매집 신호
        vol_ratio = latest["volume"] / latest["vol_ma20"] if latest["vol_ma20"] > 0 else 1
        if vol_ratio > 2.0 and latest["price_change"] > 0:
            score += 15
            reasons.append(f"거래량폭증+상승({vol_ratio:.1f}x)")
        elif vol_ratio > 2.0 and latest["price_change"] < 0:
            score -= 15
            reasons.append(f"거래량폭증+하락({vol_ratio:.1f}x)")

        # 2. OBV 추세
        if latest["obv"] > latest["obv_ma5"]:
            score += 10
            reasons.append("OBV 상승추세")
        else:
            score -= 10
            reasons.append("OBV 하락추세")

        # 3. 5일 평균 거래량 추세
        vol_trend = (latest["vol_ma5"] / latest["vol_ma20"]) if latest["vol_ma20"] > 0 else 1
        if vol_trend > 1.3:
            score += 5
            reasons.append("거래량 증가 추세")

        score = max(0, min(100, score))
        reason = " | ".join(reasons) if reasons else "수급 중립"

        if score >= 65:
            action = StockSignal.BUY
        elif score <= 35:
            action = StockSignal.SELL
        else:
            action = StockSignal.HOLD

        return StockSignal(action, score, reason)
