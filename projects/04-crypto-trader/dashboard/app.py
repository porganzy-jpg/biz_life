"""
CryptoBot 대시보드
웹 브라우저에서 매매 현황을 실시간 모니터링
핸드폰/노트북에서도 접속 가능
"""
import sys
import os
import json
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-bot"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "strategy"))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from trader import CryptoTrader
from config import DASHBOARD_HOST, DASHBOARD_PORT

app = FastAPI(title="CryptoBot Dashboard")
trader = CryptoTrader(paper_trading=True)
bot_running = False
bot_thread = None


def run_bot():
    """백그라운드에서 봇 실행"""
    global bot_running
    from config import TRADING_CONFIG
    while bot_running:
        try:
            trader.run_cycle()
        except Exception as e:
            print(f"봇 오류: {e}")
        time.sleep(TRADING_CONFIG["trade_interval_seconds"])


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """메인 대시보드 페이지"""
    return DASHBOARD_HTML


@app.get("/api/status")
async def get_status():
    """봇 상태 API"""
    status = trader.get_status()
    status["bot_running"] = bot_running
    return status


@app.get("/api/history")
async def get_history():
    """매매 이력 API"""
    return {"trades": trader.trade_history}


@app.post("/api/bot/start")
async def start_bot():
    """봇 시작"""
    global bot_running, bot_thread
    if bot_running:
        return {"status": "already_running"}
    bot_running = True
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    return {"status": "started"}


@app.post("/api/bot/stop")
async def stop_bot():
    """봇 정지"""
    global bot_running
    bot_running = False
    return {"status": "stopped"}


