"""
StockBot ML 기반 종목 선정 모델 v3.7

22개 피처 기반 XGBoost 분류 모델.
학습된 모델이 없으면 50점(중립) 반환 → 기존 5전략과 동일하게 동작.

피처 (22개):
  returns(3) + volatility(2) + RSI(2) + MACD(1) + BB(1)
  + MA정렬(3) + OBV/거래량(2) + regime(3) + 서브스코어(5)
"""
import logging
import os
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "stock_selector_xgb.pkl")

# 22개 피처 이름 (train/inference 일관성 보장)
FEATURE_NAMES = [
    # returns (3)
    "ret_5d", "ret_20d", "ret_60d",
    # volatility (2)
    "vol_20d", "vol_60d",
    # RSI (2)
    "rsi_14", "rsi_2",
    # MACD (1)
    "macd_hist_norm",
    # Bollinger Band (1)
    "bb_pband",
    # MA 정렬 (3)
    "ma5_above_ma20", "ma20_above_ma60", "ma60_above_ma120",
    # OBV/거래량 (2)
    "obv_ratio", "vol_ratio_5_20",
    # regime (3)
    "regime_bull", "regime_bear", "regime_sideways",
    # 서브스코어 (5)
    "sub_mean_rev", "sub_trend", "sub_korea_mom", "sub_volume", "sub_volatility",
]


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI 계산"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return (100 - (100 / (1 + rs))).fillna(50)


