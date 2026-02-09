"""
FastAPI Dashboard for Scalping Bot (port 8081).
"""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import config

logger = logging.getLogger("scalper.dashboard")

# Trader instance will be set externally
_trader = None


def set_trader(trader):
    global _trader
    _trader = trader


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Dashboard starting on port {config.DASHBOARD_PORT}")
    yield
    logger.info("Dashboard shutting down")


app = FastAPI(title="Upbit Scalper Dashboard", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index():
    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Upbit Scalper Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
h1 { color: #58a6ff; margin-bottom: 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 20px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
.card h3 { color: #8b949e; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }
.card .value { font-size: 24px; font-weight: bold; }
.positive { color: #3fb950; }
.negative { color: #f85149; }
.neutral { color: #58a6ff; }
table { width: 100%; border-collapse: collapse; margin-top: 16px; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #30363d; }
th { color: #8b949e; font-size: 12px; text-transform: uppercase; }
.btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; margin-right: 8px; }
.btn-start { background: #238636; color: white; }
.btn-stop { background: #da3633; color: white; }
.btn-refresh { background: #30363d; color: #c9d1d9; }
#status { margin: 20px 0; }
.positions { margin-top: 20px; }
.weights { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.weight-badge { background: #21262d; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
</style>
</head>
<body>
<div class="container">
<h1>Upbit Scalper Dashboard</h1>
<div>
  <button class="btn btn-start" onclick="startBot()">Start Bot</button>
  <button class="btn btn-stop" onclick="stopBot()">Stop Bot</button>
  <button class="btn btn-refresh" onclick="refresh()">Refresh</button>
</div>

<div id="status"></div>
<div class="grid" id="cards"></div>
<div class="positions" id="positions"></div>

<h2 style="margin-top:20px; color:#58a6ff;">Recent Trades</h2>
<table id="trades">
<thead><tr><th>Market</th><th>Entry</th><th>Exit</th><th>PnL %</th><th>PnL KRW</th><th>Exit Type</th><th>Duration</th></tr></thead>
<tbody></tbody>
</table>

<h2 style="margin-top:20px; color:#58a6ff;">Ensemble Weights</h2>
<div class="weights" id="weights"></div>
</div>

<script>
async function refresh() {
  try {
    const res = await fetch('/api/status');
    const d = await res.json();
    renderCards(d);
    renderPositions(d.open_positions);
    renderTrades(d.recent_trades);
    renderWeights(d.ensemble);
  } catch(e) { console.error(e); }
}

function renderCards(d) {
  const pnlClass = d.daily_pnl >= 0 ? 'positive' : 'negative';
  const wrClass = d.win_rate >= 50 ? 'positive' : 'negative';
  document.getElementById('cards').innerHTML = `
    <div class="card"><h3>Balance</h3><div class="value neutral">${fmt(d.balance_krw)} KRW</div></div>
    <div class="card"><h3>Daily PnL</h3><div class="value ${pnlClass}">${d.daily_pnl >= 0 ? '+' : ''}${fmt(d.daily_pnl)} KRW</div></div>
    <div class="card"><h3>Trades (W/L)</h3><div class="value">${d.wins} / ${d.losses}</div></div>
    <div class="card"><h3>Win Rate</h3><div class="value ${wrClass}">${d.win_rate.toFixed(1)}%</div></div>
    <div class="card"><h3>Cycle</h3><div class="value">${d.cycle_count}</div></div>
    <div class="card"><h3>Status</h3><div class="value ${d.running ? 'positive' : 'negative'}">${d.running ? 'RUNNING' : 'STOPPED'}</div></div>
  `;
  const cb = d.circuit_breaker;
  document.getElementById('status').innerHTML = cb.can_trade
    ? '<div style="color:#3fb950;margin:10px 0">Circuit Breaker: OK</div>'
    : '<div style="color:#f85149;margin:10px 0">Circuit Breaker: ' + cb.reason + '</div>';
}

function renderPositions(positions) {
  const el = document.getElementById('positions');
  const entries = Object.entries(positions);
  if (!entries.length) { el.innerHTML = '<p style="color:#8b949e">No open positions</p>'; return; }
  let html = '<h2 style="color:#58a6ff">Open Positions</h2><table><thead><tr><th>Market</th><th>Entry Price</th><th>Amount</th><th>Since</th></tr></thead><tbody>';
  entries.forEach(([m, p]) => {
    html += `<tr><td>${m}</td><td>${fmt(p.entry_price)}</td><td>${p.amount.toFixed(8)}</td><td>${p.entry_time}</td></tr>`;
  });
  el.innerHTML = html + '</tbody></table>';
}

function renderTrades(trades) {
  const tbody = document.querySelector('#trades tbody');
  if (!trades || !trades.length) { tbody.innerHTML = '<tr><td colspan="7" style="color:#8b949e">No trades yet</td></tr>'; return; }
  tbody.innerHTML = trades.slice().reverse().map(t => {
    const cls = t.pnl_krw >= 0 ? 'positive' : 'negative';
    return `<tr><td>${t.market}</td><td>${fmt(t.entry_price)}</td><td>${fmt(t.exit_price)}</td>
    <td class="${cls}">${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%</td>
    <td class="${cls}">${t.pnl_krw >= 0 ? '+' : ''}${fmt(t.pnl_krw)}</td>
    <td>${t.exit_type}</td><td>${t.duration_sec.toFixed(0)}s</td></tr>`;
  }).join('');
}

function renderWeights(ens) {
  if (!ens) return;
  const el = document.getElementById('weights');
  el.innerHTML = Object.entries(ens.weights).map(([k,v]) =>
    `<span class="weight-badge">${k}: ${(v*100).toFixed(1)}%</span>`
  ).join('');
}

function fmt(n) { return Math.round(n).toLocaleString(); }

async function startBot() {
  await fetch('/api/bot/start', {method:'POST'});
  setTimeout(refresh, 1000);
}
async function stopBot() {
  await fetch('/api/bot/stop', {method:'POST'});
  setTimeout(refresh, 1000);
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


@app.get("/api/status")
async def get_status():
    if _trader is None:
        return {"running": False, "balance_krw": 0, "daily_pnl": 0,
                "wins": 0, "losses": 0, "win_rate": 0, "cycle_count": 0,
                "open_positions": {}, "total_trades": 0,
                "circuit_breaker": {"can_trade": False, "reason": "Not initialized"},
                "ensemble": {"weights": {}}, "recent_trades": []}
    return _trader.get_status()


@app.post("/api/bot/start")
async def start_bot():
    if _trader is None:
        return {"error": "Trader not initialized"}
    if _trader.running:
        return {"status": "already running"}
    t = threading.Thread(target=_trader.run, daemon=True)
    t.start()
    return {"status": "started"}


@app.post("/api/bot/stop")
async def stop_bot():
    if _trader is None:
        return {"error": "Trader not initialized"}
    _trader.stop()
    return {"status": "stopped"}


@app.post("/api/bot/halt")
async def halt_bot():
    if _trader:
        _trader.circuit.force_halt("Manual halt via dashboard")
    return {"status": "halted"}


@app.post("/api/bot/resume")
async def resume_bot():
    if _trader:
        _trader.circuit.resume()
    return {"status": "resumed"}


def run_dashboard(trader=None):
    """Run the dashboard server."""
    import uvicorn
    if trader:
        set_trader(trader)
    uvicorn.run(app, host="0.0.0.0", port=config.DASHBOARD_PORT)
