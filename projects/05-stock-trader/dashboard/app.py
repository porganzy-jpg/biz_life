"""
StockBot 대시보드
"""
import sys
import os
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-bot"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "strategy"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "news"))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

from trader import StockTrader
from config import DASHBOARD_HOST, DASHBOARD_PORT, WATCHLIST

app = FastAPI(title="StockBot Dashboard")
trader = StockTrader(paper_trading=True)
bot_running = False
bot_thread = None


def run_bot():
    global bot_running
    from config import STOCK_TRADING_CONFIG
    while bot_running:
        try:
            trader.run_cycle()
        except Exception as e:
            print(f"Bot error: {e}")
        time.sleep(STOCK_TRADING_CONFIG["trade_interval_minutes"] * 60)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


@app.get("/api/status")
async def get_status():
    status = trader.get_status()
    status["bot_running"] = bot_running
    return status


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
    return {"trades": trader.trade_history}


@app.post("/api/bot/start")
async def start_bot():
    global bot_running, bot_thread
    if bot_running:
        return {"status": "already_running"}
    bot_running = True
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    return {"status": "started"}


@app.post("/api/bot/stop")
async def stop_bot():
    global bot_running
    bot_running = False
    return {"status": "stopped"}


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockBot Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0f1923; color: #e1e5ee; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #1a2332, #0f1923); padding: 20px; border-bottom: 1px solid #2d3548; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.5rem; color: #4fc3f7; }
        .mode { background: #00897b; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }
        .stat-card { background: #1a2332; border: 1px solid #2d3548; border-radius: 10px; padding: 16px; }
        .stat-card .label { color: #8b949e; font-size: 0.8rem; margin-bottom: 6px; }
        .stat-card .value { font-size: 1.6rem; font-weight: 700; }
        .positive { color: #ef5350; }
        .negative { color: #42a5f5; }
        .neutral { color: #4fc3f7; }
        .section { background: #1a2332; border: 1px solid #2d3548; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
        .section h2 { color: #4fc3f7; font-size: 1rem; margin-bottom: 12px; border-bottom: 1px solid #2d3548; padding-bottom: 8px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #1e2d3d; font-size: 0.85rem; }
        th { color: #8b949e; font-weight: 600; }
        .btn { padding: 8px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.9rem; }
        .btn-start { background: #00897b; color: white; }
        .btn-stop { background: #ef5350; color: white; }
        .btn-scan { background: #1565c0; color: white; }
        .controls { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
        .score-bar { width: 60px; height: 8px; background: #1e2d3d; border-radius: 4px; display: inline-block; position: relative; }
        .score-fill { height: 100%; border-radius: 4px; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
        .badge-buy { background: #1b3a2d; color: #4caf50; }
        .badge-sell { background: #3a1b1b; color: #ef5350; }
        .badge-hold { background: #1e2d3d; color: #8b949e; }
    </style>
</head>
<body>
    <div class="header">
        <h1>StockBot Dashboard</h1>
        <span class="mode" id="mode">Loading...</span>
    </div>
    <div class="container">
        <div class="controls">
            <button class="btn btn-start" onclick="startBot()">Start Bot</button>
            <button class="btn btn-stop" onclick="stopBot()">Stop Bot</button>
            <button class="btn btn-scan" onclick="scanAll()">Scan Watchlist</button>
        </div>
        <div class="stats-grid">
            <div class="stat-card"><div class="label">Total Assets</div><div class="value neutral" id="totalAssets">-</div></div>
            <div class="stat-card"><div class="label">Cash</div><div class="value" id="cash">-</div></div>
            <div class="stat-card"><div class="label">Positions</div><div class="value" id="posCount">0</div></div>
            <div class="stat-card"><div class="label">Total Trades</div><div class="value" id="trades">0</div></div>
            <div class="stat-card"><div class="label">Win Rate</div><div class="value" id="winRate">0%</div></div>
        </div>
        <div class="section">
            <h2>Watchlist Scan</h2>
            <table><thead><tr><th>Name</th><th>Code</th><th>Score</th><th>Action</th><th>Price</th><th>Reasons</th></tr></thead>
            <tbody id="scanResults"><tr><td colspan="6" style="color:#8b949e">Click "Scan Watchlist"</td></tr></tbody></table>
        </div>
        <div class="section">
            <h2>Positions</h2>
            <div id="positions" style="color:#8b949e">No positions</div>
        </div>
        <div class="section">
            <h2>Recent Trades</h2>
            <table><thead><tr><th>Time</th><th>Action</th><th>Name</th><th>Qty</th><th>Price</th><th>PnL</th></tr></thead>
            <tbody id="recentTrades"></tbody></table>
        </div>
    </div>
    <script>
        async function fetchStatus() {
            try {
                const r = await fetch('/api/status');
                const d = await r.json();
                document.getElementById('mode').textContent = d.bot_running ? 'BOT RUNNING' : d.mode;
                document.getElementById('totalAssets').textContent = (d.balance?.total_eval||0).toLocaleString() + ' won';
                document.getElementById('cash').textContent = (d.balance?.cash||0).toLocaleString() + ' won';
                const pos = d.positions || {};
                document.getElementById('posCount').textContent = Object.keys(pos).length;
                document.getElementById('trades').textContent = d.total_trades || 0;
                document.getElementById('winRate').textContent = (d.win_rate || 0) + '%';
                // Positions
                const posEl = document.getElementById('positions');
                const entries = Object.entries(pos);
                if (entries.length === 0) { posEl.innerHTML = '<p style="color:#8b949e">No positions</p>'; }
                else { posEl.innerHTML = entries.map(([s,p]) => `<div style="padding:6px 0;border-bottom:1px solid #1e2d3d"><strong>${p.name||s}</strong> (${s}) | ${p.qty}주 @ ${(p.avg_price||0).toLocaleString()}원</div>`).join(''); }
                // Trades
                const tbody = document.getElementById('recentTrades');
                const trades = (d.recent_trades || []).reverse();
                tbody.innerHTML = trades.map(t => {
                    const cls = t.action==='BUY'?'badge-buy':t.action.includes('STOP')?'badge-sell':'badge-sell';
                    const pnl = t.pnl_pct ? `<span class="${t.pnl_pct>=0?'positive':'negative'}">${t.pnl_pct>=0?'+':''}${t.pnl_pct}%</span>` : '-';
                    return `<tr><td>${new Date(t.timestamp).toLocaleString('ko')}</td><td><span class="badge ${cls}">${t.action}</span></td><td>${t.name||t.symbol}</td><td>${t.qty||'-'}</td><td>${(t.price||0).toLocaleString()}</td><td>${pnl}</td></tr>`;
                }).join('');
            } catch(e) { console.error(e); }
        }
        async function scanAll() {
            document.getElementById('scanResults').innerHTML = '<tr><td colspan="6">Scanning...</td></tr>';
            const r = await fetch('/api/scan');
            const d = await r.json();
            const tbody = document.getElementById('scanResults');
            tbody.innerHTML = (d.results||[]).map(s => {
                const cls = s.action==='BUY'?'badge-buy':s.action==='SELL'?'badge-sell':'badge-hold';
                const barW = Math.max(0, Math.min(100, s.score));
                const barColor = s.score>=65?'#4caf50':s.score<=35?'#ef5350':'#8b949e';
                return `<tr><td><strong>${s.name}</strong></td><td>${s.symbol}</td><td><div class="score-bar"><div class="score-fill" style="width:${barW}%;background:${barColor}"></div></div> ${s.score}</td><td><span class="badge ${cls}">${s.action}</span></td><td>${(s.current_price||0).toLocaleString()}</td><td style="font-size:0.8rem">${(s.reasons||[]).join(', ')}</td></tr>`;
            }).join('');
        }
        async function startBot() { await fetch('/api/bot/start',{method:'POST'}); fetchStatus(); }
        async function stopBot() { await fetch('/api/bot/stop',{method:'POST'}); fetchStatus(); }
        fetchStatus();
        setInterval(fetchStatus, 30000);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    print("=" * 50)
    print(f"  StockBot Dashboard - http://localhost:{DASHBOARD_PORT}")
    print("=" * 50)
    uvicorn.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT)