class MLStockPredictor:
    """ML 기반 종목 선정 예측기"""

    def __init__(self):
        self._model = None
        self._loaded = False
        self._load_model()

    def _load_model(self):
        """학습된 모델 로드"""
        if not os.path.exists(MODEL_PATH):
            logger.info("ML 모델 파일 없음 → 중립(50점) 반환 모드")
            return

        try:
            import joblib
            self._model = joblib.load(MODEL_PATH)
            self._loaded = True
            logger.info(f"ML 모델 로드 완료: {MODEL_PATH}")
        except Exception as e:
            logger.warning(f"ML 모델 로드 실패: {e} → 중립(50점) 반환 모드")

    def is_available(self) -> bool:
        """모델 사용 가능 여부"""
        return self._loaded and self._model is not None

    def extract_features(self, df: pd.DataFrame, regime: str = "SIDEWAYS",
                         sub_scores: dict = None) -> Optional[np.ndarray]:
        """
        22개 피처 추출.

        Args:
            df: OHLCV DataFrame (open, high, low, close, volume)
            regime: 시장 국면 ("BULL", "BEAR", "SIDEWAYS")
            sub_scores: 서브스코어 dict {"평균회귀": float, ...}

        Returns:
            np.ndarray shape (1, 22) or None if insufficient data
        """
        if df is None or len(df) < 130:
            return None

        try:
            close = df["close"].astype(float)
            high = df["high"].astype(float)
            low = df["low"].astype(float)
            volume = df["volume"].astype(float)
            current = float(close.iloc[-1])

            # returns (3)
            ret_5d = float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) > 6 else 0
            ret_20d = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else 0
            ret_60d = float(close.iloc[-1] / close.iloc[-61] - 1) if len(close) > 61 else 0

            # volatility (2)
            returns = close.pct_change().dropna()
            vol_20d = float(returns.tail(20).std() * np.sqrt(252)) if len(returns) >= 20 else 0
            vol_60d = float(returns.tail(60).std() * np.sqrt(252)) if len(returns) >= 60 else vol_20d

            # RSI (2)
            rsi_14 = float(_compute_rsi(close, 14).iloc[-1])
            rsi_2 = float(_compute_rsi(close, 2).iloc[-1])

            # MACD (1)
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            hist = float((macd_line - signal_line).iloc[-1])
            macd_hist_norm = hist / (current * 0.01) if current > 0 else 0

            # Bollinger Band %B (1)
            ma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            upper = ma20 + 2 * std20
            lower = ma20 - 2 * std20
            band = float(upper.iloc[-1]) - float(lower.iloc[-1])
            bb_pband = (current - float(lower.iloc[-1])) / band if band > current * 0.001 else 0.5

            # MA 정렬 (3)
            ma5 = float(close.rolling(5).mean().iloc[-1])
            ma20_val = float(ma20.iloc[-1])
            ma60 = float(close.rolling(60).mean().iloc[-1])
            ma120 = float(close.rolling(120).mean().iloc[-1])
            ma5_above_ma20 = 1.0 if ma5 > ma20_val else 0.0
            ma20_above_ma60 = 1.0 if ma20_val > ma60 else 0.0
            ma60_above_ma120 = 1.0 if ma60 > ma120 else 0.0

            # OBV/거래량 (2)
            obv = (volume * np.sign(close.diff().fillna(0))).cumsum()
            obv_ma5 = float(obv.rolling(5).mean().iloc[-1])
            obv_current = float(obv.iloc[-1])
            obv_ratio = obv_current / obv_ma5 if obv_ma5 != 0 else 1.0

            vol_ma5 = float(volume.rolling(5).mean().iloc[-1])
            vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
            vol_ratio_5_20 = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1.0

            # regime (3) - one-hot
            regime_bull = 1.0 if regime == "BULL" else 0.0
            regime_bear = 1.0 if regime == "BEAR" else 0.0
            regime_sideways = 1.0 if regime == "SIDEWAYS" else 0.0

            # 서브스코어 (5) - 정규화 (0~1)
            ss = sub_scores or {}
            sub_mean_rev = ss.get("평균회귀", 50) / 100
            sub_trend = ss.get("추세추종", 50) / 100
            sub_korea_mom = ss.get("한국형모멘텀", 50) / 100
            sub_volume = ss.get("거래량", 50) / 100
            sub_volatility = ss.get("변동성", 50) / 100

            features = np.array([[
                ret_5d, ret_20d, ret_60d,
                vol_20d, vol_60d,
                rsi_14, rsi_2,
                macd_hist_norm,
                bb_pband,
                ma5_above_ma20, ma20_above_ma60, ma60_above_ma120,
                obv_ratio, vol_ratio_5_20,
                regime_bull, regime_bear, regime_sideways,
                sub_mean_rev, sub_trend, sub_korea_mom, sub_volume, sub_volatility,
            ]])

            # NaN/Inf 가드
            features = np.nan_to_num(features, nan=0.0, posinf=1.0, neginf=-1.0)

            return features

        except Exception as e:
            logger.warning(f"피처 추출 실패: {e}")
            return None

    def predict_score(self, df: pd.DataFrame, regime: str = "SIDEWAYS",
                      sub_scores: dict = None) -> float:
        """
        ML 예측 점수 반환.

        모델이 없으면 50점(중립) 반환.
        P(BUY) - P(SELL)을 10~90 범위로 선형 매핑.

        Returns:
            float: 10~90 점수
        """
        if not self.is_available():
            return 50.0

        features = self.extract_features(df, regime, sub_scores)
        if features is None:
            return 50.0

        try:
            # predict_proba: [[P(SELL), P(HOLD), P(BUY)]] or [[P(0), P(1)]]
            proba = self._model.predict_proba(features)[0]

            if len(proba) == 3:
                # 3클래스: SELL(-1), HOLD(0), BUY(1)
                p_buy = proba[2]
                p_sell = proba[0]
            elif len(proba) == 2:
                # 2클래스: SELL/HOLD(0), BUY(1)
                p_buy = proba[1]
                p_sell = proba[0]
            else:
                return 50.0

            # P(BUY) - P(SELL) → [-1, 1] → [10, 90]
            diff = p_buy - p_sell
            score = 50 + diff * 40
            return round(max(10, min(90, score)), 1)

        except Exception as e:
            logger.warning(f"ML 예측 실패: {e}")
            return 50.0
