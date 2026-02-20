"""
Multi-Timeframe Confluence Analyzer.

Analyzes 3 timeframes simultaneously (15min, 1h, 4h) and produces
a confluence score indicating how many timeframes agree on direction.

Confluence scoring:
  +1 per bullish timeframe (max 3)
  0 = all disagree -> block trade
  1 = weak alignment -> reduce confidence 30%
  2 = moderate alignment -> proceed
  3 = strong alignment -> full confidence

Caches higher timeframe data to avoid excessive API calls.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import numpy as np

from .. import config

logger = logging.getLogger("scalper.mtf")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TimeframeBias:
    """Analysis result for a single timeframe."""
    timeframe: str            # "15m", "1h", "4h"
    trend: str                # "bullish", "bearish", "neutral"
    rsi: float                # RSI value (0-100)
    rsi_zone: str             # "oversold", "neutral", "overbought"
    ema_direction: str        # "bullish" (fast>slow), "bearish", "neutral"
    price_vs_vwap: str        # "above", "below", "at"
    ema_fast_val: float = 0.0
    ema_slow_val: float = 0.0
    close_price: float = 0.0

    @property
    def is_bullish(self) -> bool:
        return self.trend == "bullish"

    @property
    def is_bearish(self) -> bool:
        return self.trend == "bearish"

    @property
    def arrow(self) -> str:
        """Return a trend arrow for dashboard display."""
        arrows = {
            "bullish": "\u2191",     # up arrow
            "bearish": "\u2193",     # down arrow
            "neutral": "\u2192",     # right arrow
        }
        return arrows.get(self.trend, "\u2192")

    def to_dict(self) -> dict:
        return {
            "timeframe": self.timeframe,
            "trend": self.trend,
            "arrow": self.arrow,
            "rsi": round(self.rsi, 1),
            "rsi_zone": self.rsi_zone,
            "ema_direction": self.ema_direction,
            "price_vs_vwap": self.price_vs_vwap,
            "ema_fast": round(self.ema_fast_val, 2),
            "ema_slow": round(self.ema_slow_val, 2),
            "close_price": round(self.close_price, 2),
        }


@dataclass
class MTFSignal:
    """Multi-timeframe confluence signal."""
    confluence_score: int             # 0-3
    tf_15m: Optional[TimeframeBias] = None
    tf_1h: Optional[TimeframeBias] = None
    tf_4h: Optional[TimeframeBias] = None
    nearest_support: float = 0.0
    nearest_resistance: float = 0.0
    recommendation: str = "neutral"   # strong_buy / buy / neutral / sell / strong_sell
    available: bool = True            # False if higher TF data unavailable

    @property
    def bullish_count(self) -> int:
        count = 0
        for tf in [self.tf_15m, self.tf_1h, self.tf_4h]:
            if tf and tf.is_bullish:
                count += 1
        return count

    @property
    def bearish_count(self) -> int:
        count = 0
        for tf in [self.tf_15m, self.tf_1h, self.tf_4h]:
            if tf and tf.is_bearish:
                count += 1
        return count

    def to_dict(self) -> dict:
        return {
            "confluence_score": self.confluence_score,
            "recommendation": self.recommendation,
            "bullish_count": self.bullish_count,
            "bearish_count": self.bearish_count,
            "tf_15m": self.tf_15m.to_dict() if self.tf_15m else None,
            "tf_1h": self.tf_1h.to_dict() if self.tf_1h else None,
            "tf_4h": self.tf_4h.to_dict() if self.tf_4h else None,
            "nearest_support": round(self.nearest_support, 2),
            "nearest_resistance": round(self.nearest_resistance, 2),
            "available": self.available,
        }


# ---------------------------------------------------------------------------
# Cache entry for higher timeframe data
# ---------------------------------------------------------------------------

@dataclass
class _CachedTF:
    """Cached higher-timeframe DataFrame + timestamp."""
    df: Optional[pd.DataFrame] = None
    fetched_at: float = 0.0


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

class MultiTimeframeAnalyzer:
    """Analyzes multiple timeframes and produces a confluence score.

    Uses the same pyupbit client to fetch candles on 3 intervals:
      - minute15 (execution timeframe, passed in from caller)
      - minute60 (1h trend)
      - minute240 (4h macro)

    Higher timeframe data is cached for MTF_CACHE_SEC seconds to avoid
    unnecessary API calls (default 300s = 5 min).
    """

    # EMA periods used per timeframe for trend analysis
    EMA_FAST = 9
    EMA_SLOW = 21
    RSI_PERIOD = 14
    VWAP_PERIOD = 14

    def __init__(self):
        # Cache: market -> interval -> _CachedTF
        self._cache: dict[str, dict[str, _CachedTF]] = {}
        self._enabled = getattr(config, "MTF_ENABLED", True)
        self._timeframes = getattr(config, "MTF_TIMEFRAMES",
                                   ["minute15", "minute60", "minute240"])
        self._min_confluence = getattr(config, "MTF_MIN_CONFLUENCE", 2)
        self._cache_sec = getattr(config, "MTF_CACHE_SEC", 300)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, market: str, client, df_15m: Optional[pd.DataFrame] = None) -> MTFSignal:
        """Run multi-timeframe analysis for *market*.

        Parameters
        ----------
        market : str
            Upbit market code, e.g. "KRW-BTC".
        client : UpbitClient
            Used to fetch higher-timeframe candles.
        df_15m : pd.DataFrame or None
            15-minute candle data (already fetched by the main loop).
            If None, will be fetched via *client*.

        Returns
        -------
        MTFSignal with confluence score and per-timeframe breakdown.
        """
        if not self._enabled:
            return self._fallback_signal()

        # 1. 15-minute (execution TF) -- use the data already fetched
        if df_15m is None:
            df_15m = client.get_ohlcv(market, self._timeframes[0],
                                       config.CANDLE_COUNT)
        tf_15m = self._analyze_timeframe(df_15m, "15m") if df_15m is not None else None

        # 2. 1-hour (trend TF) -- cached
        df_1h = self._get_cached_or_fetch(market, self._timeframes[1], client, count=96)
        tf_1h = self._analyze_timeframe(df_1h, "1h") if df_1h is not None else None

        # 3. 4-hour (macro TF) -- cached
        df_4h = self._get_cached_or_fetch(market, self._timeframes[2], client, count=60)
        tf_4h = self._analyze_timeframe(df_4h, "4h") if df_4h is not None else None

        # Handle missing higher TF data gracefully
        if tf_1h is None and tf_4h is None:
            # Cannot do MTF analysis -- fallback
            logger.debug(f"[MTF] {market}: higher TF data unavailable, fallback")
            sig = self._fallback_signal()
            sig.tf_15m = tf_15m
            sig.available = False
            return sig

        # 4. Confluence scoring
        confluence = 0
        for tf in [tf_15m, tf_1h, tf_4h]:
            if tf and tf.is_bullish:
                confluence += 1

        # 5. Support / Resistance from the highest available TF
        sr_df = df_4h if df_4h is not None else (df_1h if df_1h is not None else df_15m)
        support, resistance = 0.0, 0.0
        if sr_df is not None:
            levels = self.get_support_resistance(sr_df)
            current_price = float(sr_df["close"].iloc[-1])
            support, resistance = self._nearest_levels(current_price, levels)

        # 6. Recommendation
        recommendation = self._compute_recommendation(confluence, tf_15m, tf_1h, tf_4h)

        return MTFSignal(
            confluence_score=confluence,
            tf_15m=tf_15m,
            tf_1h=tf_1h,
            tf_4h=tf_4h,
            nearest_support=support,
            nearest_resistance=resistance,
            recommendation=recommendation,
            available=True,
        )

    def get_confluence_filter(self, mtf_signal: MTFSignal, original_confidence: float) -> tuple[bool, float]:
        """Apply MTF confluence filter to a proposed trade.

        Parameters
        ----------
        mtf_signal : MTFSignal
        original_confidence : float
            Confidence from the ensemble strategy.

        Returns
        -------
        (allow_trade: bool, adjusted_confidence: float)
        """
        if not self._enabled or not mtf_signal.available:
            # MTF disabled or data not available -- pass through
            return True, original_confidence

        min_conf = self._min_confluence
        score = mtf_signal.confluence_score

        if score >= min_conf:
            # Good alignment -- full confidence
            return True, original_confidence
        elif score == min_conf - 1:
            # Marginal -- reduce confidence by 30%
            return True, original_confidence * 0.7
        else:
            # No alignment -- block
            return False, 0.0

    def get_status(self) -> dict:
        """Summary for dashboard / get_status()."""
        return {
            "enabled": self._enabled,
            "timeframes": list(self._timeframes),
            "min_confluence": self._min_confluence,
            "cache_sec": self._cache_sec,
        }

    # ------------------------------------------------------------------
    # Per-timeframe analysis
    # ------------------------------------------------------------------

    def _analyze_timeframe(self, df: pd.DataFrame, label: str) -> Optional[TimeframeBias]:
        """Compute trend bias for one timeframe."""
        if df is None or len(df) < max(self.EMA_SLOW, self.RSI_PERIOD) + 5:
            return None

        try:
            close = df["close"]
            high = df["high"]
            low = df["low"]
            volume = df["volume"]
            current_close = float(close.iloc[-1])

            # --- EMA direction ---
            ema_fast = close.ewm(span=self.EMA_FAST, adjust=False).mean()
            ema_slow = close.ewm(span=self.EMA_SLOW, adjust=False).mean()
            ema_fast_val = float(ema_fast.iloc[-1])
            ema_slow_val = float(ema_slow.iloc[-1])

            if pd.isna(ema_fast_val) or pd.isna(ema_slow_val):
                return None

            if ema_fast_val > ema_slow_val * 1.0005:
                ema_direction = "bullish"
            elif ema_fast_val < ema_slow_val * 0.9995:
                ema_direction = "bearish"
            else:
                ema_direction = "neutral"

            # --- RSI ---
            rsi_val = self._compute_rsi(close)
            if rsi_val is None:
                rsi_val = 50.0

            if rsi_val < 30:
                rsi_zone = "oversold"
            elif rsi_val > 70:
                rsi_zone = "overbought"
            else:
                rsi_zone = "neutral"

            # --- Price vs VWAP ---
            vwap_val = self._compute_vwap(high, low, close, volume)
            if vwap_val is not None and not pd.isna(vwap_val):
                if current_close > vwap_val * 1.001:
                    price_vs_vwap = "above"
                elif current_close < vwap_val * 0.999:
                    price_vs_vwap = "below"
                else:
                    price_vs_vwap = "at"
            else:
                price_vs_vwap = "at"  # fallback

            # --- Overall trend bias ---
            trend = self.get_trend_bias(ema_direction, rsi_val, current_close, ema_slow_val)

            return TimeframeBias(
                timeframe=label,
                trend=trend,
                rsi=rsi_val,
                rsi_zone=rsi_zone,
                ema_direction=ema_direction,
                price_vs_vwap=price_vs_vwap,
                ema_fast_val=ema_fast_val,
                ema_slow_val=ema_slow_val,
                close_price=current_close,
            )
        except Exception as e:
            logger.warning(f"[MTF] {label} analysis error: {e}")
            return None

    # ------------------------------------------------------------------
    # Trend bias logic
    # ------------------------------------------------------------------

    @staticmethod
    def get_trend_bias(ema_direction: str, rsi: float, price: float,
                       ema21: float) -> str:
        """Determine overall trend bias from indicators.

        Rules:
          - EMA crossover direction (fast > slow = bullish)
          - Price above/below EMA21
          - RSI above/below 50

        Requires 2 of 3 bullish signals for "bullish", 2 of 3 bearish
        for "bearish", otherwise "neutral".
        """
        bullish_points = 0
        bearish_points = 0

        # 1. EMA direction
        if ema_direction == "bullish":
            bullish_points += 1
        elif ema_direction == "bearish":
            bearish_points += 1

        # 2. Price vs EMA21
        if ema21 > 0:
            if price > ema21:
                bullish_points += 1
            elif price < ema21:
                bearish_points += 1

        # 3. RSI above/below 50
        if rsi > 55:
            bullish_points += 1
        elif rsi < 45:
            bearish_points += 1

        if bullish_points >= 2:
            return "bullish"
        elif bearish_points >= 2:
            return "bearish"
        return "neutral"

    # ------------------------------------------------------------------
    # Support / Resistance
    # ------------------------------------------------------------------

    @staticmethod
    def get_support_resistance(df: pd.DataFrame, lookback: int = 30,
                               tolerance_pct: float = 0.005) -> list[tuple[float, str]]:
        """Find recent swing highs (resistance) and swing lows (support).

        Returns a list of (price, type) where type is "support" or
        "resistance", sorted by distance from current price (nearest
        first).
        """
        if df is None or len(df) < lookback:
            return []

        high = df["high"].values
        low = df["low"].values
        close_now = float(df["close"].iloc[-1])
        levels: list[tuple[float, str]] = []

        tail_high = high[-lookback:]
        tail_low = low[-lookback:]

        # Swing highs (local maxima with 2-bar look-around)
        for i in range(2, len(tail_high) - 2):
            if (tail_high[i] > tail_high[i - 1] and tail_high[i] > tail_high[i - 2]
                    and tail_high[i] > tail_high[i + 1] and tail_high[i] > tail_high[i + 2]):
                price = float(tail_high[i])
                # Deduplicate within tolerance
                if not any(abs(p - price) / price < tolerance_pct for p, _ in levels):
                    levels.append((price, "resistance"))

        # Swing lows (local minima with 2-bar look-around)
        for i in range(2, len(tail_low) - 2):
            if (tail_low[i] < tail_low[i - 1] and tail_low[i] < tail_low[i - 2]
                    and tail_low[i] < tail_low[i + 1] and tail_low[i] < tail_low[i + 2]):
                price = float(tail_low[i])
                if not any(abs(p - price) / price < tolerance_pct for p, _ in levels):
                    levels.append((price, "support"))

        # Sort by proximity to current price
        levels.sort(key=lambda x: abs(x[0] - close_now))
        return levels

    @staticmethod
    def _nearest_levels(current_price: float,
                        levels: list[tuple[float, str]]) -> tuple[float, float]:
        """Extract nearest support and nearest resistance from levels list."""
        nearest_support = 0.0
        nearest_resistance = 0.0

        for price, kind in levels:
            if kind == "support" and price < current_price:
                if nearest_support == 0.0 or abs(price - current_price) < abs(nearest_support - current_price):
                    nearest_support = price
            elif kind == "resistance" and price > current_price:
                if nearest_resistance == 0.0 or abs(price - current_price) < abs(nearest_resistance - current_price):
                    nearest_resistance = price

        return nearest_support, nearest_resistance

    # ------------------------------------------------------------------
    # Recommendation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_recommendation(confluence: int,
                                tf_15m: Optional[TimeframeBias],
                                tf_1h: Optional[TimeframeBias],
                                tf_4h: Optional[TimeframeBias]) -> str:
        """Compute overall recommendation from confluence + bias."""
        bearish_count = sum(1 for tf in [tf_15m, tf_1h, tf_4h]
                           if tf and tf.is_bearish)

        if confluence == 3:
            return "strong_buy"
        elif confluence == 2:
            return "buy"
        elif confluence == 0 and bearish_count >= 2:
            if bearish_count == 3:
                return "strong_sell"
            return "sell"
        return "neutral"

    # ------------------------------------------------------------------
    # Indicator helpers
    # ------------------------------------------------------------------

    def _compute_rsi(self, close: pd.Series) -> Optional[float]:
        """Compute RSI for the close series."""
        if len(close) < self.RSI_PERIOD + 2:
            return None
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta.clip(upper=0))
        avg_gain = gain.rolling(window=self.RSI_PERIOD,
                                min_periods=self.RSI_PERIOD).mean()
        avg_loss = loss.rolling(window=self.RSI_PERIOD,
                                min_periods=self.RSI_PERIOD).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return float(val) if not pd.isna(val) else None

    def _compute_vwap(self, high: pd.Series, low: pd.Series,
                      close: pd.Series, volume: pd.Series) -> Optional[float]:
        """Compute rolling VWAP."""
        if len(close) < self.VWAP_PERIOD:
            return None
        tp = (high + low + close) / 3
        cum_tp_vol = (tp * volume).rolling(window=self.VWAP_PERIOD).sum()
        cum_vol = volume.rolling(window=self.VWAP_PERIOD).sum()
        vwap = cum_tp_vol / cum_vol.replace(0, 1e-10)
        val = vwap.iloc[-1]
        return float(val) if not pd.isna(val) else None

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _get_cached_or_fetch(self, market: str, interval: str,
                             client, count: int = 96) -> Optional[pd.DataFrame]:
        """Return cached DataFrame if fresh enough, else fetch new."""
        if market not in self._cache:
            self._cache[market] = {}

        entry = self._cache[market].get(interval)
        now = time.time()

        if entry and entry.df is not None and (now - entry.fetched_at) < self._cache_sec:
            return entry.df

        # Fetch fresh data
        try:
            df = client.get_ohlcv(market, interval, count)
            self._cache[market][interval] = _CachedTF(df=df, fetched_at=now)
            return df
        except Exception as e:
            logger.warning(f"[MTF] Failed to fetch {interval} for {market}: {e}")
            # Return stale cache if available
            if entry and entry.df is not None:
                return entry.df
            return None

    def clear_cache(self, market: Optional[str] = None):
        """Clear cached data for a market or all markets."""
        if market:
            self._cache.pop(market, None)
        else:
            self._cache.clear()

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_signal() -> MTFSignal:
        """Return a neutral signal when MTF analysis cannot be performed."""
        return MTFSignal(
            confluence_score=0,
            recommendation="neutral",
            available=False,
        )
