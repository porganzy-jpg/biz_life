"""
변동성 타겟팅 전략

목표 변동성을 설정하고 현재 변동성에 따라 포지션 크기 조절
변동성이 낮을 때 더 공격적, 높을 때 방어적
"""
import pandas as pd
import numpy as np
from base_strategy import BaseStockStrategy, StockSignal


class VolatilityTargetStrategy(BaseStockStrategy):
    """변동성 타겟팅 전략"""

    name = "변동성타겟"
    weight = 0.15

    def __init__(self, target_vol: float = 0.15, lookback: int = 20):
        self.target_vol = target_vol  # 연간 목표 변동성 15%
        self.lookback = lookback

    def analyze(self, df: pd.DataFrame) -> StockSignal:
        if len(df) < self.lookback + 5:
            return StockSignal("HOLD", 50, "데이터 부족")

        close = df["close"]
        returns = close.pct_change().dropna()

        # 현재 변동성 (연율화)
        current_vol = returns.tail(self.lookback).std() * np.sqrt(252)

        # 과거 평균 변동성
        hist_vol = returns.tail(60).std() * np.sqrt(252) if len(returns) >= 60 else current_vol

        # 변동성 비율 (목표 대비)
        vol_ratio = self.target_vol / current_vol if current_vol > 0 else 1.0
        vol_ratio = max(0.2, min(2.0, vol_ratio))  # 20%~200% 클램프

        # 변동성 추세 (증가 vs 감소)
        if len(returns) >= self.lookback * 2:
            prev_vol = returns.iloc[-self.lookback*2:-self.lookback].std() * np.sqrt(252)
            vol_trend = (current_vol - prev_vol) / prev_vol if prev_vol > 0 else 0
        else:
            vol_trend = 0

        # 볼린저밴드 %B로 가격 위치 참고
        ma = close.rolling(self.lookback).mean()
        std = close.rolling(self.lookback).std()
        current_price = close.iloc[-1]
        upper = ma.iloc[-1] + 2 * std.iloc[-1]
        lower = ma.iloc[-1] - 2 * std.iloc[-1]
        pct_b = (current_price - lower) / (upper - lower) if upper != lower else 0.5

        # 점수 계산
        score = 50

        # 변동성이 목표보다 낮으면 (+) → 더 투자 가능
        if current_vol < self.target_vol:
            score += min(15, (self.target_vol - current_vol) / self.target_vol * 30)
        else:
            score -= min(15, (current_vol - self.target_vol) / self.target_vol * 30)

        # 변동성 감소 추세면 (+)
        if vol_trend < -0.1:
            score += 5
        elif vol_trend > 0.2:
            score -= 10

        # 가격이 밴드 하단이면 (+) 역추세 기회
        if pct_b < 0.2 and current_vol > hist_vol:
            score += 10  # 고변동성 + 밴드 하단 = 반등 기회
        elif pct_b > 0.8 and current_vol > hist_vol:
            score -= 10  # 고변동성 + 밴드 상단 = 과열

        score = max(10, min(90, score))

        if score >= 65:
            return StockSignal("BUY", round(score, 1),
                               f"저변동성 환경 (변동성:{current_vol*100:.1f}% 목표:{self.target_vol*100:.0f}% 비율:{vol_ratio:.1f}x)")
        elif score <= 35:
            return StockSignal("SELL", round(score, 1),
                               f"고변동성 위험 (변동성:{current_vol*100:.1f}% 추세:{vol_trend*100:+.1f}%)")
        else:
            return StockSignal("HOLD", round(score, 1),
                               f"변동성 적정 ({current_vol*100:.1f}%)")
