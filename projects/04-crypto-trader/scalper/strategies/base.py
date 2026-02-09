"""
Base classes for scalping strategies.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class ScalpSignal:
    signal: SignalType
    strategy_name: str
    confidence: float = 0.0  # 0.0 ~ 1.0
    reason: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def is_buy(self) -> bool:
        return self.signal == SignalType.BUY

    @property
    def is_sell(self) -> bool:
        return self.signal == SignalType.SELL


class BaseScalpStrategy(ABC):
    """Abstract base class for all scalping strategies."""

    name: str = "base"

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> ScalpSignal:
        """
        Analyze candle data and produce a signal.

        Args:
            df: DataFrame with columns [open, high, low, close, volume, timestamp]
                sorted ascending (oldest first).

        Returns:
            ScalpSignal with BUY/SELL/HOLD.
        """
        ...

    def _validate_df(self, df: pd.DataFrame, min_rows: int = 20) -> bool:
        if df is None or len(df) < min_rows:
            return False
        required = {"open", "high", "low", "close", "volume"}
        return required.issubset(set(df.columns))

    def _hold(self, reason: str = "") -> ScalpSignal:
        return ScalpSignal(
            signal=SignalType.HOLD,
            strategy_name=self.name,
            confidence=0.0,
            reason=reason,
        )
