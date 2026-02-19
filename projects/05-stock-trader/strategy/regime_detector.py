"""
시장 국면(Regime) 감지 모듈

시장 상태를 BULL / BEAR / SIDEWAYS 3가지로 분류하고
각 국면별 전략 가중치를 동적으로 조정합니다.

감지 기준:
  - 20일/60일 이동평균 크로스 (추세 방향)
  - ADX 유사 지표 (추세 강도)
  - 변동성 수준 (고/저 변동성 판별)
"""
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """시장 국면"""
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"


# ──────────────────────────────────────────────
# 국면별 전략 가중치 프로필
# 키는 BaseStockStrategy.name 과 동일해야 합니다.
# ──────────────────────────────────────────────
REGIME_WEIGHT_PROFILES: Dict[MarketRegime, Dict[str, float]] = {
    MarketRegime.BULL: {
        "Bollinger":          0.10,
        "RSI":                0.15,
        "MACD":               0.15,
        "MovingAverage":      0.25,
        "InstitutionalFlow":  0.15,
        "모멘텀":              0.25,
        "듀얼모멘텀":           0.20,
        "변동성타겟":           0.10,
    },
    MarketRegime.BEAR: {
        "Bollinger":          0.25,
        "RSI":                0.25,
        "MACD":               0.15,
        "MovingAverage":      0.10,
        "InstitutionalFlow":  0.15,
        "모멘텀":              0.05,
        "듀얼모멘텀":           0.15,
        "변동성타겟":           0.25,
    },
    MarketRegime.SIDEWAYS: {
        "Bollinger":          0.25,
        "RSI":                0.25,
        "MACD":               0.15,
        "MovingAverage":      0.10,
        "InstitutionalFlow":  0.10,
        "모멘텀":              0.10,
        "듀얼모멘텀":           0.10,
        "변동성타겟":           0.20,
    },
}

# 기본(중립) 가중치 — 국면 감지 실패 시 폴백
DEFAULT_WEIGHTS: Dict[str, float] = {
    "Bollinger":          0.15,
    "RSI":                0.20,
    "MACD":               0.20,
    "MovingAverage":      0.20,
    "InstitutionalFlow":  0.25,
    "모멘텀":              0.20,
    "듀얼모멘텀":           0.15,
    "변동성타겟":           0.15,
}


