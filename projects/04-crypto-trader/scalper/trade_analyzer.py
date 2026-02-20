"""
Trade Performance Analytics Engine.

Provides deep analysis of trade history:
- Per-strategy analytics (win rate, profit factor, max consecutive, hold duration)
- Time-based analysis (hourly, daily, monthly breakdowns)
- Risk metrics (max drawdown, Sharpe/Sortino ratio, recovery time)
- Strategy attribution (contribution, correlation, ensemble accuracy)

Loads trades from scalp_trades.json and computes all metrics on demand
or incrementally as new trades arrive.
"""
import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("scalper.trade_analyzer")

LOG_FILE = Path(__file__).parent / "scalp_trades.json"

# Annualisation factor: ~365 days, assuming multiple trades per day
ANNUALIZE_FACTOR = math.sqrt(365)


def _load_trades() -> list[dict]:
    """Load all trades from the JSON log file."""
    try:
        if LOG_FILE.exists():
            data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Failed to load trades: {e}")
    return []


def _parse_dt(dt_str: str) -> Optional[datetime]:
    """Parse datetime string from trade record."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(dt_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


# ────────────────────────────────────────────────────────────────
# Per-Strategy Analytics
# ────────────────────────────────────────────────────────────────

def compute_per_strategy_analytics(trades: list[dict]) -> dict[str, dict]:
    """Compute detailed analytics per contributing strategy.

    If trades lack contributing_strategies, we group by exit_type
    or treat all as 'unknown'.

    Returns: { strategy_name: { win_rate, avg_profit, avg_loss, ... } }
    """
    # Group trades by strategy
    strategy_trades: dict[str, list[dict]] = defaultdict(list)

    for t in trades:
        strategies = t.get("contributing_strategies", [])
        if strategies:
            for s in strategies:
                strategy_trades[s].append(t)
        else:
            strategy_trades["_all"].append(t)

    # Always compute global "_all"
    strategy_trades["_all"] = list(trades)

    result = {}
    for name, st_trades in strategy_trades.items():
        if not st_trades:
            continue
        result[name] = _analyze_trade_list(st_trades)

    return result


def _analyze_trade_list(trades: list[dict]) -> dict:
    """Compute analytics for a list of trades."""
    n = len(trades)
    if n == 0:
        return _empty_strategy_stats()

    pnl_list = [t.get("pnl_krw", 0) for t in trades]
    pct_list = [t.get("pnl_pct", 0) for t in trades]
    durations = [t.get("duration_sec", 0) for t in trades]

    wins = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p <= 0]
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / n * 100) if n > 0 else 0

    avg_profit = (sum(wins) / len(wins)) if wins else 0
    avg_loss = (sum(losses) / len(losses)) if losses else 0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
        999.99 if gross_profit > 0 else 0
    )

    # Max consecutive wins/losses
    max_consec_wins, max_consec_losses = _max_consecutive(pnl_list)

    # Best/worst trade
    best_trade = max(pnl_list) if pnl_list else 0
    worst_trade = min(pnl_list) if pnl_list else 0
    best_pct = max(pct_list) if pct_list else 0
    worst_pct = min(pct_list) if pct_list else 0

    # Average hold duration
    avg_duration = (sum(durations) / len(durations)) if durations else 0

    # Total PnL
    total_pnl = sum(pnl_list)

    return {
        "total_trades": n,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": round(win_rate, 2),
        "avg_profit_krw": round(avg_profit, 0),
        "avg_loss_krw": round(avg_loss, 0),
        "profit_factor": round(profit_factor, 2),
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "avg_duration_sec": round(avg_duration, 0),
        "best_trade_krw": round(best_trade, 0),
        "worst_trade_krw": round(worst_trade, 0),
        "best_trade_pct": round(best_pct, 2),
        "worst_trade_pct": round(worst_pct, 2),
        "total_pnl_krw": round(total_pnl, 0),
    }


def _max_consecutive(pnl_list: list[float]) -> tuple[int, int]:
    """Compute max consecutive wins and losses."""
    max_w, max_l = 0, 0
    cur_w, cur_l = 0, 0
    for p in pnl_list:
        if p > 0:
            cur_w += 1
            cur_l = 0
        else:
            cur_l += 1
            cur_w = 0
        max_w = max(max_w, cur_w)
        max_l = max(max_l, cur_l)
    return max_w, max_l


def _empty_strategy_stats() -> dict:
    return {
        "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0,
        "avg_profit_krw": 0, "avg_loss_krw": 0, "profit_factor": 0,
        "max_consecutive_wins": 0, "max_consecutive_losses": 0,
        "avg_duration_sec": 0, "best_trade_krw": 0, "worst_trade_krw": 0,
        "best_trade_pct": 0, "worst_trade_pct": 0, "total_pnl_krw": 0,
    }


# ────────────────────────────────────────────────────────────────
# Time-Based Analysis
# ────────────────────────────────────────────────────────────────

def compute_time_analysis(trades: list[dict]) -> dict:
    """Compute win rate by hour of day, performance by day of week,
    and monthly returns breakdown.

    Returns:
        {
            "hourly_win_rate": { 0: {wins, losses, win_rate, total_pnl}, ... },
            "daily_performance": { "Mon": {...}, "Tue": {...}, ... },
            "monthly_returns": { "2025-01": {...}, ... },
        }
    """
    hourly: dict[int, dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0, "count": 0})
    daily: dict[str, dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0, "count": 0})
    monthly: dict[str, dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0, "count": 0, "trades": []})

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_names_kr = ["월", "화", "수", "목", "금", "토", "일"]

    for t in trades:
        dt = _parse_dt(t.get("exit_time", ""))
        if dt is None:
            continue
        pnl = t.get("pnl_krw", 0)
        won = pnl > 0

        # Hourly
        hour = dt.hour
        hourly[hour]["count"] += 1
        hourly[hour]["pnl"] += pnl
        if won:
            hourly[hour]["wins"] += 1
        else:
            hourly[hour]["losses"] += 1

        # Daily (day of week)
        dow = dt.weekday()  # 0=Monday
        day_key = day_names[dow]
        daily[day_key]["count"] += 1
        daily[day_key]["pnl"] += pnl
        if won:
            daily[day_key]["wins"] += 1
        else:
            daily[day_key]["losses"] += 1

        # Monthly
        month_key = dt.strftime("%Y-%m")
        monthly[month_key]["count"] += 1
        monthly[month_key]["pnl"] += pnl
        monthly[month_key]["trades"].append(pnl)
        if won:
            monthly[month_key]["wins"] += 1
        else:
            monthly[month_key]["losses"] += 1

    # Compute win rates
    hourly_result = {}
    for h in range(24):
        d = hourly[h]
        c = d["count"]
        hourly_result[h] = {
            "wins": d["wins"],
            "losses": d["losses"],
            "count": c,
            "win_rate": round(d["wins"] / c * 100, 1) if c > 0 else 0,
            "total_pnl": round(d["pnl"], 0),
            "avg_pnl": round(d["pnl"] / c, 0) if c > 0 else 0,
        }

    daily_result = {}
    for i, day in enumerate(day_names):
        d = daily[day]
        c = d["count"]
        daily_result[day] = {
            "name_kr": day_names_kr[i],
            "wins": d["wins"],
            "losses": d["losses"],
            "count": c,
            "win_rate": round(d["wins"] / c * 100, 1) if c > 0 else 0,
            "total_pnl": round(d["pnl"], 0),
            "avg_pnl": round(d["pnl"] / c, 0) if c > 0 else 0,
        }

    monthly_result = {}
    for month_key in sorted(monthly.keys()):
        d = monthly[month_key]
        c = d["count"]
        pnl_trades = d["trades"]
        monthly_result[month_key] = {
            "wins": d["wins"],
            "losses": d["losses"],
            "count": c,
            "win_rate": round(d["wins"] / c * 100, 1) if c > 0 else 0,
            "total_pnl": round(d["pnl"], 0),
            "avg_pnl": round(d["pnl"] / c, 0) if c > 0 else 0,
            "best_trade": round(max(pnl_trades), 0) if pnl_trades else 0,
            "worst_trade": round(min(pnl_trades), 0) if pnl_trades else 0,
        }

    return {
        "hourly_win_rate": hourly_result,
        "daily_performance": daily_result,
        "monthly_returns": monthly_result,
    }


# ────────────────────────────────────────────────────────────────
# Risk Metrics
# ────────────────────────────────────────────────────────────────

def compute_risk_metrics(trades: list[dict], initial_balance: float = 1_000_000) -> dict:
    """Compute risk-adjusted metrics.

    Returns:
        {
            "max_drawdown_krw", "max_drawdown_pct", "recovery_time_trades",
            "recovery_time_hours", "sharpe_ratio", "sortino_ratio",
            "pnl_distribution": { bins, counts },
            "win_loss_ratio", "expectancy",
            "drawdown_series": [{trade_num, drawdown, cumulative_pnl}],
        }
    """
    if not trades:
        return _empty_risk_metrics()

    pnl_list = [t.get("pnl_krw", 0) for t in trades]
    pct_list = [t.get("pnl_pct", 0) for t in trades]

    # --- Max Drawdown & Recovery ---
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    max_dd_peak_idx = 0
    max_dd_trough_idx = 0
    current_peak_idx = 0
    recovery_idx = -1

    drawdown_series = []
    equity_series = []

    for i, pnl in enumerate(pnl_list):
        cumulative += pnl
        equity_series.append(cumulative)
        if cumulative > peak:
            peak = cumulative
            current_peak_idx = i
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
            max_dd_peak_idx = current_peak_idx
            max_dd_trough_idx = i
        drawdown_series.append({
            "trade_num": i + 1,
            "drawdown": round(peak - cumulative, 0),
            "drawdown_pct": round((peak - cumulative) / max(initial_balance + peak, 1) * 100, 2),
            "cumulative_pnl": round(cumulative, 0),
        })

    # Recovery time: how many trades from trough to new peak
    recovery_trades = 0
    recovery_hours = 0
    if max_dd > 0 and max_dd_trough_idx < len(equity_series) - 1:
        trough_val = equity_series[max_dd_trough_idx]
        peak_before = equity_series[max_dd_peak_idx]
        for j in range(max_dd_trough_idx + 1, len(equity_series)):
            if equity_series[j] >= peak_before:
                recovery_trades = j - max_dd_trough_idx
                # Calculate approximate hours
                dt_trough = _parse_dt(trades[max_dd_trough_idx].get("exit_time", ""))
                dt_recovery = _parse_dt(trades[j].get("exit_time", ""))
                if dt_trough and dt_recovery:
                    recovery_hours = round((dt_recovery - dt_trough).total_seconds() / 3600, 1)
                break

    max_dd_pct = (max_dd / max(initial_balance, 1)) * 100

    # --- Sharpe Ratio ---
    # Using per-trade returns (pct)
    if len(pct_list) >= 2:
        avg_ret = sum(pct_list) / len(pct_list)
        variance = sum((r - avg_ret) ** 2 for r in pct_list) / (len(pct_list) - 1)
        std_ret = math.sqrt(variance) if variance > 0 else 1e-10
        # Annualised: assume ~2 trades/day on average
        trades_per_year = max(len(pct_list), 1)
        # Simple Sharpe (risk-free = 0 for crypto)
        sharpe = (avg_ret / std_ret) * math.sqrt(trades_per_year) if std_ret > 1e-10 else 0
    else:
        sharpe = 0
        avg_ret = 0
        std_ret = 0

    # --- Sortino Ratio ---
    # Only downside deviation
    if len(pct_list) >= 2:
        downside = [r for r in pct_list if r < 0]
        if downside:
            downside_var = sum(r ** 2 for r in downside) / len(pct_list)
            downside_dev = math.sqrt(downside_var)
            sortino = (avg_ret / downside_dev) * math.sqrt(len(pct_list)) if downside_dev > 1e-10 else 0
        else:
            sortino = 999.99  # No losses
    else:
        sortino = 0

    # --- Win/Loss Ratio Distribution ---
    wins = [p for p in pnl_list if p > 0]
    losses = [abs(p) for p in pnl_list if p < 0]
    avg_win = (sum(wins) / len(wins)) if wins else 0
    avg_loss_val = (sum(losses) / len(losses)) if losses else 1
    win_loss_ratio = (avg_win / avg_loss_val) if avg_loss_val > 0 else (999.99 if avg_win > 0 else 0)

    # Expectancy
    win_rate = len(wins) / len(pnl_list) if pnl_list else 0
    loss_rate = 1 - win_rate
    expectancy = (win_rate * avg_win) - (loss_rate * avg_loss_val)

    # --- PnL Distribution (histogram bins) ---
    pnl_distribution = _compute_distribution(pnl_list, num_bins=20)

    return {
        "max_drawdown_krw": round(max_dd, 0),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "recovery_time_trades": recovery_trades,
        "recovery_time_hours": recovery_hours,
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3) if sortino != 999.99 else 999.99,
        "win_loss_ratio": round(win_loss_ratio, 2) if win_loss_ratio != 999.99 else 999.99,
        "expectancy_krw": round(expectancy, 0),
        "pnl_distribution": pnl_distribution,
        "drawdown_series": drawdown_series,
    }


def _compute_distribution(values: list[float], num_bins: int = 20) -> dict:
    """Compute histogram distribution of values."""
    if not values:
        return {"bins": [], "counts": [], "bin_labels": []}

    min_val = min(values)
    max_val = max(values)

    if min_val == max_val:
        return {"bins": [min_val], "counts": [len(values)], "bin_labels": [str(round(min_val, 0))]}

    bin_width = (max_val - min_val) / num_bins
    bins = []
    counts = []
    bin_labels = []

    for i in range(num_bins):
        lo = min_val + i * bin_width
        hi = lo + bin_width
        count = sum(1 for v in values if lo <= v < hi)
        if i == num_bins - 1:
            count = sum(1 for v in values if lo <= v <= hi)
        bins.append(round(lo, 0))
        counts.append(count)
        label = f"{round(lo/1000, 1)}K" if abs(lo) >= 1000 else f"{round(lo, 0)}"
        bin_labels.append(label)

    return {"bins": bins, "counts": counts, "bin_labels": bin_labels}


def _empty_risk_metrics() -> dict:
    return {
        "max_drawdown_krw": 0, "max_drawdown_pct": 0,
        "recovery_time_trades": 0, "recovery_time_hours": 0,
        "sharpe_ratio": 0, "sortino_ratio": 0,
        "win_loss_ratio": 0, "expectancy_krw": 0,
        "pnl_distribution": {"bins": [], "counts": [], "bin_labels": []},
        "drawdown_series": [],
    }


# ────────────────────────────────────────────────────────────────
# Strategy Attribution
# ────────────────────────────────────────────────────────────────

def compute_strategy_attribution(trades: list[dict]) -> dict:
    """Compute which strategy contributed most to profits and strategy correlations.

    Returns:
        {
            "contribution": { strategy: { pnl, pnl_pct_of_total, trade_count } },
            "strategy_correlation": { (s1,s2): agreement_pct },
            "ensemble_accuracy": { total_votes, correct_votes, accuracy_pct },
            "cumulative_by_strategy": { strategy: [ {trade_num, cum_pnl} ] },
        }
    """
    # Contribution
    contribution: dict[str, dict] = defaultdict(lambda: {"pnl": 0, "count": 0, "wins": 0})

    for t in trades:
        strategies = t.get("contributing_strategies", [])
        pnl = t.get("pnl_krw", 0)
        won = pnl > 0
        if strategies:
            # Attribute PnL proportionally to each contributing strategy
            share = pnl / len(strategies) if strategies else pnl
            for s in strategies:
                contribution[s]["pnl"] += share
                contribution[s]["count"] += 1
                if won:
                    contribution[s]["wins"] += 1
        else:
            contribution["_unknown"]["pnl"] += pnl
            contribution["_unknown"]["count"] += 1
            if won:
                contribution["_unknown"]["wins"] += 1

    total_pnl = sum(t.get("pnl_krw", 0) for t in trades)
    contribution_result = {}
    for s, data in sorted(contribution.items(), key=lambda x: x[1]["pnl"], reverse=True):
        contribution_result[s] = {
            "total_pnl_krw": round(data["pnl"], 0),
            "pnl_pct_of_total": round(data["pnl"] / total_pnl * 100, 1) if total_pnl != 0 else 0,
            "trade_count": data["count"],
            "wins": data["wins"],
            "win_rate": round(data["wins"] / data["count"] * 100, 1) if data["count"] > 0 else 0,
        }

    # Strategy correlation (co-occurrence agreement)
    strategy_correlation = _compute_strategy_correlation(trades)

    # Ensemble vote accuracy (how often the majority vote was correct)
    ensemble_accuracy = _compute_ensemble_accuracy(trades)

    # Cumulative PnL by strategy (for line chart)
    cumulative_by_strategy = _compute_cumulative_by_strategy(trades)

    return {
        "contribution": contribution_result,
        "strategy_correlation": strategy_correlation,
        "ensemble_accuracy": ensemble_accuracy,
        "cumulative_by_strategy": cumulative_by_strategy,
    }


def _compute_strategy_correlation(trades: list[dict]) -> dict:
    """Compute how often pairs of strategies appear together and agree on direction."""
    pair_counts: dict[str, dict] = defaultdict(lambda: {"co_occur": 0, "both_win": 0, "both_lose": 0})

    for t in trades:
        strategies = t.get("contributing_strategies", [])
        won = t.get("pnl_krw", 0) > 0
        if len(strategies) < 2:
            continue
        for i in range(len(strategies)):
            for j in range(i + 1, len(strategies)):
                key = tuple(sorted([strategies[i], strategies[j]]))
                key_str = f"{key[0]}+{key[1]}"
                pair_counts[key_str]["co_occur"] += 1
                if won:
                    pair_counts[key_str]["both_win"] += 1
                else:
                    pair_counts[key_str]["both_lose"] += 1

    result = {}
    for pair, data in pair_counts.items():
        co = data["co_occur"]
        result[pair] = {
            "co_occurrences": co,
            "both_win": data["both_win"],
            "both_lose": data["both_lose"],
            "agreement_win_rate": round(data["both_win"] / co * 100, 1) if co > 0 else 0,
        }
    return result


def _compute_ensemble_accuracy(trades: list[dict]) -> dict:
    """Compute ensemble voting accuracy."""
    total = len(trades)
    if total == 0:
        return {"total_trades": 0, "winning_trades": 0, "accuracy_pct": 0}

    winning = sum(1 for t in trades if t.get("pnl_krw", 0) > 0)
    return {
        "total_trades": total,
        "winning_trades": winning,
        "accuracy_pct": round(winning / total * 100, 1),
    }


def _compute_cumulative_by_strategy(trades: list[dict]) -> dict[str, list]:
    """Build cumulative PnL series per strategy."""
    strategy_cum: dict[str, float] = defaultdict(float)
    strategy_series: dict[str, list] = defaultdict(list)

    for i, t in enumerate(trades):
        strategies = t.get("contributing_strategies", [])
        pnl = t.get("pnl_krw", 0)
        if strategies:
            share = pnl / len(strategies)
            for s in strategies:
                strategy_cum[s] += share
                strategy_series[s].append({
                    "trade_num": i + 1,
                    "cumulative_pnl": round(strategy_cum[s], 0),
                    "time": t.get("exit_time", ""),
                })
        else:
            strategy_cum["_unknown"] += pnl
            strategy_series["_unknown"].append({
                "trade_num": i + 1,
                "cumulative_pnl": round(strategy_cum["_unknown"], 0),
                "time": t.get("exit_time", ""),
            })

    return dict(strategy_series)


# ────────────────────────────────────────────────────────────────
# Full Analytics (combined)
# ────────────────────────────────────────────────────────────────

def get_full_analytics(initial_balance: float = 1_000_000) -> dict:
    """Compute full analytics from the trade log.

    Returns the complete analytics payload suitable for the dashboard API.
    """
    trades = _load_trades()
    if not trades:
        return {
            "total_trades": 0,
            "per_strategy": {},
            "time_analysis": {
                "hourly_win_rate": {},
                "daily_performance": {},
                "monthly_returns": {},
            },
            "risk_metrics": _empty_risk_metrics(),
            "strategy_attribution": {
                "contribution": {},
                "strategy_correlation": {},
                "ensemble_accuracy": {"total_trades": 0, "winning_trades": 0, "accuracy_pct": 0},
                "cumulative_by_strategy": {},
            },
        }

    return {
        "total_trades": len(trades),
        "per_strategy": compute_per_strategy_analytics(trades),
        "time_analysis": compute_time_analysis(trades),
        "risk_metrics": compute_risk_metrics(trades, initial_balance),
        "strategy_attribution": compute_strategy_attribution(trades),
    }


def get_strategy_analytics(strategy_name: str) -> dict:
    """Compute analytics for a specific strategy.

    Returns detailed stats for the given strategy name.
    """
    trades = _load_trades()
    if not trades:
        return _empty_strategy_stats()

    # Filter trades where this strategy contributed
    if strategy_name == "_all":
        filtered = trades
    else:
        filtered = [t for t in trades
                     if strategy_name in t.get("contributing_strategies", [])]

    if not filtered:
        return _empty_strategy_stats()

    base_stats = _analyze_trade_list(filtered)

    # Add time analysis for this strategy's trades
    time_analysis = compute_time_analysis(filtered)

    # Add cumulative PnL series
    cum = 0.0
    cum_series = []
    for i, t in enumerate(filtered):
        cum += t.get("pnl_krw", 0)
        cum_series.append({
            "trade_num": i + 1,
            "cumulative_pnl": round(cum, 0),
            "time": t.get("exit_time", ""),
        })

    return {
        **base_stats,
        "time_analysis": time_analysis,
        "cumulative_series": cum_series,
    }


# ────────────────────────────────────────────────────────────────
# Incremental Update Support
# ────────────────────────────────────────────────────────────────

class TradeAnalyticsCache:
    """Maintains an in-memory cache of analytics, updated incrementally
    when new trades arrive.

    Usage:
        cache = TradeAnalyticsCache()
        cache.maybe_refresh()   # Call periodically
        data = cache.get_data() # Get cached analytics
    """

    def __init__(self, initial_balance: float = 1_000_000):
        self._initial_balance = initial_balance
        self._trade_count = 0
        self._cached_data: Optional[dict] = None
        self._last_refresh = 0.0

    def maybe_refresh(self, force: bool = False) -> bool:
        """Refresh analytics if new trades have arrived.

        Returns True if data was refreshed.
        """
        import time
        now = time.time()

        # Rate limit: at most once per 5 seconds
        if not force and now - self._last_refresh < 5.0:
            return False

        trades = _load_trades()
        if len(trades) == self._trade_count and self._cached_data is not None:
            return False

        self._trade_count = len(trades)
        self._last_refresh = now

        if not trades:
            self._cached_data = get_full_analytics(self._initial_balance)
            return True

        self._cached_data = {
            "total_trades": len(trades),
            "per_strategy": compute_per_strategy_analytics(trades),
            "time_analysis": compute_time_analysis(trades),
            "risk_metrics": compute_risk_metrics(trades, self._initial_balance),
            "strategy_attribution": compute_strategy_attribution(trades),
        }
        return True

    def get_data(self) -> dict:
        """Get cached analytics data."""
        if self._cached_data is None:
            self.maybe_refresh(force=True)
        return self._cached_data or get_full_analytics(self._initial_balance)

    def on_new_trade(self, trade_record: dict):
        """Called when a new trade is recorded. Triggers refresh."""
        self.maybe_refresh(force=True)
