"""
변동성 돌파 전략 (래리 윌리엄스)

전략 로직:
- 전일 변동폭(고가-저가)의 K배만큼 당일 시가 대비 상승 시 매수
- 다음날 시가에 전량 매도 (1일 단위 단타)

이 전략은 "추세 추종" 이론에 기반합니다.
강한 변동성이 발생하면 그 방향으로 추세가 이어진다는 가정.

K값은 0.4~0.6 사이가 일반적이며, 백테스트를 통해 최적화합니다.
"""
import pandas as pd
import ta

from base_strategy import BaseStrategy, Signal


class VolatilityBreakoutStrategy(BaseStrategy):
    """변동성 돌파 전략"""

    def __init__(self, config: dict = None):
        default_config = {
            "k_value": 0.5,           # 변동성 돌파 계수
            "ma_period": 5,           # 이동평균 기간 (필터용)
            "volume_threshold": 1.2,  # 거래량 조건 (평균 대비 배수)
        }
        merged_config = {**default_config, **(config or {})}
        super().__init__("VolatilityBreakout", merged_config)

    def analyze(self, df: pd.DataFrame, symbol: str) -> Signal:
        """변동성 돌파 분석"""
        if len(df) < 20:
            return Signal(Signal.HOLD, symbol, 0.0, "데이터 부족")

        df = df.copy()

        # 전일 변동폭 계산
        df["prev_high"] = df["high"].shift(1)
        df["prev_low"] = df["low"].shift(1)
        df["prev_close"] = df["close"].shift(1)
        df["range"] = df["prev_high"] - df["prev_low"]

        # 변동성 돌파 타겟 가격 = 시가 + (전일 변동폭 * K)
        df["target_price"] = df["open"] + (df["range"] * self.config["k_value"])

        # 이동평균선 (추세 필터)
        df["ma"] = df["close"].rolling(window=self.config["ma_period"]).mean()

        # 거래량 이동평균
        df["vol_ma"] = df["volume"].rolling(window=20).mean()

        latest = df.iloc[-1]
        current_price = latest["close"]
        target_price = latest["target_price"]
        ma_value = latest["ma"]
        vol_ratio = latest["volume"] / latest["vol_ma"] if latest["vol_ma"] > 0 else 0

        # 매수 조건:
        # 1. 현재가가 변동성 돌파 타겟 이상
        # 2. 이동평균선 위에 있음 (상승 추세)
        # 3. 거래량이 평균 이상
        if (current_price >= target_price and
                current_price > ma_value and
                vol_ratio >= self.config["volume_threshold"]):
            confidence = min(1.0, 0.5 + (current_price - target_price) / target_price * 10)
            return Signal(
                Signal.BUY, symbol, confidence,
                f"변동성돌파(현재가:{current_price:,.0f} >= 타겟:{target_price:,.0f}) "
                f"+ MA위({ma_value:,.0f}) + 거래량({vol_ratio:.1f}x)"
            )

        # 매도 조건: 이동평균선 하향 돌파
        if current_price < ma_value and df.iloc[-2]["close"] >= df.iloc[-2]["ma"]:
            return Signal(
                Signal.SELL, symbol, 0.7,
                f"MA하향돌파(현재가:{current_price:,.0f} < MA:{ma_value:,.0f})"
            )

        return Signal(
            Signal.HOLD, symbol, 0.0,
            f"관망(현재가:{current_price:,.0f}, 타겟:{target_price:,.0f}, MA:{ma_value:,.0f})"
        )
