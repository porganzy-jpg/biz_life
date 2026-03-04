"""
StockBot v3.5 대시보드
5전략 앙상블 + ATR 포지션사이징 + 서킷브레이커 + 일일성과 + 시장국면감지
+ 성과 차트 (Equity Curve, Daily PnL, Strategy Stats, Trade Distribution)
+ 전략 분석 (Strategy Heatmap, Rolling Performance, Toggle, Ranking)
+ 시장 레짐 (Dashboard Regime Detection & Strategy Rotation)
+ 스마트 주문 실행 (TWAP/VWAP/Smart Execute, 슬리피지 분석)
"""
import sys
import os
import json
import math

# dashboard/regime_detector.py를 trader.py import 전에 먼저 로드 (이름 충돌 방지)
import importlib.util as _ilu
_dashboard_dir = os.path.dirname(__file__)
_spec = _ilu.spec_from_file_location(
    "dashboard_regime", os.path.join(_dashboard_dir, "regime_detector.py"))
_drm = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_drm)

DashboardRegimeDetector = _drm.RegimeDetector
StrategyRotator = _drm.StrategyRotator
DashboardRegime = _drm.DashboardRegime
compute_regime_from_trades = _drm.compute_regime_from_trades
get_regime_display = _drm.get_regime_display
REGIME_STRATEGY_NAMES = _drm.STRATEGY_NAMES

sys.path.insert(0, os.path.join(_dashboard_dir, "..", "trading-bot"))
sys.path.insert(0, os.path.join(_dashboard_dir, "..", "strategy"))
sys.path.insert(0, os.path.join(_dashboard_dir, "..", "news"))

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import uvicorn

from trader import StockTrader
from database import get_connection
from config import DASHBOARD_HOST, DASHBOARD_PORT, WATCHLIST, TRADING_MODE, LIVE_TRADING_CONFIRMED

from datetime import datetime, timedelta

from backtest_portal import backtest_router
from correlation_monitor import CorrelationMonitor

app = FastAPI(title="StockBot v3.5 Dashboard")
app.include_router(backtest_router)
_is_live = (TRADING_MODE == "live" and LIVE_TRADING_CONFIRMED)
trader = StockTrader(paper_trading=not _is_live)

# --- Dashboard regime detector & strategy rotator ---
dashboard_regime_detector = DashboardRegimeDetector()
strategy_rotator = StrategyRotator()

# --- Portfolio correlation monitor ---
correlation_monitor = CorrelationMonitor(broker_client=trader.client)

# --- Strategy toggle state (in-memory, persisted to JSON) ---
STRATEGY_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "strategy_config.json")
STRATEGY_NAMES = [
    "Bollinger", "RSI", "MACD", "MA", "InstitutionalFlow",
    "Momentum", "DualMomentum", "VolatilityTarget",
]


def _load_strategy_config() -> dict:
    """Load strategy enable/disable config from JSON file."""
    if os.path.exists(STRATEGY_CONFIG_PATH):
        try:
            with open(STRATEGY_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    # Default: all strategies enabled
    return {name: True for name in STRATEGY_NAMES}


def _save_strategy_config(config: dict):
    """Save strategy enable/disable config to JSON file."""
    with open(STRATEGY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _parse_strategy_from_reasons(reasons: list, strategy_names: list) -> list:
    """Parse reason strings to find matching strategy names."""
    matched = []
    for sname in strategy_names:
        for reason in reasons:
            if sname.lower() in str(reason).lower():
                matched.append(sname)
                break
    return matched


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


@app.get("/api/status")
async def get_status():
    return trader.get_status()


@app.get("/api/scan")
async def scan_watchlist():
    results = trader.scan_watchlist()
    return {"results": results}


@app.get("/api/analyze/{symbol}")
async def analyze_stock(symbol: str):
    stock = next((s for s in WATCHLIST if s["code"] == symbol), None)
    name = stock["name"] if stock else symbol
    return trader.analyze_stock(symbol, name)


@app.get("/api/history")
async def get_history():
    return {"trades": trader.db.get_trades(limit=100)}


@app.get("/api/performance")
async def get_performance():
    return {"daily": trader.db.get_daily_performance(days=30)}


@app.get("/api/stats")
async def get_stats():
    return {
        "7d": trader.db.get_trade_stats(days=7),
        "30d": trader.db.get_trade_stats(days=30),
        "all": trader.db.get_trade_stats(days=365),
    }


@app.get("/api/equity-curve")
async def get_equity_curve(period: str = Query("ALL")):
    """Equity curve data: date, balance, drawdown, cumulative P&L."""
    days_map = {"1W": 7, "1M": 30, "3M": 90, "ALL": 3650}
    days = days_map.get(period, 3650)
    conn = get_connection()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT date, total_assets, total_pnl, total_pnl_pct, cash, invested "
        "FROM daily_performance WHERE date >= ? ORDER BY date ASC",
        (since,),
    ).fetchall()
    conn.close()

    data = []
    peak = 0
    for r in rows:
        balance = r["total_assets"] or 0
        if balance > peak:
            peak = balance
        drawdown = ((balance - peak) / peak * 100) if peak > 0 else 0
        data.append({
            "date": r["date"],
            "balance": balance,
            "pnl": r["total_pnl"] or 0,
            "pnl_pct": r["total_pnl_pct"] or 0,
            "drawdown": round(drawdown, 2),
        })
    return {"data": data}


@app.get("/api/daily-pnl")
async def get_daily_pnl(period: str = Query("ALL")):
    """Daily P&L values with running total."""
    days_map = {"1W": 7, "1M": 30, "3M": 90, "ALL": 3650}
    days = days_map.get(period, 3650)
    conn = get_connection()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Compute daily PnL from trades table grouped by date
    rows = conn.execute(
        "SELECT DATE(timestamp) as trade_date, SUM(pnl) as day_pnl "
        "FROM trades WHERE timestamp >= ? AND action != 'BUY' "
        "GROUP BY DATE(timestamp) ORDER BY trade_date ASC",
        (since,),
    ).fetchall()
    conn.close()

    data = []
    running_total = 0
    for r in rows:
        day_pnl = r["day_pnl"] or 0
        running_total += day_pnl
        data.append({
            "date": r["trade_date"],
            "pnl": round(day_pnl),
            "running_total": round(running_total),
        })
    return {"data": data}


@app.get("/api/strategy-stats")
async def get_strategy_stats(period: str = Query("ALL")):
    """Per-strategy win/loss counts based on trade reasons."""
    days_map = {"1W": 7, "1M": 30, "3M": 90, "ALL": 3650}
    days = days_map.get(period, 3650)
    conn = get_connection()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT action, pnl, pnl_pct, reasons FROM trades "
        "WHERE timestamp >= ? AND action != 'BUY'",
        (since,),
    ).fetchall()
    conn.close()

    # Map sell trades to contributing strategies via the buy reasons.
    # Also inspect the action type for exit strategy attribution.
    strategy_names = [
        "Bollinger", "RSI", "MACD", "MA", "InstitutionalFlow",
        "Momentum", "DualMomentum", "VolatilityTarget",
    ]
    stats = {}
    for name in strategy_names:
        stats[name] = {"wins": 0, "losses": 0, "total_pnl": 0}

    # Also track exit-type strategies
    exit_types = {"STOP_LOSS": 0, "TAKE_PROFIT": 0, "TRAILING_STOP": 0, "SELL": 0}

    for r in rows:
        is_win = (r["pnl"] or 0) > 0
        pnl = r["pnl"] or 0
        action = r["action"] or ""

        if action in exit_types:
            exit_types[action] += 1

        # Parse reasons to find which strategies contributed
        try:
            reasons = json.loads(r["reasons"]) if r["reasons"] else []
        except (json.JSONDecodeError, TypeError):
            reasons = []

        matched = False
        for sname in strategy_names:
            for reason in reasons:
                if sname.lower() in str(reason).lower():
                    if is_win:
                        stats[sname]["wins"] += 1
                    else:
                        stats[sname]["losses"] += 1
                    stats[sname]["total_pnl"] += pnl
                    matched = True
                    break

        # If no strategy matched from reasons, attribute proportionally
        if not matched and reasons:
            share = 1.0 / len(strategy_names)
            for sname in strategy_names:
                if is_win:
                    stats[sname]["wins"] += share
                else:
                    stats[sname]["losses"] += share
                stats[sname]["total_pnl"] += pnl * share

    result = {}
    for sname, s in stats.items():
        total = s["wins"] + s["losses"]
        result[sname] = {
            "wins": round(s["wins"], 1),
            "losses": round(s["losses"], 1),
            "total": round(total, 1),
            "win_rate": round(s["wins"] / total * 100, 1) if total > 0 else 0,
            "total_pnl": round(s["total_pnl"]),
        }

    return {"strategies": result, "exit_types": exit_types}


