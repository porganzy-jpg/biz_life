"""
종목 선정 앙상블 v2.1

8가지 전략의 가중 합산으로 종합 판단
기본 5전략 + 모멘텀 + 듀얼모멘텀 + 변동성타겟
+ 시장 국면(Regime) 기반 전략 가중치 동적 조정
"""
import sys
import os
import logging
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from base_strategy import StockSignal
from bollinger_strategy import BollingerStrategy
from rsi_strategy import RSIStrategy
from macd_strategy import MACDStockStrategy
from ma_strategy import MAStockStrategy
from institutional_flow import InstitutionalFlowStrategy
from momentum_strategy import MomentumStrategy
from dual_momentum import DualMomentumStrategy
from volatility_target import VolatilityTargetStrategy

logger = logging.getLogger(__name__)


class StockSelectorEnsemble:
    """종목 선정 앙상블 v2.1 (8전략 + 시장국면 적응형 가중치)"""

    def __init__(self):
        self.strategies = [
            BollingerStrategy(),
            RSIStrategy(),
            MACDStockStrategy(),
            MAStockStrategy(),
            InstitutionalFlowStrategy(),
            MomentumStrategy(),
            DualMomentumStrategy(),
            VolatilityTargetStrategy(),
        ]

    def apply_regime_weights(self, regime_weights: dict) -> None:
        """
        외부에서 전달받은 국면별 가중치를 전략에 적용합니다.

        Args:
            regime_weights: {strategy_name: weight, ...}
        """
        for strategy in self.strategies:
            if strategy.name in regime_weights:
                old_w = strategy.weight
                strategy.weight = regime_weights[strategy.name]
                if old_w != strategy.weight:
                    logger.debug(
                        f"전략 가중치 변경: {strategy.name} {old_w:.2f} -> {strategy.weight:.2f}"
                    )

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
