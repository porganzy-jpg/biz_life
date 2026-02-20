"""
Dashboard Market Regime Detection & Dynamic Strategy Rotation

Classifies market into 4 regimes using database trade history:
  - BULL_TREND:     Positive 20d return, low volatility, price > 50d MA
  - BEAR_TREND:     Negative 20d return, rising vol, price < 50d MA
  - RANGING:        Low absolute returns, low volatility
  - HIGH_VOLATILITY: Vol > 2 std above mean

Provides a StrategyRotator that maps each regime to optimal
strategy weights and blends with equal-weight defaults based on
confidence.  Regime history is persisted to a JSON file.
"""
import json
import logging
import math
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
REGIME_HISTORY_PATH = os.path.join(_DIR, "..", "regime_history.json")

# ---------------------------------------------------------------------------
# Regime enum
# ---------------------------------------------------------------------------

class DashboardRegime(str, Enum):
    """Market regime classification (4-state model)."""
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


# ---------------------------------------------------------------------------
# RegimeResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class RegimeResult:
    """Result of a regime classification."""
    regime: DashboardRegime
    confidence: float  # 0.0 .. 1.0
    indicators: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 4),
            "indicators": self.indicators,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Strategy names (canonical, matching STRATEGY_NAMES in app.py)
# ---------------------------------------------------------------------------
STRATEGY_NAMES = [
    "Bollinger",
    "RSI",
    "MACD",
    "MA",
    "InstitutionalFlow",
    "Momentum",
    "DualMomentum",
    "VolatilityTarget",
]

NUM_STRATEGIES = len(STRATEGY_NAMES)
EQUAL_WEIGHT = 1.0 / NUM_STRATEGIES  # 12.5%


# ---------------------------------------------------------------------------
# RegimeDetector
# ---------------------------------------------------------------------------

