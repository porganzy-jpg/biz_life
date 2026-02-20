# -*- coding: utf-8 -*-
"""
Portfolio Correlation Monitor - 포트폴리오 상관관계 모니터링

포지션 간 상관관계 분석, 섹터 편중도, 분산투자 점수, 집중도 리스크(HHI) 산출.
결과는 5분 TTL 캐시 + 일일 JSON 스냅샷으로 추적.
"""
import json
import logging
import math
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_DIR = os.path.join(_DIR, "..", "correlation_snapshots")
SNAPSHOT_HISTORY_PATH = os.path.join(_DIR, "..", "correlation_history.json")

# ---------------------------------------------------------------------------
# Korean sector classification mapping
# ---------------------------------------------------------------------------
SECTOR_MAP: Dict[str, str] = {
    # 반도체 -> IT
    "반도체": "IT",
    "인터넷": "IT",
    "소프트웨어": "IT",
    "IT": "IT",
    "통신": "IT",
    # 금융
    "금융": "금융",
    "은행": "금융",
    "보험": "금융",
    "증권": "금융",
    # 바이오
    "바이오": "바이오",
    "제약": "바이오",
    "헬스케어": "바이오",
    # 소비재
    "소비재": "소비재",
    "유통": "소비재",
    "음식료": "소비재",
    "의류": "소비재",
    # 산업재
    "산업재": "산업재",
    "건설": "산업재",
    "기계": "산업재",
    "조선": "산업재",
    "운송": "산업재",
    # 에너지/소재
    "화학": "에너지/소재",
    "에너지": "에너지/소재",
    "정유": "에너지/소재",
    "철강": "에너지/소재",
    # 2차전지/전기차
    "2차전지": "2차전지",
    "전기차": "2차전지",
    # 자동차
    "자동차": "자동차",
    # 기타
    "기타": "기타",
}

# Sector display colours for charts
SECTOR_COLORS: Dict[str, str] = {
    "IT": "#58a6ff",
    "금융": "#3fb950",
    "바이오": "#bc8cff",
    "소비재": "#f778ba",
    "산업재": "#d29922",
    "에너지/소재": "#f97316",
    "2차전지": "#39d2c0",
    "자동차": "#79c0ff",
    "기타": "#8b949e",
}


def _classify_sector(raw_sector: str) -> str:
    """Map a raw sector string to one of the Korean classification buckets."""
    if not raw_sector:
        return "기타"
    return SECTOR_MAP.get(raw_sector, "기타")


