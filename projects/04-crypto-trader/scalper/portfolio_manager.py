"""
Cross-Market Correlation & Portfolio Risk Management.

Provides:
- CorrelationMatrix: rolling Pearson correlation across all traded markets
- PortfolioRiskManager: portfolio-level VaR, concentration risk, trade gating
"""
import logging
import math
from collections import defaultdict
from typing import Optional

from . import config

logger = logging.getLogger("scalper.portfolio")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pearson(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation between two equal-length lists.

    Returns 0.0 on insufficient data or zero variance.
    """
    n = min(len(x), len(y))
    if n < 5:
        return 0.0

    x = x[-n:]
    y = y[-n:]

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = 0.0
    var_x = 0.0
    var_y = 0.0
    for i in range(n):
        dx = x[i] - mean_x
        dy = y[i] - mean_y
        cov += dx * dy
        var_x += dx * dx
        var_y += dy * dy

    denom = math.sqrt(var_x * var_y)
    if denom < 1e-12:
        return 0.0
    return cov / denom


def _returns_from_closes(closes: list[float]) -> list[float]:
    """Convert a list of close prices into simple returns."""
    if len(closes) < 2:
        return []
    return [(closes[i] / closes[i - 1]) - 1.0 for i in range(1, len(closes))]


# ---------------------------------------------------------------------------
# CorrelationMatrix
# ---------------------------------------------------------------------------

class CorrelationMatrix:
    """Maintains rolling returns per market and computes NxN correlations.

    Rolling window default: 96 candles (24 h of 15-min candles).
    """

    def __init__(self, window: int = None):
        self.window: int = window or getattr(config, "CORRELATION_WINDOW", 96)
        # market -> list of most-recent returns (max length = window)
        self._returns: dict[str, list[float]] = defaultdict(list)

    # -- public API ----------------------------------------------------------

    def update(self, market: str, returns_list: list[float]) -> None:
        """Store / replace rolling returns for *market*.

        ``returns_list`` should contain the most recent N simple returns
        (newest last).  We keep only the latest ``self.window`` entries.
        """
        trimmed = returns_list[-self.window:] if len(returns_list) > self.window else list(returns_list)
        self._returns[market] = trimmed

    def feed_closes(self, market: str, closes: list[float]) -> None:
        """Convenience: compute returns from close prices and store them."""
        rets = _returns_from_closes(closes)
        self.update(market, rets)

    @property
    def markets(self) -> list[str]:
        """Markets that currently have stored returns."""
        return sorted(self._returns.keys())

    def get_pair_correlation(self, a: str, b: str) -> float:
        """Pearson correlation between two markets.

        Returns 0.0 if either market has no data.  Returns 1.0 if a == b.
        """
        if a == b:
            return 1.0
        ra = self._returns.get(a, [])
        rb = self._returns.get(b, [])
        if not ra or not rb:
            return 0.0
        return _pearson(ra, rb)

    def get_matrix(self) -> dict[str, dict[str, float]]:
        """Compute and return full NxN correlation matrix.

        Returns dict-of-dicts: ``matrix[a][b] = correlation``.
        """
        mkts = self.markets
        matrix: dict[str, dict[str, float]] = {}
        for a in mkts:
            matrix[a] = {}
            for b in mkts:
                matrix[a][b] = self.get_pair_correlation(a, b)
        return matrix

    def get_max_corr_pair(self) -> tuple[str, str, float]:
        """Return the pair of markets with the highest absolute correlation.

        Returns ("", "", 0.0) if fewer than 2 markets.
        """
        mkts = self.markets
        if len(mkts) < 2:
            return ("", "", 0.0)

        best_a, best_b, best_corr = "", "", -2.0
        for i, a in enumerate(mkts):
            for b in mkts[i + 1:]:
                c = abs(self.get_pair_correlation(a, b))
                if c > best_corr:
                    best_a, best_b, best_corr = a, b, c
        return (best_a, best_b, round(best_corr, 4))

    def get_data_readiness(self) -> dict[str, int]:
        """Return number of stored returns per market (debug helper)."""
        return {m: len(r) for m, r in self._returns.items()}


# ---------------------------------------------------------------------------
# PortfolioRiskManager
# ---------------------------------------------------------------------------

class PortfolioRiskManager:
    """Portfolio-level risk checks: VaR, concentration, trade gating.

    Works on top of ``CorrelationMatrix`` and the list of open positions.
    """

    def __init__(self):
        self.correlation = CorrelationMatrix()
        self._enabled: bool = getattr(config, "PORTFOLIO_RISK_ENABLED", True)
        self._max_var_pct: float = getattr(config, "MAX_PORTFOLIO_VAR_PCT", 0.05)
        self._conc_threshold: float = getattr(config, "CONCENTRATION_THRESHOLD", 0.8)
        self._max_corr_positions: int = getattr(config, "MAX_CORRELATED_POSITIONS", 2)
        # Track portfolio value for VaR percentage
        self._last_portfolio_value: float = 0.0

    # -- feed data -----------------------------------------------------------

    def feed_closes(self, market: str, closes: list[float]) -> None:
        """Pass-through to CorrelationMatrix.feed_closes."""
        self.correlation.feed_closes(market, closes)

    # -- portfolio VaR -------------------------------------------------------

    def calculate_portfolio_var(
        self,
        positions: dict[str, dict],
        balance_krw: float = 0.0,
        confidence_z: float = 1.65,
    ) -> dict:
        """Compute correlation-adjusted portfolio VaR.

        Uses the variance-covariance (parametric) method:
            portfolio_var = z * sqrt( w^T * C * w )

        where *w* is the vector of position values and *C* is the covariance
        matrix (correlation * vol_i * vol_j).

        ``positions`` is ``{market: {entry_price, amount, ...}}``.

        Returns dict with ``var_krw``, ``var_pct``, ``undiversified_var_krw``,
        ``diversification_ratio``.
        """
        mkts = list(positions.keys())
        n = len(mkts)

        if n == 0:
            return {
                "var_krw": 0.0,
                "var_pct": 0.0,
                "undiversified_var_krw": 0.0,
                "diversification_ratio": 1.0,
            }

        # Position values (KRW)
        values = []
        for m in mkts:
            p = positions[m]
            entry = p.get("entry_price", 0)
            amount = p.get("amount", 0)
            current = p.get("current_price", entry)
            values.append(current * amount if current and amount else entry * amount)

        total_value = sum(values) if sum(values) > 0 else 1.0
        self._last_portfolio_value = total_value

        # Per-asset volatilities (std of returns)
        vols = []
        for m in mkts:
            rets = self.correlation._returns.get(m, [])
            if len(rets) >= 5:
                mean_r = sum(rets) / len(rets)
                var_r = sum((r - mean_r) ** 2 for r in rets) / len(rets)
                vols.append(math.sqrt(var_r))
            else:
                # Default 2% daily vol proxy for crypto (conservative)
                vols.append(0.02)

        # Undiversified VaR = sum of individual VaRs
        individual_vars = [confidence_z * vols[i] * values[i] for i in range(n)]
        undiversified_var = sum(individual_vars)

        # Correlation-adjusted (diversified) portfolio variance
        port_variance = 0.0
        for i in range(n):
            for j in range(n):
                corr_ij = self.correlation.get_pair_correlation(mkts[i], mkts[j])
                port_variance += values[i] * values[j] * vols[i] * vols[j] * corr_ij

        port_std = math.sqrt(max(0.0, port_variance))
        diversified_var = confidence_z * port_std

        # Diversification ratio
        div_ratio = (undiversified_var / diversified_var) if diversified_var > 0 else 1.0

        # VaR as percentage of total portfolio (balance + position value)
        portfolio_total = max(balance_krw + total_value, 1.0)
        var_pct = diversified_var / portfolio_total

        return {
            "var_krw": round(diversified_var, 0),
            "var_pct": round(var_pct, 4),
            "undiversified_var_krw": round(undiversified_var, 0),
            "diversification_ratio": round(div_ratio, 3),
        }

    # -- concentration risk --------------------------------------------------

    def check_concentration_risk(
        self,
        positions: dict[str, dict],
    ) -> dict:
        """Flag if >60% of total exposure sits in highly correlated (>threshold) assets.

        Returns dict with ``is_concentrated``, ``correlated_groups``,
        ``correlated_exposure_pct``.
        """
        mkts = list(positions.keys())
        n = len(mkts)
        threshold = self._conc_threshold

        if n < 2:
            return {
                "is_concentrated": False,
                "correlated_groups": [],
                "correlated_exposure_pct": 0.0,
            }

        # Position values
        values: dict[str, float] = {}
        for m in mkts:
            p = positions[m]
            entry = p.get("entry_price", 0)
            amount = p.get("amount", 0)
            current = p.get("current_price", entry)
            values[m] = current * amount if current and amount else entry * amount

        total_exposure = sum(values.values()) or 1.0

        # Find groups of mutually correlated markets
        correlated_groups: list[dict] = []
        visited = set()
        for i, a in enumerate(mkts):
            if a in visited:
                continue
            group = [a]
            for b in mkts[i + 1:]:
                if b in visited:
                    continue
                corr = abs(self.correlation.get_pair_correlation(a, b))
                if corr >= threshold:
                    group.append(b)
            if len(group) > 1:
                group_val = sum(values.get(m, 0) for m in group)
                group_pct = group_val / total_exposure
                correlated_groups.append({
                    "markets": group,
                    "exposure_pct": round(group_pct, 3),
                    "max_corr": round(max(
                        abs(self.correlation.get_pair_correlation(group[gi], group[gj]))
                        for gi in range(len(group))
                        for gj in range(gi + 1, len(group))
                    ), 3),
                })
                for m in group:
                    visited.add(m)

        # Total correlated exposure
        correlated_total = sum(g["exposure_pct"] for g in correlated_groups)
        is_concentrated = correlated_total > 0.60

        return {
            "is_concentrated": is_concentrated,
            "correlated_groups": correlated_groups,
            "correlated_exposure_pct": round(correlated_total, 3),
        }

    # -- trade gating --------------------------------------------------------

    def should_allow_trade(
        self,
        market: str,
        positions: dict[str, dict],
        balance_krw: float = 0.0,
    ) -> tuple[bool, str]:
        """Decide whether opening a new position in *market* is safe.

        Returns ``(allowed, reason)``.
        """
        if not self._enabled:
            return (True, "portfolio risk disabled")

        mkts_in_positions = list(positions.keys())

        # 1. Check how many existing positions are highly correlated with
        #    the candidate market.
        corr_count = 0
        for m in mkts_in_positions:
            corr = abs(self.correlation.get_pair_correlation(market, m))
            if corr >= self._conc_threshold:
                corr_count += 1

        if corr_count >= self._max_corr_positions:
            return (
                False,
                f"already {corr_count} correlated (>{self._conc_threshold:.0%}) positions for {market}",
            )

        # 2. Check current portfolio VaR (before the new trade)
        var_info = self.calculate_portfolio_var(positions, balance_krw)
        if var_info["var_pct"] >= self._max_var_pct:
            return (
                False,
                f"portfolio VaR {var_info['var_pct']:.2%} >= limit {self._max_var_pct:.2%}",
            )

        # 3. Check concentration risk
        conc = self.check_concentration_risk(positions)
        if conc["is_concentrated"]:
            return (
                False,
                f"concentration risk: {conc['correlated_exposure_pct']:.0%} in correlated assets",
            )

        return (True, "ok")

    # -- stats ---------------------------------------------------------------

    def get_portfolio_stats(
        self,
        positions: dict[str, dict],
        balance_krw: float = 0.0,
    ) -> dict:
        """Aggregate portfolio statistics for the dashboard.

        Returns a flat dict suitable for JSON serialisation.
        """
        # Total exposure
        total_exposure = 0.0
        for p in positions.values():
            entry = p.get("entry_price", 0)
            amount = p.get("amount", 0)
            current = p.get("current_price", entry)
            total_exposure += current * amount if current and amount else entry * amount

        # VaR
        var_info = self.calculate_portfolio_var(positions, balance_krw)

        # Concentration
        conc = self.check_concentration_risk(positions)

        # Max correlated pair (across all tracked markets, not just positions)
        max_pair = self.correlation.get_max_corr_pair()

        # Correlation matrix (for heatmap)
        matrix = self.correlation.get_matrix()

        # Data readiness
        readiness = self.correlation.get_data_readiness()
        markets_with_data = sum(1 for v in readiness.values() if v >= 10)

        return {
            "enabled": self._enabled,
            "total_exposure_krw": round(total_exposure, 0),
            "var_krw": var_info["var_krw"],
            "var_pct": var_info["var_pct"],
            "max_var_pct": self._max_var_pct,
            "undiversified_var_krw": var_info["undiversified_var_krw"],
            "diversification_ratio": var_info["diversification_ratio"],
            "is_concentrated": conc["is_concentrated"],
            "correlated_groups": conc["correlated_groups"],
            "correlated_exposure_pct": conc["correlated_exposure_pct"],
            "concentration_threshold": self._conc_threshold,
            "max_correlated_positions": self._max_corr_positions,
            "max_corr_pair": {
                "a": max_pair[0],
                "b": max_pair[1],
                "corr": max_pair[2],
            },
            "correlation_matrix": matrix,
            "markets_tracked": len(readiness),
            "markets_with_data": markets_with_data,
            "data_readiness": readiness,
        }
