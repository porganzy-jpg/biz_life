"""
전략 앙상블 (가중 투표 시스템)

여러 전략의 신호를 가중 투표로 결합하여 최종 신호를 결정합니다.
각 전략에 가중치를 부여하고, 과거 성과에 따라 동적으로 조정할 수 있습니다.
"""
import pandas as pd
from typing import List, Dict

from base_strategy import BaseStrategy, Signal


class StrategyEnsemble:
    """전략 앙상블 - 가중 투표"""

    def __init__(self, strategies: List[BaseStrategy], weights: Dict[str, float] = None):
        """
        Args:
            strategies: 전략 인스턴스 리스트
            weights: 전략별 가중치 {"전략이름": 가중치}
                     None이면 균등 가중치
        """
        self.strategies = strategies
        if weights:
            self.weights = weights
        else:
            equal_w = 1.0 / len(strategies)
            self.weights = {s.name: equal_w for s in strategies}

        # 전략별 성과 추적 (동적 가중치 조정용)
        self.performance = {s.name: {"wins": 0, "losses": 0, "total": 0} for s in strategies}

    def analyze(self, df: pd.DataFrame, symbol: str) -> dict:
        """
        앙상블 분석 실행

        Returns:
            dict: {
                "action": str,
                "confidence": float,
                "signals": list,
                "vote_detail": dict,
            }
        """
        signals = []
        for strategy in self.strategies:
            try:
                signal = strategy.analyze(df, symbol)
                signals.append((strategy.name, signal))
            except Exception:
                signals.append((strategy.name, Signal(Signal.HOLD, symbol, 0.0, "분석 오류")))

        # 가중 투표 계산
        buy_score = 0.0
        sell_score = 0.0
        hold_score = 0.0

        for name, signal in signals:
            weight = self.weights.get(name, 0.0)
            weighted = weight * signal.confidence

            if signal.action == Signal.BUY:
                buy_score += weighted
            elif signal.action == Signal.SELL:
                sell_score += weighted
            else:
                hold_score += weight * 0.3  # HOLD는 낮은 가중치

        total = buy_score + sell_score + hold_score
        if total == 0:
            total = 1.0

        # 최종 결정
        vote_detail = {
            "buy_score": round(buy_score, 4),
            "sell_score": round(sell_score, 4),
            "hold_score": round(hold_score, 4),
        }

        # 매수/매도 점수가 최소 임계값을 넘어야 실행
        min_threshold = 0.15

        if buy_score > sell_score and buy_score > hold_score and buy_score >= min_threshold:
            action = Signal.BUY
            confidence = min(1.0, buy_score / total)
        elif sell_score > buy_score and sell_score > hold_score and sell_score >= min_threshold:
            action = Signal.SELL
            confidence = min(1.0, sell_score / total)
        else:
            action = Signal.HOLD
            confidence = 0.0

        return {
            "action": action,
            "confidence": round(confidence, 4),
            "signals": [
                {"strategy": name, "action": s.action, "confidence": s.confidence, "reason": s.reason}
                for name, s in signals
            ],
            "vote_detail": vote_detail,
        }

    def update_performance(self, strategy_name: str, was_profitable: bool):
        """전략 성과 업데이트 (동적 가중치 조정에 사용)"""
        if strategy_name in self.performance:
            self.performance[strategy_name]["total"] += 1
            if was_profitable:
                self.performance[strategy_name]["wins"] += 1
            else:
                self.performance[strategy_name]["losses"] += 1

    def adjust_weights(self):
        """성과 기반 가중치 동적 조정"""
        total_win_rate = 0
        win_rates = {}

        for name, perf in self.performance.items():
            if perf["total"] >= 10:  # 최소 10회 이상 거래
                wr = perf["wins"] / perf["total"]
                win_rates[name] = wr
                total_win_rate += wr

        if not win_rates or total_win_rate == 0:
            return

        # 승률 비례 가중치 조정
        for name, wr in win_rates.items():
            self.weights[name] = wr / total_win_rate

    def get_strategy_report(self) -> dict:
        """전략별 성과 리포트"""
        report = {}
        for name, perf in self.performance.items():
            total = perf["total"]
            report[name] = {
                "weight": round(self.weights.get(name, 0), 4),
                "total_trades": total,
                "wins": perf["wins"],
                "losses": perf["losses"],
                "win_rate": round(perf["wins"] / max(total, 1) * 100, 1),
            }
        return report