# ---------------------------------------------------------------------------
# Simple TTL Cache
# ---------------------------------------------------------------------------
class _TTLCache:
    """Minimal key-value cache with per-entry TTL (seconds)."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def invalidate(self, key: str = None) -> None:
        if key:
            self._store.pop(key, None)
        else:
            self._store.clear()


# ---------------------------------------------------------------------------
# CorrelationMonitor
# ---------------------------------------------------------------------------
class CorrelationMonitor:
    """
    Portfolio correlation & risk monitoring.

    All heavy computations are cached with a 5-minute TTL.
    Daily snapshots are stored in JSON for trend tracking.
    """

    def __init__(self, broker_client=None):
        """
        Args:
            broker_client: BrokerClient instance for fetching OHLCV data.
                           If None, correlation methods will return empty/default.
        """
        self.broker = broker_client
        self._cache = _TTLCache(ttl_seconds=300)  # 5-min TTL

        # Ensure snapshot directory exists
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)

        # Alerts accumulator (reset each time get_alerts is called)
        self._alerts: List[Dict[str, str]] = []

        # Load history
        self._history: List[dict] = []
        self._load_history()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_correlation_matrix(
        self,
        positions: Dict[str, dict],
        lookback: int = 20,
    ) -> Dict[str, Any]:
        """
        Calculate pairwise correlation matrix for held positions using
        daily close returns.

        Args:
            positions: {symbol: {qty, avg_price, name, sector?, ...}}
            lookback:  Number of trading days for rolling window.

        Returns:
            {
              "symbols": [str, ...],
              "names": [str, ...],
              "matrix": [[float, ...], ...],   # NxN correlation
              "avg_correlation": float,
              "timestamp": str,
            }
        """
        cache_key = f"corr_matrix_{_positions_hash(positions)}_{lookback}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        symbols = list(positions.keys())
        names = [positions[s].get("name", s) for s in symbols]
        n = len(symbols)

        if n < 2 or self.broker is None:
            result = {
                "symbols": symbols,
                "names": names,
                "matrix": [[1.0] * n for _ in range(n)],
                "avg_correlation": 0.0,
                "timestamp": datetime.now().isoformat(),
            }
            self._cache.set(cache_key, result)
            return result

        # Fetch daily close returns
        returns_map: Dict[str, List[float]] = {}
        for sym in symbols:
            try:
                df = self.broker.fetch_ohlcv(sym, count=lookback + 5)
                if df is not None and len(df) >= 2:
                    closes = df["close"].tolist()
                    rets = []
                    for i in range(1, len(closes)):
                        prev = closes[i - 1]
                        if prev != 0:
                            rets.append((closes[i] - prev) / prev)
                        else:
                            rets.append(0.0)
                    # Trim to lookback
                    returns_map[sym] = rets[-lookback:]
                else:
                    returns_map[sym] = []
            except Exception as e:
                logger.debug(f"OHLCV fetch failed for {sym}: {e}")
                returns_map[sym] = []

        # Align lengths
        min_len = min((len(v) for v in returns_map.values()), default=0)
        if min_len < 3:
            result = {
                "symbols": symbols,
                "names": names,
                "matrix": [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)],
                "avg_correlation": 0.0,
                "timestamp": datetime.now().isoformat(),
            }
            self._cache.set(cache_key, result)
            return result

        aligned: Dict[str, List[float]] = {}
        for sym in symbols:
            aligned[sym] = returns_map[sym][-min_len:]

        # Compute NxN Pearson correlation
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                elif j > i:
                    corr = _pearson(aligned[symbols[i]], aligned[symbols[j]])
                    matrix[i][j] = round(corr, 4)
                    matrix[j][i] = round(corr, 4)
                # j < i already filled by symmetry in the elif branch

        # Average off-diagonal correlation
        off_diag = []
        for i in range(n):
            for j in range(i + 1, n):
                off_diag.append(matrix[i][j])
        avg_corr = round(sum(off_diag) / len(off_diag), 4) if off_diag else 0.0

        result = {
            "symbols": symbols,
            "names": names,
            "matrix": matrix,
            "avg_correlation": avg_corr,
            "timestamp": datetime.now().isoformat(),
        }
        self._cache.set(cache_key, result)
        return result

    def detect_correlation_spike(
        self,
        positions: Dict[str, dict],
        threshold: float = 0.2,
        lookback: int = 20,
    ) -> Dict[str, Any]:
        """
        Detect when average pairwise correlation jumps significantly
        compared to a longer lookback baseline.

        Args:
            positions: Current held positions.
            threshold: Minimum increase in avg correlation to trigger alert.
            lookback:  Short window for current correlation.

        Returns:
            {
              "spike_detected": bool,
              "current_avg": float,
              "baseline_avg": float,
              "delta": float,
              "threshold": float,
            }
        """
        cache_key = f"corr_spike_{_positions_hash(positions)}_{threshold}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        current = self.compute_correlation_matrix(positions, lookback=lookback)
        baseline = self.compute_correlation_matrix(positions, lookback=lookback * 3)

        current_avg = current["avg_correlation"]
        baseline_avg = baseline["avg_correlation"]
        delta = round(current_avg - baseline_avg, 4)
        spike = delta >= threshold

        if spike:
            self._alerts.append({
                "level": "warning",
                "type": "correlation_spike",
                "message": (
                    f"상관관계 급등 감지: 평균 상관계수 {current_avg:.2f} "
                    f"(기준선 {baseline_avg:.2f} 대비 +{delta:.2f})"
                ),
                "timestamp": datetime.now().isoformat(),
            })

        result = {
            "spike_detected": spike,
            "current_avg": current_avg,
            "baseline_avg": baseline_avg,
            "delta": delta,
            "threshold": threshold,
        }
        self._cache.set(cache_key, result)
        return result

    def get_sector_exposure(
        self,
        positions: Dict[str, dict],
    ) -> Dict[str, Any]:
        """
        Calculate sector weight percentages.

        Args:
            positions: {symbol: {qty, avg_price, name, sector?, ...}}

        Returns:
            {
              "sectors": {sector_name: {"weight_pct": float, "value": float, "stocks": [str]}},
              "total_value": float,
              "sector_count": int,
            }
        """
        cache_key = f"sector_exp_{_positions_hash(positions)}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        sectors: Dict[str, Dict[str, Any]] = {}
        total_value = 0.0

        for sym, pos in positions.items():
            qty = pos.get("qty", 0)
            price = pos.get("avg_price", 0)
            value = qty * price
            total_value += value

            raw_sector = pos.get("sector", "기타")
            sector = _classify_sector(raw_sector)

            if sector not in sectors:
                sectors[sector] = {"value": 0.0, "stocks": [], "color": SECTOR_COLORS.get(sector, "#8b949e")}
            sectors[sector]["value"] += value
            sectors[sector]["stocks"].append(pos.get("name", sym))

        # Calculate percentages
        for sec in sectors.values():
            sec["weight_pct"] = round(sec["value"] / total_value * 100, 1) if total_value > 0 else 0.0

        result = {
            "sectors": sectors,
            "total_value": total_value,
            "sector_count": len(sectors),
        }
        self._cache.set(cache_key, result)
        return result

    def sector_rebalance_signal(
        self,
        positions: Dict[str, dict],
        threshold: float = 35.0,
    ) -> Dict[str, Any]:
        """
        Warn when any sector exceeds the given threshold percentage.

        Returns:
            {
              "rebalance_needed": bool,
              "over_threshold": [{sector, weight_pct, excess_pct}],
              "threshold": float,
              "suggestions": [str],
            }
        """
        cache_key = f"sector_rebal_{_positions_hash(positions)}_{threshold}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        exposure = self.get_sector_exposure(positions)
        sectors = exposure["sectors"]

        over = []
        suggestions = []
        for name, data in sectors.items():
            w = data["weight_pct"]
            if w > threshold:
                excess = round(w - threshold, 1)
                over.append({
                    "sector": name,
                    "weight_pct": w,
                    "excess_pct": excess,
                })
                suggestions.append(
                    f"{name} 섹터 비중 {w:.1f}% (한도 {threshold:.0f}% 초과 +{excess:.1f}%) "
                    f"- 비중 축소 권고"
                )
                self._alerts.append({
                    "level": "warning",
                    "type": "sector_overweight",
                    "message": f"{name} 섹터 비중 초과: {w:.1f}% (한도 {threshold:.0f}%)",
                    "timestamp": datetime.now().isoformat(),
                })

        result = {
            "rebalance_needed": len(over) > 0,
            "over_threshold": over,
            "threshold": threshold,
            "suggestions": suggestions,
        }
        self._cache.set(cache_key, result)
        return result

    def get_diversification_score(
        self,
        positions: Dict[str, dict],
        lookback: int = 20,
    ) -> Dict[str, Any]:
        """
        Compute a 0-100 diversification score for the portfolio.

        Score components:
            - Position count bonus (up to 30 pts)
            - Sector diversity bonus (up to 30 pts)
            - Low avg correlation bonus (up to 25 pts)
            - Even weight distribution bonus (up to 15 pts)

        Returns:
            {"score": float, "grade": str, "components": {...}}
        """
        cache_key = f"div_score_{_positions_hash(positions)}_{lookback}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        n = len(positions)
        if n == 0:
            result = {
                "score": 0,
                "grade": "N/A",
                "components": {},
                "description": "보유 포지션 없음",
            }
            self._cache.set(cache_key, result)
            return result

        # --- Component 1: Position count (max 30) ---
        # 1 stock = 5, 5 stocks = 20, 10+ stocks = 30
        pos_score = min(30, n * 3)

        # --- Component 2: Sector diversity (max 30) ---
        exposure = self.get_sector_exposure(positions)
        sector_count = exposure["sector_count"]
        # 1 sector = 5, 3 sectors = 15, 5+ sectors = 30
        sector_score = min(30, sector_count * 6)

        # --- Component 3: Low correlation (max 25) ---
        corr_data = self.compute_correlation_matrix(positions, lookback=lookback)
        avg_corr = corr_data["avg_correlation"]
        # avg_corr 0.0 = 25 pts, 0.5 = 12.5 pts, 1.0 = 0 pts
        corr_score = max(0, round(25 * (1.0 - abs(avg_corr)), 1))

        # --- Component 4: Weight evenness (max 15) ---
        total_value = exposure["total_value"]
        if total_value > 0 and n > 0:
            weights = []
            for sym, pos in positions.items():
                v = pos.get("qty", 0) * pos.get("avg_price", 0)
                weights.append(v / total_value)
            # Measure how close to equal-weight (1/n)
            ideal = 1.0 / n
            deviation = sum(abs(w - ideal) for w in weights) / n
            # deviation 0 = perfectly even (15 pts), deviation 1/n = uneven (0 pts)
            evenness = max(0, 1.0 - deviation * n)
            weight_score = round(15 * evenness, 1)
        else:
            weight_score = 0

        total_score = round(pos_score + sector_score + corr_score + weight_score, 1)
        total_score = min(100, max(0, total_score))

        # Grade
        if total_score >= 80:
            grade = "우수"
        elif total_score >= 60:
            grade = "양호"
        elif total_score >= 40:
            grade = "보통"
        elif total_score >= 20:
            grade = "미흡"
        else:
            grade = "위험"

        result = {
            "score": total_score,
            "grade": grade,
            "components": {
                "position_count": {"score": pos_score, "max": 30, "detail": f"{n}개 종목"},
                "sector_diversity": {"score": sector_score, "max": 30, "detail": f"{sector_count}개 섹터"},
                "correlation": {"score": round(corr_score, 1), "max": 25, "detail": f"평균 상관계수 {avg_corr:.2f}"},
                "weight_evenness": {"score": round(weight_score, 1), "max": 15, "detail": "비중 균등도"},
            },
            "description": f"분산투자 등급: {grade} ({total_score:.0f}/100)",
        }
        self._cache.set(cache_key, result)
        return result

    def get_concentration_risk(
        self,
        positions: Dict[str, dict],
    ) -> Dict[str, Any]:
        """
        Compute the Herfindahl-Hirschman Index (HHI) for position concentration.

        HHI ranges from 1/N (perfectly diversified) to 1.0 (single position).
        Normalized HHI: 0 = perfect diversification, 1 = single position.

        Returns:
            {
              "hhi": float,
              "hhi_normalized": float,
              "risk_level": str,
              "top_positions": [{symbol, name, weight_pct}],
            }
        """
        cache_key = f"conc_risk_{_positions_hash(positions)}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        n = len(positions)
        if n == 0:
            result = {
                "hhi": 0,
                "hhi_normalized": 0,
                "risk_level": "N/A",
                "top_positions": [],
                "description": "보유 포지션 없음",
            }
            self._cache.set(cache_key, result)
            return result

        total_value = sum(
            pos.get("qty", 0) * pos.get("avg_price", 0)
            for pos in positions.values()
        )

        weights = []
        pos_list = []
        for sym, pos in positions.items():
            v = pos.get("qty", 0) * pos.get("avg_price", 0)
            w = v / total_value if total_value > 0 else 0
            weights.append(w)
            pos_list.append({
                "symbol": sym,
                "name": pos.get("name", sym),
                "weight_pct": round(w * 100, 1),
            })

        # HHI = sum of squared market shares
        hhi = sum(w * w for w in weights)
        hhi = round(hhi, 4)

        # Normalized HHI: (HHI - 1/N) / (1 - 1/N)
        if n > 1:
            hhi_norm = (hhi - 1.0 / n) / (1.0 - 1.0 / n)
            hhi_norm = round(max(0, min(1, hhi_norm)), 4)
        else:
            hhi_norm = 1.0

        # Risk level
        if hhi_norm < 0.15:
            risk_level = "낮음"
        elif hhi_norm < 0.25:
            risk_level = "보통"
        elif hhi_norm < 0.50:
            risk_level = "높음"
        else:
            risk_level = "매우 높음"
            self._alerts.append({
                "level": "danger",
                "type": "concentration_risk",
                "message": f"집중도 위험: HHI {hhi_norm:.2f} (매우 높음)",
                "timestamp": datetime.now().isoformat(),
            })

        # Sort by weight descending
        pos_list.sort(key=lambda x: x["weight_pct"], reverse=True)

        result = {
            "hhi": hhi,
            "hhi_normalized": hhi_norm,
            "risk_level": risk_level,
            "top_positions": pos_list[:5],
            "description": f"집중도: {risk_level} (HHI {hhi:.4f})",
        }
        self._cache.set(cache_key, result)
        return result

    def get_all_alerts(self) -> List[Dict[str, str]]:
        """Return accumulated alerts and clear the list."""
        alerts = list(self._alerts)
        self._alerts.clear()
        return alerts

    def get_full_risk_report(
        self,
        positions: Dict[str, dict],
        lookback: int = 20,
        sector_threshold: float = 35.0,
        correlation_threshold: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Generate a full portfolio risk report combining all metrics.
        Triggers all analyses so alerts accumulate.
        """
        self._alerts.clear()

        div_score = self.get_diversification_score(positions, lookback)
        conc_risk = self.get_concentration_risk(positions)
        sector_exp = self.get_sector_exposure(positions)
        rebalance = self.sector_rebalance_signal(positions, sector_threshold)
        corr_spike = self.detect_correlation_spike(positions, correlation_threshold, lookback)
        corr_matrix = self.compute_correlation_matrix(positions, lookback)

        alerts = self.get_all_alerts()

        report = {
            "diversification": div_score,
            "concentration": conc_risk,
            "sector_exposure": sector_exp,
            "sector_rebalance": rebalance,
            "correlation_spike": corr_spike,
            "avg_correlation": corr_matrix["avg_correlation"],
            "alerts": alerts,
            "timestamp": datetime.now().isoformat(),
        }

        # Save daily snapshot
        self._save_daily_snapshot(report)

        return report

    # ------------------------------------------------------------------
    # History / snapshot persistence
    # ------------------------------------------------------------------

    def _save_daily_snapshot(self, report: dict) -> None:
        """Save a daily snapshot to JSON for trend tracking."""
        today = datetime.now().strftime("%Y-%m-%d")
        snapshot = {
            "date": today,
            "timestamp": report.get("timestamp", datetime.now().isoformat()),
            "avg_correlation": report.get("avg_correlation", 0),
            "diversification_score": report.get("diversification", {}).get("score", 0),
            "hhi": report.get("concentration", {}).get("hhi", 0),
            "hhi_normalized": report.get("concentration", {}).get("hhi_normalized", 0),
            "sector_count": report.get("sector_exposure", {}).get("sector_count", 0),
            "alert_count": len(report.get("alerts", [])),
            "correlation_spike": report.get("correlation_spike", {}).get("spike_detected", False),
        }

        # Append to history (one entry per day, replace if same day)
        self._history = [h for h in self._history if h.get("date") != today]
        self._history.append(snapshot)
        # Keep at most 365 days
        if len(self._history) > 365:
            self._history = self._history[-365:]
        self._persist_history()

        # Also save standalone snapshot file
        try:
            path = os.path.join(SNAPSHOT_DIR, f"snapshot_{today}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save snapshot: {e}")

    def get_correlation_history(self, days: int = 30) -> List[dict]:
        """Return correlation history for the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return [h for h in self._history if h.get("date", "") >= cutoff]

    def _load_history(self) -> None:
        if os.path.exists(SNAPSHOT_HISTORY_PATH):
            try:
                with open(SNAPSHOT_HISTORY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._history = data
                else:
                    self._history = []
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load correlation history: {e}")
                self._history = []
        else:
            self._history = []

    def _persist_history(self) -> None:
        try:
            with open(SNAPSHOT_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to persist correlation history: {e}")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _pearson(x: List[float], y: List[float]) -> float:
    """Compute Pearson correlation coefficient between two equal-length lists."""
    n = len(x)
    if n < 2:
        return 0.0

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
    if denom == 0:
        return 0.0
    return cov / denom


def _positions_hash(positions: Dict[str, dict]) -> str:
    """Create a lightweight hash of position keys + quantities for cache keying."""
    items = sorted(
        (sym, pos.get("qty", 0)) for sym, pos in positions.items()
    )
    return str(hash(tuple(items)))
