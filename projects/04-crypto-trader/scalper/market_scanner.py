"""
Dynamic Market Scanner: periodically selects top-volume KRW markets.

Runs on a configurable interval (default 1 hour), fetching 24h trading
volume for all KRW pairs and selecting the top N above a minimum threshold.
"""
import logging
import threading
import time
from typing import Optional

from . import config

logger = logging.getLogger("scalper.scanner")


class MarketScanner:
    """Scans Upbit KRW markets by 24h trading volume."""

    def __init__(self, top_n: int = None, scan_interval_sec: int = None,
                 min_volume_krw: float = None):
        self._top_n = top_n or config.SCANNER_TOP_N
        self._scan_interval = scan_interval_sec or config.SCANNER_INTERVAL_SEC
        self._min_volume = min_volume_krw or config.SCANNER_MIN_VOLUME_KRW
        self._lock = threading.Lock()
        self._active_markets: list[str] = list(config.MARKETS)  # start with defaults
        self._last_scan: float = 0.0
        self._last_volumes: dict[str, float] = {}  # market -> 24h volume KRW

        logger.info(f"MarketScanner initialized (top_n={self._top_n}, "
                    f"interval={self._scan_interval}s, "
                    f"min_vol={self._min_volume:,.0f} KRW)")

    def get_markets(self, open_positions: dict) -> list[str]:
        """Return current active markets, preserving open position markets.

        Args:
            open_positions: dict of market -> OpenPosition from trader
        Returns:
            list of market tickers to scan
        """
        now = time.time()
        if now - self._last_scan > self._scan_interval:
            try:
                self._scan()
            except Exception as e:
                logger.error(f"Scanner error: {e}", exc_info=True)

        with self._lock:
            markets = list(self._active_markets)

        # Always include markets where we have open positions
        for m in open_positions:
            if m not in markets:
                markets.append(m)
                logger.debug(f"Scanner: keeping {m} (open position)")

        return markets

    def _scan(self):
        """Fetch all KRW tickers and select top N by 24h trading volume."""
        try:
            import pyupbit
        except ImportError:
            logger.warning("pyupbit not installed, using default markets")
            return

        logger.info("Scanner: fetching KRW market volumes...")
        start = time.time()

        try:
            tickers = pyupbit.get_tickers(fiat="KRW")
        except Exception as e:
            logger.error(f"Scanner: failed to get tickers: {e}")
            return

        if not tickers:
            logger.warning("Scanner: no tickers returned")
            return

        # Fetch 24h volume + volatility for each ticker
        volumes: dict[str, float] = {}
        volatilities: dict[str, float] = {}  # ticker -> (high-low)/close
        for ticker in tickers:
            try:
                df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
                if df is not None and not df.empty:
                    # pyupbit day candle has 'value' column = 24h trading value in KRW
                    if "value" in df.columns:
                        vol_krw = float(df["value"].iloc[-1])
                    else:
                        # Fallback: close * volume
                        vol_krw = float(df["close"].iloc[-1] * df["volume"].iloc[-1])
                    volumes[ticker] = vol_krw
                    # 24h 변동성: (고가-저가)/종가
                    close = float(df["close"].iloc[-1])
                    if close > 0:
                        volatilities[ticker] = (float(df["high"].iloc[-1]) - float(df["low"].iloc[-1])) / close
                time.sleep(0.1)  # Rate limit: 10 req/sec for Upbit
            except Exception as e:
                logger.debug(f"Scanner: failed to get volume for {ticker}: {e}")
                continue

        if not volumes:
            logger.warning("Scanner: no volume data retrieved")
            return

        # Filter by minimum volume, then score by volume * volatility
        qualified = {k: v for k, v in volumes.items() if v >= self._min_volume}
        # Combined score: volume_rank * volatility -> favors liquid + volatile coins
        scores = {}
        for ticker, vol in qualified.items():
            vol_pct = volatilities.get(ticker, 0.0)
            # Score = volume * (1 + volatility*10): volatile coins boosted
            scores[ticker] = vol * (1 + vol_pct * 10)

        sorted_markets = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_markets = [m for m, _ in sorted_markets[:self._top_n]]

        # Always include default markets (BTC, ETH etc.) even if scanner missed them
        for default_market in config.MARKETS:
            if default_market not in top_markets:
                top_markets.append(default_market)
                logger.info(f"Scanner: keeping default market {default_market}")

        # Log changes
        with self._lock:
            old_set = set(self._active_markets)
            new_set = set(top_markets)
            added = new_set - old_set
            removed = old_set - new_set

            if added or removed:
                logger.info(f"Scanner: markets updated "
                           f"(+{list(added) if added else '[]'}, "
                           f"-{list(removed) if removed else '[]'})")

            self._active_markets = top_markets
            self._last_volumes = volumes
            self._last_scan = time.time()

        elapsed = time.time() - start
        logger.info(f"Scanner: selected {len(top_markets)} markets in {elapsed:.1f}s: "
                    f"{top_markets}")

        # Log top volumes for reference
        for market, vol in sorted_markets[:self._top_n + 3]:
            logger.debug(f"  {market}: {vol:,.0f} KRW")

    def get_active_markets(self) -> list[str]:
        """Return current active markets (for dashboard)."""
        with self._lock:
            return list(self._active_markets)

    def get_status(self) -> dict:
        """Status for dashboard display."""
        with self._lock:
            return {
                "enabled": True,
                "active_markets": list(self._active_markets),
                "last_scan": self._last_scan,
                "scan_interval_sec": self._scan_interval,
                "top_n": self._top_n,
                "min_volume_krw": self._min_volume,
                "market_volumes": {
                    k: round(v, 0)
                    for k, v in sorted(
                        self._last_volumes.items(),
                        key=lambda x: x[1], reverse=True
                    )[:10]
                },
            }