@app.get("/api/analyze/{symbol}")
async def analyze_symbol(symbol: str):
    """특정 심볼 분석"""
    analysis = trader.analyze_market(symbol)
    return {
        "symbol": analysis["symbol"],
        "consensus": analysis["consensus"],
        "confidence": analysis["avg_confidence"],
        "signals": [
            {"action": s.action, "confidence": s.confidence, "reason": s.reason}
            for s in analysis["signals"]
        ],
    }


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CryptoBot Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', -apple-system, sans-serif;
            background: #0a0e17;
            color: #e1e5ee;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1f36, #0d1117);
            padding: 20px;
            border-bottom: 1px solid #2d3548;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 1.5rem;
            color: #58a6ff;
        }
        .header .mode {
            background: #238636;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: #161b22;
            border: 1px solid #2d3548;
            border-radius: 12px;
            padding: 20px;
        }
        .stat-card .label {
            color: #8b949e;
            font-size: 0.85rem;
            margin-bottom: 8px;
        }
        .stat-card .value {
            font-size: 1.8rem;
            font-weight: 700;
        }
        .positive { color: #3fb950; }
        .negative { color: #f85149; }
        .neutral { color: #58a6ff; }
        .section {
            background: #161b22;
            border: 1px solid #2d3548;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        }
        .section h2 {
            color: #58a6ff;
            font-size: 1.1rem;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #2d3548;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid #21262d;
            font-size: 0.9rem;
        }
        th {
            color: #8b949e;
            font-weight: 600;
        }
        .btn {
            padding: 10px 24px;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-start {
            background: #238636;
            color: white;
        }
        .btn-start:hover { background: #2ea043; }
        .btn-stop {
            background: #da3633;
            color: white;
        }
        .btn-stop:hover { background: #f85149; }
        .btn-analyze {
            background: #1f6feb;
            color: white;
            margin-right: 8px;
        }
        .controls {
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }
        .position-card {
            background: #0d1117;
            border: 1px solid #2d3548;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .signal-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .signal-buy { background: #0e4429; color: #3fb950; }
        .signal-sell { background: #490e0e; color: #f85149; }
        .signal-hold { background: #1c2333; color: #8b949e; }
        @media (max-width: 768px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .header { flex-direction: column; gap: 10px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>CryptoBot Dashboard</h1>
        <span class="mode" id="mode">Loading...</span>
    </div>

    <div class="container">
        <div class="controls">
            <button class="btn btn-start" onclick="startBot()">Start Bot</button>
            <button class="btn btn-stop" onclick="stopBot()">Stop Bot</button>
            <button class="btn btn-analyze" onclick="analyzeAll()">Analyze All</button>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">KRW Balance</div>
                <div class="value neutral" id="balance">-</div>
            </div>
            <div class="stat-card">
                <div class="label">Total Trades</div>
                <div class="value" id="totalTrades">0</div>
            </div>
            <div class="stat-card">
                <div class="label">Win Rate</div>
                <div class="value" id="winRate">0%</div>
            </div>
            <div class="stat-card">
                <div class="label">Total PnL</div>
                <div class="value" id="totalPnl">0%</div>
            </div>
        </div>

        <div class="section">
            <h2>Open Positions</h2>
            <div id="positions">No positions</div>
        </div>

        <div class="section">
            <h2>Recent Trades</h2>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Action</th>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>PnL</th>
                    </tr>
                </thead>
                <tbody id="trades"></tbody>
            </table>
        </div>

        <div class="section">
            <h2>Market Analysis</h2>
            <div id="analysis">Click "Analyze All" to start</div>
        </div>
    </div>

    <script>
        const API = '';

        async function fetchStatus() {
            try {
                const res = await fetch(API + '/api/status');
                const data = await res.json();
                updateDashboard(data);
            } catch (e) {
                console.error('Status fetch error:', e);
            }
        }

        function updateDashboard(data) {
            document.getElementById('mode').textContent =
                data.bot_running ? 'BOT RUNNING' : data.mode;
            document.getElementById('mode').style.background =
                data.bot_running ? '#238636' : '#6e7681';

            const krw = data.balance?.KRW || 0;
            document.getElementById('balance').textContent =
                Math.floor(krw).toLocaleString() + ' won';

            document.getElementById('totalTrades').textContent = data.total_trades;

            const winRate = data.win_rate || 0;
            const winEl = document.getElementById('winRate');
            winEl.textContent = winRate.toFixed(1) + '%';
            winEl.className = 'value ' + (winRate >= 50 ? 'positive' : 'negative');

            const pnl = data.total_pnl_pct || 0;
            const pnlEl = document.getElementById('totalPnl');
            pnlEl.textContent = (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + '%';
            pnlEl.className = 'value ' + (pnl >= 0 ? 'positive' : 'negative');

            // Positions
            const posEl = document.getElementById('positions');
            const positions = data.positions || {};
            if (Object.keys(positions).length === 0) {
                posEl.innerHTML = '<p style="color:#8b949e">No open positions</p>';
            } else {
                posEl.innerHTML = Object.entries(positions).map(([sym, pos]) =>
                    `<div class="position-card">
                        <div><strong>${sym}</strong><br>Qty: ${pos.qty?.toFixed(8) || 0}</div>
                        <div>Avg: ${pos.avg_price?.toLocaleString() || '-'} KRW</div>
                    </div>`
                ).join('');
            }

            // Recent trades
            const tradesEl = document.getElementById('trades');
            const trades = (data.recent_trades || []).reverse();
            tradesEl.innerHTML = trades.map(t => {
                const actionClass = t.action === 'BUY' ? 'signal-buy' :
                    t.action.includes('STOP') ? 'signal-sell' :
                    t.action === 'SELL' ? 'signal-sell' : 'signal-hold';
                const pnl = t.pnl_pct !== undefined ?
                    `<span class="${t.pnl_pct >= 0 ? 'positive' : 'negative'}">${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct}%</span>` : '-';
                return `<tr>
                    <td>${new Date(t.timestamp).toLocaleString('ko-KR')}</td>
                    <td><span class="signal-badge ${actionClass}">${t.action}</span></td>
                    <td>${t.symbol}</td>
                    <td>${t.price?.toLocaleString() || '-'}</td>
                    <td>${pnl}</td>
                </tr>`;
            }).join('');
        }

        async function startBot() {
            await fetch(API + '/api/bot/start', { method: 'POST' });
            fetchStatus();
        }

        async function stopBot() {
            await fetch(API + '/api/bot/stop', { method: 'POST' });
            fetchStatus();
        }

        async function analyzeAll() {
            const symbols = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-DOGE', 'KRW-ADA'];
            const el = document.getElementById('analysis');
            el.innerHTML = '<p>Analyzing...</p>';

            const results = [];
            for (const sym of symbols) {
                try {
                    const res = await fetch(API + '/api/analyze/' + sym);
                    const data = await res.json();
                    results.push(data);
                } catch (e) {
                    results.push({ symbol: sym, consensus: 'ERROR', confidence: 0, signals: [] });
                }
            }

            el.innerHTML = results.map(r => {
                const actionClass = r.consensus === 'BUY' ? 'signal-buy' :
                    r.consensus === 'SELL' ? 'signal-sell' : 'signal-hold';
                const signals = (r.signals || []).map(s =>
                    `<div style="font-size:0.8rem;color:#8b949e;margin:4px 0">
                        <span class="signal-badge ${s.action === 'BUY' ? 'signal-buy' : s.action === 'SELL' ? 'signal-sell' : 'signal-hold'}">${s.action}</span>
                        ${s.reason}
                    </div>`
                ).join('');
                return `<div class="position-card" style="flex-direction:column;align-items:stretch">
                    <div style="display:flex;justify-content:space-between;margin-bottom:8px">
                        <strong>${r.symbol}</strong>
                        <span class="signal-badge ${actionClass}">${r.consensus} (${(r.confidence*100).toFixed(0)}%)</span>
                    </div>
                    ${signals}
                </div>`;
            }).join('');
        }

        // Auto refresh every 30 seconds
        fetchStatus();
        setInterval(fetchStatus, 30000);
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    print("=" * 50)
    print("  CryptoBot Dashboard")
    print(f"  http://localhost:{DASHBOARD_PORT}")
    print("  (같은 WiFi의 핸드폰에서도 접속 가능)")
    print("=" * 50)
    uvicorn.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT)