class RegimeDetector:
    """
    Classify the market into one of four regimes using price returns
    and volatility information derived from database trade data or
    from raw price arrays.

    Core method:
        classify_regime(returns, volatility, prices=None)
            returns   -- array-like of recent daily returns (newest last)
            volatility -- array-like of recent rolling volatility values
            prices     -- (optional) array-like of recent closing prices

    Returns a RegimeResult(regime, confidence, indicators).
    """

    # Tunable thresholds
    RETURN_LOOKBACK = 20        # 20-day returns window
    VOL_LOOKBACK = 20           # recent vol window
    VOL_LONG_LOOKBACK = 60      # long-term vol window for z-score
    MA_PERIOD = 50              # moving average period for trend filter
    RANGING_ABS_THRESHOLD = 1.0 # |20d return| below this => ranging candidate
    HIGH_VOL_Z_THRESHOLD = 2.0  # vol z-score above this => HIGH_VOLATILITY

    def classify_regime(
        self,
        returns: List[float],
        volatility: List[float],
        prices: Optional[List[float]] = None,
    ) -> RegimeResult:
        """
        Classify the current market regime.

        Args:
            returns:    Daily return percentages (newest last).
                        At least 20 values recommended.
            volatility: Rolling volatility values (newest last).
                        At least 60 values recommended for z-score.
            prices:     (Optional) Closing prices (newest last).
                        Used for MA comparison.  At least 50 values.

        Returns:
            RegimeResult with regime, confidence (0-1), and indicators dict.
        """
        # ----- Compute indicators -----
        returns_arr = list(returns) if returns else []
        vol_arr = list(volatility) if volatility else []
        prices_arr = list(prices) if prices else []

        # 20-day return
        ret_20d = self._sum_recent(returns_arr, self.RETURN_LOOKBACK)

        # Recent volatility (mean of last 20 vol readings)
        recent_vol = self._mean_recent(vol_arr, self.VOL_LOOKBACK)

        # Long-term volatility (mean of last 60 vol readings)
        long_vol = self._mean_recent(vol_arr, self.VOL_LONG_LOOKBACK)

        # Volatility standard deviation over long window (for z-score)
        vol_std = self._std_recent(vol_arr, self.VOL_LONG_LOOKBACK)

        # Volatility z-score
        if vol_std > 0 and long_vol is not None and recent_vol is not None:
            vol_z = (recent_vol - long_vol) / vol_std
        else:
            vol_z = 0.0

        # Price vs 50d MA
        price_above_ma = None
        ma_50 = None
        latest_price = None
        if prices_arr and len(prices_arr) >= self.MA_PERIOD:
            ma_50 = sum(prices_arr[-self.MA_PERIOD:]) / self.MA_PERIOD
            latest_price = prices_arr[-1]
            price_above_ma = latest_price > ma_50
        elif prices_arr:
            latest_price = prices_arr[-1]

        # Volatility trend (is vol rising?)
        vol_rising = False
        if len(vol_arr) >= 10:
            recent_5 = self._mean_recent(vol_arr, 5)
            prev_5 = self._mean_slice(vol_arr, -10, -5)
            if recent_5 is not None and prev_5 is not None and prev_5 > 0:
                vol_rising = recent_5 > prev_5 * 1.05  # 5% increase

        # ----- Classification logic -----
        regime = DashboardRegime.RANGING
        confidence = 0.5

        # Check HIGH_VOLATILITY first (overrides other regimes)
        if vol_z > self.HIGH_VOL_Z_THRESHOLD:
            regime = DashboardRegime.HIGH_VOLATILITY
            # Confidence scales with how far above threshold
            confidence = min(1.0, 0.5 + (vol_z - self.HIGH_VOL_Z_THRESHOLD) * 0.25)

        # BULL_TREND: positive 20d return + low vol + price > 50d MA
        elif (ret_20d is not None and ret_20d > 0
              and recent_vol is not None
              and vol_z < 1.0
              and (price_above_ma is True or price_above_ma is None)):
            # Stronger bull if return is large and vol is low
            if ret_20d > 2.0:
                regime = DashboardRegime.BULL_TREND
                bull_strength = min(ret_20d / 10.0, 0.4)
                vol_bonus = max(0, (1.0 - vol_z) * 0.1) if vol_z < 1.0 else 0
                confidence = min(1.0, 0.5 + bull_strength + vol_bonus)
            elif ret_20d > 0.5:
                regime = DashboardRegime.BULL_TREND
                confidence = 0.4 + min(ret_20d / 5.0, 0.3)
            else:
                # Very weak positive return -> ranging
                regime = DashboardRegime.RANGING
                confidence = 0.5

        # BEAR_TREND: negative 20d return + rising vol + price < 50d MA
        elif (ret_20d is not None and ret_20d < 0
              and (vol_rising or vol_z > 0.5)
              and (price_above_ma is False or price_above_ma is None)):
            if ret_20d < -2.0:
                regime = DashboardRegime.BEAR_TREND
                bear_strength = min(abs(ret_20d) / 10.0, 0.4)
                vol_bonus = min(vol_z * 0.1, 0.1) if vol_z > 0 else 0
                confidence = min(1.0, 0.5 + bear_strength + vol_bonus)
            elif ret_20d < -0.5:
                regime = DashboardRegime.BEAR_TREND
                confidence = 0.4 + min(abs(ret_20d) / 5.0, 0.3)
            else:
                regime = DashboardRegime.RANGING
                confidence = 0.5

        # RANGING: low absolute returns, low vol
        else:
            regime = DashboardRegime.RANGING
            if ret_20d is not None:
                # Confidence is higher when return is closer to 0
                abs_ret = abs(ret_20d)
                if abs_ret < self.RANGING_ABS_THRESHOLD:
                    confidence = 0.6 + min((self.RANGING_ABS_THRESHOLD - abs_ret) / self.RANGING_ABS_THRESHOLD * 0.3, 0.3)
                else:
                    confidence = max(0.3, 0.6 - abs_ret * 0.05)
            else:
                confidence = 0.5

        # ----- Build indicators dict -----
        indicators = {
            "return_20d": round(ret_20d, 4) if ret_20d is not None else None,
            "recent_vol": round(recent_vol, 4) if recent_vol is not None else None,
            "long_vol": round(long_vol, 4) if long_vol is not None else None,
            "vol_z_score": round(vol_z, 4),
            "vol_rising": vol_rising,
            "price_above_ma50": price_above_ma,
            "latest_price": round(latest_price, 4) if latest_price is not None else None,
            "ma_50": round(ma_50, 4) if ma_50 is not None else None,
        }

        return RegimeResult(
            regime=regime,
            confidence=round(confidence, 4),
            indicators=indicators,
        )

    # ----- Utility helpers -----

    @staticmethod
    def _sum_recent(arr: list, n: int) -> Optional[float]:
        if not arr or len(arr) < 1:
            return None
        window = arr[-n:] if len(arr) >= n else arr
        return sum(window)

    @staticmethod
    def _mean_recent(arr: list, n: int) -> Optional[float]:
        if not arr or len(arr) < 1:
            return None
        window = arr[-n:] if len(arr) >= n else arr
        return sum(window) / len(window)

    @staticmethod
    def _mean_slice(arr: list, start: int, end: int) -> Optional[float]:
        sliced = arr[start:end]
        if not sliced:
            return None
        return sum(sliced) / len(sliced)

    @staticmethod
    def _std_recent(arr: list, n: int) -> float:
        if not arr or len(arr) < 2:
            return 0.0
        window = arr[-n:] if len(arr) >= n else arr
        if len(window) < 2:
            return 0.0
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        return math.sqrt(variance)


