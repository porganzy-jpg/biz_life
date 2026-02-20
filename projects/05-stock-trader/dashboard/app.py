"""
StockBot v2.1 대시보드
8전략 앙상블 + 뉴스감성 + 서킷브레이커 + 일일성과 + 시장국면감지
+ 성과 차트 (Equity Curve, Daily PnL, Strategy Stats, Trade Distribution)
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-bot"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "strategy"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "news"))

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import uvicorn

from trader import StockTrader
from database import get_connection
from config import DASHBOARD_HOST, DASHBOARD_PORT, WATCHLIST

from datetime import datetime, timedelta

from backtest_portal import backtest_router

app = FastAPI(title="StockBot v2.1 Dashboard")
app.include_router(backtest_router)
trader = StockTrader(paper_trading=False)


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


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockBot v2.1</title>
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

        @media (max-width: 900px) {
            .grid-2 { grid-template-columns: 1fr; }
            .perf-grid { grid-template-columns: 1fr; }
            .perf-right { grid-template-rows: auto auto; }
            .perf-grid-bottom { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>StockBot v2.1</h1>
        <div class="header-right">
            <a href="/backtest" style="color:#58a6ff;text-decoration:none;font-size:0.85rem;padding:4px 12px;border:1px solid #1f6feb;border-radius:6px;margin-right:10px;">Backtest</a>
            <span class="refresh-info" id="lastUpdate">-</span>
            <span class="mode mode-paper" id="modeTag">Loading...</span>
        </div>
    </div>
    <div class="container">
        <div class="circuit-alert" id="circuitAlert">
            <span style="font-size:1.2rem">&#x1F6A8;</span>
            <div><b>Circuit Breaker</b> <span id="cbReason"></span>
            <button class="btn btn-sm btn-stop" onclick="resetCB()" style="margin-left:8px">Reset</button></div>
        </div>
        <div class="controls">
            <button class="btn btn-start" onclick="startBot()">Start Auto</button>
            <button class="btn btn-stop" onclick="stopBot()">Stop</button>
            <button class="btn btn-scan" onclick="scanAll()">Scan Watchlist</button>
            <button class="btn btn-cycle" onclick="runCycle()">Run 1 Cycle</button>
            <span id="schedInfo" class="refresh-info" style="margin-left:auto"></span>
        </div>
        <div class="card" style="margin-bottom:12px">
            <h2>Market Regime</h2>
            <div class="regime-panel">
                <span class="badge-regime regime-sideways" id="regimeBadge">SIDEWAYS</span>
                <div class="regime-detail">ADX: <span id="regimeADX">-</span></div>
                <div class="regime-detail">Volatility: <span id="regimeVol">-</span></div>
                <div class="regime-detail">20D Return: <span id="regimeReturn">-</span></div>
                <div class="regime-detail">MA Diff: <span id="regimeMaDiff">-</span></div>
                <div class="regime-detail" id="regimeSince" style="margin-left:auto"></div>
            </div>
            <div id="regimeWeights" style="margin-top:10px;font-size:0.75rem;color:#8b949e"></div>
        </div>
        <div class="grid-6">
            <div class="card stat-card"><div class="label">Total Assets</div><div class="value accent" id="totalAssets">-</div></div>
            <div class="card stat-card"><div class="label">Cash</div><div class="value" id="cash">-</div></div>
            <div class="card stat-card"><div class="label">Total PnL</div><div class="value" id="totalPnl">-</div></div>
            <div class="card stat-card"><div class="label">Positions</div><div class="value" id="posCount">0</div></div>
            <div class="card stat-card"><div class="label">Win Rate (30d)</div><div class="value green" id="winRate">-</div></div>
            <div class="card stat-card"><div class="label">Regime</div><div class="value" id="regimeStat">-</div></div>
        </div>

        <!-- Performance Charts Section -->
        <div class="perf-section">
            <div class="section-header">
                <span class="section-title">Performance</span>
                <div class="period-selector">
                    <button class="period-btn" data-period="1W" onclick="setPeriod('1W')">1W</button>
                    <button class="period-btn" data-period="1M" onclick="setPeriod('1M')">1M</button>
                    <button class="period-btn" data-period="3M" onclick="setPeriod('3M')">3M</button>
                    <button class="period-btn active" data-period="ALL" onclick="setPeriod('ALL')">ALL</button>
                </div>
            </div>
            <div class="perf-grid">
                <div class="card">
                    <h2>Equity Curve</h2>
                    <div class="chart-container large">
                        <canvas id="equityChart"></canvas>
                        <div class="chart-empty" id="equityEmpty">No equity data available yet</div>
                    </div>
                </div>
                <div class="perf-right">
                    <div class="card">
                        <h2>Daily P&amp;L</h2>
                        <div class="chart-container medium">
                            <canvas id="dailyPnlChart"></canvas>
                            <div class="chart-empty" id="pnlEmpty">No trade data available yet</div>
                        </div>
                    </div>
                    <div class="card">
                        <h2>Strategy Win Contribution</h2>
                        <div class="chart-container medium">
                            <canvas id="strategyChart"></canvas>
                            <div class="chart-empty" id="strategyEmpty">No strategy data available yet</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="perf-grid-bottom">
                <div class="card">
                    <h2>Trade Return Distribution</h2>
                    <div class="chart-container" style="height:200px">
                        <canvas id="distChart"></canvas>
                        <div class="chart-empty" id="distEmpty">No trade data available yet</div>
                    </div>
                </div>
                <div class="card">
                    <h2>Strategy Win Rates</h2>
                    <div class="scroll-table" id="strategyTable">
                        <p class="neu">Loading strategy data...</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="grid-2">
            <div class="card">
                <h2>Watchlist Analysis</h2>
                <div class="scroll-table">
                <table><thead><tr><th>Name</th><th>Score</th><th>Action</th><th>Price</th><th>Sentiment</th><th>Reasons</th></tr></thead>
                <tbody id="scanResults"><tr><td colspan="6" class="neu">Click "Scan Watchlist"</td></tr></tbody></table>
                </div>
            </div>
            <div class="card">
                <h2>Positions</h2>
                <div class="scroll-table" id="positions"><p class="neu">No positions</p></div>
            </div>
        </div>
        <div class="grid-2">
            <div class="card">
                <h2>Recent Trades</h2>
                <div class="scroll-table">
                <table><thead><tr><th>Time</th><th>Action</th><th>Name</th><th>Qty</th><th>Price</th><th>PnL</th></tr></thead>
                <tbody id="recentTrades"></tbody></table>
                </div>
            </div>
            <div class="card">
                <h2>Trade Statistics</h2>
                <div id="tradeStats" class="neu">Loading...</div>
            </div>
        </div>
    </div>
    <script>
        const fmt = n => n ? n.toLocaleString('ko-KR') : '0';
        const fmtW = n => { if(!n) return '0'; if(Math.abs(n)>=1e8) return (n/1e8).toFixed(1)+'\\uc5b5'; if(Math.abs(n)>=1e4) return (n/1e4).toFixed(0)+'\\ub9cc'; return fmt(n); };

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
            document.querySelectorAll('.period-btn').forEach(b => {
                b.classList.toggle('active', b.dataset.period === period);
            });
            loadAllCharts();
        }

        /* ========== Equity Curve Chart ========== */
        async function loadEquityChart() {
            try {
                const r = await fetch('/api/equity-curve?period=' + currentPeriod);
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
                                label: 'Cumulative P&L',
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
                                label: 'Drawdown %',
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
                                        if (ctx.datasetIndex === 0) return 'P&L: ' + fmtW(ctx.raw) + '\\uc6d0';
                                        return 'Drawdown: ' + ctx.raw.toFixed(2) + '%';
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
            } catch(e) { console.error('Equity chart error:', e); }
        }

        /* ========== Daily P&L Bar Chart ========== */
        async function loadDailyPnlChart() {
            try {
                const r = await fetch('/api/daily-pnl?period=' + currentPeriod);
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
                                label: 'Daily P&L',
                                data: pnlData,
                                backgroundColor: barColors,
                                borderRadius: 2,
                                yAxisID: 'y',
                                order: 2,
                            },
                            {
                                label: 'Running Total',
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
                                        return ctx.dataset.label + ': ' + fmtW(ctx.raw) + '\\uc6d0';
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
            } catch(e) { console.error('Daily PnL chart error:', e); }
        }

        /* ========== Strategy Doughnut Chart ========== */
        async function loadStrategyChart() {
            try {
                const r = await fetch('/api/strategy-stats?period=' + currentPeriod);
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
                    tableEl.innerHTML = '<p class="neu">No strategy data available yet</p>';
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
                                        return ctx.label + ': ' + Math.round(ctx.raw) + ' wins (' + (s.win_rate||0) + '% WR)';
                                    }
                                }
                            }
                        }
                    }
                });

                // Strategy win rates table
                let html = '<table><thead><tr><th>Strategy</th><th>Wins</th><th>Losses</th><th>Win Rate</th><th>PnL</th></tr></thead><tbody>';
                for (const name of names) {
                    const s = strategies[name];
                    const pnlClass = (s.total_pnl||0) >= 0 ? 'pos' : 'neg';
                    html += '<tr><td>' + name + '</td><td class="green">' + Math.round(s.wins) + '</td><td class="pos">' + Math.round(s.losses) + '</td>'
                         + '<td class="green">' + s.win_rate + '%</td>'
                         + '<td class="' + pnlClass + '">' + fmtW(s.total_pnl) + '\\uc6d0</td></tr>';
                }
                html += '</tbody></table>';
                tableEl.innerHTML = html;

            } catch(e) { console.error('Strategy chart error:', e); }
        }

        /* ========== Trade Distribution Histogram ========== */
        async function loadDistChart() {
            try {
                const r = await fetch('/api/trade-distribution?period=' + currentPeriod);
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
                            label: 'Trade Count',
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
                                    title: ctx => 'Return: ' + ctx[0].label,
                                    afterBody: function() {
                                        return 'Avg: ' + d.avg_return + '% | Med: ' + d.median_return + '%';
                                    }
                                }
                            },
                        },
                        scales: {
                            x: { grid: { display: false }, title: { display: true, text: 'Return %', font: { size: 10 } } },
                            y: { grid: { color: '#21262d' }, title: { display: true, text: 'Trades', font: { size: 10 } },
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
            } catch(e) { console.error('Distribution chart error:', e); }
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
                mt.textContent = d.scheduler?.running ? 'AUTO RUNNING' : d.mode;
                mt.className = 'mode ' + (d.mode==='\\uc2e4\\uc804\\ud22c\\uc790'?'mode-live':'mode-paper');
                if(d.scheduler?.running) { mt.className='mode'; mt.style.cssText='padding:4px 12px;border-radius:12px;font-size:0.8rem;font-weight:600;background:#23863633;color:#3fb950;border:1px solid #238636'; }
                document.getElementById('totalAssets').textContent = fmtW(d.balance?.total_eval||0)+'\\uc6d0';
                document.getElementById('cash').textContent = fmtW(d.balance?.cash||0)+'\\uc6d0';
                const pnl = d.total_pnl||0; const pnlPct = d.total_pnl_pct||0;
                const pnlEl = document.getElementById('totalPnl');
                pnlEl.textContent = (pnl>=0?'+':'')+fmtW(pnl)+'\\uc6d0 ('+(pnlPct>=0?'+':'')+pnlPct.toFixed(2)+'%)';
                pnlEl.className = 'value '+(pnl>=0?'pos':'neg');
                document.getElementById('posCount').textContent = Object.keys(d.positions||{}).length;
                document.getElementById('winRate').textContent = (d.win_rate||0)+'%';
                const cb = d.circuit_breaker||{};
                const cbEl = document.getElementById('circuitAlert');
                if(cb.tripped) { cbEl.classList.add('active'); document.getElementById('cbReason').textContent=cb.reason; }
                else { cbEl.classList.remove('active'); }
                const si = d.scheduler||{};
                document.getElementById('schedInfo').textContent = (si.is_market_hours?'\\uc7a5\\uc911':'\\uc7a5\\uc678')+' | '+si.time_until_open;
                const posEl = document.getElementById('positions');
                const pe = Object.entries(d.positions||{});
                if(!pe.length) { posEl.innerHTML='<p class="neu">No positions</p>'; }
                else {
                    posEl.innerHTML = '<table><thead><tr><th>Name</th><th>Qty</th><th>Avg</th><th>Value</th></tr></thead><tbody>'
                        + pe.map(([s,p]) => {
                            const val = (p.qty||0)*(p.avg_price||0);
                            return '<tr><td><b>'+(p.name||s)+'</b><br><span class="neu" style="font-size:0.72rem">'+s+'</span></td><td>'+fmt(p.qty)+'</td><td>'+fmt(p.avg_price)+'</td><td>'+fmtW(val)+'\\uc6d0</td></tr>';
                        }).join('')+'</tbody></table>';
                }
                const tb = document.getElementById('recentTrades');
                const trades = (d.recent_trades||[]).slice(-15).reverse();
                tb.innerHTML = trades.map(t => {
                    const badge = t.action==='BUY'?'badge-buy':t.action.includes('STOP')||t.action==='SELL'?'badge-sell':'badge-hold';
                    const pnl = t.pnl_pct?'<span class="'+(t.pnl_pct>=0?'pos':'neg')+'">'+(t.pnl_pct>=0?'+':'')+t.pnl_pct+'%</span>':'-';
                    const time = new Date(t.timestamp).toLocaleString('ko',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
                    return '<tr><td>'+time+'</td><td><span class="badge '+badge+'">'+t.action+'</span></td><td>'+(t.name||t.symbol)+'</td><td>'+(t.qty||'-')+'</td><td>'+fmt(t.price)+'</td><td>'+pnl+'</td></tr>';
                }).join('');
                // Regime display
                const rg = d.regime||{};
                const rgBadge = document.getElementById('regimeBadge');
                const rgName = rg.regime||'SIDEWAYS';
                rgBadge.textContent = rgName;
                rgBadge.className = 'badge-regime regime-'+rgName.toLowerCase();
                const rgDet = rg.details||{};
                document.getElementById('regimeADX').textContent = rgDet.adx!==undefined ? rgDet.adx : '-';
                document.getElementById('regimeVol').textContent = rgDet.recent_volatility!==undefined ? rgDet.recent_volatility+'%' : '-';
                document.getElementById('regimeReturn').textContent = rgDet.recent_return_pct!==undefined ? (rgDet.recent_return_pct>=0?'+':'')+rgDet.recent_return_pct+'%' : '-';
                document.getElementById('regimeMaDiff').textContent = rgDet.ma_diff_pct!==undefined ? (rgDet.ma_diff_pct>=0?'+':'')+rgDet.ma_diff_pct+'%' : '-';
                document.getElementById('regimeSince').textContent = rg.regime_since ? 'Since: '+new Date(rg.regime_since).toLocaleString('ko',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) : '';
                const rgStatEl = document.getElementById('regimeStat');
                rgStatEl.textContent = rgName;
                rgStatEl.className = 'value '+(rgName==='BULL'?'green':rgName==='BEAR'?'pos':'yellow');
                // Regime weights
                const rgw = rg.weights||{};
                const wHtml = Object.entries(rgw).map(([k,v]) => {
                    const pct = Math.round(v*100);
                    return k+': <b>'+pct+'%</b><span class="weight-bar" style="width:'+pct+'px"></span>';
                }).join(' &nbsp; ');
                document.getElementById('regimeWeights').innerHTML = 'Active Weights: '+wHtml;

                document.getElementById('lastUpdate').textContent = 'Updated: '+new Date().toLocaleTimeString('ko');
            } catch(e) { console.error(e); }
        }

        async function fetchStats() {
            try {
                const r = await fetch('/api/stats');
                const d = await r.json();
                const el = document.getElementById('tradeStats');
                const s7 = d['7d']||{}, s30 = d['30d']||{}, sa = d['all']||{};
                el.innerHTML =
                    '<table><tr><th></th><th>7 Days</th><th>30 Days</th><th>All</th></tr>'
                    +'<tr><td>Trades</td><td>'+(s7.total||0)+'</td><td>'+(s30.total||0)+'</td><td>'+(sa.total||0)+'</td></tr>'
                    +'<tr><td>Wins</td><td>'+(s7.wins||0)+'</td><td>'+(s30.wins||0)+'</td><td>'+(sa.wins||0)+'</td></tr>'
                    +'<tr><td>Win Rate</td><td class="green">'+(s7.win_rate||0)+'%</td><td class="green">'+(s30.win_rate||0)+'%</td><td class="green">'+(sa.win_rate||0)+'%</td></tr>'
                    +'<tr><td>Total PnL</td><td class="'+((s7.total_pnl||0)>=0?'pos':'neg')+'">'+fmtW(s7.total_pnl||0)+'\\uc6d0</td>'
                    +'<td class="'+((s30.total_pnl||0)>=0?'pos':'neg')+'">'+fmtW(s30.total_pnl||0)+'\\uc6d0</td>'
                    +'<td class="'+((sa.total_pnl||0)>=0?'pos':'neg')+'">'+fmtW(sa.total_pnl||0)+'\\uc6d0</td></tr>'
                    +'<tr><td>Avg PnL</td><td>'+(s7.avg_pnl_pct||0)+'%</td><td>'+(s30.avg_pnl_pct||0)+'%</td><td>'+(sa.avg_pnl_pct||0)+'%</td></tr></table>';
            } catch(e) {}
        }

        async function scanAll() {
            document.getElementById('scanResults').innerHTML='<tr><td colspan="6">Scanning 15 stocks...</td></tr>';
            const r = await fetch('/api/scan');
            const d = await r.json();
            const tb = document.getElementById('scanResults');
            tb.innerHTML = (d.results||[]).map(s => {
                const badge = s.action==='BUY'?'badge-buy':s.action==='SELL'?'badge-sell':'badge-hold';
                const barW = Math.max(0,Math.min(100,s.score));
                const barC = s.score>=65?'#3fb950':s.score<=35?'#f85149':'#8b949e';
                const sent = s.sentiment ? '<span class="'+(s.sentiment.overall>0?'green':s.sentiment.overall<0?'pos':'neu')+'">'+(s.sentiment.overall>0?'+':'')+(s.sentiment.overall*100).toFixed(0)+'</span>' : '-';
                return '<tr><td><b>'+s.name+'</b><br><span class="neu" style="font-size:0.7rem">'+s.symbol+'</span></td>'
                    +'<td><div class="score-bar"><div class="score-fill" style="width:'+barW+'%;background:'+barC+'"></div></div> '+s.score+'</td>'
                    +'<td><span class="badge '+badge+'">'+s.action+'</span></td>'
                    +'<td>'+fmt(s.current_price)+'</td><td>'+sent+'</td>'
                    +'<td style="font-size:0.72rem;max-width:200px;overflow:hidden;text-overflow:ellipsis">'+(s.reasons||[]).slice(0,2).join(', ')+'</td></tr>';
            }).join('');
        }

        async function startBot() { await fetch('/api/bot/start',{method:'POST'}); fetchStatus(); }
        async function stopBot() { await fetch('/api/bot/stop',{method:'POST'}); fetchStatus(); }
        async function runCycle() {
            document.getElementById('scanResults').innerHTML='<tr><td colspan="6">Running cycle...</td></tr>';
            await fetch('/api/cycle',{method:'POST'});
            fetchStatus(); fetchStats();
        }
        async function resetCB() { await fetch('/api/circuit-breaker/reset',{method:'POST'}); fetchStatus(); }

        /* ========== Initialize ========== */
        fetchStatus(); fetchStats(); loadAllCharts();
        setInterval(fetchStatus, 15000);
        setInterval(fetchStats, 60000);
        setInterval(loadAllCharts, 120000);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print("=" * 50)
    print(f"  StockBot v2.1 Dashboard")
    print(f"  http://localhost:{DASHBOARD_PORT}")
    print("=" * 50)
    uvicorn.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT)
