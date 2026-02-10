"""
StockBot v2.0 대시보드
8전략 앙상블 + 뉴스감성 + 서킷브레이커 + 일일성과
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-bot"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "strategy"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "news"))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

from trader import StockTrader
from config import DASHBOARD_HOST, DASHBOARD_PORT, WATCHLIST

app = FastAPI(title="StockBot v2.0 Dashboard")
trader = StockTrader(paper_trading=True)


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
    <title>StockBot v2.0</title>
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
        table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
        th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid #161b28; }
        th { color: #8b949e; font-weight: 600; background: #0d1117; position: sticky; top: 0; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: 600; }
        .badge-buy { background: #23863633; color: #3fb950; }
        .badge-sell { background: #f8514933; color: #f85149; }
        .badge-hold { background: #21262d; color: #8b949e; }
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
        @media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>StockBot v2.0</h1>
        <div class="header-right">
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
        <div class="grid-5">
            <div class="card stat-card"><div class="label">Total Assets</div><div class="value accent" id="totalAssets">-</div></div>
            <div class="card stat-card"><div class="label">Cash</div><div class="value" id="cash">-</div></div>
            <div class="card stat-card"><div class="label">Total PnL</div><div class="value" id="totalPnl">-</div></div>
            <div class="card stat-card"><div class="label">Positions</div><div class="value" id="posCount">0</div></div>
            <div class="card stat-card"><div class="label">Win Rate (30d)</div><div class="value green" id="winRate">-</div></div>
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
        const fmtW = n => { if(!n) return '0'; if(Math.abs(n)>=1e8) return (n/1e8).toFixed(1)+'억'; if(Math.abs(n)>=1e4) return (n/1e4).toFixed(0)+'만'; return fmt(n); };

        async function fetchStatus() {
            try {
                const r = await fetch('/api/status');
                const d = await r.json();
                const mt = document.getElementById('modeTag');
                mt.textContent = d.scheduler?.running ? 'AUTO RUNNING' : d.mode;
                mt.className = 'mode ' + (d.mode==='실전투자'?'mode-live':'mode-paper');
                if(d.scheduler?.running) { mt.className='mode'; mt.style.cssText='padding:4px 12px;border-radius:12px;font-size:0.8rem;font-weight:600;background:#23863633;color:#3fb950;border:1px solid #238636'; }
                document.getElementById('totalAssets').textContent = fmtW(d.balance?.total_eval||0)+'원';
                document.getElementById('cash').textContent = fmtW(d.balance?.cash||0)+'원';
                const pnl = d.total_pnl||0; const pnlPct = d.total_pnl_pct||0;
                const pnlEl = document.getElementById('totalPnl');
                pnlEl.textContent = (pnl>=0?'+':'')+fmtW(pnl)+'원 ('+(pnlPct>=0?'+':'')+pnlPct.toFixed(2)+'%)';
                pnlEl.className = 'value '+(pnl>=0?'pos':'neg');
                document.getElementById('posCount').textContent = Object.keys(d.positions||{}).length;
                document.getElementById('winRate').textContent = (d.win_rate||0)+'%';
                const cb = d.circuit_breaker||{};
                const cbEl = document.getElementById('circuitAlert');
                if(cb.tripped) { cbEl.classList.add('active'); document.getElementById('cbReason').textContent=cb.reason; }
                else { cbEl.classList.remove('active'); }
                const si = d.scheduler||{};
                document.getElementById('schedInfo').textContent = (si.is_market_hours?'장중':'장외')+' | '+si.time_until_open;
                const posEl = document.getElementById('positions');
                const pe = Object.entries(d.positions||{});
                if(!pe.length) { posEl.innerHTML='<p class="neu">No positions</p>'; }
                else {
                    posEl.innerHTML = '<table><thead><tr><th>Name</th><th>Qty</th><th>Avg</th><th>Value</th></tr></thead><tbody>'
                        + pe.map(([s,p]) => {
                            const val = (p.qty||0)*(p.avg_price||0);
                            return '<tr><td><b>'+(p.name||s)+'</b><br><span class="neu" style="font-size:0.72rem">'+s+'</span></td><td>'+fmt(p.qty)+'</td><td>'+fmt(p.avg_price)+'</td><td>'+fmtW(val)+'원</td></tr>';
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
                    +'<tr><td>Total PnL</td><td class="'+((s7.total_pnl||0)>=0?'pos':'neg')+'">'+fmtW(s7.total_pnl||0)+'원</td>'
                    +'<td class="'+((s30.total_pnl||0)>=0?'pos':'neg')+'">'+fmtW(s30.total_pnl||0)+'원</td>'
                    +'<td class="'+((sa.total_pnl||0)>=0?'pos':'neg')+'">'+fmtW(sa.total_pnl||0)+'원</td></tr>'
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

        fetchStatus(); fetchStats();
        setInterval(fetchStatus, 15000);
        setInterval(fetchStats, 60000);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print("=" * 50)
    print(f"  StockBot v2.0 Dashboard")
    print(f"  http://localhost:{DASHBOARD_PORT}")
    print("=" * 50)
    uvicorn.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT)
