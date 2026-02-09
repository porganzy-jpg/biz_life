"""
StockBot 전략 베이스 클래스
"""
from abc import ABC, abstractmethod
import pandas as pd


class StockSignal:
    """주식 매매 신호"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

    def __init__(self, action: str, score: float = 50.0, reason: str = ""):
        self.action = action
        self.score = score        # 0~100 (50이 중립)
        self.reason = reason

    def __repr__(self):
        return f"StockSignal({self.action}, score={self.score:.1f}, {self.reason})"


class BaseStockStrategy(ABC):
    """주식 매매 전략 베이스"""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> StockSignal:
        """분석 후 신호 반환"""
        pass