@app.get("/api/trade-distribution")
async def get_trade_distribution(period: str = Query("ALL")):
    """Histogram of trade return percentages."""
    days_map = {"1W": 7, "1M": 30, "3M": 90, "ALL": 3650}
    days = days_map.get(period, 3650)
    conn = get_connection()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT pnl_pct FROM trades WHERE timestamp >= ? AND action != 'BUY' "
        "AND pnl_pct IS NOT NULL",
        (since,),
    ).fetchall()
    conn.close()

    returns = [r["pnl_pct"] for r in rows if r["pnl_pct"] is not None]

    # Create histogram bins: -10%, -8%, ..., -2%, 0%, 2%, ..., 8%, 10%+
    bins = {}
    bin_edges = list(range(-10, 12, 2))
    for edge in bin_edges:
        label = f"{edge:+d}%"
        bins[label] = 0

    for ret in returns:
        clamped = max(-10, min(10, ret))
        # Find the nearest lower even bin edge
        bin_idx = int((clamped + 10) // 2)
        bin_idx = max(0, min(len(bin_edges) - 1, bin_idx))
        label = f"{bin_edges[bin_idx]:+d}%"
        bins[label] += 1

    return {
        "bins": list(bins.keys()),
        "counts": list(bins.values()),
        "total_trades": len(returns),
        "avg_return": round(sum(returns) / len(returns), 2) if returns else 0,
        "median_return": round(sorted(returns)[len(returns) // 2], 2) if returns else 0,
    }


@app.post("/api/bot/start")
async def start_bot():
    if trader.scheduler.is_running:
        return {"status": "already_running"}
    trader.start_auto()
    return {"status": "started"}


@app.post("/api/bot/stop")
async def stop_bot():
    trader.stop_auto()
    return {"status": "stopped"}


@app.post("/api/cycle")
async def run_single_cycle():
    result = trader.run_cycle()
    return result


@app.get("/api/regime")
async def get_regime():
    return trader.regime_detector.get_status()


@app.post("/api/circuit-breaker/reset")
async def reset_circuit_breaker():
    trader.circuit_breaker.reset()
    return {"status": "reset"}


# =====================================================================
# Dashboard Regime Detection & Strategy Rotation API Endpoints
# =====================================================================

@app.get("/api/regime/current")
async def get_dashboard_regime_current():
    """Current market regime + confidence + recommended weights.
    Uses database trades and daily performance for classification.
    """
    conn = get_connection()
    # Fetch daily_performance (last 90 days, ordered ASC)
    since_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    daily_rows = conn.execute(
        "SELECT date, total_assets, total_pnl, total_pnl_pct, cash, invested "
        "FROM daily_performance WHERE date >= ? ORDER BY date ASC",
        (since_date,),
    ).fetchall()

    # Fetch sell trades (last 90 days, ordered ASC)
    since_ts = (datetime.now() - timedelta(days=90)).isoformat()
    trade_rows = conn.execute(
        "SELECT timestamp, pnl, pnl_pct, reasons FROM trades "
        "WHERE timestamp >= ? AND action != 'BUY' ORDER BY timestamp ASC",
        (since_ts,),
    ).fetchall()
    conn.close()

    daily_dicts = [dict(r) for r in daily_rows]
    trade_dicts = [dict(r) for r in trade_rows]

    result = compute_regime_from_trades(trade_dicts, daily_dicts)

    # Save to history
    strategy_rotator.save_to_history(result)

    # Get optimal weights
    weights = strategy_rotator.get_optimal_weights(result.regime, result.confidence)

    # Get display metadata
    display = get_regime_display(result.regime)

    return {
        "regime": result.regime.value,
        "confidence": result.confidence,
        "indicators": result.indicators,
        "timestamp": result.timestamp,
        "display": display,
        "recommended_weights": weights,
    }


@app.get("/api/regime/history")
async def get_dashboard_regime_history(days: int = Query(30)):
    """Regime history for the last N days."""
    history = strategy_rotator.get_history(days=days)
    return {"history": history, "days": days}


@app.post("/api/regime/apply-weights")
async def apply_regime_weights():
    """Apply recommended regime weights to strategy config.
    Re-computes the current regime, generates optimal weights,
    and saves them as enabled/weight config.
    """
    conn = get_connection()
    since_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    daily_rows = conn.execute(
        "SELECT date, total_assets, total_pnl, total_pnl_pct, cash, invested "
        "FROM daily_performance WHERE date >= ? ORDER BY date ASC",
        (since_date,),
    ).fetchall()

    since_ts = (datetime.now() - timedelta(days=90)).isoformat()
    trade_rows = conn.execute(
        "SELECT timestamp, pnl, pnl_pct, reasons FROM trades "
        "WHERE timestamp >= ? AND action != 'BUY' ORDER BY timestamp ASC",
        (since_ts,),
    ).fetchall()
    conn.close()

    daily_dicts = [dict(r) for r in daily_rows]
    trade_dicts = [dict(r) for r in trade_rows]

    result = compute_regime_from_trades(trade_dicts, daily_dicts)
    weights = strategy_rotator.get_optimal_weights(result.regime, result.confidence)

    # Load current strategy config and update
    config = _load_strategy_config()
    for name in STRATEGY_NAMES:
        if name not in config:
            config[name] = True
    _save_strategy_config(config)

    # Save the weights to a separate JSON file for runtime use
    weights_config_path = os.path.join(
        os.path.dirname(__file__), "..", "strategy_weights.json"
    )
    weights_data = {
        "regime": result.regime.value,
        "confidence": result.confidence,
        "weights": weights,
        "applied_at": datetime.now().isoformat(),
    }
    with open(weights_config_path, "w", encoding="utf-8") as f:
        json.dump(weights_data, f, indent=2, ensure_ascii=False)

    return {
        "status": "applied",
        "regime": result.regime.value,
        "confidence": result.confidence,
        "weights": weights,
        "applied_at": weights_data["applied_at"],
    }


# =====================================================================
# Strategy Analysis API Endpoints
# =====================================================================

@app.get("/api/strategy-heatmap")
async def get_strategy_heatmap(period: str = Query("7d")):
    """Win rate per strategy per day as a 2D matrix.
    period: 7d, 14d, 30d, 90d
    """
    days_map = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}
    days = days_map.get(period, 7)
    conn = get_connection()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT DATE(timestamp) as trade_date, pnl, reasons FROM trades "
        "WHERE timestamp >= ? AND action != 'BUY'",
        (since,),
    ).fetchall()
    conn.close()

    # Build per-strategy-per-day win/total counters
    # {strategy: {date: {"wins": int, "total": int}}}
    heatmap_data = {name: {} for name in STRATEGY_NAMES}
    all_dates = set()

    for r in rows:
        trade_date = r["trade_date"]
        all_dates.add(trade_date)
        is_win = (r["pnl"] or 0) > 0
        try:
            reasons = json.loads(r["reasons"]) if r["reasons"] else []
        except (json.JSONDecodeError, TypeError):
            reasons = []

        matched = _parse_strategy_from_reasons(reasons, STRATEGY_NAMES)
        if not matched:
            # If no match, attribute to all strategies proportionally
            matched = STRATEGY_NAMES

        for sname in matched:
            if trade_date not in heatmap_data[sname]:
                heatmap_data[sname][trade_date] = {"wins": 0, "total": 0}
            heatmap_data[sname][trade_date]["total"] += 1
            if is_win:
                heatmap_data[sname][trade_date]["wins"] += 1

    # Sort dates
    sorted_dates = sorted(all_dates)

    # Build matrix: rows=strategies, cols=dates, values=win_rate (null if no trades)
    matrix = {}
    for sname in STRATEGY_NAMES:
        row = []
        for d in sorted_dates:
            if d in heatmap_data[sname] and heatmap_data[sname][d]["total"] > 0:
                wr = round(heatmap_data[sname][d]["wins"] / heatmap_data[sname][d]["total"] * 100, 1)
                row.append(wr)
            else:
                row.append(None)
        matrix[sname] = row

    return {"dates": sorted_dates, "strategies": STRATEGY_NAMES, "matrix": matrix}


@app.get("/api/strategy-rolling")
async def get_strategy_rolling(window: int = Query(20)):
    """Rolling win rate for each strategy over the last N trades."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT timestamp, pnl, reasons FROM trades "
        "WHERE action != 'BUY' ORDER BY timestamp ASC"
    ).fetchall()
    conn.close()

    # Collect per-strategy ordered list of (timestamp, is_win)
    strategy_trades = {name: [] for name in STRATEGY_NAMES}

    for r in rows:
        is_win = 1 if (r["pnl"] or 0) > 0 else 0
        ts = r["timestamp"]
        try:
            reasons = json.loads(r["reasons"]) if r["reasons"] else []
        except (json.JSONDecodeError, TypeError):
            reasons = []

        matched = _parse_strategy_from_reasons(reasons, STRATEGY_NAMES)
        if not matched:
            matched = STRATEGY_NAMES

        for sname in matched:
            strategy_trades[sname].append({"timestamp": ts, "win": is_win})

    # Compute rolling win rate
    result = {}
    for sname in STRATEGY_NAMES:
        trades_list = strategy_trades[sname]
        rolling = []
        for i in range(len(trades_list)):
            start = max(0, i - window + 1)
            window_slice = trades_list[start:i + 1]
            win_count = sum(t["win"] for t in window_slice)
            wr = round(win_count / len(window_slice) * 100, 1)
            rolling.append({
                "index": i,
                "timestamp": trades_list[i]["timestamp"],
                "win_rate": wr,
            })
        result[sname] = rolling

    return {"window": window, "strategies": result}


@app.post("/api/strategy/{name}/toggle")
async def toggle_strategy(name: str):
    """Enable/disable a strategy from the ensemble."""
    if name not in STRATEGY_NAMES:
        return {"error": f"Unknown strategy: {name}", "valid": STRATEGY_NAMES}

    config = _load_strategy_config()
    current = config.get(name, True)
    config[name] = not current
    _save_strategy_config(config)
    return {"strategy": name, "enabled": config[name], "config": config}


@app.get("/api/strategy-config")
async def get_strategy_config():
    """Return current strategy enable/disable states."""
    config = _load_strategy_config()
    # Ensure all strategy names are present
    for name in STRATEGY_NAMES:
        if name not in config:
            config[name] = True
    return {"config": config}


@app.get("/api/strategy-ranking")
async def get_strategy_ranking(period: str = Query("ALL")):
    """Rank strategies by Sharpe ratio with detailed metrics."""
    days_map = {"1W": 7, "1M": 30, "3M": 90, "ALL": 3650}
    days = days_map.get(period, 3650)
    conn = get_connection()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT pnl, pnl_pct, reasons FROM trades "
        "WHERE timestamp >= ? AND action != 'BUY'",
        (since,),
    ).fetchall()
    conn.close()

    config = _load_strategy_config()

    # Collect per-strategy return streams
    strategy_returns = {name: [] for name in STRATEGY_NAMES}

    for r in rows:
        pnl_pct = r["pnl_pct"] or 0
        is_win = (r["pnl"] or 0) > 0
        try:
            reasons = json.loads(r["reasons"]) if r["reasons"] else []
        except (json.JSONDecodeError, TypeError):
            reasons = []

        matched = _parse_strategy_from_reasons(reasons, STRATEGY_NAMES)
        if not matched:
            matched = STRATEGY_NAMES

        for sname in matched:
            strategy_returns[sname].append({"pnl_pct": pnl_pct, "win": is_win})

    ranking = []
    for sname in STRATEGY_NAMES:
        returns = strategy_returns[sname]
        total = len(returns)
        if total == 0:
            ranking.append({
                "strategy": sname,
                "trades": 0, "win_rate": 0, "avg_return": 0,
                "sharpe": 0, "enabled": config.get(sname, True),
            })
            continue

        wins = sum(1 for r in returns if r["win"])
        avg_ret = sum(r["pnl_pct"] for r in returns) / total
        std_ret = math.sqrt(sum((r["pnl_pct"] - avg_ret) ** 2 for r in returns) / total) if total > 1 else 0
        sharpe = round(avg_ret / std_ret, 2) if std_ret > 0 else 0

        ranking.append({
            "strategy": sname,
            "trades": total,
            "win_rate": round(wins / total * 100, 1),
            "avg_return": round(avg_ret, 2),
            "sharpe": sharpe,
            "enabled": config.get(sname, True),
        })

    # Sort by Sharpe descending
    ranking.sort(key=lambda x: x["sharpe"], reverse=True)
    return {"ranking": ranking}


# =====================================================================
# Portfolio Correlation & Risk Monitoring API Endpoints
# =====================================================================

def _get_positions_with_sector() -> dict:
    """Merge broker positions with DB positions to include sector info."""
    broker_pos = trader.client.get_positions()
    db_positions = trader.db.get_positions()
    db_map = {p["symbol"]: p for p in db_positions}

    merged = {}
    for sym, pos in broker_pos.items():
        db_p = db_map.get(sym, {})
        merged[sym] = {
            "qty": pos.get("qty", 0),
            "avg_price": pos.get("avg_price", 0),
            "name": pos.get("name", db_p.get("name", sym)),
            "sector": pos.get("sector", db_p.get("sector", "기타")),
        }
    # Also include any DB-only positions
    for p in db_positions:
        sym = p["symbol"]
        if sym not in merged and p.get("qty", 0) > 0:
            merged[sym] = {
                "qty": p.get("qty", 0),
                "avg_price": p.get("avg_price", 0),
                "name": p.get("name", sym),
                "sector": p.get("sector", "기타"),
            }
    return merged


@app.get("/api/correlation-matrix")
async def get_correlation_matrix(lookback: int = Query(20)):
    """Correlation heatmap data for held positions."""
    positions = _get_positions_with_sector()
    result = correlation_monitor.compute_correlation_matrix(positions, lookback=lookback)
    return result


@app.get("/api/sector-weights")
async def get_sector_weights():
    """Sector pie chart data."""
    positions = _get_positions_with_sector()
    exposure = correlation_monitor.get_sector_exposure(positions)
    rebalance = correlation_monitor.sector_rebalance_signal(positions)

    sectors_data = []
    for name, data in exposure["sectors"].items():
        sectors_data.append({
            "sector": name,
            "weight_pct": data["weight_pct"],
            "value": data["value"],
            "stocks": data["stocks"],
            "color": data.get("color", "#8b949e"),
        })
    sectors_data.sort(key=lambda x: x["weight_pct"], reverse=True)

    return {
        "sectors": sectors_data,
        "total_value": exposure["total_value"],
        "sector_count": exposure["sector_count"],
        "rebalance": rebalance,
    }


@app.get("/api/portfolio-risk")
async def get_portfolio_risk():
    """Diversification score + concentration risk + alerts."""
    positions = _get_positions_with_sector()
    report = correlation_monitor.get_full_risk_report(positions)
    return report


@app.get("/api/correlation-history")
async def get_correlation_history(days: int = Query(30)):
    """Historical correlation trend data."""
    history = correlation_monitor.get_correlation_history(days=days)
    return {"history": history, "days": days}


# =====================================================================
# Smart Order Execution API Endpoints
# =====================================================================

@app.get("/api/execution/stats")
async def get_execution_stats():
    """오늘의 실행 엔진 통계."""
    stats = trader.execution_engine.get_daily_stats()
    active = trader.execution_engine.get_active_orders()
    return {"stats": stats, "active_orders": active}


@app.get("/api/execution/history")
async def get_execution_history(days: int = Query(30)):
    """과거 실행 이력 및 슬리피지 분석."""
    return trader.execution_engine.get_historical(days=days)


@app.get("/api/execution/report/{order_id}")
async def get_execution_report(order_id: str):
    """개별 주문 실행 리포트."""
    report = trader.execution_engine.get_execution_report(order_id)
    if report is None:
        return {"error": "주문을 찾을 수 없습니다."}
    return report


@app.get("/api/execution/volume-profile/{symbol}")
async def get_volume_profile(symbol: str):
    """종목의 장중 거래량 프로파일."""
    return trader.execution_engine.get_volume_profile(symbol)


@app.get("/api/execution/slippage-estimate/{symbol}")
async def get_slippage_estimate(symbol: str, qty: int = Query(100)):
    """주문의 예상 슬리피지 추정."""
    return trader.execution_engine.estimate_slippage(symbol, qty)


@app.post("/api/execution/cancel/{order_id}")
async def cancel_execution(order_id: str):
    """실행 중인 주문 취소."""
    success = trader.execution_engine.cancel_order(order_id)
    return {"success": success, "order_id": order_id}


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockBot v3.5</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0a0e17; color: #c9d1d9; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #161b28, #0a0e17); padding: 16px 24px; border-bottom: 1px solid #21262d;
                   display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.4rem; color: #58a6ff; }
        .header-right { display: flex; gap: 10px; align-items: center; }
        .mode { padding: 4px 12px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
        .mode-paper { background: #1f6feb33; color: #58a6ff; border: 1px solid #1f6feb; }
        .mode-live { background: #f8514933; color: #f85149; border: 1px solid #f85149; }
        .container { max-width: 1600px; margin: 0 auto; padding: 16px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
        .grid-5 { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 14px; }
        .grid-6 { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 14px; }
        .card { background: #161b28; border: 1px solid #21262d; border-radius: 8px; padding: 14px; }
        .card h2 { color: #58a6ff; font-size: 0.9rem; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid #21262d; }
        .stat-card { text-align: center; }
        .stat-card .label { color: #8b949e; font-size: 0.75rem; margin-bottom: 4px; }
        .stat-card .value { font-size: 1.5rem; font-weight: 700; }
        .pos { color: #f85149; }
        .neg { color: #58a6ff; }
        .neu { color: #8b949e; }
        .accent { color: #58a6ff; }
        .green { color: #3fb950; }
        .yellow { color: #d29922; }
        table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
        th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid #161b28; }
        th { color: #8b949e; font-weight: 600; background: #0d1117; position: sticky; top: 0; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: 600; }
        .badge-buy { background: #23863633; color: #3fb950; }
        .badge-sell { background: #f8514933; color: #f85149; }
        .badge-hold { background: #21262d; color: #8b949e; }
        .badge-regime { padding: 3px 10px; border-radius: 6px; font-size: 0.82rem; font-weight: 700; letter-spacing: 0.5px; }
        .regime-bull { background: #23863633; color: #3fb950; border: 1px solid #238636; }
        .regime-bear { background: #f8514933; color: #f85149; border: 1px solid #f85149; }
        .regime-sideways { background: #d2992233; color: #d29922; border: 1px solid #d29922; }
        .regime-panel { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
        .regime-detail { font-size: 0.75rem; color: #8b949e; }
        .regime-detail span { color: #c9d1d9; font-weight: 600; }
        .btn { padding: 7px 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.82rem; transition: opacity 0.2s; }
        .btn:hover { opacity: 0.85; }
        .btn-start { background: #238636; color: white; }
        .btn-stop { background: #da3633; color: white; }
        .btn-scan { background: #1f6feb; color: white; }
        .btn-cycle { background: #6e40c9; color: white; }
        .btn-sm { padding: 4px 10px; font-size: 0.75rem; }
        .controls { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; align-items: center; }
        .score-bar { width: 50px; height: 6px; background: #21262d; border-radius: 3px; display: inline-block; vertical-align: middle; }
        .score-fill { height: 100%; border-radius: 3px; }
        .circuit-alert { background: #f8514915; border: 1px solid #f85149; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; display: none; }
        .circuit-alert.active { display: flex; align-items: center; gap: 10px; }
        .scroll-table { max-height: 300px; overflow-y: auto; }
        .refresh-info { color: #484f58; font-size: 0.72rem; }
        .weight-bar { display: inline-block; height: 4px; border-radius: 2px; background: #58a6ff; vertical-align: middle; margin-left: 4px; }

        /* Performance section styles */
        .perf-section { margin-bottom: 12px; }
        .perf-section .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .perf-section .section-title { color: #58a6ff; font-size: 1.1rem; font-weight: 700; }
        .period-selector { display: flex; gap: 4px; }
        .period-btn { padding: 4px 12px; border: 1px solid #21262d; border-radius: 4px; background: #0d1117;
                      color: #8b949e; cursor: pointer; font-size: 0.75rem; font-weight: 600; transition: all 0.2s; }
        .period-btn:hover { border-color: #58a6ff; color: #c9d1d9; }
        .period-btn.active { background: #1f6feb33; color: #58a6ff; border-color: #1f6feb; }
        .perf-grid { display: grid; grid-template-columns: 3fr 2fr; gap: 12px; margin-bottom: 12px; }
        .perf-right { display: grid; grid-template-rows: 1fr 1fr; gap: 12px; }
        .chart-container { position: relative; width: 100%; }
        .chart-container.large { height: 320px; }
        .chart-container.medium { height: 150px; }
        .chart-empty { display: flex; align-items: center; justify-content: center; height: 100%;
                       color: #484f58; font-size: 0.82rem; font-style: italic; }
        .perf-grid-bottom { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }

        /* Strategy Analysis section styles */
        .sa-section { margin-bottom: 12px; }
        .sa-section .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .sa-section .section-title { color: #d29922; font-size: 1.1rem; font-weight: 700; }
        .sa-grid-top { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
        .sa-grid-bottom { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }

        /* Heatmap styles */
        .heatmap-wrap { overflow-x: auto; }
        .heatmap-table { border-collapse: collapse; font-size: 0.75rem; width: 100%; }
        .heatmap-table th, .heatmap-table td { padding: 5px 8px; text-align: center; border: 1px solid #21262d; white-space: nowrap; }
        .heatmap-table th { background: #0d1117; color: #8b949e; font-weight: 600; }
        .heatmap-table td.strategy-name { text-align: left; font-weight: 600; color: #c9d1d9; background: #0d1117; min-width: 110px; }
        .heatmap-cell { min-width: 50px; font-weight: 600; border-radius: 2px; }

        /* Toggle switch styles */
        .toggle-controls { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 8px; }
        .toggle-item { display: flex; align-items: center; justify-content: space-between; background: #0d1117;
                       padding: 8px 12px; border-radius: 6px; border: 1px solid #21262d; }
        .toggle-item .name { font-size: 0.82rem; font-weight: 600; color: #c9d1d9; }
        .toggle-switch { position: relative; width: 40px; height: 22px; cursor: pointer; }
        .toggle-switch input { opacity: 0; width: 0; height: 0; }
        .toggle-slider { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: #484f58;
                         border-radius: 11px; transition: 0.3s; }
        .toggle-slider:before { content: ''; position: absolute; height: 16px; width: 16px; left: 3px; bottom: 3px;
                                background: #c9d1d9; border-radius: 50%; transition: 0.3s; }
        .toggle-switch input:checked + .toggle-slider { background: #238636; }
        .toggle-switch input:checked + .toggle-slider:before { transform: translateX(18px); }

        /* Ranking table */
        .rank-badge { display: inline-block; width: 22px; height: 22px; line-height: 22px; text-align: center;
                      border-radius: 50%; font-size: 0.72rem; font-weight: 700; }
        .rank-1 { background: #d29922; color: #0a0e17; }
        .rank-2 { background: #8b949e; color: #0a0e17; }
        .rank-3 { background: #a0522d; color: #fff; }
        .rank-n { background: #21262d; color: #8b949e; }
        .status-active { color: #3fb950; font-weight: 600; font-size: 0.75rem; }
        .status-disabled { color: #f85149; font-weight: 600; font-size: 0.75rem; }

        /* Dashboard Regime section styles */
        .regime-section { margin-bottom: 12px; }
        .regime-section .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .regime-section .section-title { color: #f97316; font-size: 1.1rem; font-weight: 700; }
        .regime-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
        .regime-badge-lg { display: inline-block; padding: 8px 20px; border-radius: 8px; font-size: 1.1rem; font-weight: 700;
                           letter-spacing: 0.5px; }
        .regime-bull-trend { background: #23863633; color: #3fb950; border: 1px solid #238636; }
        .regime-bear-trend { background: #f8514933; color: #f85149; border: 1px solid #f85149; }
        .regime-ranging { background: #d2992233; color: #d29922; border: 1px solid #d29922; }
        .regime-high-vol { background: #f9731633; color: #f97316; border: 1px solid #f97316; }
        .regime-info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
        .regime-info-item { background: #0d1117; border-radius: 6px; padding: 8px 12px; }
        .regime-info-item .info-label { font-size: 0.72rem; color: #8b949e; margin-bottom: 2px; }
        .regime-info-item .info-value { font-size: 0.9rem; font-weight: 600; color: #c9d1d9; }
        .regime-confidence-bar { width: 100%; height: 8px; background: #21262d; border-radius: 4px; margin-top: 6px; overflow: hidden; }
        .regime-confidence-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
        .weight-compare-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 0.78rem; }
        .weight-compare-row .wc-name { width: 110px; font-weight: 600; color: #c9d1d9; text-align: right; }
        .weight-compare-bars { flex: 1; display: flex; flex-direction: column; gap: 2px; }
        .weight-bar-row { display: flex; align-items: center; gap: 4px; }
        .weight-bar-label { width: 60px; font-size: 0.68rem; color: #8b949e; text-align: right; }
        .weight-bar-track { flex: 1; height: 6px; background: #21262d; border-radius: 3px; overflow: hidden; }
        .weight-bar-fill-rec { height: 100%; background: #58a6ff; border-radius: 3px; transition: width 0.5s ease; }
        .weight-bar-fill-cur { height: 100%; background: #8b949e; border-radius: 3px; transition: width 0.5s ease; }
        .weight-pct { width: 36px; font-size: 0.68rem; color: #8b949e; }
        .btn-apply { background: #f97316; color: #fff; }
        .btn-apply:hover { opacity: 0.85; }

        /* Portfolio Risk section styles */
        .pr-section { margin-bottom: 12px; }
        .pr-section .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .pr-section .section-title { color: #bc8cff; font-size: 1.1rem; font-weight: 700; }
        .pr-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
        .pr-grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 12px; }

        /* Correlation heatmap */
        .corr-heatmap-table { border-collapse: collapse; font-size: 0.75rem; width: 100%; }
        .corr-heatmap-table th, .corr-heatmap-table td { padding: 5px 8px; text-align: center; border: 1px solid #21262d; white-space: nowrap; }
        .corr-heatmap-table th { background: #0d1117; color: #8b949e; font-weight: 600; }
        .corr-heatmap-table td.stock-name { text-align: left; font-weight: 600; color: #c9d1d9; background: #0d1117; min-width: 80px; }
        .corr-cell { min-width: 45px; font-weight: 600; border-radius: 2px; font-size: 0.72rem; }

        /* Gauge display */
        .gauge-container { display: flex; flex-direction: column; align-items: center; gap: 4px; }
        .gauge-ring { position: relative; width: 140px; height: 140px; }
        .gauge-ring svg { transform: rotate(-90deg); }
        .gauge-ring .gauge-bg { fill: none; stroke: #21262d; stroke-width: 12; }
        .gauge-ring .gauge-fill { fill: none; stroke-width: 12; stroke-linecap: round; transition: stroke-dashoffset 0.8s ease; }
        .gauge-center { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; }
        .gauge-value { font-size: 1.8rem; font-weight: 700; }
        .gauge-label { font-size: 0.75rem; color: #8b949e; }

        /* Alert list */
        .alert-list { display: flex; flex-direction: column; gap: 6px; max-height: 250px; overflow-y: auto; }
        .alert-item { display: flex; align-items: flex-start; gap: 8px; padding: 8px 10px; border-radius: 6px; font-size: 0.78rem; }
        .alert-item.warning { background: #d2992215; border-left: 3px solid #d29922; }
        .alert-item.danger { background: #f8514915; border-left: 3px solid #f85149; }
        .alert-item.info { background: #58a6ff15; border-left: 3px solid #58a6ff; }
        .alert-icon { font-size: 1rem; flex-shrink: 0; }
        .alert-text { flex: 1; color: #c9d1d9; }
        .alert-time { font-size: 0.68rem; color: #484f58; white-space: nowrap; }

        /* Concentration bar */
        .conc-bar-wrap { margin-top: 8px; }
        .conc-bar-label { display: flex; justify-content: space-between; font-size: 0.72rem; color: #8b949e; margin-bottom: 3px; }
        .conc-bar-track { width: 100%; height: 10px; background: #21262d; border-radius: 5px; overflow: hidden; }
        .conc-bar-fill { height: 100%; border-radius: 5px; transition: width 0.5s ease; }

        /* Suggestion list */
        .suggestion-list { display: flex; flex-direction: column; gap: 4px; }
        .suggestion-item { padding: 6px 10px; background: #0d1117; border-radius: 4px; font-size: 0.78rem; color: #c9d1d9; border-left: 2px solid #bc8cff; }

        /* Execution Engine section styles */
        .exec-section { margin-bottom: 12px; }
        .exec-section .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .exec-section .section-title { color: #f472b6; font-size: 1.1rem; font-weight: 700; }
        .exec-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
        .exec-grid-3 { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 12px; margin-bottom: 12px; }
        .exec-stat-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 0.82rem; }
        .exec-stat-label { color: #8b949e; }
        .exec-stat-value { color: #c9d1d9; font-weight: 600; }
        .exec-quality-gauge { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 10px 0; }
        .eq-ring { position: relative; width: 120px; height: 120px; }
        .eq-ring svg { transform: rotate(-90deg); }
        .eq-ring .eq-bg { fill: none; stroke: #21262d; stroke-width: 10; }
        .eq-ring .eq-fill { fill: none; stroke-width: 10; stroke-linecap: round; transition: stroke-dashoffset 0.8s ease; }
        .eq-center { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; }
        .eq-value { font-size: 1.5rem; font-weight: 700; }
        .eq-label { font-size: 0.7rem; color: #8b949e; }
        .active-order-item { display: flex; justify-content: space-between; align-items: center;
                             padding: 8px 10px; background: #0d1117; border-radius: 6px;
                             border-left: 3px solid #f472b6; margin-bottom: 6px; font-size: 0.78rem; }
        .active-order-item .ao-symbol { font-weight: 700; color: #c9d1d9; }
        .active-order-item .ao-type { color: #f472b6; font-weight: 600; font-size: 0.72rem; }
        .active-order-item .ao-progress { color: #8b949e; }
        .ao-bar { width: 80px; height: 5px; background: #21262d; border-radius: 3px; overflow: hidden; display: inline-block; vertical-align: middle; margin-left: 4px; }
        .ao-bar-fill { height: 100%; background: #f472b6; border-radius: 3px; transition: width 0.3s; }
        .vp-bar-row { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; font-size: 0.72rem; }
        .vp-label { width: 40px; color: #8b949e; text-align: right; flex-shrink: 0; }
        .vp-bar { flex: 1; height: 14px; background: #21262d; border-radius: 3px; overflow: hidden; }
        .vp-bar-fill { height: 100%; background: linear-gradient(90deg, #f472b6, #a855f7); border-radius: 3px; transition: width 0.5s; }
        .vp-pct { width: 36px; color: #8b949e; font-size: 0.68rem; }

        @media (max-width: 900px) {
            .grid-2 { grid-template-columns: 1fr; }
            .perf-grid { grid-template-columns: 1fr; }
            .perf-right { grid-template-rows: auto auto; }
            .perf-grid-bottom { grid-template-columns: 1fr; }
            .sa-grid-top { grid-template-columns: 1fr; }
            .sa-grid-bottom { grid-template-columns: 1fr; }
            .regime-grid { grid-template-columns: 1fr; }
            .pr-grid { grid-template-columns: 1fr; }
            .pr-grid-3 { grid-template-columns: 1fr; }
            .exec-grid { grid-template-columns: 1fr; }
            .exec-grid-3 { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div style="display:flex;align-items:center;gap:10px">
            <h1>StockBot v3.5</h1>
            <button onclick="document.getElementById('glossaryModal').style.display='flex'" style="background:#1f6feb33;color:#58a6ff;border:1px solid #1f6feb;border-radius:50%;width:28px;height:28px;cursor:pointer;font-weight:700;font-size:0.9rem" title="주식 용어 사전">?</button>
        </div>
        <div class="header-right">
            <a href="/backtest" style="color:#58a6ff;text-decoration:none;font-size:0.85rem;padding:4px 12px;border:1px solid #1f6feb;border-radius:6px;margin-right:10px;">\ubc31\ud14c\uc2a4\ud2b8</a>
            <span class="refresh-info" id="lastUpdate">-</span>
            <span class="mode mode-paper" id="modeTag">\ub85c\ub529 \uc911...</span>
        </div>
    </div>
    <div class="container">
        <div class="circuit-alert" id="circuitAlert">
            <span style="font-size:1.2rem">&#x1F6A8;</span>
            <div><b>\uc11c\ud0b7\ube0c\ub808\uc774\ucee4</b> <span id="cbReason"></span>
            <button class="btn btn-sm btn-stop" onclick="resetCB()" style="margin-left:8px">\ucd08\uae30\ud654</button></div>
        </div>
        <div class="controls">
            <button class="btn btn-start" onclick="startBot()">\uc790\ub3d9\ub9e4\ub9e4 \uc2dc\uc791</button>
            <button class="btn btn-stop" onclick="stopBot()">\uc911\uc9c0</button>
            <button class="btn btn-scan" onclick="scanAll()">\uc885\ubaa9 \uc2a4\uce94</button>
            <button class="btn btn-cycle" onclick="runCycle()">1\ud68c \uc2e4\ud589</button>
            <span id="schedInfo" class="refresh-info" style="margin-left:auto"></span>
        </div>
        <div class="card" style="margin-bottom:12px">
            <h2>\uc2dc\uc7a5 \uad6d\uba74</h2>
            <div class="regime-panel">
                <span class="badge-regime regime-sideways" id="regimeBadge">SIDEWAYS</span>
                <div class="regime-detail" title="&#xcd94;&#xc138; &#xac15;&#xb3c4; &#xc9c0;&#xd45c;. 25&#xc774;&#xc0c1;=&#xb73b;&#xb837;&#xd55c; &#xcd94;&#xc138;, 50&#xc774;&#xc0c1;=&#xb9e4;&#xc6b0; &#xac15;&#xd55c; &#xcd94;&#xc138;">ADX: <span id="regimeADX">-</span></div>
                <div class="regime-detail" title="&#xac00;&#xaca9; &#xbcc0;&#xb3d9; &#xd3ed;. &#xb192;&#xc744;&#xc218;&#xb85d; &#xac00;&#xaca9;&#xc774; &#xb9ce;&#xc774; &#xc624;&#xb974;&#xb0b4;&#xb9b4;">&#xbcc0;&#xb3d9;&#xc131;: <span id="regimeVol">-</span></div>
                <div class="regime-detail" title="&#xcd5c;&#xadfc; 20&#xac70;&#xb798;&#xc77c;&#xac04; &#xc8fc;&#xac00; &#xc0c1;&#xc2b9;/&#xd558;&#xb77d; &#xbe44;&#xc728;">20&#xc77c; &#xc218;&#xc775;&#xb960;: <span id="regimeReturn">-</span></div>
                <div class="regime-detail" title="&#xd604;&#xc7ac; &#xc8fc;&#xac00;&#xc640; 50&#xc77c; &#xc774;&#xb3d9;&#xd3c9;&#xade0;&#xc758; &#xcc28;&#xc774;. +&#xba74; &#xd3c9;&#xade0; &#xc704;(&#xac15;&#xc138;)">MA &#xad34;&#xb9ac;: <span id="regimeMaDiff">-</span></div>
                <div class="regime-detail" id="regimeSince" style="margin-left:auto"></div>
            </div>
            <div id="regimeWeights" style="margin-top:10px;font-size:0.75rem;color:#8b949e"></div>
        </div>
        <div class="grid-6">
            <div class="card stat-card" title="&#xd604;&#xae08; + &#xc8fc;&#xc2dd; &#xd3c9;&#xac00;&#xc561;&#xc758; &#xd569;&#xacc4;"><div class="label">&#xcd1d; &#xc790;&#xc0b0; &#x24d8;</div><div class="value accent" id="totalAssets">-</div></div>
            <div class="card stat-card" title="&#xd604;&#xc7ac; &#xb9e4;&#xc218;&#xc5d0; &#xc0ac;&#xc6a9; &#xac00;&#xb2a5;&#xd55c; &#xd604;&#xae08;"><div class="label">&#xd604;&#xae08; &#x24d8;</div><div class="value" id="cash">-</div></div>
            <div class="card stat-card" title="&#xcd08;&#xae30; &#xc790;&#xbcf8; &#xb300;&#xbe44; &#xc5bc;&#xb9c8;&#xb098; &#xbc8c;&#xc5c8;&#xb294;&#xc9c0;(+) &#xb610;&#xb294; &#xc78e;&#xc5c8;&#xb294;&#xc9c0;(-)"><div class="label">&#xb204;&#xc801; &#xc190;&#xc775; &#x24d8;</div><div class="value" id="totalPnl">-</div></div>
            <div class="card stat-card" title="&#xd604;&#xc7ac; &#xbcf4;&#xc720; &#xc911;&#xc778; &#xc8fc;&#xc2dd; &#xc885;&#xbaa9; &#xc218; (&#xcd5c;&#xb300; 4&#xac1c;)"><div class="label">&#xbcf4;&#xc720; &#xc885;&#xbaa9; &#x24d8;</div><div class="value" id="posCount">0</div></div>
            <div class="card stat-card" title="&#xcd5c;&#xadfc; 30&#xc77c;&#xac04; &#xb9e4;&#xb3c4; &#xc911; &#xc218;&#xc775;&#xc73c;&#xb85c; &#xb05d;&#xb09c; &#xbe44;&#xc728;. 50% &#xc774;&#xc0c1;&#xc774;&#xba74; &#xc591;&#xd638;"><div class="label">&#xc2b9;&#xb960; (30&#xc77c;) &#x24d8;</div><div class="value green" id="winRate">-</div></div>
            <div class="card stat-card" title="&#xd604;&#xc7ac; &#xc2dc;&#xc7a5; &#xc0c1;&#xd0dc;. &#xac15;&#xc138;=&#xc0c1;&#xc2b9;&#xc7a5;, &#xc57d;&#xc138;=&#xd558;&#xb77d;&#xc7a5;, &#xd69f;&#xbcf4;=&#xbc29;&#xd5a5; &#xc5c6;&#xc74c;"><div class="label">&#xad6d;&#xba74; &#x24d8;</div><div class="value" id="regimeStat">-</div></div>
        </div>

        <!-- Performance Charts Section -->
        <div class="perf-section">
            <div class="section-header">
                <span class="section-title">\uc131\uacfc \ucc28\ud2b8</span>
                <div class="period-selector">
                    <button class="period-btn" data-period="1W" onclick="setPeriod('1W')">1W</button>
                    <button class="period-btn" data-period="1M" onclick="setPeriod('1M')">1M</button>
                    <button class="period-btn" data-period="3M" onclick="setPeriod('3M')">3M</button>
                    <button class="period-btn active" data-period="ALL" onclick="setPeriod('ALL')">ALL</button>
                </div>
            </div>
            <div class="perf-grid">
                <div class="card">
                    <h2 title="시간에 따른 총 자산(현금+주식) 변화 그래프. 빨간 영역은 낙폭(MDD: 최고점 대비 하락폭)">\uc790\uc0b0 \uace1\uc120 \u24d8</h2>
                    <div class="chart-container large">
                        <canvas id="equityChart"></canvas>
                        <div class="chart-empty" id="equityEmpty">\uc790\uc0b0 \ub370\uc774\ud130 \uc5c6\uc74c</div>
                    </div>
                </div>
                <div class="perf-right">
                    <div class="card">
                        <h2 title="날짜별 수익/손실 금액. 초록=수익, 빨강=손실">\uc77c\ubcc4 \uc190\uc775 \u24d8</h2>
                        <div class="chart-container medium">
                            <canvas id="dailyPnlChart"></canvas>
                            <div class="chart-empty" id="pnlEmpty">\uac70\ub798 \ub370\uc774\ud130 \uc5c6\uc74c</div>
                        </div>
                    </div>
                    <div class="card">
                        <h2 title="각 전략(볼린저, RSI, MACD 등)이 전체 수익에 기여한 비율">\uc804\ub7b5 \uc2b9\ub960 \uae30\uc5ec \u24d8</h2>
                        <div class="chart-container medium">
                            <canvas id="strategyChart"></canvas>
                            <div class="chart-empty" id="strategyEmpty">\uc804\ub7b5 \ub370\uc774\ud130 \uc5c6\uc74c</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="perf-grid-bottom">
                <div class="card">
                    <h2 title="각 거래의 수익률 분포. 대부분 0% 근처에 모이면 안정적, 넓게 퍼지면 변동성이 큰 매매">\uac70\ub798 \uc218\uc775\ub960 \ubd84\ud3ec \u24d8</h2>
                    <div class="chart-container" style="height:200px">
                        <canvas id="distChart"></canvas>
                        <div class="chart-empty" id="distEmpty">\uac70\ub798 \ub370\uc774\ud130 \uc5c6\uc74c</div>
                    </div>
                </div>
                <div class="card">
                    <h2 title="8개 전략(볼린저, RSI, MACD 등) 각각의 승률 비교">\uc804\ub7b5\ubcc4 \uc2b9\ub960 \u24d8</h2>
                    <div class="scroll-table" id="strategyTable">
                        <p class="neu">\uc804\ub7b5 \ub370\uc774\ud130 \ub85c\ub529 \uc911...</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Strategy Analysis Section -->
        <div class="sa-section">
            <div class="section-header">
                <span class="section-title">\uc804\ub7b5 \ubd84\uc11d</span>
                <div class="period-selector">
                    <button class="period-btn sa-period-btn" data-sa-period="7d" onclick="setSAPeriod('7d')">7D</button>
                    <button class="period-btn sa-period-btn active" data-sa-period="14d" onclick="setSAPeriod('14d')">14D</button>
                    <button class="period-btn sa-period-btn" data-sa-period="30d" onclick="setSAPeriod('30d')">30D</button>
                    <button class="period-btn sa-period-btn" data-sa-period="90d" onclick="setSAPeriod('90d')">90D</button>
                </div>
            </div>
            <div class="sa-grid-top">
                <div class="card">
                    <h2 title="날짜별로 각 전략의 승/패를 색상으로 표시. 초록=승, 빨강=패">\uc804\ub7b5 \ud788\ud2b8\ub9f5 (\uc77c\ubcc4 \uc2b9\ub960) \u24d8</h2>
                    <div class="heatmap-wrap" id="strategyHeatmap">
                        <p class="neu">\ud788\ud2b8\ub9f5 \ub370\uc774\ud130 \ub85c\ub529 \uc911...</p>
                    </div>
                </div>
                <div class="card">
                    <h2 title="최근 거래 기준 이동 승률. 추세가 올라가면 전략이 잘 맞는 중">\ub864\ub9c1 \uc2b9\ub960 (\ucd5c\uadfc N\uac74) \u24d8</h2>
                    <div class="chart-container large">
                        <canvas id="rollingChart"></canvas>
                        <div class="chart-empty" id="rollingEmpty">\ub864\ub9c1 \ub370\uc774\ud130 \uc5c6\uc74c</div>
                    </div>
                </div>
            </div>
            <div class="sa-grid-bottom">
                <div class="card">
                    <h2 title="각 전략을 켜거나 끌 수 있는 설정. 특정 전략이 계속 지면 끄기 가능">\uc804\ub7b5 \ud1a0\uae00 \uc124\uc815 \u24d8</h2>
                    <div class="toggle-controls" id="strategyToggles">
                        <p class="neu">\uc804\ub7b5 \uc124\uc815 \ub85c\ub529 \uc911...</p>
                    </div>
                </div>
                <div class="card">
                    <h2 title="샤프 비율(위험 대비 수익률) 기준 전략 순위. 1이상 양호, 2이상 우수">\uc804\ub7b5 \ub7ad\ud0b9 (\uc0e4\ud504 \ube44\uc728) \u24d8</h2>
                    <div class="scroll-table" id="strategyRanking">
                        <p class="neu">\ub7ad\ud0b9 \ub370\uc774\ud130 \ub85c\ub529 \uc911...</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Market Regime Detection Section -->
        <div class="regime-section">
            <div class="section-header">
                <span class="section-title">\uc2dc\uc7a5 \uad6d\uba74 \uac10\uc9c0</span>
                <button class="btn btn-apply" onclick="applyRegimeWeights()">\uac00\uc911\uce58 \uc801\uc6a9</button>
            </div>
            <div class="regime-grid">
                <div class="card">
                    <h2>\ud604\uc7ac \uad6d\uba74</h2>
                    <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
                        <span class="regime-badge-lg regime-ranging" id="dashRegimeBadge">RANGING</span>
                        <div style="flex:1;min-width:120px">
                            <div style="font-size:0.78rem;color:#8b949e">\uc2e0\ub8b0\ub3c4</div>
                            <div style="font-size:1.3rem;font-weight:700" id="dashRegimeConf">0%</div>
                            <div class="regime-confidence-bar">
                                <div class="regime-confidence-fill" id="dashRegimeConfBar" style="width:0%;background:#d29922"></div>
                            </div>
                        </div>
                    </div>
                    <div class="regime-info-grid" id="dashRegimeIndicators">
                        <div class="regime-info-item"><div class="info-label">20\uc77c \uc218\uc775\ub960</div><div class="info-value" id="drInd20dRet">-</div></div>
                        <div class="regime-info-item"><div class="info-label">\ucd5c\uadfc \ubcc0\ub3d9\uc131</div><div class="info-value" id="drIndRecentVol">-</div></div>
                        <div class="regime-info-item"><div class="info-label">\ubcc0\ub3d9\uc131 Z\uc810\uc218</div><div class="info-value" id="drIndVolZ">-</div></div>
                        <div class="regime-info-item"><div class="info-label">\uac00\uaca9 vs MA50</div><div class="info-value" id="drIndPriceMa">-</div></div>
                    </div>
                </div>
                <div class="card">
                    <h2 title="최근 30일간 시장 국면(강세/약세/횡보) 변화 추이">\uad6d\uba74 \ud0c0\uc784\ub77c\uc778 (30\uc77c) \u24d8</h2>
                    <div class="chart-container" style="height:180px">
                        <canvas id="regimeTimelineChart"></canvas>
                        <div class="chart-empty" id="regimeTimelineEmpty">\uad6d\uba74 \uc774\ub825 \ub370\uc774\ud130 \uc5c6\uc74c</div>
                    </div>
                </div>
            </div>
            <div class="regime-grid">
                <div class="card">
                    <h2 title="현재 시장 국면에 따라 AI가 추천하는 전략 가중치와 현재 설정 비교">\uad8c\uc7a5 vs \ud604\uc7ac \uac00\uc911\uce58 \u24d8</h2>
                    <div id="weightCompareContainer">
                        <p class="neu">\uac00\uc911\uce58 \ube44\uad50 \ub85c\ub529 \uc911...</p>
                    </div>
                </div>
                <div class="card">
                    <h2>\uad6d\uba74 \uc774\ub825 \ub85c\uadf8</h2>
                    <div class="scroll-table" id="regimeHistoryLog" style="max-height:250px">
                        <p class="neu">\uad6d\uba74 \uc774\ub825 \ub85c\ub529 \uc911...</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Portfolio Risk Section -->
        <div class="pr-section">
            <div class="section-header">
                <span class="section-title">\ud3ec\ud2b8\ud3f4\ub9ac\uc624 \ub9ac\uc2a4\ud06c</span>
                <span class="refresh-info" id="prLastUpdate">-</span>
            </div>
            <div class="pr-grid">
                <div class="card">
                    <h2 title="보유 종목 간 가격 상관관계. 빨간색(높은 상관)이 많으면 위험 분산이 안 됨">\uc0c1\uad00\uad00\uacc4 \ud788\ud2b8\ub9f5 \u24d8</h2>
                    <div class="heatmap-wrap" id="corrHeatmap">
                        <p class="neu">\ubcf4\uc720 \uc885\ubaa9 \ub370\uc774\ud130 \ub85c\ub529 \uc911...</p>
                    </div>
                    <div style="margin-top:8px;font-size:0.78rem;color:#8b949e">
                        \ud3c9\uade0 \uc0c1\uad00\uacc4\uc218: <span id="prAvgCorr" style="font-weight:700;color:#c9d1d9">-</span>
                        <span id="prCorrSpike" style="margin-left:12px"></span>
                    </div>
                </div>
                <div class="card">
                    <h2 title="보유 종목의 산업 분야(반도체/금융/자동차 등) 비중. 한 섹터에 쏠리면 위험">\uc139\ud130 \ubc30\ubd84 \ud604\ud669 \u24d8</h2>
                    <div class="chart-container" style="height:240px">
                        <canvas id="sectorPieChart"></canvas>
                        <div class="chart-empty" id="sectorPieEmpty">\ubcf4\uc720 \uc885\ubaa9 \uc5c6\uc74c</div>
                    </div>
                </div>
            </div>
            <div class="pr-grid-3">
                <div class="card">
                    <h2 title="포트폴리오가 얼마나 잘 분산되었는지 점수. 100에 가까울수록 잘 분산됨">\ubd84\uc0b0\ud22c\uc790 \uc810\uc218 \u24d8</h2>
                    <div class="gauge-container">
                        <div class="gauge-ring">
                            <svg width="140" height="140" viewBox="0 0 140 140">
                                <circle class="gauge-bg" cx="70" cy="70" r="58" />
                                <circle class="gauge-fill" id="divGaugeFill" cx="70" cy="70" r="58"
                                    stroke="#bc8cff" stroke-dasharray="364.42" stroke-dashoffset="364.42" />
                            </svg>
                            <div class="gauge-center">
                                <div class="gauge-value" id="divScoreValue">-</div>
                                <div class="gauge-label" id="divScoreGrade">-</div>
                            </div>
                        </div>
                        <div id="divScoreComponents" style="font-size:0.72rem;color:#8b949e;text-align:center;margin-top:4px"></div>
                    </div>
                </div>
                <div class="card">
                    <h2 title="HHI(허핀달-허쉬만 지수): 포트폴리오 집중도. 높을수록 한 종목에 쏠려 위험">\uc9d1\uc911\ub3c4 \ub9ac\uc2a4\ud06c (HHI) \u24d8</h2>
                    <div style="text-align:center;padding-top:10px">
                        <div style="font-size:2rem;font-weight:700" id="hhiValue">-</div>
                        <div style="font-size:0.82rem;margin-top:2px" id="hhiLevel">-</div>
                        <div class="conc-bar-wrap" style="margin-top:12px">
                            <div class="conc-bar-label">
                                <span>\ub0ae\uc74c</span>
                                <span>\ubcf4\ud1b5</span>
                                <span>\ub192\uc74c</span>
                                <span>\ub9e4\uc6b0 \ub192\uc74c</span>
                            </div>
                            <div class="conc-bar-track">
                                <div class="conc-bar-fill" id="hhiBar" style="width:0%;background:#3fb950"></div>
                            </div>
                        </div>
                        <div id="topPositions" style="margin-top:12px;text-align:left;font-size:0.75rem"></div>
                    </div>
                </div>
                <div class="card">
                    <h2>\uacbd\uace0 / \uc54c\ub9bc</h2>
                    <div class="alert-list" id="prAlerts">
                        <p class="neu">\ud65c\uc131 \uacbd\uace0 \uc5c6\uc74c</p>
                    </div>
                    <div style="margin-top:12px">
                        <h2 style="font-size:0.82rem;margin-bottom:6px">\ub9ac\ubc38\ub7f0\uc2f1 \uc81c\uc548</h2>
                        <div class="suggestion-list" id="prSuggestions">
                            <p class="neu" style="font-size:0.75rem">\uc81c\uc548 \uc5c6\uc74c</p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="pr-grid">
                <div class="card">
                    <h2>\uc0c1\uad00\uad00\uacc4 \ucd94\uc138</h2>
                    <div class="chart-container" style="height:200px">
                        <canvas id="corrTrendChart"></canvas>
                        <div class="chart-empty" id="corrTrendEmpty">\ucd94\uc138 \ub370\uc774\ud130 \uc5c6\uc74c</div>
                    </div>
                </div>
                <div class="card">
                    <h2>\ubd84\uc0b0\ud22c\uc790 \uc810\uc218 \ucd94\uc138</h2>
                    <div class="chart-container" style="height:200px">
                        <canvas id="divTrendChart"></canvas>
                        <div class="chart-empty" id="divTrendEmpty">\ucd94\uc138 \ub370\uc774\ud130 \uc5c6\uc74c</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Smart Order Execution Section -->
        <div class="exec-section">
            <div class="section-header">
                <span class="section-title">\uc8fc\ubb38 \uc2e4\ud589</span>
                <span class="refresh-info" id="execLastUpdate">-</span>
            </div>
            <div class="grid-6">
                <div class="card stat-card">
                    <div class="label">\uc624\ub298 \uc8fc\ubb38</div>
                    <div class="value accent" id="execTotalOrders">0</div>
                </div>
                <div class="card stat-card">
                    <div class="label">\uccb4\uacb0 \uc644\ub8cc</div>
                    <div class="value green" id="execFilledOrders">0</div>
                </div>
                <div class="card stat-card">
                    <div class="label">\uc2e4\ud328</div>
                    <div class="value pos" id="execFailedOrders">0</div>
                </div>
                <div class="card stat-card">
                    <div class="label">\ud3c9\uade0 \uc2ac\ub9ac\ud53c\uc9c0</div>
                    <div class="value" id="execAvgSlippage">0bp</div>
                </div>
                <div class="card stat-card">
                    <div class="label">\uccb4\uacb0 \ubb3c\ub7c9</div>
                    <div class="value accent" id="execTotalVolume">0</div>
                </div>
                <div class="card stat-card">
                    <div class="label">\ud65c\uc131 \uc8fc\ubb38</div>
                    <div class="value yellow" id="execActiveOrders">0</div>
                </div>
            </div>
            <div class="exec-grid-3">
                <div class="card">
                    <h2>\ud65c\uc131 \uc8fc\ubb38 \ubaa9\ub85d</h2>
                    <div id="execActiveList" style="max-height:280px;overflow-y:auto">
                        <p class="neu" style="font-size:0.82rem">\ud65c\uc131 \uc8fc\ubb38 \uc5c6\uc74c</p>
                    </div>
                </div>
                <div class="card">
                    <h2 title="주문 실행의 전체적인 품질 점수. 체결률과 슬리피지를 종합 평가">\uc2e4\ud589 \ud488\uc9c8 \uac8c\uc774\uc9c0 \u24d8</h2>
                    <div class="exec-quality-gauge">
                        <div class="eq-ring">
                            <svg width="120" height="120" viewBox="0 0 120 120">
                                <circle class="eq-bg" cx="60" cy="60" r="50" />
                                <circle class="eq-fill" id="eqGaugeFill" cx="60" cy="60" r="50"
                                    stroke="#f472b6" stroke-dasharray="314.16" stroke-dashoffset="314.16" />
                            </svg>
                            <div class="eq-center">
                                <div class="eq-value" id="eqGaugeValue">-</div>
                                <div class="eq-label">\uccb4\uacb0\ub960</div>
                            </div>
                        </div>
                        <div style="width:100%;margin-top:8px">
                            <div class="exec-stat-row" title="주문이 실제로 체결된 비율. 100%면 모든 주문이 성공">
                                <span class="exec-stat-label">\uccb4\uacb0\ub960</span>
                                <span class="exec-stat-value" id="eqFillRate">-</span>
                            </div>
                            <div class="exec-stat-row" title="슬리피지: 주문 가격과 실제 체결 가격의 차이. 낮을수록 좋음">
                                <span class="exec-stat-label">\ud3c9\uade0 \uc2ac\ub9ac\ud53c\uc9c0</span>
                                <span class="exec-stat-value" id="eqAvgSlip">-</span>
                            </div>
                            <div class="exec-stat-row" title="가장 유리했던 슬리피지 (가장 좋은 가격에 체결)">
                                <span class="exec-stat-label">\ucd5c\uc120 \uc2ac\ub9ac\ud53c\uc9c0</span>
                                <span class="exec-stat-value" id="eqBestSlip">-</span>
                            </div>
                            <div class="exec-stat-row" title="가장 불리했던 슬리피지 (가장 나쁜 가격에 체결)">
                                <span class="exec-stat-label">\ucd5c\uc545 \uc2ac\ub9ac\ud53c\uc9c0</span>
                                <span class="exec-stat-value" id="eqWorstSlip">-</span>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <h2>\uac70\ub798\ub7c9 \ud504\ub85c\ud544</h2>
                    <div id="execVolumeProfile" style="max-height:280px;overflow-y:auto">
                        <p class="neu" style="font-size:0.82rem">\uc885\ubaa9 \uc120\ud0dd \uc2dc \ud45c\uc2dc</p>
                    </div>
                    <div style="margin-top:8px">
                        <select id="vpSymbolSelect" style="background:#0d1117;color:#c9d1d9;border:1px solid #21262d;border-radius:4px;padding:4px 8px;font-size:0.78rem;width:100%">
                            <option value="">\uc885\ubaa9 \uc120\ud0dd...</option>
                        </select>
                    </div>
                </div>
            </div>
            <div class="exec-grid">
                <div class="card">
                    <h2 title="슬리피지: 주문가격과 체결가격의 차이. 0에 가까울수록 좋음">\uc2ac\ub9ac\ud53c\uc9c0 \ubd84\ud3ec (30\uc77c) \u24d8</h2>
                    <div class="chart-container" style="height:200px">
                        <canvas id="slippageHistChart"></canvas>
                        <div class="chart-empty" id="slippageHistEmpty">\ub370\uc774\ud130 \uc5c6\uc74c</div>
                    </div>
                </div>
                <div class="card">
                    <h2>\uc77c\ubcc4 \uc2e4\ud589 \ud1b5\uacc4</h2>
                    <div class="scroll-table" style="max-height:200px">
                        <table>
                            <thead><tr><th>\ub0a0\uc9dc</th><th>\uc8fc\ubb38</th><th>\uccb4\uacb0</th><th>\uc2e4\ud328</th><th>\ud3c9\uade0 \uc2ac\ub9ac\ud53c\uc9c0</th><th>\uccb4\uacb0\ub960</th></tr></thead>
                            <tbody id="execDailyTable">
                                <tr><td colspan="6" class="neu">\ub370\uc774\ud130 \ub85c\ub529 \uc911...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div class="grid-2">
            <div class="card">
                <h2>\uad00\uc2ec\uc885\ubaa9 \ubd84\uc11d</h2>
                <div class="scroll-table">
                <table><thead><tr><th>\uc885\ubaa9</th><th title="5\uac1c \uc804\ub7b5\uc758 \uac00\uc911 \ud3c9\uade0 \uc810\uc218. 58\uc774\uc0c1=\ub9e4\uc218, 42\uc774\ud558=\ub9e4\ub3c4">\uc810\uc218 \u24d8</th><th>\uc2e0\ud638</th><th>\uac00\uaca9</th><th title="\ub9ce\uc774 \ube60\uc9c4 \uac74 \ub2e4\uc2dc \uc624\ub974\uace0, \ub9ce\uc774 \uc624\ub978 \uac74 \ube60\uc9c4\ub2e4\ub294 \uc6d0\ub9ac. RSI\uc640 \ubcfc\ub9b0\uc800\ubc34\ub4dc \uae30\ubc18">\ud3c9\uade0\ud68c\uadc0 \u24d8</th><th title="\uc624\ub974\ub294 \uc8fc\uc2dd\uc740 \uacc4\uc18d \uc624\ub978\ub2e4\ub294 \uc6d0\ub9ac. MACD\uc640 \uc774\ub3d9\ud3c9\uade0\uc120 \ubc30\uc5f4 \uae30\ubc18">\ucd94\uc138 \u24d8</th><th title="\ud55c\uad6d \uc2dc\uc7a5 \ud2b9\uc131 \ubc18\uc601. \ucd5c\uadfc \uae09\ub4f1\uc8fc\ub294 \ub2e8\uae30 \ud558\ub77d \uac00\ub2a5\uc131 \ud3c9\uac00">\ubaa8\uba58\ud140 \u24d8</th><th title="\uac70\ub798\ub7c9\uc774 \ud3c9\uc18c\ubcf4\ub2e4 \ub9ce\uc73c\uba74\uc11c \uc0c1\uc2b9\ud558\uba74 \uae0d\uc815\uc801">\uac70\ub798\ub7c9 \u24d8</th><th title="\uac00\uaca9 \ubcc0\ub3d9 \ud3ed\uc774 \uc904\uc5b4\ub4e4\uba74 \uc548\uc815\uc801(\uae0d\uc815), \ub298\uc5b4\ub098\uba74 \ubd88\uc548\uc815(\ubd80\uc815)">\ubcc0\ub3d9\uc131 \u24d8</th><th>\uc0ac\uc720</th></tr></thead>
                <tbody id="scanResults"><tr><td colspan="10" class="neu">"\uc885\ubaa9 \uc2a4\uce94" \ubc84\ud2bc\uc744 \ud074\ub9ad\ud558\uc138\uc694</td></tr></tbody></table>
                </div>
            </div>
            <div class="card">
                <h2>\ubcf4\uc720 \uc885\ubaa9</h2>
                <div class="scroll-table" id="positions"><p class="neu">\ubcf4\uc720 \uc885\ubaa9 \uc5c6\uc74c</p></div>
            </div>
        </div>
        <div class="grid-2">
            <div class="card">
                <h2>\ucd5c\uadfc \uac70\ub798</h2>
                <div class="scroll-table">
                <table><thead><tr><th>\uc2dc\uac04</th><th>\uc720\ud615</th><th>\uc885\ubaa9</th><th>\uc218\ub7c9</th><th>\uac00\uaca9</th><th>\uc190\uc775</th></tr></thead>
                <tbody id="recentTrades"></tbody></table>
                </div>
            </div>
            <div class="card">
                <h2>\uac70\ub798 \ud1b5\uacc4</h2>
                <div id="tradeStats" class="neu">\ub85c\ub529 \uc911...</div>
            </div>
        </div>
    </div>
    <script>
        const fmt = n => n ? n.toLocaleString('ko-KR') : '0';
        const fmtW = n => { if(!n) return '0'; if(Math.abs(n)>=1e8) return (n/1e8).toFixed(1)+'\uc5b5'; if(Math.abs(n)>=1e4) return (n/1e4).toFixed(0)+'\ub9cc'; return fmt(n); };

        /* ========== Shared Regime Labels & CSS Map ========== */
        const REGIME_LABELS = {
            'BULL': '\uac15\uc138(\uc0c1\uc2b9\uc7a5)',
            'BEAR': '\uc57d\uc138(\ud558\ub77d\uc7a5)',
            'SIDEWAYS': '\ud6a1\ubcf4(\ubcf4\ud569\uc7a5)',
            'BULL_TREND': '\uac15\uc138 \ucd94\uc138',
            'BEAR_TREND': '\uc57d\uc138 \ucd94\uc138',
            'RANGING': '\ud6a1\ubcf4(\ubcf4\ud569\uc7a5)',
            'HIGH_VOLATILITY': '\uace0\ubcc0\ub3d9\uc131',
        };
        const REGIME_CLASS_MAP = {
            'BULL': 'regime-bull',
            'BEAR': 'regime-bear',
            'SIDEWAYS': 'regime-sideways',
            'BULL_TREND': 'regime-bull-trend',
            'BEAR_TREND': 'regime-bear-trend',
            'RANGING': 'regime-ranging',
            'HIGH_VOLATILITY': 'regime-high-vol',
        };

        /* ========== HTML escape helper (XSS prevention) ========== */
        function escapeHtml(str) {
            if (!str) return '';
            return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
        }

        /* ========== Toast notification ========== */
        function showToast(message, type) {
            const toast = document.createElement('div');
            const bg = type === 'success' ? '#238636' : type === 'error' ? '#da3633' : '#1f6feb';
            toast.style.cssText = 'position:fixed;top:20px;right:20px;padding:12px 20px;border-radius:8px;color:#fff;font-size:0.85rem;font-weight:600;z-index:9999;transition:opacity 0.5s;background:' + bg;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => { toast.style.opacity = '0'; }, 2500);
            setTimeout(() => { toast.remove(); }, 3000);
        }

        /* ========== Chart.js global defaults for dark theme ========== */
        Chart.defaults.color = '#8b949e';
        Chart.defaults.borderColor = '#21262d';
        Chart.defaults.font.family = "'Segoe UI', sans-serif";
        Chart.defaults.font.size = 11;

        /* ========== Chart instances ========== */
        let equityChartInst = null;
        let dailyPnlChartInst = null;
        let strategyChartInst = null;
        let distChartInst = null;
        let currentPeriod = 'ALL';

        /* ========== Period selector ========== */
        function setPeriod(period) {
            currentPeriod = period;
            document.querySelectorAll('.period-btn[data-period]').forEach(b => {
                b.classList.toggle('active', b.dataset.period === period);
            });
            loadAllCharts();
            loadStrategyRanking();
        }

        /* ========== Equity Curve Chart ========== */
        async function loadEquityChart() {
            try {
                const r = await fetch('/api/equity-curve?period=' + currentPeriod);
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const d = await r.json();
                const data = d.data || [];
                const emptyEl = document.getElementById('equityEmpty');
                const canvas = document.getElementById('equityChart');

                if (!data.length) {
                    emptyEl.style.display = 'flex';
                    canvas.style.display = 'none';
                    if (equityChartInst) { equityChartInst.destroy(); equityChartInst = null; }
                    return;
                }
                emptyEl.style.display = 'none';
                canvas.style.display = 'block';

                const labels = data.map(d => d.date);
                const pnlData = data.map(d => d.pnl);
                const ddData = data.map(d => d.drawdown);

                if (equityChartInst) equityChartInst.destroy();
                equityChartInst = new Chart(canvas, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: '\ub204\uc801 \uc190\uc775',
                                data: pnlData,
                                borderColor: '#58a6ff',
                                backgroundColor: 'rgba(88,166,255,0.08)',
                                fill: true,
                                tension: 0.3,
                                pointRadius: data.length > 60 ? 0 : 2,
                                pointHoverRadius: 4,
                                borderWidth: 2,
                                yAxisID: 'y',
                            },
                            {
                                label: '\ub0a8\ud3ed %',
                                data: ddData,
                                borderColor: '#f8514988',
                                backgroundColor: 'rgba(248,81,73,0.12)',
                                fill: true,
                                tension: 0.3,
                                pointRadius: 0,
                                borderWidth: 1,
                                yAxisID: 'y1',
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: { display: true, position: 'top', labels: { boxWidth: 12, padding: 8 } },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        if (ctx.datasetIndex === 0) return '\uc190\uc775: ' + fmtW(ctx.raw) + '\uc6d0';
                                        return '\ub0a8\ud3ed: ' + ctx.raw.toFixed(2) + '%';
                                    }
                                }
                            },
                            annotation: undefined
                        },
                        scales: {
                            x: { grid: { color: '#21262d' }, ticks: { maxTicksLimit: 10 } },
                            y: {
                                position: 'left',
                                grid: { color: '#21262d' },
                                ticks: { callback: v => fmtW(v) },
                            },
                            y1: {
                                position: 'right',
                                grid: { display: false },
                                ticks: { callback: v => v.toFixed(1) + '%' },
                                max: 0,
                            }
                        }
                    },
                    plugins: [{
                        id: 'zeroLine',
                        afterDraw(chart) {
                            const yScale = chart.scales.y;
                            const yPixel = yScale.getPixelForValue(0);
                            if (yPixel >= yScale.top && yPixel <= yScale.bottom) {
                                const ctx = chart.ctx;
                                ctx.save();
                                ctx.beginPath();
                                ctx.moveTo(chart.chartArea.left, yPixel);
                                ctx.lineTo(chart.chartArea.right, yPixel);
                                ctx.strokeStyle = '#484f58';
                                ctx.lineWidth = 1;
                                ctx.setLineDash([4, 4]);
                                ctx.stroke();
                                ctx.restore();
                            }
                        }
                    }]
                });
            } catch(e) {
                console.error('Equity chart error:', e);
                const emptyEl = document.getElementById('equityEmpty');
                emptyEl.style.display = 'flex';
                emptyEl.innerHTML = '\ub370\uc774\ud130 \ub85c\ub4dc \uc2e4\ud328. \uc0c8\ub85c\uace0\uce68\ud558\uc138\uc694. <button class="btn btn-sm btn-scan" onclick="loadEquityChart()" style="margin-left:8px">\uc7ac\uc2dc\ub3c4</button>';
                document.getElementById('equityChart').style.display = 'none';
            }
        }

        /* ========== Daily P&L Bar Chart ========== */
        async function loadDailyPnlChart() {
            try {
                const r = await fetch('/api/daily-pnl?period=' + currentPeriod);
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const d = await r.json();
                const data = d.data || [];
                const emptyEl = document.getElementById('pnlEmpty');
                const canvas = document.getElementById('dailyPnlChart');

                if (!data.length) {
                    emptyEl.style.display = 'flex';
                    canvas.style.display = 'none';
                    if (dailyPnlChartInst) { dailyPnlChartInst.destroy(); dailyPnlChartInst = null; }
                    return;
                }
                emptyEl.style.display = 'none';
                canvas.style.display = 'block';

                const labels = data.map(d => d.date);
                const pnlData = data.map(d => d.pnl);
                const runningData = data.map(d => d.running_total);
                const barColors = pnlData.map(v => v >= 0 ? '#3fb950' : '#f85149');

                if (dailyPnlChartInst) dailyPnlChartInst.destroy();
                dailyPnlChartInst = new Chart(canvas, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: '\uc77c\ubcc4 \uc190\uc775',
                                data: pnlData,
                                backgroundColor: barColors,
                                borderRadius: 2,
                                yAxisID: 'y',
                                order: 2,
                            },
                            {
                                label: '\ub204\uc801 \ud569\uacc4',
                                data: runningData,
                                type: 'line',
                                borderColor: '#d29922',
                                backgroundColor: 'transparent',
                                tension: 0.3,
                                pointRadius: 0,
                                borderWidth: 1.5,
                                yAxisID: 'y1',
                                order: 1,
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: { display: true, position: 'top', labels: { boxWidth: 10, padding: 6, font: { size: 10 } } },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        return ctx.dataset.label + ': ' + fmtW(ctx.raw) + '\uc6d0';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: { grid: { display: false }, ticks: { maxTicksLimit: 8, font: { size: 9 } } },
                            y: { position: 'left', grid: { color: '#21262d' }, ticks: { callback: v => fmtW(v), font: { size: 9 } } },
                            y1: { position: 'right', grid: { display: false }, ticks: { callback: v => fmtW(v), font: { size: 9 } } }
                        }
                    }
                });
            } catch(e) {
                console.error('Daily PnL chart error:', e);
                const emptyEl = document.getElementById('pnlEmpty');
                emptyEl.style.display = 'flex';
                emptyEl.innerHTML = '\ub370\uc774\ud130 \ub85c\ub4dc \uc2e4\ud328. \uc0c8\ub85c\uace0\uce68\ud558\uc138\uc694. <button class="btn btn-sm btn-scan" onclick="loadDailyPnlChart()" style="margin-left:8px">\uc7ac\uc2dc\ub3c4</button>';
                document.getElementById('dailyPnlChart').style.display = 'none';
            }
        }

        /* ========== Strategy Doughnut Chart ========== */
        async function loadStrategyChart() {
            try {
                const r = await fetch('/api/strategy-stats?period=' + currentPeriod);
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const d = await r.json();
                const strategies = d.strategies || {};
                const emptyEl = document.getElementById('strategyEmpty');
                const canvas = document.getElementById('strategyChart');
                const tableEl = document.getElementById('strategyTable');

                const names = Object.keys(strategies);
                const winData = names.map(n => strategies[n].wins || 0);
                const totalWins = winData.reduce((a, b) => a + b, 0);

                if (!totalWins) {
                    emptyEl.style.display = 'flex';
                    canvas.style.display = 'none';
                    if (strategyChartInst) { strategyChartInst.destroy(); strategyChartInst = null; }
                    tableEl.innerHTML = '<p class="neu">\uc804\ub7b5 \ub370\uc774\ud130 \uc5c6\uc74c</p>';
                    return;
                }
                emptyEl.style.display = 'none';
                canvas.style.display = 'block';

                const chartColors = [
                    '#58a6ff', '#3fb950', '#d29922', '#f85149', '#bc8cff',
                    '#39d2c0', '#f778ba', '#79c0ff'
                ];

                if (strategyChartInst) strategyChartInst.destroy();
                strategyChartInst = new Chart(canvas, {
                    type: 'doughnut',
                    data: {
                        labels: names,
                        datasets: [{
                            data: winData,
                            backgroundColor: chartColors,
                            borderColor: '#161b28',
                            borderWidth: 2,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '55%',
                        plugins: {
                            legend: {
                                display: true,
                                position: 'right',
                                labels: {
                                    boxWidth: 8,
                                    padding: 4,
                                    font: { size: 9 },
                                    generateLabels: function(chart) {
                                        const dataset = chart.data.datasets[0];
                                        return chart.data.labels.map((label, i) => {
                                            const wr = strategies[label] ? strategies[label].win_rate : 0;
                                            return {
                                                text: label + ' (' + wr + '%)',
                                                fillStyle: chartColors[i],
                                                strokeStyle: '#161b28',
                                                lineWidth: 1,
                                                index: i,
                                                hidden: false,
                                            };
                                        });
                                    }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        const s = strategies[ctx.label] || {};
                                        return ctx.label + ': ' + Math.round(ctx.raw) + '\uc2b9 (' + (s.win_rate||0) + '% \uc2b9\ub960)';
                                    }
                                }
                            }
                        }
                    }
                });

                // Strategy win rates table
                let html = '<table><thead><tr><th>\uc804\ub7b5</th><th>\uc2b9</th><th>\ud328</th><th>\uc2b9\ub960</th><th>\uc190\uc775</th></tr></thead><tbody>';
                for (const name of names) {
                    const s = strategies[name];
                    const pnlClass = (s.total_pnl||0) >= 0 ? 'pos' : 'neg';
                    html += '<tr><td>' + name + '</td><td class="green">' + Math.round(s.wins) + '</td><td class="pos">' + Math.round(s.losses) + '</td>'
                         + '<td class="green">' + s.win_rate + '%</td>'
                         + '<td class="' + pnlClass + '">' + fmtW(s.total_pnl) + '\uc6d0</td></tr>';
                }
                html += '</tbody></table>';
                tableEl.innerHTML = html;

            } catch(e) {
                console.error('Strategy chart error:', e);
                const emptyEl = document.getElementById('strategyEmpty');
                emptyEl.style.display = 'flex';
                emptyEl.innerHTML = '\ub370\uc774\ud130 \ub85c\ub4dc \uc2e4\ud328. \uc0c8\ub85c\uace0\uce68\ud558\uc138\uc694. <button class="btn btn-sm btn-scan" onclick="loadStrategyChart()" style="margin-left:8px">\uc7ac\uc2dc\ub3c4</button>';
                document.getElementById('strategyChart').style.display = 'none';
            }
        }

        /* ========== Trade Distribution Histogram ========== */
        async function loadDistChart() {
            try {
                const r = await fetch('/api/trade-distribution?period=' + currentPeriod);
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const d = await r.json();
                const emptyEl = document.getElementById('distEmpty');
                const canvas = document.getElementById('distChart');

                if (!d.total_trades) {
                    emptyEl.style.display = 'flex';
                    canvas.style.display = 'none';
                    if (distChartInst) { distChartInst.destroy(); distChartInst = null; }
                    return;
                }
                emptyEl.style.display = 'none';
                canvas.style.display = 'block';

                const bins = d.bins || [];
                const counts = d.counts || [];
                const barColors = bins.map(b => {
                    const val = parseInt(b);
                    if (val > 0) return '#3fb950';
                    if (val < 0) return '#f85149';
                    return '#8b949e';
                });

                if (distChartInst) distChartInst.destroy();
                distChartInst = new Chart(canvas, {
                    type: 'bar',
                    data: {
                        labels: bins,
                        datasets: [{
                            label: '\uac70\ub798 \uac74\uc218',
                            data: counts,
                            backgroundColor: barColors,
                            borderRadius: 2,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    title: ctx => '\uc218\uc775\ub960: ' + ctx[0].label,
                                    afterBody: function() {
                                        return '\ud3c9\uade0: ' + d.avg_return + '% | \uc911\uc559: ' + d.median_return + '%';
                                    }
                                }
                            },
                        },
                        scales: {
                            x: { grid: { display: false }, title: { display: true, text: '\uc218\uc775\ub960 %', font: { size: 10 } } },
                            y: { grid: { color: '#21262d' }, title: { display: true, text: '\uac70\ub798 \uac74\uc218', font: { size: 10 } },
                                 ticks: { stepSize: 1 } }
                        }
                    },
                    plugins: [{
                        id: 'avgLine',
                        afterDraw(chart) {
                            if (!d.avg_return) return;
                            const xScale = chart.scales.x;
                            // Find the bin index closest to avg
                            const avgBin = bins.findIndex(b => parseFloat(b) >= d.avg_return);
                            if (avgBin < 0) return;
                            const xPixel = xScale.getPixelForValue(avgBin);
                            const ctx = chart.ctx;
                            ctx.save();
                            ctx.beginPath();
                            ctx.moveTo(xPixel, chart.chartArea.top);
                            ctx.lineTo(xPixel, chart.chartArea.bottom);
                            ctx.strokeStyle = '#d29922';
                            ctx.lineWidth = 1.5;
                            ctx.setLineDash([4, 3]);
                            ctx.stroke();
                            ctx.restore();
                        }
                    }]
                });
            } catch(e) {
                console.error('Distribution chart error:', e);
                const emptyEl = document.getElementById('distEmpty');
                emptyEl.style.display = 'flex';
                emptyEl.innerHTML = '\ub370\uc774\ud130 \ub85c\ub4dc \uc2e4\ud328. \uc0c8\ub85c\uace0\uce68\ud558\uc138\uc694. <button class="btn btn-sm btn-scan" onclick="loadDistChart()" style="margin-left:8px">\uc7ac\uc2dc\ub3c4</button>';
                document.getElementById('distChart').style.display = 'none';
            }
        }

        /* ========== Load All Charts ========== */
        function loadAllCharts() {
            loadEquityChart();
            loadDailyPnlChart();
            loadStrategyChart();
            loadDistChart();
        }

        /* ========== Existing functions (unchanged) ========== */
        async function fetchStatus() {
            try {
                const r = await fetch('/api/status');
                const d = await r.json();
                const mt = document.getElementById('modeTag');
                mt.textContent = d.scheduler?.running ? '\uc790\ub3d9\ub9e4\ub9e4 \uc911' : d.mode;
                mt.className = 'mode ' + (d.mode==='\uc2e4\uc804\ud22c\uc790'?'mode-live':'mode-paper');
                if(d.scheduler?.running) { mt.className='mode'; mt.style.cssText='padding:4px 12px;border-radius:12px;font-size:0.8rem;font-weight:600;background:#23863633;color:#3fb950;border:1px solid #238636'; }
                document.getElementById('totalAssets').textContent = fmtW(d.balance?.total_eval||0)+'\uc6d0';
                document.getElementById('cash').textContent = fmtW(d.balance?.cash||0)+'\uc6d0';
                const pnl = d.total_pnl||0; const pnlPct = d.total_pnl_pct||0;
                const pnlEl = document.getElementById('totalPnl');
                pnlEl.textContent = (pnl>=0?'+':'')+fmtW(pnl)+'\uc6d0 ('+(pnlPct>=0?'+':'')+pnlPct.toFixed(2)+'%)';
                pnlEl.className = 'value '+(pnl>=0?'pos':'neg');
                document.getElementById('posCount').textContent = Object.keys(d.positions||{}).length;
                document.getElementById('winRate').textContent = (d.win_rate||0)+'%';
                const cb = d.circuit_breaker||{};
                const cbEl = document.getElementById('circuitAlert');
                if(cb.tripped) { cbEl.classList.add('active'); document.getElementById('cbReason').textContent=cb.reason; }
                else { cbEl.classList.remove('active'); }
                const si = d.scheduler||{};
                document.getElementById('schedInfo').textContent = (si.is_market_hours?'\uc7a5\uc911':'\uc7a5\uc678')+' | '+si.time_until_open;
                const posEl = document.getElementById('positions');
                const pe = Object.entries(d.positions||{});
                if(!pe.length) { posEl.innerHTML='<p class="neu">\ubcf4\uc720 \uc885\ubaa9 \uc5c6\uc74c</p>'; }
                else {
                    posEl.innerHTML = '<table><thead><tr><th>\uc885\ubaa9</th><th>\uc218\ub7c9</th><th>\ud3c9\uade0\uac00</th><th>\ud3c9\uac00\uae08\uc561</th></tr></thead><tbody>'
                        + pe.map(([s,p]) => {
                            const val = (p.qty||0)*(p.avg_price||0);
                            return '<tr><td><b>'+(p.name||s)+'</b><br><span class="neu" style="font-size:0.72rem">'+s+'</span></td><td>'+fmt(p.qty)+'</td><td>'+fmt(p.avg_price)+'</td><td>'+fmtW(val)+'\uc6d0</td></tr>';
                        }).join('')+'</tbody></table>';
                }
                const tb = document.getElementById('recentTrades');
                const trades = (d.recent_trades||[]).slice(-15).reverse();
                const ACTION_KO = {'BUY':'\ub9e4\uc218','SELL':'\ub9e4\ub3c4','STOP_LOSS':'\uc190\uc808','TAKE_PROFIT':'\uc775\uc808','TRAILING_STOP':'\ucd94\uc801\uc190\uc808'};
                tb.innerHTML = trades.map(t => {
                    const badge = t.action==='BUY'?'badge-buy':t.action.includes('STOP')||t.action==='SELL'?'badge-sell':'badge-hold';
                    const actionText = ACTION_KO[t.action] || t.action;
                    const pnl = t.pnl_pct?'<span class="'+(t.pnl_pct>=0?'pos':'neg')+'">'+(t.pnl_pct>=0?'+':'')+t.pnl_pct+'%</span>':'-';
                    const time = new Date(t.timestamp).toLocaleString('ko',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
                    return '<tr><td>'+time+'</td><td><span class="badge '+badge+'">'+actionText+'</span></td><td>'+(t.name||t.symbol)+'</td><td>'+(t.qty||'-')+'</td><td>'+fmt(t.price)+'</td><td>'+pnl+'</td></tr>';
                }).join('');
                // Regime display
                const rg = d.regime||{};
                const rgBadge = document.getElementById('regimeBadge');
                const rgName = rg.regime||'SIDEWAYS';
                rgBadge.textContent = REGIME_LABELS[rgName] || rgName;
                rgBadge.className = 'badge-regime ' + (REGIME_CLASS_MAP[rgName] || 'regime-sideways');
                const rgDet = rg.details||{};
                document.getElementById('regimeADX').textContent = rgDet.adx!==undefined ? rgDet.adx : '-';
                document.getElementById('regimeVol').textContent = rgDet.recent_volatility!==undefined ? rgDet.recent_volatility+'%' : '-';
                document.getElementById('regimeReturn').textContent = rgDet.recent_return_pct!==undefined ? (rgDet.recent_return_pct>=0?'+':'')+rgDet.recent_return_pct+'%' : '-';
                document.getElementById('regimeMaDiff').textContent = rgDet.ma_diff_pct!==undefined ? (rgDet.ma_diff_pct>=0?'+':'')+rgDet.ma_diff_pct+'%' : '-';
                document.getElementById('regimeSince').textContent = rg.regime_since ? '\uc2dc\uc791: '+new Date(rg.regime_since).toLocaleString('ko',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) : '';
                const rgStatEl = document.getElementById('regimeStat');
                rgStatEl.textContent = REGIME_LABELS[rgName] || rgName;
                rgStatEl.className = 'value '+(rgName==='BULL'?'green':rgName==='BEAR'?'pos':'yellow');
                // Regime weights
                const rgw = rg.weights||{};
                const wHtml = Object.entries(rgw).map(([k,v]) => {
                    const pct = Math.round(v*100);
                    return k+': <b>'+pct+'%</b><span class="weight-bar" style="width:'+pct+'px"></span>';
                }).join(' &nbsp; ');
                document.getElementById('regimeWeights').innerHTML = '\ud65c\uc131 \uac00\uc911\uce58: '+wHtml;

                document.getElementById('lastUpdate').textContent = '\uac31\uc2e0: '+new Date().toLocaleTimeString('ko');
            } catch(e) { console.error(e); }
        }

        async function fetchStats() {
            try {
                const r = await fetch('/api/stats');
                const d = await r.json();
                const el = document.getElementById('tradeStats');
                const s7 = d['7d']||{}, s30 = d['30d']||{}, sa = d['all']||{};
                el.innerHTML =
                    '<table><tr><th></th><th>7\uc77c</th><th>30\uc77c</th><th>\uc804\uccb4</th></tr>'
                    +'<tr><td>\uac70\ub798</td><td>'+(s7.total||0)+'</td><td>'+(s30.total||0)+'</td><td>'+(sa.total||0)+'</td></tr>'
                    +'<tr><td>\uc2b9\ub9ac</td><td>'+(s7.wins||0)+'</td><td>'+(s30.wins||0)+'</td><td>'+(sa.wins||0)+'</td></tr>'
                    +'<tr><td>\uc2b9\ub960</td><td class="green">'+(s7.win_rate||0)+'%</td><td class="green">'+(s30.win_rate||0)+'%</td><td class="green">'+(sa.win_rate||0)+'%</td></tr>'
                    +'<tr><td>\ub204\uc801 \uc190\uc775</td><td class="'+((s7.total_pnl||0)>=0?'pos':'neg')+'">'+fmtW(s7.total_pnl||0)+'\uc6d0</td>'
                    +'<td class="'+((s30.total_pnl||0)>=0?'pos':'neg')+'">'+fmtW(s30.total_pnl||0)+'\uc6d0</td>'
                    +'<td class="'+((sa.total_pnl||0)>=0?'pos':'neg')+'">'+fmtW(sa.total_pnl||0)+'\uc6d0</td></tr>'
                    +'<tr><td>\ud3c9\uade0 \uc218\uc775</td><td>'+(s7.avg_pnl_pct||0)+'%</td><td>'+(s30.avg_pnl_pct||0)+'%</td><td>'+(sa.avg_pnl_pct||0)+'%</td></tr></table>';
            } catch(e) {}
        }

        async function scanAll() {
            document.getElementById('scanResults').innerHTML='<tr><td colspan="10">15\uac1c \uc885\ubaa9 \uc2a4\uce94 \uc911...</td></tr>';
            const r = await fetch('/api/scan');
            const d = await r.json();
            const tb = document.getElementById('scanResults');
            const SCAN_ACTION_KO = {'BUY':'\ub9e4\uc218','SELL':'\ub9e4\ub3c4','HOLD':'\ubcf4\ub958'};
            tb.innerHTML = (d.results||[]).map(s => {
                const badge = s.action==='BUY'?'badge-buy':s.action==='SELL'?'badge-sell':'badge-hold';
                const barW = Math.max(0,Math.min(100,s.score));
                const barC = s.score>=58?'#3fb950':s.score<=42?'#f85149':'#8b949e';
                const ss = s.sub_scores||{};
                const subCell = (v) => {
                    const val = (v||50).toFixed(0);
                    const c = v>=58?'green':v<=42?'pos':'neu';
                    return '<span class="'+c+'">'+val+'</span>';
                };
                return '<tr><td><b>'+s.name+'</b><br><span class="neu" style="font-size:0.7rem">'+s.symbol+'</span></td>'
                    +'<td><div class="score-bar"><div class="score-fill" style="width:'+barW+'%;background:'+barC+'"></div></div> '+s.score+'</td>'
                    +'<td><span class="badge '+badge+'">'+(SCAN_ACTION_KO[s.action]||s.action)+'</span></td>'
                    +'<td>'+fmt(s.current_price)+'</td>'
                    +'<td>'+subCell(ss['\ud3c9\uade0\ud68c\uadc0'])+'</td>'
                    +'<td>'+subCell(ss['\ucd94\uc138\ucd94\uc885'])+'</td>'
                    +'<td>'+subCell(ss['\ud55c\uad6d\ud615\ubaa8\uba58\ud140'])+'</td>'
                    +'<td>'+subCell(ss['\uac70\ub798\ub7c9'])+'</td>'
                    +'<td>'+subCell(ss['\ubcc0\ub3d9\uc131'])+'</td>'
                    +'<td style="font-size:0.72rem;max-width:200px;overflow:hidden;text-overflow:ellipsis">'+(s.reasons||[]).slice(0,2).join(', ')+'</td></tr>';
            }).join('');
        }

        async function startBot() {
            const btn = document.querySelector('.btn-start');
            const origText = btn.textContent;
            btn.disabled = true; btn.textContent = '\uc2dc\uc791 \uc911...';
            try {
                await fetch('/api/bot/start',{method:'POST'});
                fetchStatus();
            } catch(e) { console.error(e); showToast('\uc790\ub3d9\ub9e4\ub9e4 \uc2dc\uc791 \uc2e4\ud328', 'error'); }
            finally { btn.disabled = false; btn.textContent = origText; }
        }
        async function stopBot() {
            const btn = document.querySelector('.btn-stop');
            const origText = btn.textContent;
            btn.disabled = true; btn.textContent = '\uc911\uc9c0 \uc911...';
            try {
                await fetch('/api/bot/stop',{method:'POST'});
                fetchStatus();
            } catch(e) { console.error(e); showToast('\uc911\uc9c0 \uc2e4\ud328', 'error'); }
            finally { btn.disabled = false; btn.textContent = origText; }
        }
        async function runCycle() {
            const btn = document.querySelector('.btn-cycle');
            const origText = btn.textContent;
            btn.disabled = true; btn.textContent = '\uc2e4\ud589 \uc911...';
            document.getElementById('scanResults').innerHTML='<tr><td colspan="10">\ub9e4\ub9e4 \uc0ac\uc774\ud074 \uc2e4\ud589 \uc911...</td></tr>';
            try {
                await fetch('/api/cycle',{method:'POST'});
                fetchStatus(); fetchStats();
            } catch(e) { console.error(e); showToast('1\ud68c \uc2e4\ud589 \uc2e4\ud328', 'error'); }
            finally { btn.disabled = false; btn.textContent = origText; }
        }
        async function resetCB() { await fetch('/api/circuit-breaker/reset',{method:'POST'}); fetchStatus(); }

        /* ========== Strategy Analysis Variables ========== */
        let rollingChartInst = null;
        let currentSAPeriod = '14d';
        let rollingWindow = 20;

        /* ========== Strategy Analysis Period Selector ========== */
        function setSAPeriod(period) {
            currentSAPeriod = period;
            document.querySelectorAll('.sa-period-btn').forEach(b => {
                b.classList.toggle('active', b.dataset.saPeriod === period);
            });
            loadStrategyHeatmap();
        }

        /* ========== Strategy Heatmap ========== */
        async function loadStrategyHeatmap() {
            try {
                const r = await fetch('/api/strategy-heatmap?period=' + currentSAPeriod);
                const d = await r.json();
                const el = document.getElementById('strategyHeatmap');

                const dates = d.dates || [];
                const strategies = d.strategies || [];
                const matrix = d.matrix || {};

                if (!dates.length) {
                    el.innerHTML = '<p class="neu">\ud574\ub2f9 \uae30\uac04 \ud788\ud2b8\ub9f5 \ub370\uc774\ud130 \uc5c6\uc74c</p>';
                    return;
                }

                // Build heatmap table
                let html = '<table class="heatmap-table"><thead><tr><th>\uc804\ub7b5</th>';
                for (const dt of dates) {
                    // Show short date MM-DD
                    const parts = dt.split('-');
                    html += '<th>' + parts[1] + '-' + parts[2] + '</th>';
                }
                html += '</tr></thead><tbody>';

                for (const sname of strategies) {
                    html += '<tr><td class="strategy-name">' + sname + '</td>';
                    const row = matrix[sname] || [];
                    for (let i = 0; i < dates.length; i++) {
                        const val = row[i];
                        if (val === null || val === undefined) {
                            html += '<td class="heatmap-cell" style="background:#161b28;color:#484f58">-</td>';
                        } else {
                            const bg = heatmapColor(val);
                            const textColor = val > 60 ? '#0a0e17' : '#c9d1d9';
                            html += '<td class="heatmap-cell" style="background:' + bg + ';color:' + textColor + '">' + val + '%</td>';
                        }
                    }
                    html += '</tr>';
                }
                html += '</tbody></table>';
                el.innerHTML = html;
            } catch(e) { console.error('Heatmap error:', e); }
        }

        function heatmapColor(value) {
            // Interpolate from red (0%) -> yellow (50%) -> green (100%)
            const v = Math.max(0, Math.min(100, value));
            let r, g, b;
            if (v <= 50) {
                // Red to Yellow
                const t = v / 50;
                r = 200 + Math.round(55 * t);   // 200 -> 255
                g = Math.round(180 * t);          // 0 -> 180
                b = 50;
            } else {
                // Yellow to Green
                const t = (v - 50) / 50;
                r = 255 - Math.round(200 * t);   // 255 -> 55
                g = 180 + Math.round(5 * t);      // 180 -> 185
                b = 50 + Math.round(30 * t);      // 50 -> 80
            }
            return 'rgba(' + r + ',' + g + ',' + b + ',0.85)';
        }

        /* ========== Rolling Win Rate Chart ========== */
        async function loadRollingChart() {
            try {
                const r = await fetch('/api/strategy-rolling?window=' + rollingWindow);
                const d = await r.json();
                const strategiesData = d.strategies || {};
                const emptyEl = document.getElementById('rollingEmpty');
                const canvas = document.getElementById('rollingChart');

                // Check if any strategy has data
                const hasData = Object.values(strategiesData).some(arr => arr.length > 0);
                if (!hasData) {
                    emptyEl.style.display = 'flex';
                    canvas.style.display = 'none';
                    if (rollingChartInst) { rollingChartInst.destroy(); rollingChartInst = null; }
                    return;
                }
                emptyEl.style.display = 'none';
                canvas.style.display = 'block';

                const chartColors = [
                    '#58a6ff', '#3fb950', '#d29922', '#f85149',
                    '#bc8cff', '#39d2c0', '#f778ba', '#79c0ff'
                ];

                const strategyNames = Object.keys(strategiesData);
                const datasets = strategyNames.map((name, idx) => {
                    const trades = strategiesData[name] || [];
                    return {
                        label: name,
                        data: trades.map(t => t.win_rate),
                        borderColor: chartColors[idx % chartColors.length],
                        backgroundColor: 'transparent',
                        tension: 0.3,
                        pointRadius: 0,
                        pointHoverRadius: 3,
                        borderWidth: 1.5,
                    };
                });

                // Use the longest strategy's indices as labels
                let maxLen = 0;
                let maxName = strategyNames[0];
                for (const name of strategyNames) {
                    if ((strategiesData[name] || []).length > maxLen) {
                        maxLen = (strategiesData[name] || []).length;
                        maxName = name;
                    }
                }
                const labels = (strategiesData[maxName] || []).map((t, i) => i + 1);

                if (rollingChartInst) rollingChartInst.destroy();
                rollingChartInst = new Chart(canvas, {
                    type: 'line',
                    data: { labels: labels, datasets: datasets },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: {
                                display: true, position: 'top',
                                labels: { boxWidth: 10, padding: 6, font: { size: 9 } }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        return ctx.dataset.label + ': ' + ctx.raw + '%';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: { color: '#21262d' },
                                title: { display: true, text: '\uac70\ub798 #', font: { size: 10 } },
                                ticks: { maxTicksLimit: 12 }
                            },
                            y: {
                                grid: { color: '#21262d' },
                                title: { display: true, text: '\uc2b9\ub960 %', font: { size: 10 } },
                                min: 0, max: 100,
                                ticks: { callback: v => v + '%' }
                            }
                        }
                    },
                    plugins: [{
                        id: 'fiftyLine',
                        afterDraw(chart) {
                            const yScale = chart.scales.y;
                            const yPixel = yScale.getPixelForValue(50);
                            const ctx = chart.ctx;
                            ctx.save();
                            ctx.beginPath();
                            ctx.moveTo(chart.chartArea.left, yPixel);
                            ctx.lineTo(chart.chartArea.right, yPixel);
                            ctx.strokeStyle = '#484f58';
                            ctx.lineWidth = 1;
                            ctx.setLineDash([4, 4]);
                            ctx.stroke();
                            ctx.restore();
                        }
                    }]
                });
            } catch(e) { console.error('Rolling chart error:', e); }
        }

        /* ========== Strategy Toggle Controls ========== */
        async function loadStrategyToggles() {
            try {
                const r = await fetch('/api/strategy-config');
                const d = await r.json();
                const config = d.config || {};
                const el = document.getElementById('strategyToggles');

                let html = '';
                for (const [name, enabled] of Object.entries(config)) {
                    const checked = enabled ? 'checked' : '';
                    html += '<div class="toggle-item">'
                         + '<span class="name">' + name + '</span>'
                         + '<label class="toggle-switch">'
                         + '<input type="checkbox" ' + checked + ' onchange="toggleStrategy(\\'' + name + '\\', this)">'
                         + '<span class="toggle-slider"></span>'
                         + '</label></div>';
                }
                el.innerHTML = html;
            } catch(e) { console.error('Toggle load error:', e); }
        }

        async function toggleStrategy(name, checkbox) {
            const action = checkbox.checked ? '\ud65c\uc131\ud654' : '\ube44\ud65c\uc131\ud654';
            const confirmed = confirm('"' + name + '" \uc804\ub7b5\uc744 ' + action + '\ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?');
            if (!confirmed) {
                checkbox.checked = !checkbox.checked;
                return;
            }
            try {
                const r = await fetch('/api/strategy/' + name + '/toggle', { method: 'POST' });
                const d = await r.json();
                if (d.error) {
                    alert('\uc624\ub958: ' + d.error);
                    checkbox.checked = !checkbox.checked;
                    return;
                }
                // Update checkbox to reflect actual server state
                checkbox.checked = d.enabled;
                // Show success toast
                showToast(name + ' \uc804\ub7b5\uc774 ' + (d.enabled ? '\ud65c\uc131\ud654' : '\ube44\ud65c\uc131\ud654') + '\ub418\uc5c8\uc2b5\ub2c8\ub2e4.', 'success');
                // Reload ranking to reflect status changes
                loadStrategyRanking();
            } catch(e) {
                console.error('Toggle error:', e);
                checkbox.checked = !checkbox.checked;
            }
        }

        /* ========== Strategy Ranking Table ========== */
        async function loadStrategyRanking() {
            try {
                const r = await fetch('/api/strategy-ranking?period=' + currentPeriod);
                const d = await r.json();
                const ranking = d.ranking || [];
                const el = document.getElementById('strategyRanking');

                if (!ranking.length) {
                    el.innerHTML = '<p class="neu">\ub7ad\ud0b9 \ub370\uc774\ud130 \uc5c6\uc74c</p>';
                    return;
                }

                let html = '<table><thead><tr><th>#</th><th>\uc804\ub7b5</th><th title="\ud574\ub2f9 \uc804\ub7b5\uc73c\ub85c \ubc1c\uc0dd\ud55c \ucd1d \uac70\ub798 \ud69f\uc218">\uac70\ub798</th><th title="\ub9e4\ub3c4 \uc911 \uc218\uc775\uc73c\ub85c \ub05d\ub09c \ube44\uc728. 50% \uc774\uc0c1\uc774\uba74 \uc591\ud638">\uc2b9\ub960</th><th title="\uac70\ub798\ub2f9 \ud3c9\uade0 \uc218\uc775\ub960">\ud3c9\uade0 \uc218\uc775</th><th title="\uc0e4\ud504 \ube44\uc728(Sharpe Ratio): \uc704\ud5d8 \ub300\ube44 \uc218\uc775\ub960. 1\uc774\uc0c1 \uc591\ud638, 2\uc774\uc0c1 \uc6b0\uc218. \ub192\uc744\uc218\ub85d \uc548\uc815\uc801\uc73c\ub85c \ubc88\ub2e4\ub294 \ub73b">\uc0e4\ud504</th><th title="\uc804\ub7b5 \ud65c\uc131/\ube44\ud65c\uc131 \uc0c1\ud0dc">\uc0c1\ud0dc</th></tr></thead><tbody>';
                ranking.forEach((s, idx) => {
                    const rank = idx + 1;
                    let rankClass = 'rank-n';
                    if (rank === 1) rankClass = 'rank-1';
                    else if (rank === 2) rankClass = 'rank-2';
                    else if (rank === 3) rankClass = 'rank-3';

                    const wrClass = s.win_rate >= 50 ? 'green' : s.win_rate > 0 ? 'yellow' : 'neu';
                    const retClass = s.avg_return >= 0 ? 'green' : 'pos';
                    const sharpeClass = s.sharpe > 0 ? 'green' : s.sharpe < 0 ? 'pos' : 'neu';
                    const statusClass = s.enabled ? 'status-active' : 'status-disabled';
                    const statusText = s.enabled ? '\ud65c\uc131' : '\ube44\ud65c\uc131';

                    html += '<tr>'
                         + '<td><span class="rank-badge ' + rankClass + '">' + rank + '</span></td>'
                         + '<td><b>' + s.strategy + '</b></td>'
                         + '<td>' + s.trades + '</td>'
                         + '<td class="' + wrClass + '">' + s.win_rate + '%</td>'
                         + '<td class="' + retClass + '">' + (s.avg_return >= 0 ? '+' : '') + s.avg_return + '%</td>'
                         + '<td class="' + sharpeClass + '">' + s.sharpe + '</td>'
                         + '<td class="' + statusClass + '">' + statusText + '</td>'
                         + '</tr>';
                });
                html += '</tbody></table>';
                el.innerHTML = html;
            } catch(e) { console.error('Ranking error:', e); }
        }

        /* ========== Load All Strategy Analysis ========== */
        function loadAllStrategyAnalysis() {
            loadStrategyHeatmap();
            loadRollingChart();
            loadStrategyToggles();
            loadStrategyRanking();
        }

        /* ========== Dashboard Regime Detection ========== */
        let regimeTimelineChartInst = null;
        let lastRegimeWeights = {};

        const REGIME_COLORS = {
            'BULL_TREND': '#3fb950',
            'BEAR_TREND': '#f85149',
            'RANGING': '#d29922',
            'HIGH_VOLATILITY': '#f97316',
        };
        async function loadDashboardRegime() {
            try {
                const r = await fetch('/api/regime/current');
                const d = await r.json();
                const regime = d.regime || 'RANGING';
                const confidence = d.confidence || 0;
                const indicators = d.indicators || {};
                const weights = d.recommended_weights || {};
                lastRegimeWeights = weights;

                // Update badge
                const badge = document.getElementById('dashRegimeBadge');
                badge.textContent = (REGIME_LABELS[regime] || regime);
                badge.className = 'regime-badge-lg ' + (REGIME_CLASS_MAP[regime] || 'regime-ranging');

                // Update confidence
                const confPct = Math.round(confidence * 100);
                document.getElementById('dashRegimeConf').textContent = confPct + '%';
                const confBar = document.getElementById('dashRegimeConfBar');
                confBar.style.width = confPct + '%';
                confBar.style.background = REGIME_COLORS[regime] || '#d29922';

                // Update indicators
                const ret20d = indicators.return_20d;
                document.getElementById('drInd20dRet').textContent = ret20d !== null && ret20d !== undefined ? (ret20d >= 0 ? '+' : '') + ret20d.toFixed(2) + '%' : '-';
                document.getElementById('drInd20dRet').style.color = ret20d > 0 ? '#3fb950' : ret20d < 0 ? '#f85149' : '#c9d1d9';

                const recentVol = indicators.recent_vol;
                document.getElementById('drIndRecentVol').textContent = recentVol !== null && recentVol !== undefined ? recentVol.toFixed(3) : '-';

                const volZ = indicators.vol_z_score;
                document.getElementById('drIndVolZ').textContent = volZ !== null && volZ !== undefined ? volZ.toFixed(2) : '-';
                const volZEl = document.getElementById('drIndVolZ');
                if (volZ > 2) volZEl.style.color = '#f85149';
                else if (volZ > 1) volZEl.style.color = '#f97316';
                else volZEl.style.color = '#c9d1d9';

                const priceMa = indicators.price_above_ma50;
                document.getElementById('drIndPriceMa').textContent = priceMa === true ? '\uc0c1\ud68c' : priceMa === false ? '\ud558\ud68c' : '-';
                document.getElementById('drIndPriceMa').style.color = priceMa === true ? '#3fb950' : priceMa === false ? '#f85149' : '#c9d1d9';

                // Update weight comparison
                loadWeightComparison(weights);
            } catch(e) { console.error('Dashboard regime error:', e); }
        }

        async function loadWeightComparison(recommendedWeights) {
            const el = document.getElementById('weightCompareContainer');
            try {
                const r = await fetch('/api/strategy-config');
                const d = await r.json();
                const config = d.config || {};

                // Equal weight for "current" display
                const equalWeight = 1.0 / 8;
                const strategies = ['Bollinger', 'RSI', 'MACD', 'MA', 'InstitutionalFlow', 'Momentum', 'DualMomentum', 'VolatilityTarget'];
                const maxW = Math.max(...Object.values(recommendedWeights || {}), equalWeight) || 0.25;

                let html = '';
                for (const name of strategies) {
                    const rec = recommendedWeights[name] || equalWeight;
                    const cur = equalWeight;
                    const recPct = Math.round(rec * 100);
                    const curPct = Math.round(cur * 100);
                    const recBarW = Math.round((rec / maxW) * 100);
                    const curBarW = Math.round((cur / maxW) * 100);
                    const enabled = config[name] !== false;
                    const nameColor = enabled ? '#c9d1d9' : '#484f58';

                    html += '<div class="weight-compare-row">'
                         + '<div class="wc-name" style="color:' + nameColor + '">' + name + '</div>'
                         + '<div class="weight-compare-bars">'
                         + '<div class="weight-bar-row"><div class="weight-bar-label" style="color:#58a6ff">\uad8c\uc7a5</div>'
                         + '<div class="weight-bar-track"><div class="weight-bar-fill-rec" style="width:' + recBarW + '%"></div></div>'
                         + '<div class="weight-pct" style="color:#58a6ff">' + recPct + '%</div></div>'
                         + '<div class="weight-bar-row"><div class="weight-bar-label">\ud604\uc7ac</div>'
                         + '<div class="weight-bar-track"><div class="weight-bar-fill-cur" style="width:' + curBarW + '%"></div></div>'
                         + '<div class="weight-pct">' + curPct + '%</div></div>'
                         + '</div></div>';
                }
                el.innerHTML = html;
            } catch(e) {
                console.error('Weight comparison error:', e);
                el.innerHTML = '<p class="neu">\uac00\uc911\uce58 \ube44\uad50 \ub85c\ub529 \uc2e4\ud328</p>';
            }
        }

        async function loadRegimeTimeline() {
            try {
                const r = await fetch('/api/regime/history?days=30');
                const d = await r.json();
                const history = d.history || [];
                const emptyEl = document.getElementById('regimeTimelineEmpty');
                const canvas = document.getElementById('regimeTimelineChart');

                if (!history.length) {
                    emptyEl.style.display = 'flex';
                    canvas.style.display = 'none';
                    if (regimeTimelineChartInst) { regimeTimelineChartInst.destroy(); regimeTimelineChartInst = null; }
                    return;
                }
                emptyEl.style.display = 'none';
                canvas.style.display = 'block';

                // Group by date, take the latest regime per day
                const byDate = {};
                for (const entry of history) {
                    const ts = entry.timestamp || '';
                    const dateStr = ts.substring(0, 10);
                    if (dateStr) {
                        byDate[dateStr] = entry;
                    }
                }
                const dates = Object.keys(byDate).sort();
                const regimeValues = { 'BULL_TREND': 4, 'RANGING': 3, 'HIGH_VOLATILITY': 2, 'BEAR_TREND': 1 };
                const dataPoints = dates.map(dt => regimeValues[byDate[dt].regime] || 3);
                const bgColors = dates.map(dt => REGIME_COLORS[byDate[dt].regime] || '#d29922');
                const confData = dates.map(dt => Math.round((byDate[dt].confidence || 0) * 100));
                const shortDates = dates.map(dt => { const p = dt.split('-'); return p[1] + '-' + p[2]; });

                if (regimeTimelineChartInst) regimeTimelineChartInst.destroy();
                regimeTimelineChartInst = new Chart(canvas, {
                    type: 'bar',
                    data: {
                        labels: shortDates,
                        datasets: [
                            {
                                label: '\uad6d\uba74',
                                data: dataPoints,
                                backgroundColor: bgColors,
                                borderRadius: 3,
                                yAxisID: 'y',
                                order: 2,
                            },
                            {
                                label: '\uc2e0\ub8b0\ub3c4',
                                data: confData,
                                type: 'line',
                                borderColor: '#8b949e',
                                backgroundColor: 'transparent',
                                tension: 0.3,
                                pointRadius: 2,
                                pointBackgroundColor: '#8b949e',
                                borderWidth: 1.5,
                                yAxisID: 'y1',
                                order: 1,
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: { display: true, position: 'top', labels: { boxWidth: 10, padding: 6, font: { size: 9 } } },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        if (ctx.datasetIndex === 0) {
                                            const dateKey = dates[ctx.dataIndex];
                                            const r = byDate[dateKey] ? byDate[dateKey].regime : '-';
                                            return '\uad6d\uba74: ' + (REGIME_LABELS[r] || r);
                                        }
                                        return '\uc2e0\ub8b0\ub3c4: ' + ctx.raw + '%';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: { grid: { display: false }, ticks: { maxTicksLimit: 15, font: { size: 9 } } },
                            y: {
                                position: 'left',
                                min: 0, max: 5,
                                grid: { color: '#21262d' },
                                ticks: {
                                    stepSize: 1,
                                    font: { size: 9 },
                                    callback: function(v) {
                                        const labels = { 1: '\uc57d\uc138', 2: '\uace0\ubcc0\ub3d9', 3: '\ud6a1\ubcf4', 4: '\uac15\uc138' };
                                        return labels[v] || '';
                                    }
                                }
                            },
                            y1: {
                                position: 'right',
                                min: 0, max: 100,
                                grid: { display: false },
                                ticks: { callback: v => v + '%', font: { size: 9 } }
                            }
                        }
                    }
                });
            } catch(e) { console.error('Regime timeline error:', e); }
        }

        async function loadRegimeHistory() {
            try {
                const r = await fetch('/api/regime/history?days=30');
                const d = await r.json();
                const history = d.history || [];
                const el = document.getElementById('regimeHistoryLog');

                if (!history.length) {
                    el.innerHTML = '<p class="neu">\uad6d\uba74 \uc774\ub825 \uc5c6\uc74c</p>';
                    return;
                }

                // Show last 30 entries, newest first
                const recent = history.slice(-30).reverse();
                let html = '<table><thead><tr><th>\uc2dc\uac04</th><th>\uad6d\uba74</th><th>\uc2e0\ub8b0\ub3c4</th><th>20\uc77c \uc218\uc775\ub960</th></tr></thead><tbody>';
                for (const entry of recent) {
                    const ts = entry.timestamp ? new Date(entry.timestamp).toLocaleString('ko', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' }) : '-';
                    const regime = entry.regime || 'RANGING';
                    const css = REGIME_CLASS_MAP[regime] || 'regime-ranging';
                    const conf = entry.confidence ? Math.round(entry.confidence * 100) + '%' : '-';
                    const ind = entry.indicators || {};
                    const ret20d = ind.return_20d !== null && ind.return_20d !== undefined ? (ind.return_20d >= 0 ? '+' : '') + ind.return_20d.toFixed(2) + '%' : '-';
                    const retColor = (ind.return_20d || 0) >= 0 ? '#3fb950' : '#f85149';

                    html += '<tr><td>' + ts + '</td>'
                         + '<td><span class="badge-regime ' + css + '" style="font-size:0.7rem;padding:2px 6px">' + (REGIME_LABELS[regime] || regime) + '</span></td>'
                         + '<td>' + conf + '</td>'
                         + '<td style="color:' + retColor + '">' + ret20d + '</td></tr>';
                }
                html += '</tbody></table>';
                el.innerHTML = html;
            } catch(e) { console.error('Regime history error:', e); }
        }

        async function applyRegimeWeights() {
            if (!confirm('\uad8c\uc7a5 \uad6d\uba74 \uac00\uc911\uce58\ub97c \uc804\ub7b5 \uc124\uc815\uc5d0 \uc801\uc6a9\ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?')) return;
            try {
                const r = await fetch('/api/regime/apply-weights', { method: 'POST' });
                const d = await r.json();
                if (d.status === 'applied') {
                    alert('\uac00\uc911\uce58 \uc801\uc6a9 \uc644\ub8cc!\\n\uad6d\uba74: ' + (REGIME_LABELS[d.regime] || d.regime) + '\\n\uc2e0\ub8b0\ub3c4: ' + Math.round(d.confidence * 100) + '%');
                    loadDashboardRegime();
                    loadStrategyToggles();
                } else {
                    alert('\uac00\uc911\uce58 \uc801\uc6a9 \uc2e4\ud328');
                }
            } catch(e) {
                console.error('Apply weights error:', e);
                alert('\uac00\uc911\uce58 \uc801\uc6a9 \uc911 \uc624\ub958 \ubc1c\uc0dd');
            }
        }

        function loadAllRegimeData() {
            loadDashboardRegime();
            loadRegimeTimeline();
            loadRegimeHistory();
        }

        /* ========== Portfolio Risk Section ========== */
        let sectorPieChartInst = null;
        let corrTrendChartInst = null;
        let divTrendChartInst = null;

        function corrCellColor(value) {
            // -1 (blue) -> 0 (neutral) -> +1 (red)
            const v = Math.max(-1, Math.min(1, value));
            let r, g, b;
            if (v <= 0) {
                const t = (v + 1) / 1; // 0..1
                r = Math.round(30 + 50 * t);
                g = Math.round(80 + 100 * t);
                b = Math.round(200 - 80 * t);
            } else {
                const t = v; // 0..1
                r = Math.round(80 + 170 * t);
                g = Math.round(180 - 130 * t);
                b = Math.round(120 - 80 * t);
            }
            return 'rgba(' + r + ',' + g + ',' + b + ',0.85)';
        }

        async function loadCorrelationHeatmap() {
            try {
                const r = await fetch('/api/correlation-matrix?lookback=20');
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const d = await r.json();
                const el = document.getElementById('corrHeatmap');
                const symbols = d.symbols || [];
                const names = d.names || [];
                const matrix = d.matrix || [];
                const n = symbols.length;

                document.getElementById('prAvgCorr').textContent = (d.avg_correlation !== undefined) ? d.avg_correlation.toFixed(3) : '-';

                if (n < 2) {
                    el.innerHTML = '<p class="neu">\uc0c1\uad00\uad00\uacc4 \ubd84\uc11d\uc744 \uc704\ud574 2\uac1c \uc774\uc0c1 \uc885\ubaa9 \ud544\uc694</p>';
                    return;
                }

                let html = '<table class="corr-heatmap-table"><thead><tr><th></th>';
                for (let i = 0; i < n; i++) {
                    const short = names[i].length > 4 ? names[i].substring(0, 4) + '..' : names[i];
                    html += '<th title="' + names[i] + '">' + short + '</th>';
                }
                html += '</tr></thead><tbody>';

                for (let i = 0; i < n; i++) {
                    html += '<tr><td class="stock-name" title="' + symbols[i] + '">' + names[i] + '</td>';
                    for (let j = 0; j < n; j++) {
                        const val = matrix[i][j];
                        const bg = i === j ? '#21262d' : corrCellColor(val);
                        const text = i === j ? '1.00' : val.toFixed(2);
                        const textColor = i === j ? '#484f58' : (Math.abs(val) > 0.5 ? '#0a0e17' : '#c9d1d9');
                        html += '<td class="corr-cell" style="background:' + bg + ';color:' + textColor + '">' + text + '</td>';
                    }
                    html += '</tr>';
                }
                html += '</tbody></table>';
                el.innerHTML = html;
            } catch(e) {
                console.error('Correlation heatmap error:', e);
                document.getElementById('corrHeatmap').innerHTML = '\ub370\uc774\ud130 \ub85c\ub4dc \uc2e4\ud328. \uc0c8\ub85c\uace0\uce68\ud558\uc138\uc694. <button class="btn btn-sm btn-scan" onclick="loadCorrelationHeatmap()" style="margin-left:8px">\uc7ac\uc2dc\ub3c4</button>';
            }
        }

        async function loadSectorPie() {
            try {
                const r = await fetch('/api/sector-weights');
                const d = await r.json();
                const sectors = d.sectors || [];
                const emptyEl = document.getElementById('sectorPieEmpty');
                const canvas = document.getElementById('sectorPieChart');

                if (!sectors.length) {
                    emptyEl.style.display = 'flex';
                    canvas.style.display = 'none';
                    if (sectorPieChartInst) { sectorPieChartInst.destroy(); sectorPieChartInst = null; }
                    return;
                }
                emptyEl.style.display = 'none';
                canvas.style.display = 'block';

                const labels = sectors.map(s => s.sector + ' (' + s.weight_pct + '%)');
                const data = sectors.map(s => s.weight_pct);
                const colors = sectors.map(s => s.color || '#8b949e');

                if (sectorPieChartInst) sectorPieChartInst.destroy();
                sectorPieChartInst = new Chart(canvas, {
                    type: 'doughnut',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: data,
                            backgroundColor: colors,
                            borderColor: '#161b28',
                            borderWidth: 2,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '50%',
                        plugins: {
                            legend: {
                                display: true,
                                position: 'right',
                                labels: { boxWidth: 10, padding: 6, font: { size: 10 }, color: '#c9d1d9' }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        const sec = sectors[ctx.dataIndex] || {};
                                        const stocks = (sec.stocks || []).join(', ');
                                        return sec.sector + ': ' + sec.weight_pct + '% (' + stocks + ')';
                                    }
                                }
                            }
                        }
                    }
                });
            } catch(e) { console.error('Sector pie error:', e); }
        }

        async function loadPortfolioRisk() {
            try {
                const r = await fetch('/api/portfolio-risk');
                const d = await r.json();

                // Diversification gauge
                const divData = d.diversification || {};
                const score = divData.score || 0;
                const grade = divData.grade || '-';
                const circumference = 2 * Math.PI * 58; // 364.42
                const offset = circumference * (1 - Math.max(0, Math.min(1, score / 100)));
                const gaugeFill = document.getElementById('divGaugeFill');

                let gaugeColor = '#f85149';
                if (score >= 80) gaugeColor = '#3fb950';
                else if (score >= 60) gaugeColor = '#58a6ff';
                else if (score >= 40) gaugeColor = '#d29922';
                else if (score >= 20) gaugeColor = '#f97316';

                gaugeFill.setAttribute('stroke', gaugeColor);
                gaugeFill.setAttribute('stroke-dashoffset', offset.toFixed(2));
                document.getElementById('divScoreValue').textContent = Math.round(score);
                document.getElementById('divScoreValue').style.color = gaugeColor;
                document.getElementById('divScoreGrade').textContent = grade;

                const comps = divData.components || {};
                let compHtml = '';
                const compOrder = ['position_count', 'sector_diversity', 'correlation', 'weight_evenness'];
                const compNames = {
                    'position_count': '\uc885\ubaa9\uc218',
                    'sector_diversity': '\uc139\ud130',
                    'correlation': '\uc0c1\uad00\ub3c4',
                    'weight_evenness': '\uade0\ub4f1\ub3c4'
                };
                for (const key of compOrder) {
                    const c = comps[key];
                    if (c) {
                        compHtml += compNames[key] + ': ' + c.score + '/' + c.max + '&nbsp;&nbsp;';
                    }
                }
                document.getElementById('divScoreComponents').innerHTML = compHtml;

                // Concentration risk
                const concData = d.concentration || {};
                const hhi = concData.hhi_normalized || 0;
                const hhiLevel = concData.risk_level || '-';
                document.getElementById('hhiValue').textContent = (hhi * 100).toFixed(1) + '%';

                let hhiColor = '#3fb950';
                if (hhi >= 0.5) hhiColor = '#f85149';
                else if (hhi >= 0.25) hhiColor = '#f97316';
                else if (hhi >= 0.15) hhiColor = '#d29922';
                document.getElementById('hhiValue').style.color = hhiColor;
                document.getElementById('hhiLevel').textContent = hhiLevel;
                document.getElementById('hhiLevel').style.color = hhiColor;

                const hhiBar = document.getElementById('hhiBar');
                hhiBar.style.width = Math.min(100, hhi * 100).toFixed(1) + '%';
                hhiBar.style.background = hhiColor;

                // Top positions
                const topPos = concData.top_positions || [];
                let topHtml = '<div style="margin-bottom:4px;font-weight:600;color:#8b949e">\uc0c1\uc704 \ubcf4\uc720 \uc885\ubaa9:</div>';
                for (const p of topPos) {
                    const barW = Math.min(100, p.weight_pct);
                    topHtml += '<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">'
                        + '<span style="width:60px;text-align:right;color:#c9d1d9">' + p.name + '</span>'
                        + '<div style="flex:1;height:5px;background:#21262d;border-radius:3px;overflow:hidden">'
                        + '<div style="width:' + barW + '%;height:100%;background:#bc8cff;border-radius:3px"></div></div>'
                        + '<span style="width:36px;font-size:0.7rem;color:#8b949e">' + p.weight_pct + '%</span>'
                        + '</div>';
                }
                document.getElementById('topPositions').innerHTML = topHtml;

                // Alerts
                const alerts = d.alerts || [];
                const alertEl = document.getElementById('prAlerts');
                if (!alerts.length) {
                    alertEl.innerHTML = '<p class="neu" style="font-size:0.78rem;text-align:center;padding:12px">\ud65c\uc131 \uacbd\uace0 \uc5c6\uc74c - \ud3ec\ud2b8\ud3f4\ub9ac\uc624 \uc815\uc0c1</p>';
                } else {
                    let alertHtml = '';
                    for (const a of alerts) {
                        const cls = a.level || 'warning';
                        const icon = cls === 'danger' ? '\u26a0\ufe0f' : cls === 'warning' ? '\u26a1' : '\u2139\ufe0f';
                        const time = a.timestamp ? new Date(a.timestamp).toLocaleTimeString('ko', {hour:'2-digit', minute:'2-digit'}) : '';
                        alertHtml += '<div class="alert-item ' + cls + '">'
                            + '<span class="alert-icon">' + icon + '</span>'
                            + '<span class="alert-text">' + a.message + '</span>'
                            + '<span class="alert-time">' + time + '</span>'
                            + '</div>';
                    }
                    alertEl.innerHTML = alertHtml;
                }

                // Correlation spike indicator
                const spike = d.correlation_spike || {};
                const spikeEl = document.getElementById('prCorrSpike');
                if (spike.spike_detected) {
                    spikeEl.innerHTML = '<span style="color:#f85149;font-weight:600">\u26a0 \uc0c1\uad00\uad00\uacc4 \uae09\ub4f1 (+' + spike.delta.toFixed(3) + ')</span>';
                } else {
                    spikeEl.innerHTML = '<span style="color:#3fb950">\uc815\uc0c1</span>';
                }

                // Rebalancing suggestions
                const rebalance = d.sector_rebalance || {};
                const sugEl = document.getElementById('prSuggestions');
                const suggestions = rebalance.suggestions || [];
                if (!suggestions.length) {
                    sugEl.innerHTML = '<p class="neu" style="font-size:0.75rem">\ub9ac\ubc38\ub7f0\uc2f1 \ud544\uc694 \uc5c6\uc74c</p>';
                } else {
                    let sugHtml = '';
                    for (const s of suggestions) {
                        sugHtml += '<div class="suggestion-item">' + s + '</div>';
                    }
                    sugEl.innerHTML = sugHtml;
                }

                document.getElementById('prLastUpdate').textContent = '\uac31\uc2e0: ' + new Date().toLocaleTimeString('ko');
            } catch(e) { console.error('Portfolio risk error:', e); }
        }

        async function loadCorrelationTrend() {
            try {
                const r = await fetch('/api/correlation-history?days=30');
                const d = await r.json();
                const history = d.history || [];
                const emptyEl = document.getElementById('corrTrendEmpty');
                const canvas = document.getElementById('corrTrendChart');

                if (!history.length) {
                    emptyEl.style.display = 'flex';
                    canvas.style.display = 'none';
                    if (corrTrendChartInst) { corrTrendChartInst.destroy(); corrTrendChartInst = null; }
                    return;
                }
                emptyEl.style.display = 'none';
                canvas.style.display = 'block';

                const labels = history.map(h => { const p = h.date.split('-'); return p[1] + '-' + p[2]; });
                const corrData = history.map(h => h.avg_correlation || 0);
                const hhiData = history.map(h => h.hhi_normalized || 0);

                if (corrTrendChartInst) corrTrendChartInst.destroy();
                corrTrendChartInst = new Chart(canvas, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: '\ud3c9\uade0 \uc0c1\uad00\uacc4\uc218',
                                data: corrData,
                                borderColor: '#bc8cff',
                                backgroundColor: 'rgba(188,140,255,0.08)',
                                fill: true,
                                tension: 0.3,
                                pointRadius: 2,
                                borderWidth: 2,
                                yAxisID: 'y',
                            },
                            {
                                label: 'HHI (\uc9d1\uc911\ub3c4)',
                                data: hhiData,
                                borderColor: '#f97316',
                                backgroundColor: 'transparent',
                                tension: 0.3,
                                pointRadius: 2,
                                borderWidth: 1.5,
                                borderDash: [4, 3],
                                yAxisID: 'y1',
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: { display: true, position: 'top', labels: { boxWidth: 10, padding: 6, font: { size: 9 } } },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        return ctx.dataset.label + ': ' + ctx.raw.toFixed(3);
                                    }
                                }
                            }
                        },
                        scales: {
                            x: { grid: { display: false }, ticks: { maxTicksLimit: 10, font: { size: 9 } } },
                            y: { position: 'left', min: -1, max: 1, grid: { color: '#21262d' },
                                 ticks: { font: { size: 9 }, callback: v => v.toFixed(1) },
                                 title: { display: true, text: '\uc0c1\uad00\uacc4\uc218', font: { size: 9 } } },
                            y1: { position: 'right', min: 0, max: 1, grid: { display: false },
                                  ticks: { font: { size: 9 }, callback: v => v.toFixed(1) },
                                  title: { display: true, text: 'HHI', font: { size: 9 } } }
                        }
                    }
                });
            } catch(e) { console.error('Correlation trend error:', e); }
        }

        async function loadDivTrend() {
            try {
                const r = await fetch('/api/correlation-history?days=30');
                const d = await r.json();
                const history = d.history || [];
                const emptyEl = document.getElementById('divTrendEmpty');
                const canvas = document.getElementById('divTrendChart');

                if (!history.length) {
                    emptyEl.style.display = 'flex';
                    canvas.style.display = 'none';
                    if (divTrendChartInst) { divTrendChartInst.destroy(); divTrendChartInst = null; }
                    return;
                }
                emptyEl.style.display = 'none';
                canvas.style.display = 'block';

                const labels = history.map(h => { const p = h.date.split('-'); return p[1] + '-' + p[2]; });
                const divData = history.map(h => h.diversification_score || 0);
                const sectorData = history.map(h => h.sector_count || 0);

                if (divTrendChartInst) divTrendChartInst.destroy();
                divTrendChartInst = new Chart(canvas, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: '\ubd84\uc0b0\ud22c\uc790 \uc810\uc218',
                                data: divData,
                                borderColor: '#3fb950',
                                backgroundColor: 'rgba(63,185,80,0.08)',
                                fill: true,
                                tension: 0.3,
                                pointRadius: 2,
                                borderWidth: 2,
                                yAxisID: 'y',
                            },
                            {
                                label: '\uc139\ud130 \uc218',
                                data: sectorData,
                                borderColor: '#58a6ff',
                                backgroundColor: 'transparent',
                                tension: 0.3,
                                pointRadius: 2,
                                borderWidth: 1.5,
                                yAxisID: 'y1',
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: { display: true, position: 'top', labels: { boxWidth: 10, padding: 6, font: { size: 9 } } },
                        },
                        scales: {
                            x: { grid: { display: false }, ticks: { maxTicksLimit: 10, font: { size: 9 } } },
                            y: { position: 'left', min: 0, max: 100, grid: { color: '#21262d' },
                                 ticks: { font: { size: 9 } },
                                 title: { display: true, text: '\uc810\uc218', font: { size: 9 } } },
                            y1: { position: 'right', min: 0, grid: { display: false },
                                  ticks: { font: { size: 9 }, stepSize: 1 },
                                  title: { display: true, text: '\uc139\ud130', font: { size: 9 } } }
                        }
                    }
                });
            } catch(e) { console.error('Diversification trend error:', e); }
        }

        function loadAllPortfolioRisk() {
            loadCorrelationHeatmap();
            loadSectorPie();
            loadPortfolioRisk();
            loadCorrelationTrend();
            loadDivTrend();
        }

        /* ========== Execution Engine Section ========== */
        let slippageHistChartInst = null;

        async function loadExecutionStats() {
            try {
                const res = await fetch('/api/execution/stats');
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const data = await res.json();
                const s = data.stats || {};
                document.getElementById('execTotalOrders').textContent = (s.total_orders || 0).toLocaleString();
                document.getElementById('execFilledOrders').textContent = (s.filled_orders || 0).toLocaleString();
                document.getElementById('execFailedOrders').textContent = (s.failed_orders || 0).toLocaleString();
                const avgSlip = s.avg_slippage_bps || 0;
                const slipEl = document.getElementById('execAvgSlippage');
                slipEl.textContent = avgSlip.toFixed(1) + 'bp';
                slipEl.className = 'value ' + (avgSlip > 30 ? 'pos' : avgSlip > 10 ? 'yellow' : 'green');
                document.getElementById('execTotalVolume').textContent = (s.total_volume || 0).toLocaleString();
                document.getElementById('execActiveOrders').textContent = (s.active_orders || 0).toLocaleString();

                // Active orders list
                const activeList = document.getElementById('execActiveList');
                const orders = data.active_orders || [];
                if (orders.length === 0) {
                    activeList.innerHTML = '<p class="neu" style="font-size:0.82rem">\ud65c\uc131 \uc8fc\ubb38 \uc5c6\uc74c</p>';
                } else {
                    activeList.innerHTML = orders.map(o => {
                        const fillPct = ((o.fill_rate || 0) * 100).toFixed(0);
                        const sideClass = o.side === 'BUY' ? 'badge-buy' : 'badge-sell';
                        const sideKo = o.side === 'BUY' ? '\ub9e4\uc218' : '\ub9e4\ub3c4';
                        const safeSymbol = escapeHtml(o.symbol);
                        const safeType = escapeHtml(o.order_type);
                        return `<div class="active-order-item">
                            <div>
                                <span class="ao-symbol">${safeSymbol}</span>
                                <span class="ao-type">${safeType}</span>
                                <span class="badge ${sideClass}" style="margin-left:4px">${sideKo}</span>
                            </div>
                            <div class="ao-progress">
                                ${parseInt(o.filled_qty) || 0}/${parseInt(o.total_qty) || 0}\uc8fc
                                <div class="ao-bar"><div class="ao-bar-fill" style="width:${fillPct}%"></div></div>
                                ${fillPct}%
                            </div>
                        </div>`;
                    }).join('');
                }

                document.getElementById('execLastUpdate').textContent = '\uac31\uc2e0: ' + new Date().toLocaleTimeString('ko-KR');
            } catch(e) {
                console.error('Exec stats error:', e);
                document.getElementById('execActiveList').innerHTML = '\ub370\uc774\ud130 \ub85c\ub4dc \uc2e4\ud328. \uc0c8\ub85c\uace0\uce68\ud558\uc138\uc694. <button class="btn btn-sm btn-scan" onclick="loadExecutionStats()" style="margin-left:8px">\uc7ac\uc2dc\ub3c4</button>';
            }
        }

        async function loadExecutionHistory() {
            try {
                const res = await fetch('/api/execution/history?days=30');
                const data = await res.json();
                const summary = data.summary || {};

                // Execution quality gauge
                const fillRate = summary.fill_rate_pct || 0;
                const circumference = 314.16;
                const offset = circumference * (1 - Math.max(0, Math.min(1, fillRate / 100)));
                const gaugeFill = document.getElementById('eqGaugeFill');
                gaugeFill.setAttribute('stroke-dashoffset', offset.toFixed(2));
                const gaugeColor = fillRate >= 90 ? '#3fb950' : fillRate >= 70 ? '#d29922' : '#f85149';
                gaugeFill.setAttribute('stroke', gaugeColor);
                document.getElementById('eqGaugeValue').textContent = fillRate.toFixed(0) + '%';
                document.getElementById('eqGaugeValue').style.color = gaugeColor;

                document.getElementById('eqFillRate').textContent = fillRate.toFixed(1) + '%';
                document.getElementById('eqAvgSlip').textContent = (summary.avg_slippage_bps || 0).toFixed(1) + 'bp';
                document.getElementById('eqBestSlip').textContent = (summary.min_slippage_bps || 0).toFixed(1) + 'bp';
                document.getElementById('eqWorstSlip').textContent = (summary.max_slippage_bps || 0).toFixed(1) + 'bp';

                // Slippage histogram
                const dist = data.slippage_distribution || {};
                const bins = dist.bins || [];
                const counts = dist.counts || [];
                const histCanvas = document.getElementById('slippageHistChart');
                const histEmpty = document.getElementById('slippageHistEmpty');

                if (bins.length > 0 && counts.some(c => c > 0)) {
                    histEmpty.style.display = 'none';
                    histCanvas.style.display = 'block';
                    if (slippageHistChartInst) slippageHistChartInst.destroy();
                    slippageHistChartInst = new Chart(histCanvas.getContext('2d'), {
                        type: 'bar',
                        data: {
                            labels: bins.map(b => b + 'bp'),
                            datasets: [{
                                data: counts,
                                backgroundColor: bins.map(b => {
                                    const v = parseInt(b);
                                    if (v <= -20) return '#f8514988';
                                    if (v < 0) return '#d2992288';
                                    if (v === 0) return '#3fb95088';
                                    return '#58a6ff88';
                                }),
                                borderColor: bins.map(b => {
                                    const v = parseInt(b);
                                    if (v <= -20) return '#f85149';
                                    if (v < 0) return '#d29922';
                                    if (v === 0) return '#3fb950';
                                    return '#58a6ff';
                                }),
                                borderWidth: 1,
                            }]
                        },
                        options: {
                            responsive: true, maintainAspectRatio: false,
                            plugins: { legend: { display: false },
                                tooltip: { callbacks: { label: ctx => ctx.raw + '\uac74' } } },
                            scales: {
                                x: { ticks: { color: '#8b949e', font: { size: 9 } }, grid: { display: false } },
                                y: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } }
                            }
                        }
                    });
                } else {
                    histCanvas.style.display = 'none';
                    histEmpty.style.display = 'flex';
                }

                // Daily breakdown table
                const daily = data.daily_breakdown || [];
                const tbody = document.getElementById('execDailyTable');
                if (daily.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="neu">\ub370\uc774\ud130 \uc5c6\uc74c</td></tr>';
                } else {
                    tbody.innerHTML = daily.slice(-15).reverse().map(d => {
                        const slipClass = (d.avg_slippage_bps || 0) > 30 ? 'pos' : (d.avg_slippage_bps || 0) > 10 ? 'yellow' : 'green';
                        const fr = ((d.avg_fill_rate || 0) * 100).toFixed(0);
                        return `<tr>
                            <td>${d.date || '-'}</td>
                            <td>${d.total_orders || 0}</td>
                            <td class="green">${d.filled_orders || 0}</td>
                            <td class="pos">${d.failed_orders || 0}</td>
                            <td class="${slipClass}">${(d.avg_slippage_bps || 0).toFixed(1)}bp</td>
                            <td>${fr}%</td>
                        </tr>`;
                    }).join('');
                }
            } catch(e) { console.error('Exec history error:', e); }
        }

        async function loadVolumeProfile(symbol) {
            if (!symbol) {
                document.getElementById('execVolumeProfile').innerHTML = '<p class="neu" style="font-size:0.82rem">\uc885\ubaa9 \uc120\ud0dd \uc2dc \ud45c\uc2dc</p>';
                return;
            }
            try {
                const res = await fetch('/api/execution/volume-profile/' + symbol);
                const data = await res.json();
                const buckets = data.buckets || [];
                if (buckets.length === 0) {
                    document.getElementById('execVolumeProfile').innerHTML = '<p class="neu" style="font-size:0.82rem">\ud504\ub85c\ud544 \ub370\uc774\ud130 \uc5c6\uc74c</p>';
                    return;
                }
                const maxWeight = Math.max(...buckets.map(b => b.weight));
                let html = buckets.map(b => {
                    const pct = maxWeight > 0 ? (b.weight / maxWeight * 100).toFixed(0) : 0;
                    const wpct = (b.weight * 100).toFixed(1);
                    return `<div class="vp-bar-row">
                        <span class="vp-label">${b.label}</span>
                        <div class="vp-bar"><div class="vp-bar-fill" style="width:${pct}%"></div></div>
                        <span class="vp-pct">${wpct}%</span>
                    </div>`;
                }).join('');
                html += `<div style="margin-top:8px;font-size:0.72rem;color:#8b949e">
                    \ud3c9\uade0 \uc77c\uac70\ub798\ub7c9: <span style="color:#c9d1d9;font-weight:600">${Math.round(data.avg_daily_volume || 0).toLocaleString()}</span>
                    | \uc18c\uc2a4: <span style="color:#c9d1d9">${data.profile_source || '-'}</span>
                </div>`;
                document.getElementById('execVolumeProfile').innerHTML = html;
            } catch(e) { console.error('VP error:', e); }
        }

        // Populate symbol selector for volume profile
        function populateVPSymbolSelect() {
            const sel = document.getElementById('vpSymbolSelect');
            const watchlist = [
                {code:'005930',name:'\uc0bc\uc131\uc804\uc790'},{code:'000660',name:'SK\ud558\uc774\ub2c9\uc2a4'},
                {code:'035420',name:'NAVER'},{code:'035720',name:'\uce74\uce74\uc624'},
                {code:'051910',name:'LG\ud654\ud559'},{code:'006400',name:'\uc0bc\uc131SDI'},
                {code:'003670',name:'\ud3ec\uc2a4\ucf54\ud4e8\uccd0\uc5e0'},{code:'028260',name:'\uc0bc\uc131\ubb3c\uc0b0'},
                {code:'105560',name:'KB\uae08\uc735'},{code:'055550',name:'\uc2e0\ud55c\uc9c0\uc8fc'},
                {code:'005380',name:'\ud604\ub300\uc790\ub3d9\ucc28'},{code:'000270',name:'\uae30\uc544'},
                {code:'207940',name:'\uc0bc\uc131\ubc14\uc774\uc624\ub85c\uc9c1\uc2a4'},{code:'068270',name:'\uc140\ud2b8\ub9ac\uc628'},
                {code:'373220',name:'LG\uc5d0\ub108\uc9c0\uc194\ub8e8\uc158'}
            ];
            watchlist.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.code;
                opt.textContent = s.name + ' (' + s.code + ')';
                sel.appendChild(opt);
            });
            sel.addEventListener('change', () => loadVolumeProfile(sel.value));
        }

        function loadAllExecution() {
            loadExecutionStats();
            loadExecutionHistory();
        }

        populateVPSymbolSelect();

        /* ========== Chart resize handler ========== */
        window.addEventListener('resize', () => {
            const charts = [equityChartInst, dailyPnlChartInst, strategyChartInst, distChartInst,
                            rollingChartInst, regimeTimelineChartInst, sectorPieChartInst,
                            corrTrendChartInst, divTrendChartInst, slippageHistChartInst];
            charts.forEach(c => { if (c) c.resize(); });
        });

        /* ========== Initialize ========== */
        fetchStatus(); fetchStats(); loadAllCharts(); loadAllStrategyAnalysis(); loadAllRegimeData(); loadAllPortfolioRisk(); loadAllExecution();
        setInterval(fetchStatus, 15000);
        setInterval(fetchStats, 60000);
        setInterval(loadAllCharts, 120000);
        setInterval(loadAllStrategyAnalysis, 120000);
        setInterval(loadAllRegimeData, 120000);
        setInterval(loadAllPortfolioRisk, 120000);
        setInterval(loadAllExecution, 30000);
    </script>
<div id="glossaryModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:9999;justify-content:center;align-items:center" onclick="if(event.target===this)this.style.display='none'">
<div style="background:#161b28;border:1px solid #21262d;border-radius:12px;max-width:850px;width:92%;max-height:88vh;overflow-y:auto;padding:24px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
<h2 style="color:#58a6ff;font-size:1.2rem">📖 주식 용어 사전 (초심자용)</h2>
<button onclick="this.parentElement.parentElement.parentElement.style.display='none'" style="background:none;border:none;color:#8b949e;font-size:1.5rem;cursor:pointer">&times;</button>
</div>
<div style="font-size:0.85rem;line-height:1.8;color:#c9d1d9">

<h3 style="color:#3fb950;margin:12px 0 6px;font-size:0.95rem">🎯 매매 신호</h3>
<p><b style="color:#3fb950">BUY (매수)</b> — 종합 점수가 기준(58점) 이상일 때 "사세요" 신호. 5개 전략의 가중 평균 점수가 높으면 발생합니다.</p>
<p><b style="color:#f85149">SELL (매도)</b> — 종합 점수가 42점 이하일 때 "파세요" 신호. 또는 손절(-5%)/익절(+15%) 조건 충족 시.</p>
<p><b style="color:#8b949e">HOLD (보류)</b> — 42~58점 사이. 뚜렷한 방향이 없어 지켜보는 구간.</p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #3fb950;margin:6px 0">
<b>종합 점수 계산:</b><br>
최종점수 = 평균회귀×25% + 추세×20% + 모멘텀×20% + 거래량×20% + 변동성×15%<br>
예) 평균회귀 70 × 0.25 + 추세 60 × 0.20 + 모멘텀 55 × 0.20 + 거래량 50 × 0.20 + 변동성 65 × 0.15 = <b>60.25점 → BUY</b><br>
※ 시장 국면(상승/하락/횡보)에 따라 가중치가 자동 조정됩니다
</p>

<h3 style="color:#58a6ff;margin:16px 0 6px;font-size:0.95rem">📊 5대 전략 상세 (수학 공식 포함)</h3>

<p><b style="color:#d29922;font-size:0.95rem">1. 평균회귀 (Mean Reversion) — 가중치 25%</b></p>
<p>"많이 빠진 건 다시 오르고, 많이 오른 건 빠진다"는 원리.</p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #d29922;margin:6px 0">
<b>RSI (상대강도지수):</b><br>
RS = (14일간 평균 상승폭) ÷ (14일간 평균 하락폭)<br>
RSI = 100 - (100 ÷ (1 + RS))<br>
→ 30 이하: "너무 빠졌다" = 매수 기회 / 70 이상: "너무 올랐다" = 주의<br><br>
<b>볼린저밴드 %B:</b><br>
중심선 = 20일 이동평균<br>
상단 = 중심선 + (20일 표준편차 × 2)<br>
하단 = 중심선 - (20일 표준편차 × 2)<br>
%B = (현재가격 - 하단) ÷ (상단 - 하단)<br>
→ 0 이하: 밴드 아래 = 싸다 / 1 이상: 밴드 위 = 비싸다<br><br>
<b>점수화:</b> RSI와 %B를 Z-score(표준화)로 변환 후 50점 기준으로 환산
</p>

<p><b style="color:#d29922;font-size:0.95rem">2. 추세추종 (Trend Following) — 가중치 20%</b></p>
<p>"오르는 주식은 계속 오른다"는 원리.</p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #d29922;margin:6px 0">
<b>MACD:</b><br>
MACD선 = 12일 이동평균 - 26일 이동평균<br>
시그널선 = MACD의 9일 이동평균<br>
히스토그램 = MACD선 - 시그널선<br>
→ MACD가 시그널 위로 교차 = 골든크로스(매수 신호)<br>
→ MACD가 시그널 아래로 교차 = 데드크로스(매도 신호)<br><br>
<b>MA 정배열 점수:</b><br>
5일선 > 20일선 → +25점<br>
20일선 > 60일선 → +25점<br>
60일선 > 120일선 → +25점<br>
현재가 > 5일선 → +25점<br>
→ 정배열 = 100점(강한 상승), 역배열 = 0점(강한 하락)<br><br>
<b>이동평균(MA) 계산:</b><br>
MA(N) = 최근 N일 종가의 합 ÷ N<br>
예) 5일 MA = (오늘 + 어제 + ... + 4일전 종가) ÷ 5
</p>

<p><b style="color:#d29922;font-size:0.95rem">3. 한국형 모멘텀 (Korean Momentum) — 가중치 20%</b></p>
<p>한국 시장의 "역전 효과" 반영. 최근 급등주는 단기 하락 가능성 평가.</p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #d29922;margin:6px 0">
<b>20일 수익률:</b> (오늘 종가 - 20일 전 종가) ÷ 20일 전 종가 × 100<br>
<b>60일 수익률:</b> (오늘 종가 - 60일 전 종가) ÷ 60일 전 종가 × 100<br><br>
→ 20일 수익률이 너무 높으면(예: +30%) 점수 하락 (과열 주의)<br>
→ 적당한 상승(5~15%)이면 점수 상승 (건강한 모멘텀)<br><br>
<b>폭락 가드:</b> 20일간 -25% 이상 하락한 종목은 자동으로 매수 차단<br>
→ "떨어지는 칼날을 잡지 마라"는 원칙
</p>

<p><b style="color:#d29922;font-size:0.95rem">4. 거래량 (Volume Analysis) — 가중치 20%</b></p>
<p>거래량은 주가의 "연료". 거래량 없는 상승은 지속되기 어렵습니다.</p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #d29922;margin:6px 0">
<b>거래량 비율:</b> 오늘 거래량 ÷ 20일 평균 거래량<br>
→ 1.5 이상이면서 상승 = 강한 매수세 (긍정)<br>
→ 1.5 이상이면서 하락 = 강한 매도세 (부정)<br><br>
<b>OBV (On-Balance Volume):</b><br>
상승한 날: OBV = 전일 OBV + 오늘 거래량<br>
하락한 날: OBV = 전일 OBV - 오늘 거래량<br>
→ OBV가 상승 추세이면 = 매수세력이 모이는 중<br>
→ OBV가 하락 추세이면 = 매도세력이 빠지는 중
</p>

<p><b style="color:#d29922;font-size:0.95rem">5. 변동성 (Volatility) — 가중치 15%</b></p>
<p>가격 변동 폭이 줄어들면 안정, 늘어나면 위험.</p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #d29922;margin:6px 0">
<b>변동성 계산:</b><br>
일간 수익률 = (오늘 종가 - 어제 종가) ÷ 어제 종가<br>
N일 변동성 = 최근 N일 일간수익률의 표준편차 × √252<br>
(252 = 1년 거래일 수, 연율화)<br><br>
<b>변동성 비율:</b> 20일 변동성 ÷ 60일 변동성<br>
→ 1 미만: 최근 변동이 줄어듦 = 안정적 (긍정)<br>
→ 1 이상: 최근 변동이 늘어남 = 불안정 (부정)<br><br>
예) 20일 변동성 15%, 60일 변동성 20% → 비율 0.75 = 안정화 중 ✓
</p>

<h3 style="color:#f85149;margin:16px 0 6px;font-size:0.95rem">🛡️ 리스크 관리</h3>
<p><b>손절 (Stop Loss) -5%</b> — 매수가 대비 -5% 하락 시 자동 전량 매도.</p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #f85149;margin:6px 0">
예) 삼성전자 60,000원에 매수 → 57,000원(-5%)이면 자동 매도<br>
왜?: 작은 손실에서 끊어야 큰 손실 방지. -50%가 되면 원금 회복에 +100% 필요!
</p>
<p><b>익절 (Take Profit) +15%</b> — 매수가 대비 +15% 수익 시 전량 매도.</p>
<p><b>트레일링 스탑 (Trailing Stop) -5%</b> — 보유 중 최고가 기준 -5% 하락 시 매도.</p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #f85149;margin:6px 0">
예) 60,000원 매수 → 70,000원까지 상승(최고가 갱신)<br>
→ 트레일링 기준 = 70,000 × 0.95 = 66,500원<br>
→ 66,500원 이하로 떨어지면 매도 (수익 +10.8% 확보)<br>
핵심: 상승할 때는 따라가고, 하락 전환 시 수익을 지켜줌
</p>
<p><b>서킷브레이커</b> — 하루 -3% 손실 / 연속 5패 / 일 20거래 초과 시 자동 매매 중단 (30분 쿨다운).</p>

<h3 style="color:#d29922;margin:16px 0 6px;font-size:0.95rem">📈 시장 국면 (Regime)</h3>
<p><b style="color:#3fb950">BULL (상승장)</b> — 주가가 이동평균선 위, ADX 25+ 추세 강도. 추세추종 가중치↑</p>
<p><b style="color:#f85149">BEAR (하락장)</b> — 주가가 이동평균선 아래, 하락 추세. 평균회귀·변동성 가중치↑</p>
<p><b style="color:#d29922">SIDEWAYS (횡보장)</b> — 뚜렷한 방향 없이 좁은 범위에서 등락 반복. 평균회귀·거래량 가중치↑</p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #d29922;margin:6px 0">
<b>국면 판단 기준:</b><br>
1) 현재가가 50일 MA 위? → 상승 경향<br>
2) 50일 MA가 200일 MA 위? → 장기 상승 추세<br>
3) ADX > 25? → 추세가 뚜렷함<br>
4) 변동성이 높은가? → 급등/급락 구간<br><br>
<b>ADX (Average Directional Index) 계산:</b><br>
+DI = 상승 방향 움직임의 14일 평균<br>
-DI = 하락 방향 움직임의 14일 평균<br>
ADX = |+DI - -DI| ÷ (+DI + -DI)의 14일 평균 × 100<br>
→ 20 미만: 추세 없음(횡보) / 25~50: 추세 있음 / 50+: 매우 강한 추세
</p>

<h3 style="color:#58a6ff;margin:16px 0 6px;font-size:0.95rem">📐 성과 지표 (수학 공식)</h3>
<p><b>수익률 (Return)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
수익률(%) = (현재 자산 - 초기 자본) ÷ 초기 자본 × 100<br>
예) 초기 200만원, 현재 230만원 → (230-200)÷200×100 = <b>+15%</b>
</p>

<p><b>승률 (Win Rate)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
승률(%) = 수익 거래 수 ÷ 전체 매도 수 × 100<br>
예) 10번 매도 중 6번 수익 → 60% 승률<br>
※ 승률이 높아도 1번의 큰 손실이 있으면 전체 수익이 마이너스일 수 있음<br>
→ 그래서 샤프 비율과 PF를 함께 봐야 합니다
</p>

<p><b>MDD (Maximum Drawdown, 최대 낙폭)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
MDD = (최저점 - 최고점) ÷ 최고점 × 100<br>
예) 자산이 250만원(최고)까지 올랐다가 225만원(최저)까지 빠짐<br>
→ (225-250)÷250×100 = <b>-10% MDD</b><br>
의미: "최악의 경우 10%까지 떨어질 수 있다"<br>
-5% 이내면 안정적, -10% 이상이면 변동성 큰 전략
</p>

<p><b>샤프 비율 (Sharpe Ratio)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
샤프 = (평균 수익률 - 무위험 수익률) ÷ 수익률의 표준편차<br><br>
쉽게: "1%를 벌기 위해 얼마나 출렁거렸는가?"<br>
→ 평균 수익 10%, 표준편차 5% → 샤프 = 10÷5 = <b>2.0 (우수)</b><br>
→ 평균 수익 10%, 표준편차 20% → 샤프 = 10÷20 = <b>0.5 (불안정)</b><br><br>
판단 기준: 0 이하 = 나쁨 / 0~1 = 보통 / 1~2 = 양호 / 2+ = 우수
</p>

<p><b>PF (Profit Factor, 손익비)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
PF = 총 수익 금액 ÷ 총 손실 금액<br>
예) 수익 합계 50만원, 손실 합계 30만원 → PF = 50÷30 = <b>1.67</b><br>
→ 1 미만: 손실이 더 큼 / 1.0: 본전 / 1.5+: 양호 / 2+: 우수
</p>

<p><b>롤링 승률 (Rolling Win Rate)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
최근 N건의 거래만 보고 승률을 계산한 것 (이동 승률)<br>
예) 최근 10건 중 7건 수익 → 롤링 승률 70%<br>
→ 전체 승률은 55%여도 최근 롤링이 70%면 = 전략이 최근에 잘 맞고 있음<br>
→ 반대로 롤링이 30%로 떨어지면 = 전략이 현재 시장에 안 맞고 있음
</p>

<h3 style="color:#58a6ff;margin:16px 0 6px;font-size:0.95rem">🔧 기술적 용어</h3>

<p><b>Z-score (표준화 점수)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
Z = (현재값 - 평균) ÷ 표준편차<br>
→ "지금 값이 평소와 얼마나 다른가?"<br>
예) RSI 평균 50, 표준편차 10, 현재 RSI 30 → Z = (30-50)÷10 = <b>-2.0</b><br>
→ -2 이하: 극단적으로 낮음(매수 기회) / +2 이상: 극단적으로 높음(매도 기회)<br>
본 시스템에서는 Z-score를 tanh 함수로 변환해 50점 기준 0~100점으로 환산합니다
</p>

<p><b>표준편차 (Standard Deviation)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
"평균에서 얼마나 퍼져있는가" = 변동 폭의 크기<br>
예) A주식 수익률: +1%, +2%, -1%, +1% → 표준편차 작음 (안정적)<br>
예) B주식 수익률: +10%, -8%, +12%, -15% → 표준편차 큼 (변동 심함)
</p>

<h3 style="color:#58a6ff;margin:16px 0 6px;font-size:0.95rem">🏗️ 포트폴리오 관리</h3>
<p><b>상관관계 (Correlation)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
-1 ~ +1 사이 값. 두 종목이 얼마나 같이 움직이는지<br>
+1: 완전히 같이 움직임 (분산 효과 없음, 위험)<br>
0: 관계 없음 (이상적인 분산)<br>
-1: 반대로 움직임 (완벽한 헷지)<br>
예) 삼성전자↔SK하이닉스 = 0.85 (둘 다 반도체, 같이 움직임 → 위험)<br>
예) 삼성전자↔KB금융 = 0.2 (다른 산업, 분산 효과 좋음)
</p>

<p><b>HHI (허핀달-허쉬만 지수, 집중도)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
HHI = 각 종목 비중(%)의 제곱의 합<br>
예) 2종목, 50%씩 → 50² + 50² = <b>5,000</b><br>
예) 4종목, 25%씩 → 25²×4 = <b>2,500</b> (더 분산됨)<br>
예) 1종목 100% → 100² = <b>10,000</b> (최대 집중, 위험)<br>
→ 낮을수록 잘 분산된 포트폴리오
</p>

<p><b>슬리피지 (Slippage)</b></p>
<p style="background:#1c2333;padding:8px 12px;border-radius:6px;border-left:3px solid #58a6ff;margin:6px 0">
주문 가격과 실제 체결 가격의 차이<br>
예) 60,000원에 매수 주문 → 60,050원에 체결 → 슬리피지 +0.08%<br>
→ 양수: 불리하게 체결 / 음수: 유리하게 체결 / 0에 가까울수록 좋음
</p>

</div>
</div>
</div>
</body>
</html>
"""

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print("=" * 50)
    print(f"  StockBot v3.5 Dashboard")
    print(f"  http://localhost:{DASHBOARD_PORT}")
    print("=" * 50)
    uvicorn.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT)
