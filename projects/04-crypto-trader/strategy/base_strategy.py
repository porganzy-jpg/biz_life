"""
매매 전략 베이스 클래스
모든 전략은 이 클래스를 상속받아 구현
"""
from abc import ABC, abstractmethod
import pandas as pd


class Signal:
    """매매 신호"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

    def __init__(self, action: str, symbol: str, confidence: float = 0.0, reason: str = ""):
        self.action = action
        self.symbol = symbol
        self.confidence = confidence  # 0.0 ~ 1.0
        self.reason = reason

    def __repr__(self):
        return f"Signal({self.action}, {self.symbol}, conf={self.confidence:.2f}, {self.reason})"


class BaseStrategy(ABC):
    """
    매매 전략 베이스 클래스

    모든 전략은 이 클래스를 상속받고 analyze() 메서드를 구현해야 합니다.
    """

    def __init__(self, name: str, config: dict = None):
        self.name = name
        self.config = config or {}

    @abstractmethod
    def analyze(self, df: pd.DataFrame, symbol: str) -> Signal:
        """
        주어진 OHLCV 데이터를 분석하여 매매 신호를 반환

        Args:
            df: OHLCV DataFrame (columns: timestamp, open, high, low, close, volume)
            symbol: 마켓 심볼

        Returns:
            Signal: 매수/매도/관망 신호
        """
        pass

    def _prepare_dataframe(self, ohlcv_data: list) -> pd.DataFrame:
        """OHLCV 리스트를 DataFrame으로 변환"""
        df = pd.DataFrame(ohlcv_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df