# ---------------------------------------------------------------------------
# StrategyRotator
# ---------------------------------------------------------------------------

class StrategyRotator:
    """
    Maps each DashboardRegime to a set of strategy weights and
    blends with equal-weight defaults based on classification confidence.

    Usage:
        rotator = StrategyRotator()
        weights = rotator.get_optimal_weights(regime_result.regime,
                                               regime_result.confidence)
        rotator.save_to_history(regime_result)
    """

    # -------------------------------------------------------------------
    # REGIME_WEIGHTS: regime -> {strategy: weight}
    #
    # Weights do NOT need to sum to 1; they represent relative importance.
    # The get_optimal_weights method normalizes them.
    # -------------------------------------------------------------------
    REGIME_WEIGHTS: Dict[DashboardRegime, Dict[str, float]] = {
        DashboardRegime.BULL_TREND: {
            "Momentum":         0.25,
            "DualMomentum":     0.20,
            "MA":               0.15,
            "InstitutionalFlow": 0.15,
            "Bollinger":        0.08,
            "RSI":              0.07,
            "MACD":             0.05,
            "VolatilityTarget": 0.05,
        },
        DashboardRegime.BEAR_TREND: {
            "Bollinger":        0.25,
            "RSI":              0.20,
            "VolatilityTarget": 0.20,
            "MACD":             0.10,
            "MA":               0.10,
            "InstitutionalFlow": 0.05,
            "Momentum":         0.05,
            "DualMomentum":     0.05,
        },
        DashboardRegime.RANGING: {
            "Bollinger":        0.25,
            "RSI":              0.25,
            "MACD":             0.20,
            "MA":               0.10,
            "VolatilityTarget": 0.08,
            "InstitutionalFlow": 0.05,
            "Momentum":         0.04,
            "DualMomentum":     0.03,
        },
        DashboardRegime.HIGH_VOLATILITY: {
            "VolatilityTarget": 0.30,
            "RSI":              0.20,
            "Bollinger":        0.20,
            "MACD":             0.10,
            "MA":               0.08,
            "InstitutionalFlow": 0.05,
            "DualMomentum":     0.04,
            "Momentum":         0.03,
        },
    }

    def __init__(self):
        self._history: List[dict] = []
        self._load_history()

    # -------------------------------------------------------------------
    # Core: get optimal weights blended with default equal weights
    # -------------------------------------------------------------------

    def get_optimal_weights(
        self,
        regime: DashboardRegime,
        confidence: float,
    ) -> Dict[str, float]:
        """
        Return blended strategy weights for the given regime.

        When confidence is 1.0, returns pure regime weights.
        When confidence is 0.0, returns equal weights.
        In between, linearly blends.

        The returned weights are normalized to sum to 1.0.

        Args:
            regime:     Current DashboardRegime
            confidence: 0.0 .. 1.0 confidence of the classification

        Returns:
            Dict mapping strategy name -> weight (summing to 1.0)
        """
        confidence = max(0.0, min(1.0, confidence))

        regime_w = self.REGIME_WEIGHTS.get(regime, {})
        blended = {}
        for name in STRATEGY_NAMES:
            rw = regime_w.get(name, EQUAL_WEIGHT)
            eq = EQUAL_WEIGHT
            blended[name] = confidence * rw + (1.0 - confidence) * eq

        # Normalize to sum to 1.0
        total = sum(blended.values())
        if total > 0:
            blended = {k: round(v / total, 6) for k, v in blended.items()}

        return blended

    # -------------------------------------------------------------------
    # History persistence
    # -------------------------------------------------------------------

    def save_to_history(self, result: RegimeResult) -> None:
        """Append a regime classification result to the history file."""
        entry = result.to_dict()
        self._history.append(entry)
        # Keep at most 365 days of history
        if len(self._history) > 365:
            self._history = self._history[-365:]
        self._persist_history()

    def get_history(self, days: int = 30) -> List[dict]:
        """
        Return regime history entries from the last N days.

        Args:
            days: Number of days of history to return.

        Returns:
            List of regime result dicts, oldest first.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        result = [
            entry for entry in self._history
            if entry.get("timestamp", "") >= cutoff
        ]
        return result

    def _load_history(self) -> None:
        """Load regime history from JSON file."""
        if os.path.exists(REGIME_HISTORY_PATH):
            try:
                with open(REGIME_HISTORY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._history = data
                else:
                    self._history = []
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load regime history: {e}")
                self._history = []
        else:
            self._history = []

    def _persist_history(self) -> None:
        """Save regime history to JSON file."""
        try:
            with open(REGIME_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to persist regime history: {e}")


# ---------------------------------------------------------------------------
# Helper: compute regime from database trades
# ---------------------------------------------------------------------------

def compute_regime_from_trades(
    trade_rows: list,
    daily_perf_rows: list,
) -> RegimeResult:
    """
    Compute the current market regime using trade history and daily
    performance data from the SQLite database.

    This function extracts returns and volatility series from the
    available data and feeds them to RegimeDetector.classify_regime().

    Args:
        trade_rows:      List of trade dicts from the trades table
                         (action != 'BUY', ordered by timestamp ASC).
        daily_perf_rows: List of daily_performance dicts ordered by date ASC.

    Returns:
        RegimeResult
    """
    detector = RegimeDetector()

    # ----- Build daily returns from daily_performance -----
    returns: List[float] = []
    volatilities: List[float] = []
    prices: List[float] = []

    if daily_perf_rows and len(daily_perf_rows) >= 2:
        # Use total_assets as price proxy
        asset_values = []
        for row in daily_perf_rows:
            val = row.get("total_assets") or row.get("total_pnl") or 0
            asset_values.append(float(val) if val else 0.0)

        # Daily returns as percentage
        for i in range(1, len(asset_values)):
            prev = asset_values[i - 1]
            curr = asset_values[i]
            if prev > 0:
                ret = (curr - prev) / prev * 100.0
                returns.append(ret)
            else:
                returns.append(0.0)

        prices = asset_values

        # Rolling volatility (std of last N daily returns)
        for i in range(len(returns)):
            window_start = max(0, i - 19)  # 20-day rolling
            window = returns[window_start:i + 1]
            if len(window) >= 2:
                mean_r = sum(window) / len(window)
                var = sum((x - mean_r) ** 2 for x in window) / len(window)
                vol = math.sqrt(var)
                volatilities.append(vol)
            else:
                volatilities.append(0.0)
    else:
        # Fallback: use trade P&L data
        if trade_rows:
            for row in trade_rows:
                pnl_pct = row.get("pnl_pct") or 0
                returns.append(float(pnl_pct))

            for i in range(len(returns)):
                window_start = max(0, i - 19)
                window = returns[window_start:i + 1]
                if len(window) >= 2:
                    mean_r = sum(window) / len(window)
                    var = sum((x - mean_r) ** 2 for x in window) / len(window)
                    volatilities.append(math.sqrt(var))
                else:
                    volatilities.append(0.0)

    # If no data at all, return default
    if not returns:
        return RegimeResult(
            regime=DashboardRegime.RANGING,
            confidence=0.3,
            indicators={"note": "Insufficient data for classification"},
        )

    return detector.classify_regime(
        returns=returns,
        volatility=volatilities,
        prices=prices if prices else None,
    )


# ---------------------------------------------------------------------------
# Helper: regime display metadata
# ---------------------------------------------------------------------------

REGIME_DISPLAY = {
    DashboardRegime.BULL_TREND: {
        "label": "BULL_TREND",
        "label_ko": "강세 추세",
        "color": "#3fb950",
        "bg_color": "#23863633",
        "border_color": "#238636",
        "css_class": "regime-bull-trend",
    },
    DashboardRegime.BEAR_TREND: {
        "label": "BEAR_TREND",
        "label_ko": "약세 추세",
        "color": "#f85149",
        "bg_color": "#f8514933",
        "border_color": "#f85149",
        "css_class": "regime-bear-trend",
    },
    DashboardRegime.RANGING: {
        "label": "RANGING",
        "label_ko": "횡보",
        "color": "#d29922",
        "bg_color": "#d2992233",
        "border_color": "#d29922",
        "css_class": "regime-ranging",
    },
    DashboardRegime.HIGH_VOLATILITY: {
        "label": "HIGH_VOLATILITY",
        "label_ko": "고변동성",
        "color": "#f97316",
        "bg_color": "#f9731633",
        "border_color": "#f97316",
        "css_class": "regime-high-vol",
    },
}


def get_regime_display(regime: DashboardRegime) -> dict:
    """Return display metadata for a regime."""
    return REGIME_DISPLAY.get(regime, REGIME_DISPLAY[DashboardRegime.RANGING])