class RegimeDetector:
    """
    시장 국면 감지기

    워치리스트 종목들의 평균 종가 시계열을 사용하여
    시장 전체의 추세·강도·변동성을 판단합니다.
    """

    def __init__(
        self,
        ma_short: int = 20,
        ma_long: int = 60,
        adx_period: int = 14,
        adx_trending_threshold: float = 25.0,
        adx_sideways_threshold: float = 20.0,
        vol_lookback: int = 20,
        vol_long_lookback: int = 60,
    ):
        self.ma_short = ma_short
        self.ma_long = ma_long
        self.adx_period = adx_period
        self.adx_trending_threshold = adx_trending_threshold
        self.adx_sideways_threshold = adx_sideways_threshold
        self.vol_lookback = vol_lookback
        self.vol_long_lookback = vol_long_lookback

        # 상태 보관
        self._current_regime: MarketRegime = MarketRegime.SIDEWAYS
        self._previous_regime: Optional[MarketRegime] = None
        self._regime_since: Optional[str] = None
        self._detection_details: dict = {}

    # ── public API ───────────────────────────────

    @property
    def current_regime(self) -> MarketRegime:
        return self._current_regime

    def detect(self, price_series_list: List[pd.DataFrame]) -> MarketRegime:
        """
        여러 종목의 OHLCV DataFrame 리스트를 받아 시장 국면을 판단합니다.

        Args:
            price_series_list: 각 종목의 OHLCV DataFrame 리스트
                               (최소 ma_long + adx_period 일 이상)

        Returns:
            MarketRegime: 현재 시장 국면
        """
        market_avg = self._build_market_proxy(price_series_list)
        if market_avg is None or len(market_avg) < self.ma_long + self.adx_period:
            logger.debug("시장 프록시 데이터 부족 — SIDEWAYS 유지")
            return self._current_regime

        regime = self._classify(market_avg)

        # 상태 변경 감지
        if regime != self._current_regime:
            self._previous_regime = self._current_regime
            self._current_regime = regime
            self._regime_since = datetime.now().isoformat()
            logger.info(
                f"시장 국면 변경: {self._previous_regime} -> {self._current_regime}"
            )
        return self._current_regime

    def get_strategy_weights(self) -> Dict[str, float]:
        """현재 국면에 맞는 전략 가중치를 반환합니다."""
        return REGIME_WEIGHT_PROFILES.get(self._current_regime, DEFAULT_WEIGHTS).copy()

    def apply_weights(self, strategies: list) -> None:
        """
        전략 객체 리스트의 weight 속성을 현재 국면에 맞게 갱신합니다.

        Args:
            strategies: BaseStockStrategy 인스턴스 리스트
        """
        weights = self.get_strategy_weights()
        for strategy in strategies:
            name = strategy.name
            if name in weights:
                strategy.weight = weights[name]

    def get_status(self) -> dict:
        """대시보드·로깅용 상태 정보"""
        return {
            "regime": self._current_regime.value,
            "previous_regime": self._previous_regime.value if self._previous_regime else None,
            "regime_since": self._regime_since,
            "weights": self.get_strategy_weights(),
            "details": self._detection_details,
        }

    # ── internal ─────────────────────────────────

    def _build_market_proxy(
        self, price_series_list: List[pd.DataFrame]
    ) -> Optional[pd.DataFrame]:
        """
        워치리스트 종목의 종가를 정규화하여 평균 시계열을 구성합니다.

        각 종목의 종가를 최초 값 대비 비율(=1.0)로 정규화한 뒤 평균을 취합니다.
        이것이 KOSPI 프록시 역할을 합니다.
        """
        if not price_series_list:
            return None

        normalized: list = []
        for df in price_series_list:
            if df is None or len(df) < self.ma_long:
                continue
            close = df["close"].values.astype(float)
            first = close[0]
            if first <= 0:
                continue
            normalized.append(close / first)

        if not normalized:
            return None

        # 최소 공통 길이 정렬
        min_len = min(len(s) for s in normalized)
        aligned = np.column_stack([s[-min_len:] for s in normalized])
        avg_close = aligned.mean(axis=1)

        # 고·저가 프록시는 시장 평균에 ±일일 변동폭 추정
        avg_high = avg_close * 1.005  # 단순 추정 (실제 코스피 ETF가 있다면 대체)
        avg_low = avg_close * 0.995

        proxy = pd.DataFrame({
            "close": avg_close,
            "high": avg_high,
            "low": avg_low,
        })
        return proxy

    def _classify(self, df: pd.DataFrame) -> MarketRegime:
        """
        이동평균 + ADX + 변동성을 종합하여 국면을 분류합니다.
        """
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        # 1) 이동평균 (추세 방향)
        ma_short = pd.Series(close).rolling(self.ma_short).mean().values
        ma_long = pd.Series(close).rolling(self.ma_long).mean().values
        latest_ma_short = ma_short[-1]
        latest_ma_long = ma_long[-1]

        if np.isnan(latest_ma_short) or np.isnan(latest_ma_long):
            return MarketRegime.SIDEWAYS

        ma_bullish = latest_ma_short > latest_ma_long
        ma_diff_pct = (latest_ma_short - latest_ma_long) / latest_ma_long * 100

        # 2) ADX 유사 지표 (추세 강도)
        adx_value = self._calculate_adx(high, low, close)

        # 3) 변동성
        returns = np.diff(close) / close[:-1]
        recent_vol = np.std(returns[-self.vol_lookback:]) * np.sqrt(252)
        long_vol = np.std(returns[-self.vol_long_lookback:]) * np.sqrt(252) if len(returns) >= self.vol_long_lookback else recent_vol
        vol_ratio = recent_vol / long_vol if long_vol > 0 else 1.0

        # 4) 최근 20일 수익률
        if len(close) >= self.ma_short:
            recent_return = (close[-1] / close[-self.ma_short] - 1) * 100
        else:
            recent_return = 0.0

        # 로깅용 상세정보 저장
        self._detection_details = {
            "ma_short": round(float(latest_ma_short), 6),
            "ma_long": round(float(latest_ma_long), 6),
            "ma_diff_pct": round(float(ma_diff_pct), 3),
            "ma_bullish": bool(ma_bullish),
            "adx": round(float(adx_value), 2),
            "recent_volatility": round(float(recent_vol * 100), 2),
            "long_volatility": round(float(long_vol * 100), 2),
            "vol_ratio": round(float(vol_ratio), 3),
            "recent_return_pct": round(float(recent_return), 2),
        }

        # ── 분류 규칙 ──
        # 추세 강도가 충분히 높으면 BULL / BEAR
        if adx_value >= self.adx_trending_threshold:
            if ma_bullish and recent_return > 0:
                return MarketRegime.BULL
            elif not ma_bullish and recent_return < 0:
                return MarketRegime.BEAR
            else:
                # ADX 높지만 방향 불일치 → 변동성으로 보완 판단
                if vol_ratio > 1.2 and recent_return < -2:
                    return MarketRegime.BEAR
                elif vol_ratio < 0.9 and recent_return > 2:
                    return MarketRegime.BULL
                return MarketRegime.SIDEWAYS

        # ADX가 낮으면 (추세 약함)
        if adx_value < self.adx_sideways_threshold:
            # 하지만 변동성이 높고 하락 중이면 BEAR
            if vol_ratio > 1.3 and recent_return < -3:
                return MarketRegime.BEAR
            return MarketRegime.SIDEWAYS

        # ADX 20~25 애매한 구간
        if ma_bullish and recent_return > 1 and vol_ratio < 1.1:
            return MarketRegime.BULL
        elif not ma_bullish and recent_return < -1 and vol_ratio > 1.1:
            return MarketRegime.BEAR

        return MarketRegime.SIDEWAYS

    def _calculate_adx(
        self, high: np.ndarray, low: np.ndarray, close: np.ndarray
    ) -> float:
        """
        ADX(Average Directional Index)를 계산합니다.

        Wilder의 원본 ADX 공식:
        1. TR, +DM, -DM 을 계산
        2. 각각을 Wilder EMA (alpha=1/period)로 스무딩
        3. +DI = smoothed(+DM) / smoothed(TR) * 100
        4. -DI = smoothed(-DM) / smoothed(TR) * 100
        5. DX  = |+DI - -DI| / (+DI + -DI) * 100
        6. ADX = Wilder EMA of DX

        Returns:
            float: ADX 값 (0 ~ 100 범위, 0이면 계산 불가)
        """
        n = len(close)
        period = self.adx_period
        if n < period * 3:
            return 0.0

        # True Range
        tr = np.zeros(n)
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)

        for i in range(1, n):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i - 1])
            lc = abs(low[i] - close[i - 1])
            tr[i] = max(hl, hc, lc)

            up_move = high[i] - high[i - 1]
            down_move = low[i - 1] - low[i]
            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move

        # Wilder EMA smoothing (alpha = 1/period)
        alpha = 1.0 / period

        def wilder_ema(data: np.ndarray, p: int) -> np.ndarray:
            """Wilder EMA: first value is SMA of first p items, then EMA."""
            result = np.full(len(data), np.nan)
            # Initial SMA seed (using indices 1 to p inclusive)
            if p + 1 > len(data):
                return result
            result[p] = np.mean(data[1:p + 1])
            for i in range(p + 1, len(data)):
                result[i] = result[i - 1] * (1 - alpha) + data[i] * alpha
            return result

        atr = wilder_ema(tr, period)
        smooth_plus_dm = wilder_ema(plus_dm, period)
        smooth_minus_dm = wilder_ema(minus_dm, period)

        # +DI, -DI (with safe division)
        plus_di = np.zeros(n)
        minus_di = np.zeros(n)
        for i in range(period, n):
            if not np.isnan(atr[i]) and atr[i] > 0:
                plus_di[i] = (smooth_plus_dm[i] / atr[i]) * 100 if not np.isnan(smooth_plus_dm[i]) else 0
                minus_di[i] = (smooth_minus_dm[i] / atr[i]) * 100 if not np.isnan(smooth_minus_dm[i]) else 0

        # DX
        dx = np.zeros(n)
        for i in range(period, n):
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx[i] = abs(plus_di[i] - minus_di[i]) / di_sum * 100

        # ADX = Wilder EMA of DX (starting from index 2*period)
        adx_arr = np.full(n, np.nan)
        start = period * 2
        if start >= n:
            return 0.0
        adx_arr[start] = np.mean(dx[period:start + 1])
        for i in range(start + 1, n):
            adx_arr[i] = adx_arr[i - 1] * (1 - alpha) + dx[i] * alpha

        # Return last valid ADX
        last_adx = adx_arr[-1]
        if np.isnan(last_adx):
            valid = adx_arr[~np.isnan(adx_arr)]
            return float(valid[-1]) if len(valid) > 0 else 0.0
        return float(np.clip(last_adx, 0, 100))
