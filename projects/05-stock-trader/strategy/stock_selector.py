"""
종목 선정 앙상블

여러 전략의 점수를 가중 합산하여 종합 판단
"""
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from base_strategy import StockSignal
from bollinger_strategy import BollingerStrategy
from rsi_strategy import RSIStrategy
from macd_strategy import MACDStockStrategy
from ma_strategy import MAStockStrategy
from institutional_flow import InstitutionalFlowStrategy


class StockSelectorEnsemble:
    """종목 선정 앙상블"""

    def __init__(self):
        self.strategies = [
            BollingerStrategy(),
            RSIStrategy(),
            MACDStockStrategy(),
            MAStockStrategy(),
            InstitutionalFlowStrategy(),
        ]

    def evaluate(self, df: pd.DataFrame, symbol: str, name: str) -> dict:
        """
        종합 평가

        Returns:
            dict: {symbol, name, action, score, confidence, reasons, signals, current_price}
        """
        signals = []
        total_weight = 0
        weighted_score = 0

        for strategy in self.strategies:
            try:
                signal = strategy.analyze(df)
                signals.append({
                    "strategy": strategy.name,
                    "action": signal.action,
                    "score": signal.score,
                    "weight": strategy.weight,
                    "reason": signal.reason,
                })
                weighted_score += signal.score * strategy.weight
                total_weight += strategy.weight
            except Exception:
                pass

        if total_weight > 0:
            final_score = weighted_score / total_weight
        else:
            final_score = 50

        # 최종 판단
        if final_score >= 65:
            action = "BUY"
        elif final_score <= 35:
            action = "SELL"
        else:
            action = "HOLD"

        confidence = abs(final_score - 50) / 50

        # 주요 근거 수집
        reasons = [s["reason"] for s in signals if s["score"] >= 65 or s["score"] <= 35]

        current_price = int(df.iloc[-1]["close"]) if len(df) > 0 else 0

        return {
            "symbol": symbol,
            "name": name,
            "action": action,
            "score": round(final_score, 1),
            "confidence": round(confidence, 2),
            "current_price": current_price,
            "reasons": reasons,
            "signals": signals,
        }
