"""
StockBot v2.1 - Interactive Backtesting Portal

Full backtesting engine + web UI with Chart.js visualizations.
Provides async job execution, result storage, and comparison mode.
"""
import sys
import os
import uuid
import json
import math
import threading
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-bot"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "strategy"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "news"))

import numpy as np
import pandas as pd

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from config import WATCHLIST

logger = logging.getLogger(__name__)

backtest_router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
_jobs: Dict[str, Dict[str, Any]] = {}        # job_id -> {status, progress, result, ...}
_saved_results: Dict[str, Dict[str, Any]] = {}  # save_id -> serialised BacktestResult
_history: List[Dict[str, Any]] = []              # recent backtest summaries


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class BacktestResult:
    """Complete result of a single backtest run."""
    total_return_pct: float = 0.0
    annual_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    avg_hold_days: float = 0.0
    equity_curve: List[Tuple[str, float]] = field(default_factory=list)
    trades: List[Tuple[str, str, str, float, str]] = field(default_factory=list)
    daily_pnl: List[Tuple[str, float]] = field(default_factory=list)
    monthly_returns: Dict[str, Dict[str, float]] = field(default_factory=dict)
    symbol: str = ""
    name: str = ""
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 0.0
    final_capital: float = 0.0


class BacktestRequest(BaseModel):
    symbol: str
    start_date: str            # YYYY-MM-DD
    end_date: str              # YYYY-MM-DD
    initial_capital: float = 10_000_000
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 15.0
    trailing_stop_pct: float = 5.0
    strategy_weights: Optional[Dict[str, float]] = None


# ---------------------------------------------------------------------------
# Data fetching helpers
# ---------------------------------------------------------------------------
def _fetch_ohlcv(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Fetch historical OHLCV using pykrx, falling back to simulated data."""
    try:
        from pykrx import stock as pykrx_stock
        df = pykrx_stock.get_market_ohlcv_by_date(start_date, end_date, symbol)
        if df is not None and not df.empty:
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]
            rename_map = {}
            for c in df.columns:
                if "시가" in c or c == "시가":
                    rename_map[c] = "open"
                elif "고가" in c or c == "고가":
                    rename_map[c] = "high"
                elif "저가" in c or c == "저가":
                    rename_map[c] = "low"
                elif "종가" in c or c == "종가":
                    rename_map[c] = "close"
                elif "거래량" in c or c == "거래량":
                    rename_map[c] = "volume"
            if rename_map:
                df = df.rename(columns=rename_map)
            needed = {"open", "high", "low", "close", "volume"}
            if needed.issubset(set(df.columns)):
                df = df[list(needed)]
                df = df[df["volume"] > 0]
                if len(df) >= 30:
                    logger.info(f"pykrx: fetched {len(df)} rows for {symbol}")
                    return df
    except Exception as e:
        logger.debug(f"pykrx unavailable or failed for {symbol}: {e}")

    # Fallback: generate simulated data
    return _generate_sim_data(symbol, start_date, end_date)


def _generate_sim_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Generate deterministic simulated OHLCV data for a symbol."""
    sd = pd.Timestamp(start_date)
    ed = pd.Timestamp(end_date)
    dates = pd.bdate_range(sd, ed)
    n = len(dates)
    if n < 5:
        dates = pd.bdate_range(sd, periods=60)
        n = len(dates)

    seed = hash(symbol) % (2**31)
    rng = np.random.RandomState(seed)

    base_price = 50000 + (hash(symbol) % 100000)
    daily_ret = rng.randn(n) * 0.018
    # Add slight mean-reversion and trend
    trend = np.linspace(0, rng.uniform(-0.10, 0.15), n)
    cumul = np.cumsum(daily_ret) + trend
    prices = base_price * np.exp(cumul)

    spread = prices * 0.008
    return pd.DataFrame({
        "open": prices + rng.randn(n) * spread * 0.3,
        "high": prices + np.abs(rng.randn(n)) * spread,
        "low": prices - np.abs(rng.randn(n)) * spread,
        "close": prices,
        "volume": rng.randint(100_000, 15_000_000, n),
    }, index=dates)


# ---------------------------------------------------------------------------
# Backtest Engine
# ---------------------------------------------------------------------------
class BacktestEngine:
    """Core backtesting engine that replays historical data through strategies."""

    def __init__(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10_000_000,
        stop_loss_pct: float = 5.0,
        take_profit_pct: float = 15.0,
        trailing_stop_pct: float = 5.0,
        strategy_weights: Optional[Dict[str, float]] = None,
        progress_callback=None,
    ):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.strategy_weights = strategy_weights
        self._progress_cb = progress_callback

        # Look up name from watchlist
        stock = next((s for s in WATCHLIST if s["code"] == symbol), None)
        self.name = stock["name"] if stock else symbol

    # ---- helpers ----

    def _get_selector(self):
        """Lazily import and configure the ensemble selector."""
        from stock_selector import StockSelectorEnsemble
        selector = StockSelectorEnsemble()
        if self.strategy_weights:
            for strat in selector.strategies:
                if strat.name in self.strategy_weights:
                    strat.weight = self.strategy_weights[strat.name]
        return selector

    def _report_progress(self, pct: int, msg: str = ""):
        if self._progress_cb:
            self._progress_cb(pct, msg)

    # ---- main run ----

    def run(self) -> BacktestResult:
        """Execute the backtest and return a complete BacktestResult."""
        self._report_progress(5, "Fetching data...")
        df = _fetch_ohlcv(self.symbol, self.start_date, self.end_date)
        if df is None or len(df) < 30:
            raise ValueError(f"Insufficient data for {self.symbol}: got {0 if df is None else len(df)} rows")

        selector = self._get_selector()
        self._report_progress(10, "Running simulation...")

        capital = self.initial_capital
        position = None  # {qty, buy_price, buy_date, highest_price}
        FEE_RATE = 0.00015    # buy commission
        TAX_RATE = 0.0018     # sell tax
        SELL_FEE = 0.00015    # sell commission

        trades_log = []       # (entry_date, exit_date, symbol, pnl_pct, exit_reason)
        equity_curve = []     # (date_str, equity_value)
        daily_pnl_map = {}    # date_str -> pnl

        warmup = min(120, max(60, len(df) // 4))
        total_bars = len(df) - warmup

        for i in range(warmup, len(df)):
            bar_date = df.index[i]
            date_str = bar_date.strftime("%Y-%m-%d") if hasattr(bar_date, "strftime") else str(bar_date)[:10]
            current_price = float(df.iloc[i]["close"])

            # Portfolio mark-to-market
            port_value = capital
            if position:
                port_value += position["qty"] * current_price
            equity_curve.append((date_str, round(port_value, 0)))

            # Track daily PnL
            if len(equity_curve) >= 2:
                day_pnl = equity_curve[-1][1] - equity_curve[-2][1]
            else:
                day_pnl = 0
            daily_pnl_map[date_str] = round(day_pnl, 0)

            # ---- Exit logic ----
            if position:
                pnl_pct = (current_price - position["buy_price"]) / position["buy_price"] * 100

                # Update highest price for trailing stop
                if current_price > position["highest_price"]:
                    position["highest_price"] = current_price

                exit_reason = None

                # Stop loss
                if pnl_pct <= -self.stop_loss_pct:
                    exit_reason = "STOP_LOSS"

                # Take profit
                elif pnl_pct >= self.take_profit_pct:
                    exit_reason = "TAKE_PROFIT"

                # Trailing stop: only if in profit
                elif pnl_pct > 0:
                    drop_from_high = (current_price - position["highest_price"]) / position["highest_price"] * 100
                    if drop_from_high <= -self.trailing_stop_pct:
                        exit_reason = "TRAILING_STOP"

                if exit_reason:
                    proceeds = position["qty"] * current_price
                    sell_costs = proceeds * (SELL_FEE + TAX_RATE)
                    capital += proceeds - sell_costs
                    entry_date_str = position["buy_date"]
                    trades_log.append((entry_date_str, date_str, self.symbol, round(pnl_pct, 2), exit_reason))
                    position = None
                    continue

            # ---- Entry / strategy signal logic ----
            window = df.iloc[:i + 1]
            try:
                result = selector.evaluate(window, self.symbol, self.name)
            except Exception:
                continue

            if result["action"] == "BUY" and position is None:
                trade_amount = capital * 0.95  # Use 95% of capital
                qty = int(trade_amount / current_price)
                if qty > 0:
                    cost = qty * current_price
                    buy_fee = cost * FEE_RATE
                    capital -= (cost + buy_fee)
                    position = {
                        "qty": qty,
                        "buy_price": current_price,
                        "buy_date": date_str,
                        "highest_price": current_price,
                    }

            elif result["action"] == "SELL" and position is not None:
                pnl_pct = (current_price - position["buy_price"]) / position["buy_price"] * 100
                proceeds = position["qty"] * current_price
                sell_costs = proceeds * (SELL_FEE + TAX_RATE)
                capital += proceeds - sell_costs
                trades_log.append((position["buy_date"], date_str, self.symbol, round(pnl_pct, 2), "SIGNAL_SELL"))
                position = None

            # Progress
            if total_bars > 0:
                pct = 10 + int((i - warmup) / total_bars * 85)
                if (i - warmup) % max(1, total_bars // 20) == 0:
                    self._report_progress(pct, f"Bar {i - warmup}/{total_bars}")

        # ---- Close any remaining position ----
        if position:
            final_price = float(df.iloc[-1]["close"])
            pnl_pct = (final_price - position["buy_price"]) / position["buy_price"] * 100
            proceeds = position["qty"] * final_price
            sell_costs = proceeds * (SELL_FEE + TAX_RATE)
            capital += proceeds - sell_costs
            last_date = df.index[-1]
            last_date_str = last_date.strftime("%Y-%m-%d") if hasattr(last_date, "strftime") else str(last_date)[:10]
            trades_log.append((position["buy_date"], last_date_str, self.symbol, round(pnl_pct, 2), "END_OF_TEST"))

        self._report_progress(95, "Computing metrics...")

        # ---- Compute metrics ----
        final_capital = capital
        total_return_pct = (final_capital - self.initial_capital) / self.initial_capital * 100

        # Annualised return
        if len(equity_curve) > 1:
            days = max((pd.Timestamp(equity_curve[-1][0]) - pd.Timestamp(equity_curve[0][0])).days, 1)
            years = days / 365.25
            if years > 0 and final_capital > 0 and self.initial_capital > 0:
                annual_return_pct = ((final_capital / self.initial_capital) ** (1 / years) - 1) * 100
            else:
                annual_return_pct = 0.0
        else:
            days = 1
            years = days / 365.25
            annual_return_pct = 0.0

        # Max drawdown
        max_dd = 0.0
        peak = 0.0
        for _, eq in equity_curve:
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = (peak - eq) / peak * 100
                if dd > max_dd:
                    max_dd = dd

        # Sharpe ratio (annualised, risk-free ~3.5% annually)
        daily_returns = []
        for j in range(1, len(equity_curve)):
            prev_eq = equity_curve[j - 1][1]
            curr_eq = equity_curve[j][1]
            if prev_eq > 0:
                daily_returns.append((curr_eq - prev_eq) / prev_eq)
        if daily_returns:
            dr_arr = np.array(daily_returns)
            rf_daily = (1.035 ** (1 / 252)) - 1
            excess = dr_arr - rf_daily
            sharpe = (np.mean(excess) / np.std(excess)) * np.sqrt(252) if np.std(excess) > 0 else 0.0
            # Sortino
            downside = excess[excess < 0]
            downside_std = np.std(downside) if len(downside) > 0 else 1e-9
            sortino = (np.mean(excess) / downside_std) * np.sqrt(252) if downside_std > 0 else 0.0
        else:
            sharpe = 0.0
            sortino = 0.0

        # Trade statistics
        sell_trades = [t for t in trades_log]
        winners = [t for t in sell_trades if t[3] > 0]
        losers = [t for t in sell_trades if t[3] <= 0]
        total_trades = len(sell_trades)
        win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0

        gross_profit = sum(t[3] for t in winners) if winners else 0
        gross_loss = abs(sum(t[3] for t in losers)) if losers else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        avg_win = (sum(t[3] for t in winners) / len(winners)) if winners else 0
        avg_loss = (sum(t[3] for t in losers) / len(losers)) if losers else 0

        # Avg hold days
        hold_days_list = []
        for t in sell_trades:
            try:
                d1 = pd.Timestamp(t[0])
                d2 = pd.Timestamp(t[1])
                hold_days_list.append((d2 - d1).days)
            except Exception:
                pass
        avg_hold = (sum(hold_days_list) / len(hold_days_list)) if hold_days_list else 0

        # Monthly returns
        monthly_map: Dict[str, Dict[str, float]] = {}
        if len(equity_curve) > 1:
            prev_month_eq = equity_curve[0][1]
            prev_month_key = equity_curve[0][0][:7]  # YYYY-MM
            for date_str, eq in equity_curve:
                month_key = date_str[:7]
                if month_key != prev_month_key:
                    year_str = prev_month_key[:4]
                    mon_str = prev_month_key[5:7]
                    if prev_month_eq > 0:
                        monthly_ret = (eq - prev_month_eq) / prev_month_eq * 100
                    else:
                        monthly_ret = 0
                    if year_str not in monthly_map:
                        monthly_map[year_str] = {}
                    monthly_map[year_str][mon_str] = round(monthly_ret, 2)
                    prev_month_eq = eq
                    prev_month_key = month_key
            # last partial month
            if equity_curve:
                last_key = equity_curve[-1][0][:7]
                year_str = last_key[:4]
                mon_str = last_key[5:7]
                if prev_month_eq > 0:
                    monthly_ret = (equity_curve[-1][1] - prev_month_eq) / prev_month_eq * 100
                else:
                    monthly_ret = 0
                if year_str not in monthly_map:
                    monthly_map[year_str] = {}
                monthly_map[year_str][mon_str] = round(monthly_ret, 2)

        daily_pnl_list = [(k, v) for k, v in daily_pnl_map.items()]

        self._report_progress(100, "Done")

        return BacktestResult(
            total_return_pct=round(total_return_pct, 2),
            annual_return_pct=round(annual_return_pct, 2),
            max_drawdown_pct=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            total_trades=total_trades,
            win_rate=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            avg_win_pct=round(avg_win, 2),
            avg_loss_pct=round(avg_loss, 2),
            avg_hold_days=round(avg_hold, 1),
            equity_curve=equity_curve,
            trades=trades_log,
            daily_pnl=daily_pnl_list,
            monthly_returns=monthly_map,
            symbol=self.symbol,
            name=self.name,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            final_capital=round(final_capital, 0),
        )


# ---------------------------------------------------------------------------
# Background job runner
# ---------------------------------------------------------------------------
def _run_backtest_job(job_id: str, req: BacktestRequest):
    """Run a backtest in a background thread."""
    def progress_cb(pct, msg):
        _jobs[job_id]["progress"] = pct
        _jobs[job_id]["progress_msg"] = msg

    try:
        _jobs[job_id]["status"] = "running"
        engine = BacktestEngine(
            symbol=req.symbol,
            start_date=req.start_date,
            end_date=req.end_date,
            initial_capital=req.initial_capital,
            stop_loss_pct=req.stop_loss_pct,
            take_profit_pct=req.take_profit_pct,
            trailing_stop_pct=req.trailing_stop_pct,
            strategy_weights=req.strategy_weights,
            progress_callback=progress_cb,
        )
        result = engine.run()
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = asdict(result)
        _jobs[job_id]["completed_at"] = datetime.now().isoformat()
        # Add to history
        _history.insert(0, {
            "job_id": job_id,
            "symbol": req.symbol,
            "name": result.name,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "total_return_pct": result.total_return_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "win_rate": result.win_rate,
            "total_trades": result.total_trades,
            "completed_at": _jobs[job_id]["completed_at"],
        })
        # Keep only last 50 history entries
        while len(_history) > 50:
            _history.pop()
    except Exception as e:
        logger.error(f"Backtest job {job_id} failed: {e}")
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@backtest_router.post("/api/backtest/run")
async def run_backtest(req: BacktestRequest):
    """Start an asynchronous backtest job."""
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "progress_msg": "",
        "result": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "request": req.dict(),
    }
    thread = threading.Thread(target=_run_backtest_job, args=(job_id, req), daemon=True)
    thread.start()
    return {"job_id": job_id, "status": "queued"}


@backtest_router.get("/api/backtest/status/{job_id}")
async def backtest_status(job_id: str):
    """Check the progress of a running backtest."""
    if job_id not in _jobs:
        return {"error": "Job not found"}
    job = _jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "progress_msg": job["progress_msg"],
        "error": job.get("error"),
    }


@backtest_router.get("/api/backtest/result/{job_id}")
async def backtest_result(job_id: str):
    """Get the full result of a completed backtest."""
    if job_id not in _jobs:
        return {"error": "Job not found"}
    job = _jobs[job_id]
    if job["status"] != "completed":
        return {"error": f"Job status: {job['status']}", "status": job["status"]}
    return {"job_id": job_id, "result": job["result"]}


@backtest_router.get("/api/backtest/history")
async def backtest_history():
    """List recent backtest runs."""
    return {"history": _history[:20]}


@backtest_router.post("/api/backtest/save/{job_id}")
async def save_backtest(job_id: str, label: str = ""):
    """Save a completed backtest result for comparison."""
    if job_id not in _jobs or _jobs[job_id]["status"] != "completed":
        return {"error": "No completed result for this job"}
    save_id = str(uuid.uuid4())[:8]
    result = _jobs[job_id]["result"]
    _saved_results[save_id] = {
        "save_id": save_id,
        "job_id": job_id,
        "label": label or f"{result['name']} ({result['start_date']}~{result['end_date']})",
        "result": result,
        "saved_at": datetime.now().isoformat(),
    }
    return {"save_id": save_id, "label": _saved_results[save_id]["label"]}


@backtest_router.get("/api/backtest/saved")
async def list_saved():
    """List saved backtest results."""
    items = []
    for sid, data in _saved_results.items():
        r = data["result"]
        items.append({
            "save_id": sid,
            "label": data["label"],
            "total_return_pct": r["total_return_pct"],
            "sharpe_ratio": r["sharpe_ratio"],
            "saved_at": data["saved_at"],
        })
    return {"saved": items}


@backtest_router.get("/api/backtest/compare")
async def compare_saved(ids: str = ""):
    """Compare up to 3 saved results. ids = comma-separated save_ids."""
    if not ids:
        return {"error": "Provide save_ids as comma-separated 'ids' query param"}
    id_list = [i.strip() for i in ids.split(",")][:3]
    results = []
    for sid in id_list:
        if sid in _saved_results:
            results.append(_saved_results[sid])
    return {"comparisons": results}


@backtest_router.get("/api/backtest/watchlist")
async def get_watchlist():
    """Return the KOSPI watchlist for the UI dropdown."""
    return {"watchlist": WATCHLIST}


# ---------------------------------------------------------------------------
# Web UI Page
# ---------------------------------------------------------------------------
@backtest_router.get("/backtest", response_class=HTMLResponse)
async def backtest_page():
    """Serve the full interactive backtesting portal page."""
    return BACKTEST_HTML


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------
BACKTEST_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockBot v2.1 - Backtest Portal</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0a0e17; color: #c9d1d9; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #161b28, #0a0e17); padding: 16px 24px; border-bottom: 1px solid #21262d;
                   display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.4rem; color: #58a6ff; }
        .header-nav { display: flex; gap: 14px; align-items: center; }
        .header-nav a { color: #8b949e; text-decoration: none; font-size: 0.9rem; padding: 4px 10px; border-radius: 6px; transition: all 0.2s; }
        .header-nav a:hover, .header-nav a.active { color: #58a6ff; background: #1f6feb22; }
        .container { max-width: 1600px; margin: 0 auto; padding: 16px; }

        /* Cards */
        .card { background: #161b28; border: 1px solid #21262d; border-radius: 8px; padding: 16px; margin-bottom: 14px; }
        .card h2 { color: #58a6ff; font-size: 0.95rem; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #21262d; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
        .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin-bottom: 14px; }
        .grid-5 { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 14px; }

        /* Stat cards */
        .stat-card { background: #161b28; border: 1px solid #21262d; border-radius: 8px; padding: 14px; text-align: center; }
        .stat-card .label { color: #8b949e; font-size: 0.75rem; margin-bottom: 4px; }
        .stat-card .value { font-size: 1.5rem; font-weight: 700; }
        .pos { color: #f85149; }
        .neg { color: #58a6ff; }
        .green { color: #3fb950; }
        .accent { color: #58a6ff; }
        .yellow { color: #d29922; }

        /* Form */
        .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }
        .form-group { display: flex; flex-direction: column; gap: 4px; }
        .form-group label { color: #8b949e; font-size: 0.8rem; font-weight: 600; }
        .form-group input, .form-group select { background: #0d1117; border: 1px solid #30363d; color: #c9d1d9;
            padding: 8px 10px; border-radius: 6px; font-size: 0.85rem; }
        .form-group input:focus, .form-group select:focus { border-color: #58a6ff; outline: none; }

        /* Sliders */
        .slider-group { display: flex; flex-direction: column; gap: 4px; }
        .slider-group label { color: #8b949e; font-size: 0.8rem; font-weight: 600; }
        .slider-row { display: flex; align-items: center; gap: 8px; }
        .slider-row input[type="range"] { flex: 1; accent-color: #58a6ff; }
        .slider-val { color: #c9d1d9; font-size: 0.85rem; font-weight: 600; min-width: 48px; text-align: right; }

        /* Buttons */
        .btn { padding: 8px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.85rem; transition: opacity 0.2s; }
        .btn:hover { opacity: 0.85; }
        .btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .btn-primary { background: #1f6feb; color: white; }
        .btn-success { background: #238636; color: white; }
        .btn-danger { background: #da3633; color: white; }
        .btn-sm { padding: 5px 12px; font-size: 0.78rem; }
        .btn-outline { background: transparent; border: 1px solid #30363d; color: #c9d1d9; }
        .btn-outline:hover { border-color: #58a6ff; color: #58a6ff; }

        /* Progress bar */
        .progress-container { margin-top: 12px; display: none; }
        .progress-bar { width: 100%; height: 6px; background: #21262d; border-radius: 3px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #1f6feb, #58a6ff); transition: width 0.3s; width: 0%; }
        .progress-text { color: #8b949e; font-size: 0.78rem; margin-top: 4px; }

        /* Results section */
        #resultsSection { display: none; }

        /* Tables */
        table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
        th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid #21262d; }
        th { color: #8b949e; font-weight: 600; background: #0d1117; position: sticky; top: 0; }
        .scroll-table { max-height: 350px; overflow-y: auto; }

        /* Monthly heatmap */
        .heatmap-table td { text-align: center; font-size: 0.78rem; font-weight: 600; padding: 6px 8px; min-width: 55px; }
        .heatmap-table th { text-align: center; font-size: 0.75rem; }

        /* Chart containers */
        .chart-container { position: relative; height: 300px; width: 100%; }

        /* Comparison panel */
        .compare-panel { display: none; }
        .saved-list { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
        .saved-chip { background: #21262d; border: 1px solid #30363d; border-radius: 16px; padding: 4px 12px;
                      font-size: 0.78rem; cursor: pointer; transition: all 0.2s; }
        .saved-chip:hover { border-color: #58a6ff; }
        .saved-chip.selected { background: #1f6feb33; border-color: #1f6feb; color: #58a6ff; }

        /* Strategy weights section */
        .weights-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; }

        /* Badges */
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: 600; }
        .badge-sl { background: #f8514933; color: #f85149; }
        .badge-tp { background: #23863633; color: #3fb950; }
        .badge-ts { background: #d2992233; color: #d29922; }
        .badge-sig { background: #1f6feb33; color: #58a6ff; }
        .badge-end { background: #21262d; color: #8b949e; }

        /* Tabs */
        .tab-bar { display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 1px solid #21262d; padding-bottom: 0; }
        .tab-btn { background: none; border: none; color: #8b949e; font-size: 0.85rem; padding: 8px 14px; cursor: pointer;
                   border-bottom: 2px solid transparent; transition: all 0.2s; }
        .tab-btn:hover { color: #c9d1d9; }
        .tab-btn.active { color: #58a6ff; border-bottom-color: #58a6ff; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        @media (max-width: 1000px) {
            .grid-2, .grid-3 { grid-template-columns: 1fr; }
            .grid-5 { grid-template-columns: repeat(3, 1fr); }
            .form-grid { grid-template-columns: 1fr 1fr; }
        }
        @media (max-width: 600px) {
            .grid-5 { grid-template-columns: repeat(2, 1fr); }
            .form-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>StockBot v2.1 - Backtest Portal</h1>
        <div class="header-nav">
            <a href="/">Dashboard</a>
            <a href="/backtest" class="active">Backtest</a>
        </div>
    </div>

    <div class="container">
        <!-- INPUT FORM -->
        <div class="card">
            <h2>Backtest Configuration</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>Symbol</label>
                    <select id="symbolSelect"></select>
                </div>
                <div class="form-group">
                    <label>Start Date</label>
                    <input type="date" id="startDate" value="">
                </div>
                <div class="form-group">
                    <label>End Date</label>
                    <input type="date" id="endDate" value="">
                </div>
                <div class="form-group">
                    <label>Initial Capital (KRW)</label>
                    <input type="number" id="initialCapital" value="10000000" step="1000000" min="1000000">
                </div>
            </div>

            <div style="margin-top: 14px;">
                <div class="form-grid" style="grid-template-columns: repeat(3, 1fr);">
                    <div class="slider-group">
                        <label>Stop Loss %</label>
                        <div class="slider-row">
                            <input type="range" id="slSlider" min="1" max="10" step="0.5" value="5">
                            <span class="slider-val" id="slVal">5.0%</span>
                        </div>
                    </div>
                    <div class="slider-group">
                        <label>Take Profit %</label>
                        <div class="slider-row">
                            <input type="range" id="tpSlider" min="5" max="30" step="1" value="15">
                            <span class="slider-val" id="tpVal">15%</span>
                        </div>
                    </div>
                    <div class="slider-group">
                        <label>Trailing Stop %</label>
                        <div class="slider-row">
                            <input type="range" id="tsSlider" min="1" max="10" step="0.5" value="5">
                            <span class="slider-val" id="tsVal">5.0%</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Strategy Weights (collapsible) -->
            <details style="margin-top: 12px;">
                <summary style="color: #58a6ff; cursor: pointer; font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">
                    Strategy Weights (Advanced)
                </summary>
                <div class="weights-grid" id="weightsGrid"></div>
            </details>

            <div style="margin-top: 16px; display: flex; gap: 10px; align-items: center;">
                <button class="btn btn-primary" id="runBtn" onclick="runBacktest()">Run Backtest</button>
                <div class="progress-container" id="progressContainer">
                    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
                    <div class="progress-text" id="progressText">Queued...</div>
                </div>
            </div>
        </div>

        <!-- RESULTS SECTION -->
        <div id="resultsSection">
            <!-- Summary cards -->
            <div class="grid-5" id="summaryCards">
                <div class="stat-card"><div class="label">Total Return</div><div class="value" id="metricReturn">-</div></div>
                <div class="stat-card"><div class="label">Max Drawdown</div><div class="value" id="metricDD">-</div></div>
                <div class="stat-card"><div class="label">Sharpe Ratio</div><div class="value" id="metricSharpe">-</div></div>
                <div class="stat-card"><div class="label">Win Rate</div><div class="value" id="metricWinRate">-</div></div>
                <div class="stat-card"><div class="label">Profit Factor</div><div class="value" id="metricPF">-</div></div>
            </div>

            <!-- Secondary metrics -->
            <div class="grid-5" style="margin-bottom: 14px;">
                <div class="stat-card"><div class="label">Annual Return</div><div class="value" id="metricAnnual" style="font-size:1.1rem;">-</div></div>
                <div class="stat-card"><div class="label">Sortino Ratio</div><div class="value" id="metricSortino" style="font-size:1.1rem;">-</div></div>
                <div class="stat-card"><div class="label">Total Trades</div><div class="value accent" id="metricTrades" style="font-size:1.1rem;">-</div></div>
                <div class="stat-card"><div class="label">Avg Win / Loss</div><div class="value" id="metricAvgWL" style="font-size:1.1rem;">-</div></div>
                <div class="stat-card"><div class="label">Avg Hold Days</div><div class="value accent" id="metricHoldDays" style="font-size:1.1rem;">-</div></div>
            </div>

            <!-- Save + Compare buttons -->
            <div style="display: flex; gap: 8px; margin-bottom: 14px; align-items: center;">
                <button class="btn btn-success btn-sm" onclick="saveResult()">Save Result</button>
                <button class="btn btn-outline btn-sm" onclick="toggleCompare()">Compare Mode</button>
                <span id="saveMsg" style="color: #3fb950; font-size: 0.78rem;"></span>
            </div>

            <!-- Tabs -->
            <div class="tab-bar">
                <button class="tab-btn active" onclick="switchTab('charts')">Charts</button>
                <button class="tab-btn" onclick="switchTab('trades')">Trades</button>
                <button class="tab-btn" onclick="switchTab('monthly')">Monthly Returns</button>
                <button class="tab-btn" onclick="switchTab('distribution')">P&L Distribution</button>
            </div>

            <!-- Charts Tab -->
            <div class="tab-content active" id="tab-charts">
                <div class="grid-2">
                    <div class="card">
                        <h2>Equity Curve</h2>
                        <div class="chart-container"><canvas id="equityChart"></canvas></div>
                    </div>
                    <div class="card">
                        <h2>Drawdown</h2>
                        <div class="chart-container"><canvas id="drawdownChart"></canvas></div>
                    </div>
                </div>
            </div>

            <!-- Trades Tab -->
            <div class="tab-content" id="tab-trades">
                <div class="card">
                    <h2>Trade List</h2>
                    <div class="scroll-table" style="max-height: 500px;">
                        <table>
                            <thead><tr><th>#</th><th>Entry Date</th><th>Exit Date</th><th>Symbol</th><th>P&L %</th><th>Exit Reason</th></tr></thead>
                            <tbody id="tradeTableBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Monthly Returns Tab -->
            <div class="tab-content" id="tab-monthly">
                <div class="card">
                    <h2>Monthly Returns Heatmap</h2>
                    <div class="scroll-table" id="monthlyHeatmap"></div>
                </div>
            </div>

            <!-- Distribution Tab -->
            <div class="tab-content" id="tab-distribution">
                <div class="card">
                    <h2>P&L Distribution</h2>
                    <div class="chart-container" style="height: 280px;"><canvas id="distChart"></canvas></div>
                </div>
            </div>
        </div>

        <!-- COMPARISON PANEL -->
        <div class="compare-panel card" id="comparePanel">
            <h2>Compare Backtests (select up to 3)</h2>
            <div class="saved-list" id="savedList"></div>
            <button class="btn btn-primary btn-sm" onclick="runComparison()">Compare Selected</button>
            <div id="compareResult" style="margin-top: 14px;">
                <div class="chart-container" style="height: 320px;"><canvas id="compareChart"></canvas></div>
                <div id="compareTable" style="margin-top: 12px;"></div>
            </div>
        </div>

        <!-- HISTORY -->
        <div class="card" style="margin-top: 14px;">
            <h2>Recent Backtests</h2>
            <div class="scroll-table">
                <table>
                    <thead><tr><th>Time</th><th>Symbol</th><th>Period</th><th>Return</th><th>Sharpe</th><th>Win Rate</th><th>Trades</th><th></th></tr></thead>
                    <tbody id="historyBody"><tr><td colspan="8" style="color:#8b949e">No backtests yet</td></tr></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
    // === State ===
    let currentJobId = null;
    let currentResult = null;
    let pollTimer = null;
    let charts = {};  // chart instances
    let selectedSaved = new Set();

    const STRATEGY_NAMES = [
        {key: "Bollinger", label: "Bollinger Bands", default: 0.15},
        {key: "RSI", label: "RSI", default: 0.20},
        {key: "MACD", label: "MACD", default: 0.20},
        {key: "MovingAverage", label: "Moving Average", default: 0.20},
        {key: "InstitutionalFlow", label: "Institutional Flow", default: 0.25},
    ];
    // Korean-named strategies
    const STRATEGY_NAMES_KR = [
        {key: "\\ubaa8\\uba58\\ud140", label: "Momentum", default: 0.20},
        {key: "\\ub4c0\\uc5bc\\ubaa8\\uba58\\ud140", label: "Dual Momentum", default: 0.15},
        {key: "\\ubcc0\\ub3d9\\uc131\\ud0c0\\uac9f", label: "Volatility Target", default: 0.15},
    ];
    const ALL_STRATEGIES = [...STRATEGY_NAMES, ...STRATEGY_NAMES_KR];

    const fmt = n => n ? n.toLocaleString('ko-KR') : '0';

    // === Init ===
    async function init() {
        // Set date defaults (1 year ago to today)
        const today = new Date();
        const yearAgo = new Date(today);
        yearAgo.setFullYear(yearAgo.getFullYear() - 1);
        document.getElementById('endDate').value = today.toISOString().slice(0, 10);
        document.getElementById('startDate').value = yearAgo.toISOString().slice(0, 10);

        // Load watchlist
        try {
            const r = await fetch('/api/backtest/watchlist');
            const d = await r.json();
            const sel = document.getElementById('symbolSelect');
            (d.watchlist || []).forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.code;
                opt.textContent = s.name + ' (' + s.code + ')';
                sel.appendChild(opt);
            });
        } catch(e) { console.error('Failed to load watchlist', e); }

        // Slider listeners
        ['slSlider', 'tpSlider', 'tsSlider'].forEach(id => {
            const el = document.getElementById(id);
            const valId = id.replace('Slider', 'Val');
            el.addEventListener('input', () => {
                const v = parseFloat(el.value);
                document.getElementById(valId).textContent = (id === 'tpSlider') ? v + '%' : v.toFixed(1) + '%';
            });
        });

        // Build strategy weight sliders
        const grid = document.getElementById('weightsGrid');
        ALL_STRATEGIES.forEach(s => {
            const div = document.createElement('div');
            div.className = 'slider-group';
            div.innerHTML = '<label>' + s.label + '</label>'
                + '<div class="slider-row">'
                + '<input type="range" min="0" max="0.5" step="0.05" value="' + s.default + '" data-strategy="' + s.key + '" class="weight-slider">'
                + '<span class="slider-val">' + (s.default * 100).toFixed(0) + '%</span>'
                + '</div>';
            grid.appendChild(div);
        });
        document.querySelectorAll('.weight-slider').forEach(sl => {
            sl.addEventListener('input', () => {
                sl.nextElementSibling.textContent = (parseFloat(sl.value) * 100).toFixed(0) + '%';
            });
        });

        // Load history
        loadHistory();
    }

    // === Run Backtest ===
    async function runBacktest() {
        const symbol = document.getElementById('symbolSelect').value;
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        const capital = parseFloat(document.getElementById('initialCapital').value);
        const sl = parseFloat(document.getElementById('slSlider').value);
        const tp = parseFloat(document.getElementById('tpSlider').value);
        const ts = parseFloat(document.getElementById('tsSlider').value);

        if (!symbol || !startDate || !endDate) {
            alert('Please fill in symbol and date range');
            return;
        }

        // Collect strategy weights
        const weights = {};
        document.querySelectorAll('.weight-slider').forEach(sl => {
            weights[sl.dataset.strategy] = parseFloat(sl.value);
        });

        const body = {
            symbol, start_date: startDate, end_date: endDate,
            initial_capital: capital, stop_loss_pct: sl, take_profit_pct: tp,
            trailing_stop_pct: ts, strategy_weights: weights,
        };

        document.getElementById('runBtn').disabled = true;
        document.getElementById('progressContainer').style.display = 'block';
        document.getElementById('progressFill').style.width = '0%';
        document.getElementById('progressText').textContent = 'Starting...';
        document.getElementById('resultsSection').style.display = 'none';

        try {
            const r = await fetch('/api/backtest/run', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body),
            });
            const d = await r.json();
            currentJobId = d.job_id;
            pollProgress();
        } catch(e) {
            alert('Failed to start backtest: ' + e);
            document.getElementById('runBtn').disabled = false;
        }
    }

    function pollProgress() {
        if (!currentJobId) return;
        pollTimer = setInterval(async () => {
            try {
                const r = await fetch('/api/backtest/status/' + currentJobId);
                const d = await r.json();
                document.getElementById('progressFill').style.width = d.progress + '%';
                document.getElementById('progressText').textContent = d.progress_msg || d.status;

                if (d.status === 'completed') {
                    clearInterval(pollTimer);
                    await loadResult(currentJobId);
                    document.getElementById('runBtn').disabled = false;
                } else if (d.status === 'failed') {
                    clearInterval(pollTimer);
                    document.getElementById('progressText').textContent = 'FAILED: ' + (d.error || 'Unknown error');
                    document.getElementById('runBtn').disabled = false;
                }
            } catch(e) { console.error(e); }
        }, 500);
    }

    async function loadResult(jobId) {
        const r = await fetch('/api/backtest/result/' + jobId);
        const d = await r.json();
        if (d.error) { alert(d.error); return; }
        currentResult = d.result;
        renderResults(currentResult);
        loadHistory();
    }

    // === Render Results ===
    function renderResults(res) {
        document.getElementById('resultsSection').style.display = 'block';
        document.getElementById('progressContainer').style.display = 'none';

        // Summary cards
        const retEl = document.getElementById('metricReturn');
        retEl.textContent = (res.total_return_pct >= 0 ? '+' : '') + res.total_return_pct.toFixed(2) + '%';
        retEl.className = 'value ' + (res.total_return_pct >= 0 ? 'green' : 'pos');

        const ddEl = document.getElementById('metricDD');
        ddEl.textContent = '-' + res.max_drawdown_pct.toFixed(2) + '%';
        ddEl.className = 'value pos';

        const shEl = document.getElementById('metricSharpe');
        shEl.textContent = res.sharpe_ratio.toFixed(2);
        shEl.className = 'value ' + (res.sharpe_ratio >= 1 ? 'green' : res.sharpe_ratio >= 0 ? 'accent' : 'pos');

        const wrEl = document.getElementById('metricWinRate');
        wrEl.textContent = res.win_rate.toFixed(1) + '%';
        wrEl.className = 'value ' + (res.win_rate >= 50 ? 'green' : 'yellow');

        const pfEl = document.getElementById('metricPF');
        pfEl.textContent = res.profit_factor.toFixed(2);
        pfEl.className = 'value ' + (res.profit_factor >= 1.5 ? 'green' : res.profit_factor >= 1 ? 'accent' : 'pos');

        document.getElementById('metricAnnual').textContent = (res.annual_return_pct >= 0 ? '+' : '') + res.annual_return_pct.toFixed(2) + '%';
        document.getElementById('metricAnnual').className = 'value ' + (res.annual_return_pct >= 0 ? 'green' : 'pos');
        document.getElementById('metricSortino').textContent = res.sortino_ratio.toFixed(2);
        document.getElementById('metricTrades').textContent = res.total_trades;
        document.getElementById('metricAvgWL').innerHTML = '<span class="green">+' + res.avg_win_pct.toFixed(1) + '%</span> / <span class="pos">' + res.avg_loss_pct.toFixed(1) + '%</span>';
        document.getElementById('metricHoldDays').textContent = res.avg_hold_days.toFixed(1) + 'd';

        renderEquityChart(res);
        renderDrawdownChart(res);
        renderTradeTable(res);
        renderMonthlyHeatmap(res);
        renderDistribution(res);
    }

    // === Charts ===
    function destroyChart(key) {
        if (charts[key]) { charts[key].destroy(); charts[key] = null; }
    }

    function renderEquityChart(res) {
        destroyChart('equity');
        const labels = res.equity_curve.map(p => p[0]);
        const data = res.equity_curve.map(p => p[1]);
        const ctx = document.getElementById('equityChart').getContext('2d');
        charts.equity = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Portfolio Value',
                    data,
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88,166,255,0.08)',
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#8b949e', maxTicksLimit: 8 }, grid: { color: '#21262d' } },
                    y: { ticks: { color: '#8b949e', callback: v => (v/1e6).toFixed(1)+'M' }, grid: { color: '#21262d' } },
                },
                interaction: { mode: 'index', intersect: false },
            }
        });
    }

    function renderDrawdownChart(res) {
        destroyChart('drawdown');
        const eq = res.equity_curve;
        let peak = 0;
        const labels = [];
        const ddData = [];
        for (const [d, v] of eq) {
            if (v > peak) peak = v;
            const dd = peak > 0 ? -((peak - v) / peak * 100) : 0;
            labels.push(d);
            ddData.push(Math.round(dd * 100) / 100);
        }
        const ctx = document.getElementById('drawdownChart').getContext('2d');
        charts.drawdown = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Drawdown %',
                    data: ddData,
                    borderColor: '#f85149',
                    backgroundColor: 'rgba(248,81,73,0.15)',
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    borderWidth: 1.5,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#8b949e', maxTicksLimit: 8 }, grid: { color: '#21262d' } },
                    y: { ticks: { color: '#8b949e', callback: v => v.toFixed(1)+'%' }, grid: { color: '#21262d' } },
                },
            }
        });
    }

    function renderDistribution(res) {
        destroyChart('dist');
        const pnls = res.trades.map(t => t[3]);
        if (!pnls.length) return;
        // Build histogram
        const bins = {};
        const edges = [];
        for (let e = -12; e <= 20; e += 2) edges.push(e);
        edges.forEach(e => bins[e] = 0);
        for (const p of pnls) {
            let b = Math.floor(p / 2) * 2;
            b = Math.max(-12, Math.min(20, b));
            if (!(b in bins)) bins[b] = 0;
            bins[b]++;
        }
        const labels = edges.map(e => (e >= 0 ? '+' : '') + e + '%');
        const data = edges.map(e => bins[e] || 0);
        const colors = edges.map(e => e >= 0 ? 'rgba(63,185,80,0.6)' : 'rgba(248,81,73,0.6)');
        const ctx = document.getElementById('distChart').getContext('2d');
        charts.dist = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Trade Count',
                    data,
                    backgroundColor: colors,
                    borderColor: colors.map(c => c.replace('0.6', '1')),
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
                    y: { ticks: { color: '#8b949e', stepSize: 1 }, grid: { color: '#21262d' } },
                },
            }
        });
    }

    // === Trade Table ===
    function renderTradeTable(res) {
        const tbody = document.getElementById('tradeTableBody');
        if (!res.trades.length) {
            tbody.innerHTML = '<tr><td colspan="6" style="color:#8b949e">No trades</td></tr>';
            return;
        }
        tbody.innerHTML = res.trades.map((t, i) => {
            const pnl = t[3];
            const cls = pnl > 0 ? 'green' : pnl < 0 ? 'pos' : '';
            const reason = t[4];
            let badge = 'badge-end';
            if (reason === 'STOP_LOSS') badge = 'badge-sl';
            else if (reason === 'TAKE_PROFIT') badge = 'badge-tp';
            else if (reason === 'TRAILING_STOP') badge = 'badge-ts';
            else if (reason === 'SIGNAL_SELL') badge = 'badge-sig';
            return '<tr><td>' + (i+1) + '</td><td>' + t[0] + '</td><td>' + t[1] + '</td><td>' + t[2]
                + '</td><td class="' + cls + '">' + (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + '%</td>'
                + '<td><span class="badge ' + badge + '">' + reason + '</span></td></tr>';
        }).join('');
    }

    // === Monthly Heatmap ===
    function renderMonthlyHeatmap(res) {
        const container = document.getElementById('monthlyHeatmap');
        const mr = res.monthly_returns || {};
        const years = Object.keys(mr).sort();
        if (!years.length) {
            container.innerHTML = '<p style="color:#8b949e">No monthly data</p>';
            return;
        }
        const months = ['01','02','03','04','05','06','07','08','09','10','11','12'];
        let html = '<table class="heatmap-table"><thead><tr><th>Year</th>';
        months.forEach(m => html += '<th>' + m + '</th>');
        html += '<th>YTD</th></tr></thead><tbody>';
        for (const y of years) {
            html += '<tr><td style="font-weight:700">' + y + '</td>';
            let ytd = 0;
            for (const m of months) {
                const val = mr[y] && mr[y][m] !== undefined ? mr[y][m] : null;
                if (val !== null) {
                    ytd += val;
                    const bg = val > 0 ? heatColor(val, true) : val < 0 ? heatColor(val, false) : 'transparent';
                    const clr = val > 0 ? '#3fb950' : val < 0 ? '#f85149' : '#8b949e';
                    html += '<td style="background:' + bg + ';color:' + clr + '">' + (val >= 0 ? '+' : '') + val.toFixed(1) + '%</td>';
                } else {
                    html += '<td style="color:#30363d">-</td>';
                }
            }
            const ytdClr = ytd >= 0 ? '#3fb950' : '#f85149';
            html += '<td style="color:' + ytdClr + ';font-weight:700">' + (ytd >= 0 ? '+' : '') + ytd.toFixed(1) + '%</td>';
            html += '</tr>';
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    function heatColor(val, positive) {
        const intensity = Math.min(Math.abs(val) / 10, 1);
        if (positive) return 'rgba(63,185,80,' + (0.1 + intensity * 0.35) + ')';
        return 'rgba(248,81,73,' + (0.1 + intensity * 0.35) + ')';
    }

    // === Tab switching ===
    function switchTab(name) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById('tab-' + name).classList.add('active');
        event.target.classList.add('active');
    }

    // === Save & Compare ===
    async function saveResult() {
        if (!currentJobId) return;
        try {
            const r = await fetch('/api/backtest/save/' + currentJobId, {method: 'POST'});
            const d = await r.json();
            document.getElementById('saveMsg').textContent = 'Saved: ' + d.label;
            setTimeout(() => document.getElementById('saveMsg').textContent = '', 3000);
            loadSavedList();
        } catch(e) { alert('Save failed'); }
    }

    async function loadSavedList() {
        try {
            const r = await fetch('/api/backtest/saved');
            const d = await r.json();
            const container = document.getElementById('savedList');
            container.innerHTML = '';
            (d.saved || []).forEach(s => {
                const chip = document.createElement('span');
                chip.className = 'saved-chip' + (selectedSaved.has(s.save_id) ? ' selected' : '');
                chip.textContent = s.label + ' (' + (s.total_return_pct >= 0 ? '+' : '') + s.total_return_pct.toFixed(1) + '%)';
                chip.onclick = () => {
                    if (selectedSaved.has(s.save_id)) {
                        selectedSaved.delete(s.save_id);
                        chip.classList.remove('selected');
                    } else if (selectedSaved.size < 3) {
                        selectedSaved.add(s.save_id);
                        chip.classList.add('selected');
                    }
                };
                container.appendChild(chip);
            });
        } catch(e) {}
    }

    function toggleCompare() {
        const panel = document.getElementById('comparePanel');
        if (panel.style.display === 'block') {
            panel.style.display = 'none';
        } else {
            panel.style.display = 'block';
            loadSavedList();
        }
    }

    async function runComparison() {
        if (selectedSaved.size === 0) { alert('Select at least one saved result'); return; }
        const ids = [...selectedSaved].join(',');
        try {
            const r = await fetch('/api/backtest/compare?ids=' + ids);
            const d = await r.json();
            renderComparison(d.comparisons || []);
        } catch(e) { alert('Compare failed'); }
    }

    function renderComparison(comparisons) {
        destroyChart('compare');
        if (!comparisons.length) return;

        const colors = ['#58a6ff', '#3fb950', '#d29922'];
        const datasets = comparisons.map((c, i) => ({
            label: c.label,
            data: c.result.equity_curve.map(p => p[1]),
            borderColor: colors[i % 3],
            tension: 0.1,
            pointRadius: 0,
            borderWidth: 2,
            fill: false,
        }));

        // Use longest label set
        let maxLabels = [];
        comparisons.forEach(c => {
            const labels = c.result.equity_curve.map(p => p[0]);
            if (labels.length > maxLabels.length) maxLabels = labels;
        });

        const ctx = document.getElementById('compareChart').getContext('2d');
        charts.compare = new Chart(ctx, {
            type: 'line',
            data: { labels: maxLabels, datasets },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#c9d1d9' } } },
                scales: {
                    x: { ticks: { color: '#8b949e', maxTicksLimit: 8 }, grid: { color: '#21262d' } },
                    y: { ticks: { color: '#8b949e', callback: v => (v/1e6).toFixed(1)+'M' }, grid: { color: '#21262d' } },
                },
            }
        });

        // Comparison table
        let html = '<table><thead><tr><th>Metric</th>';
        comparisons.forEach(c => html += '<th>' + c.label + '</th>');
        html += '</tr></thead><tbody>';
        const metrics = [
            ['Total Return', r => (r.total_return_pct >= 0 ? '+' : '') + r.total_return_pct.toFixed(2) + '%'],
            ['Annual Return', r => (r.annual_return_pct >= 0 ? '+' : '') + r.annual_return_pct.toFixed(2) + '%'],
            ['Max Drawdown', r => '-' + r.max_drawdown_pct.toFixed(2) + '%'],
            ['Sharpe Ratio', r => r.sharpe_ratio.toFixed(2)],
            ['Win Rate', r => r.win_rate.toFixed(1) + '%'],
            ['Profit Factor', r => r.profit_factor.toFixed(2)],
            ['Total Trades', r => r.total_trades],
        ];
        metrics.forEach(([label, fn]) => {
            html += '<tr><td>' + label + '</td>';
            comparisons.forEach(c => html += '<td>' + fn(c.result) + '</td>');
            html += '</tr>';
        });
        html += '</tbody></table>';
        document.getElementById('compareTable').innerHTML = html;
    }

    // === History ===
    async function loadHistory() {
        try {
            const r = await fetch('/api/backtest/history');
            const d = await r.json();
            const tbody = document.getElementById('historyBody');
            const items = d.history || [];
            if (!items.length) {
                tbody.innerHTML = '<tr><td colspan="8" style="color:#8b949e">No backtests yet</td></tr>';
                return;
            }
            tbody.innerHTML = items.map(h => {
                const retCls = h.total_return_pct >= 0 ? 'green' : 'pos';
                return '<tr>'
                    + '<td>' + (h.completed_at || '').slice(0, 16).replace('T', ' ') + '</td>'
                    + '<td><b>' + (h.name || h.symbol) + '</b></td>'
                    + '<td>' + h.start_date + ' ~ ' + h.end_date + '</td>'
                    + '<td class="' + retCls + '">' + (h.total_return_pct >= 0 ? '+' : '') + h.total_return_pct.toFixed(2) + '%</td>'
                    + '<td>' + h.sharpe_ratio.toFixed(2) + '</td>'
                    + '<td>' + h.win_rate.toFixed(1) + '%</td>'
                    + '<td>' + h.total_trades + '</td>'
                    + '<td><button class="btn btn-outline btn-sm" onclick="loadResult(\\'' + h.job_id + '\\')">View</button></td>'
                    + '</tr>';
            }).join('');
        } catch(e) { console.error(e); }
    }

    // Boot
    init();
    </script>
</body>
</html>
"""
