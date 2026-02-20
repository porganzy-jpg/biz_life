"""
FastAPI Admin Dashboard for Scalping Bot (port 8081).

Endpoints:
- GET /              -> Full SPA dashboard (HTML/CSS/JS)
- GET /api/status    -> Real-time bot status + positions
- GET /api/market-watch -> Per-market strategy signals + indicators
- GET /api/trades/stats?period=today|week|month|all -> Period stats
- GET /api/trades/history?page=&market=&exit_type= -> Trade history
- GET /api/export/csv?market=&exit_type= -> CSV file download of trades
- GET /api/analytics -> Full trade performance analytics
- GET /api/analytics/strategy/{name} -> Per-strategy analytics detail
- GET /api/runtime   -> Runtime info + config summary
- POST /api/bot/start|stop|halt|resume -> Bot control
"""
import asyncio
import logging
import queue
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from . import config
from .trader import get_trades_stats, get_trades_history
from .trade_analyzer import get_full_analytics, get_strategy_analytics

logger = logging.getLogger("scalper.dashboard")

_trader = None


def set_trader(trader):
    global _trader
    _trader = trader


class WSManager:
    """WebSocket connection manager with thread-safe event queue."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._queue: queue.Queue = queue.Queue()
        self._drain_task = None
        self._status_interval = 5.0
        self._market_interval = 3.0

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        logger.info(f"WS client connected ({len(self._connections)} total)")
        # Send initial snapshot
        try:
            if _trader:
                await ws.send_json({"type": "status_update", "data": _trader.get_status()})
                await ws.send_json({"type": "market_update", "data": _trader.get_market_watch()})
        except Exception:
            pass

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info(f"WS client disconnected ({len(self._connections)} total)")

    async def broadcast(self, message: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def push_event(self, event: dict):
        """Thread-safe: called from trader thread."""
        self._queue.put(event)

    async def _drain_loop(self):
        """Async loop: drain queue and push periodic updates."""
        last_status = 0.0
        last_market = 0.0
        while True:
            try:
                # Drain all queued events
                while True:
                    try:
                        event = self._queue.get_nowait()
                        await self.broadcast(event)
                    except queue.Empty:
                        break

                now = time.time()
                if self._connections and _trader:
                    if now - last_status >= self._status_interval:
                        await self.broadcast({
                            "type": "status_update",
                            "data": _trader.get_status(),
                        })
                        last_status = now
                    if now - last_market >= self._market_interval:
                        await self.broadcast({
                            "type": "market_update",
                            "data": _trader.get_market_watch(),
                        })
                        last_market = now

                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WS drain error: {e}")
                await asyncio.sleep(1.0)

    async def start(self):
        self._drain_task = asyncio.create_task(self._drain_loop())

    async def stop(self):
        if self._drain_task:
            self._drain_task.cancel()
            try:
                await self._drain_task
            except asyncio.CancelledError:
                pass
        for ws in list(self._connections):
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()


ws_mgr = WSManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Dashboard starting on port {config.DASHBOARD_PORT}")
    await ws_mgr.start()
    yield
    await ws_mgr.stop()
    logger.info("Dashboard shutting down")


app = FastAPI(title="Upbit Scalper Admin Dashboard", lifespan=lifespan)


# ── API Endpoints ──────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    if _trader is None:
        return {
            "running": False, "paper": True, "balance_krw": 0, "daily_pnl": 0,
            "wins": 0, "losses": 0, "win_rate": 0, "cycle_count": 0,
            "open_positions": {}, "total_trades": 0, "total_fees_krw": 0,
            "today_trades": 0, "uptime_sec": 0,
            "circuit_breaker": {"can_trade": False, "reason": "Not initialized"},
            "ensemble": {"weights": {}}, "recent_trades": [],
        }
    return _trader.get_status()


@app.get("/api/market-watch")
async def api_market_watch():
    if _trader is None:
        return {}
    return _trader.get_market_watch()


@app.get("/api/trades/stats")
async def api_trades_stats(period: str = Query("all", pattern="^(today|week|month|all)$")):
    return get_trades_stats(period)


@app.get("/api/trades/history")
async def api_trades_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    market: str = Query(""),
    exit_type: str = Query(""),
):
    return get_trades_history(page, page_size, market, exit_type)


@app.get("/api/runtime")
async def api_runtime():
    if _trader is None:
        return {"initialized": False}
    # Active markets (dynamic or static)
    active_markets = (_trader.scanner.get_active_markets()
                      if _trader.scanner else list(config.MARKETS))
    return {
        "initialized": True,
        "paper": _trader.client.paper,
        "markets": active_markets,
        "static_markets": list(config.MARKETS),
        "loop_interval_sec": config.LOOP_INTERVAL_SEC,
        "candle_interval": config.CANDLE_INTERVAL,
        "risk_per_trade": config.RISK_PER_TRADE,
        "kelly_enabled": getattr(config, 'KELLY_ENABLED', False),
        "kelly_window": getattr(config, 'KELLY_WINDOW', 50),
        "kelly_safety_factor": getattr(config, 'KELLY_SAFETY_FACTOR', 0.5),
        "kelly_min_risk": getattr(config, 'KELLY_MIN_RISK', 0.005),
        "kelly_max_risk": getattr(config, 'KELLY_MAX_RISK', 0.04),
        "stop_loss_hard_cap": config.STOP_LOSS_HARD_CAP,
        "take_profit_pct": config.TAKE_PROFIT_PCT,
        "trailing_activate_pct": config.TRAILING_ACTIVATE_PCT,
        "trailing_stop_pct": config.TRAILING_STOP_PCT,
        "commission_rate": config.COMMISSION_RATE,
        "daily_loss_limit": config.DAILY_LOSS_LIMIT,
        "max_consecutive_losses": config.MAX_CONSECUTIVE_LOSSES,
        "cooldown_minutes": config.COOLDOWN_MINUTES,
        "min_agreement": config.MIN_AGREEMENT,
        "min_ensemble_confidence": config.MIN_ENSEMBLE_CONFIDENCE,
        "trend_ema_period": config.TREND_EMA_PERIOD,
        "uptime_sec": round(time.time() - _trader.start_time, 0),
        "scanner_status": _trader.scanner.get_status() if _trader.scanner else {"enabled": False},
        "optimizer_status": _trader.optimizer.get_status() if _trader.optimizer else {"enabled": False},
    }


@app.get("/api/export/csv")
async def export_csv(
    market: str = Query(""),
    exit_type: str = Query(""),
):
    """Export trade history as CSV file download."""
    import csv
    import io
    from datetime import datetime as _dt

    all_trades = get_trades_history(page=1, page_size=10000, market=market, exit_type=exit_type)
    trades = all_trades.get("trades", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "timestamp", "market", "side", "entry_price", "exit_price",
        "pnl_krw", "pnl_pct", "exit_type", "bars_held", "strategies",
    ])

    candle_sec = getattr(config, "CANDLE_INTERVAL_SEC", 900)
    for t in trades:
        duration = t.get("duration_sec", 0)
        bars_held = int(duration / candle_sec) if candle_sec > 0 else 0
        strategies = ", ".join(t.get("contributing_strategies", [])) if t.get("contributing_strategies") else ""
        writer.writerow([
            t.get("exit_time", ""),
            t.get("market", ""),
            t.get("side", "long"),
            t.get("entry_price", 0),
            t.get("exit_price", 0),
            round(t.get("pnl_krw", 0), 0),
            round(t.get("pnl_pct", 0), 2),
            t.get("exit_type", ""),
            bars_held,
            strategies,
        ])

    csv_content = output.getvalue()
    output.close()

    timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scalper_trades_{timestamp}.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/analytics")
async def api_analytics():
    """Full trade performance analytics."""
    initial_balance = config.PAPER_INITIAL_KRW
    if _trader and hasattr(_trader, '_analytics_cache'):
        _trader._analytics_cache.maybe_refresh()
        return _trader._analytics_cache.get_data()
    return get_full_analytics(initial_balance)


@app.get("/api/analytics/strategy/{name}")
async def api_analytics_strategy(name: str):
    """Per-strategy analytics detail."""
    return get_strategy_analytics(name)


@app.get("/api/optimizer/status")
async def api_optimizer_status():
    """Adaptive optimizer status: current params, degradation, history."""
    if _trader is None or _trader.adaptive_optimizer is None:
        return {"enabled": False}
    return _trader.adaptive_optimizer.get_status()


@app.post("/api/optimizer/trigger")
async def api_optimizer_trigger():
    """Manually trigger an optimization cycle."""
    if _trader is None or _trader.adaptive_optimizer is None:
        return {"error": "Adaptive optimizer not available"}
    open_pos = {}
    for m, p in _trader.positions.items():
        open_pos[m] = {"contributing_strategies": list(p.contributing_strategies)}
    result = _trader.adaptive_optimizer.trigger_optimization(open_pos)
    return result


@app.post("/api/optimizer/reset")
async def api_optimizer_reset(strategy: str = Query("")):
    """Reset parameters to defaults."""
    if _trader is None or _trader.param_store is None:
        return {"error": "Param store not available"}
    success = _trader.param_store.reset_to_defaults(strategy)
    if success:
        _trader.param_store.apply_to_config()
    return {"success": success, "strategy": strategy or "_all"}


@app.get("/api/optimizer/history")
async def api_optimizer_history():
    """Get parameter change history."""
    if _trader is None or _trader.param_store is None:
        return {"history": []}
    return {"history": _trader.param_store.get_history(limit=50)}


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


# ── WebSocket Endpoint ─────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_mgr.connect(ws)
    try:
        while True:
            await ws.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        ws_mgr.disconnect(ws)
    except Exception:
        ws_mgr.disconnect(ws)


# ── Dashboard HTML ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return DASHBOARD_HTML


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scalper Admin Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root{--bg:#0d1117;--surface:#161b22;--border:#30363d;--text:#c9d1d9;--text2:#8b949e;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--yellow:#d29922;--purple:#bc8cff;--orange:#f0883e}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);font-size:14px;-webkit-tap-highlight-color:transparent}
.topbar{background:var(--surface);border-bottom:1px solid var(--border);padding:12px 24px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:100}
.topbar h1{font-size:18px;color:var(--accent);white-space:nowrap}
.badge{padding:4px 10px;border-radius:4px;font-size:11px;font-weight:700;text-transform:uppercase}
.badge-paper{background:#1f3a1f;color:var(--green);border:1px solid var(--green)}
.badge-live{background:#3a1f1f;color:var(--red);border:1px solid var(--red)}
.badge-running{background:#1a3a1a;color:var(--green)}
.badge-stopped{background:#3a1a1a;color:var(--red)}
.topbar-right{margin-left:auto;display:flex;align-items:center;gap:12px}
#uptime{color:var(--text2);font-size:12px;font-family:monospace}
.btn{padding:6px 14px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;background:var(--surface);color:var(--text);transition:all .15s}
.btn:hover{border-color:var(--accent)}
.btn-green{border-color:var(--green);color:var(--green)}.btn-green:hover{background:var(--green);color:#fff}
.btn-red{border-color:var(--red);color:var(--red)}.btn-red:hover{background:var(--red);color:#fff}
.container{max-width:1400px;margin:0 auto;padding:16px 24px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:16px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px}
.card-label{color:var(--text2);font-size:11px;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}
.card-value{font-size:22px;font-weight:700}
.card-sub{font-size:11px;color:var(--text2);margin-top:2px}
.positive{color:var(--green)}.negative{color:var(--red)}
.tabs{display:flex;gap:0;margin-bottom:16px;border-bottom:1px solid var(--border)}
.tab{padding:10px 20px;cursor:pointer;color:var(--text2);border-bottom:2px solid transparent;font-size:13px;font-weight:600;transition:all .15s}
.tab:hover{color:var(--text)}.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.tab-content{display:none}.tab-content.active{display:block}
table{width:100%;border-collapse:collapse}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);font-size:13px}
th{color:var(--text2);font-size:11px;text-transform:uppercase;letter-spacing:.5px;font-weight:600;position:sticky;top:0;background:var(--surface)}
tr:hover{background:rgba(88,166,255,.04)}
.panel-title{color:var(--accent);font-size:14px;font-weight:600;margin-bottom:12px}
.chart-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.chart-box{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px}
.chart-box canvas{max-height:280px}
/* Market Watch - enhanced */
.mw-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px}
.mw-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px}
.mw-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.mw-market{font-weight:700;font-size:16px}
.mw-price{font-family:monospace;font-size:15px;font-weight:600}
.mw-trend{font-size:11px;padding:2px 8px;border-radius:3px;font-weight:600}
.trend-up{background:#1a3a1a;color:var(--green)}.trend-down{background:#3a1a1a;color:var(--red)}.trend-neutral{background:#2a2a1a;color:var(--yellow)}
.mw-chart-wrap{height:80px;margin:8px 0}
/* Indicator gauges */
.ind-section{margin-top:10px;border-top:1px solid var(--border);padding-top:10px}
.ind-row{display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:12px}
.ind-label{width:90px;color:var(--text2);flex-shrink:0}
.ind-bar-wrap{flex:1;height:16px;background:var(--bg);border-radius:3px;position:relative;overflow:hidden}
.ind-bar-zone{position:absolute;height:100%;opacity:.15}
.ind-bar-marker{position:absolute;top:0;width:3px;height:100%;border-radius:1px;z-index:2}
.ind-val{width:55px;text-align:right;font-family:monospace;font-weight:600;flex-shrink:0}
.ind-status{width:36px;text-align:center;font-size:10px;font-weight:700;border-radius:3px;padding:1px 4px;flex-shrink:0}
.sig-row{display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:12px}
.sig-name{color:var(--text2)}.sig-buy{color:var(--green);font-weight:600}.sig-sell{color:var(--red);font-weight:600}.sig-hold{color:var(--text2)}
/* MTF Confluence panel */
.mtf-panel{margin-top:10px;border-top:1px solid var(--border);padding-top:10px}
.mtf-title{font-size:11px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;display:flex;align-items:center;gap:8px}
.mtf-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;min-width:24px;text-align:center}
.mtf-badge-3{background:#1a3a1a;color:var(--green)}.mtf-badge-2{background:#1a3a1a;color:var(--green)}
.mtf-badge-1{background:#3a3a1a;color:var(--yellow)}.mtf-badge-0{background:#3a1a1a;color:var(--red)}
.mtf-tf-row{display:flex;align-items:center;gap:10px;padding:3px 0;font-size:12px}
.mtf-tf-label{width:32px;color:var(--text2);font-weight:600;flex-shrink:0}
.mtf-arrow{font-size:16px;width:20px;text-align:center;flex-shrink:0}
.mtf-arrow-bullish{color:var(--green)}.mtf-arrow-bearish{color:var(--red)}.mtf-arrow-neutral{color:var(--yellow)}
.mtf-tf-detail{font-size:11px;color:var(--text2);flex:1}
.mtf-sr{font-size:11px;color:var(--text2);margin-top:4px;display:flex;gap:16px}
.mtf-sr-label{color:var(--text2)}.mtf-sr-val{font-family:monospace;font-weight:600}
/* Portfolio Risk */
.pf-panel{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px}
.pf-title{color:var(--purple);font-size:14px;font-weight:600;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.pf-title .pf-badge{font-size:11px;padding:2px 8px;border-radius:4px;font-weight:700}
.pf-badge-ok{background:#1a3a1a;color:var(--green)}.pf-badge-warn{background:#3a3a1a;color:var(--yellow)}.pf-badge-danger{background:#3a1a1a;color:var(--red)}
.pf-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:12px}
.pf-stat{text-align:center}
.pf-stat-label{font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px}
.pf-stat-value{font-size:18px;font-weight:700}
.pf-gauge{height:8px;border-radius:4px;background:var(--bg);margin:4px 0;position:relative;overflow:hidden}
.pf-gauge-fill{height:100%;border-radius:4px;transition:width .5s}
.pf-heatmap{display:inline-grid;gap:2px;margin-top:8px}
.pf-hm-cell{width:48px;height:28px;border-radius:3px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;font-family:monospace}
.pf-hm-header{width:48px;height:18px;display:flex;align-items:center;justify-content:center;font-size:9px;color:var(--text2);font-weight:600;overflow:hidden}
.pf-conc-group{font-size:11px;padding:4px 8px;background:var(--bg);border:1px solid var(--border);border-radius:4px;margin:4px 0}
/* Positions */
.pos-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin-top:12px}
.pos-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px}
.pos-header{display:flex;justify-content:space-between;margin-bottom:8px}
.pos-market{font-weight:700;font-size:15px}
.pos-row{display:flex;justify-content:space-between;font-size:12px;padding:2px 0}
.pos-label{color:var(--text2)}
.pos-bar{height:4px;border-radius:2px;background:var(--border);margin-top:6px;position:relative}
.pos-bar-fill{height:100%;border-radius:2px;position:absolute;left:0;top:0}
/* Period / pagination / filter */
.period-btns{display:flex;gap:8px;margin-bottom:16px}
.period-btn{padding:6px 16px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:12px;background:var(--surface);color:var(--text2)}
.period-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(88,166,255,.1)}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.pagination{display:flex;justify-content:center;align-items:center;gap:8px;margin-top:16px}
.page-btn{padding:6px 12px;border:1px solid var(--border);border-radius:4px;cursor:pointer;background:var(--surface);color:var(--text);font-size:12px}
.page-btn:hover{border-color:var(--accent)}.page-btn.disabled{opacity:.3;pointer-events:none}
.page-info{color:var(--text2);font-size:12px}
.filter-row{display:flex;gap:12px;margin-bottom:12px;align-items:center}
.filter-row select{padding:6px 10px;background:var(--surface);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:12px}
.scroll-table{max-height:500px;overflow-y:auto}
/* Guide */
.guide-section{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:20px;margin-bottom:16px}
.guide-section h3{color:var(--accent);margin-bottom:10px;font-size:15px}
.guide-section p,.guide-section li{color:var(--text);font-size:13px;line-height:1.7}
.guide-section ul{padding-left:20px;margin-bottom:12px}
.guide-card{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:14px;margin-bottom:12px}
.guide-card h4{color:var(--yellow);margin-bottom:6px;font-size:14px}
.guide-highlight{color:var(--accent);font-weight:600}
.guide-buy{color:var(--green);font-weight:600}
.guide-sell{color:var(--red);font-weight:600}
/* Expandable chart panel */
.mw-card{cursor:pointer;transition:all .2s}
.mw-card.expanded{grid-column:1/-1}
.mw-detail{display:none;margin-top:12px;border-top:1px solid var(--border);padding-top:12px;max-height:550px;overflow-y:auto}
.mw-card.expanded .mw-detail{display:block}
.mw-expand-hint{font-size:10px;color:var(--text2);text-align:center;margin-top:4px}
.mw-card.expanded .mw-expand-hint{display:none}
/* Candlestick chart containers */
.tv-chart-wrap{width:100%;height:300px;border-radius:4px;overflow:hidden;background:var(--bg)}
.subchart-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:8px}
.subchart-box{background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:4px}
.subchart-label{font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px;padding:0 4px}
.subchart-canvas{width:100%;height:100px}
.subchart-canvas.vol{height:80px}
/* Trigger checklist */
.trigger-panel{margin-top:12px;border-top:1px solid var(--border);padding-top:12px}
.trigger-strat{margin-bottom:10px}
.trigger-strat-header{font-size:12px;font-weight:700;color:var(--yellow);margin-bottom:4px;display:flex;align-items:center;gap:6px}
.trigger-strat-weight{font-size:10px;color:var(--text2);font-weight:400}
.trigger-cond{display:flex;align-items:center;gap:6px;font-size:11px;padding:2px 0;padding-left:12px}
.trigger-icon{font-size:13px;width:16px;text-align:center;flex-shrink:0}
.trigger-met{color:var(--green)}.trigger-unmet{color:var(--red)}
.trigger-current{color:var(--text2);margin-left:auto;font-family:monospace;font-size:10px}
.trigger-result{font-size:11px;padding:2px 8px;margin-left:12px;color:var(--text2)}
.trigger-ensemble{margin-top:8px;padding:10px;background:var(--bg);border:1px solid var(--border);border-radius:6px}
.trigger-ensemble-title{font-size:12px;font-weight:700;color:var(--accent);margin-bottom:6px}
.trigger-ensemble-row{display:flex;justify-content:space-between;font-size:11px;padding:1px 0}
.trigger-ensemble-row .label{color:var(--text2)}.trigger-ensemble-row .val{font-weight:600}
.trigger-final{margin-top:6px;padding-top:6px;border-top:1px solid var(--border);font-size:12px;font-weight:700}
/* Guide enhancements */
.guide-live{background:var(--bg);border:1px solid var(--accent);border-radius:8px;padding:16px;margin-bottom:16px}
.guide-live h3{color:var(--accent);margin-bottom:10px;font-size:15px}
.guide-live-item{padding:6px 0;font-size:13px;border-bottom:1px solid var(--border)}
.guide-live-item:last-child{border-bottom:none}
.guide-flow{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:16px;margin-bottom:12px;font-family:monospace;font-size:12px;line-height:1.8;white-space:pre-wrap;color:var(--text)}
.guide-flow .step{color:var(--accent);font-weight:700}
.guide-flow .yes{color:var(--green)}.guide-flow .no{color:var(--red)}
/* Analytics heatmap */
.hm-grid{display:inline-grid;gap:2px}
.hm-cell{width:42px;height:32px;border-radius:3px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;font-family:monospace;cursor:default}
.hm-header{width:42px;height:20px;display:flex;align-items:center;justify-content:center;font-size:9px;color:var(--text2);font-weight:600}
.hm-row-label{width:32px;height:32px;display:flex;align-items:center;font-size:10px;color:var(--text2);font-weight:600}
.analytics-metric{text-align:center;padding:8px}
.analytics-metric .metric-label{font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px}
.analytics-metric .metric-value{font-size:20px;font-weight:700}
.analytics-metric .metric-sub{font-size:10px;color:var(--text2);margin-top:2px}
.attr-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);font-size:12px}
.attr-row:last-child{border-bottom:none}
.attr-name{font-weight:600;color:var(--text)}
.attr-bar{flex:1;margin:0 12px;height:8px;background:var(--bg);border-radius:4px;position:relative;overflow:hidden}
.attr-bar-fill{height:100%;border-radius:4px}
.attr-val{font-family:monospace;font-weight:600;min-width:80px;text-align:right}
/* Tablet */
@media(max-width:768px){
.chart-row,.mw-grid{grid-template-columns:1fr}
.topbar{flex-wrap:wrap;padding:10px 12px;gap:8px}
.topbar h1{font-size:15px}
.topbar-right{width:100%;justify-content:flex-end;gap:6px;flex-wrap:wrap}
.container{padding:12px}
.cards{grid-template-columns:repeat(3,1fr);gap:8px}
.card{padding:10px}
.card-value{font-size:18px}
.tabs{overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{padding:8px 14px;font-size:12px;white-space:nowrap}
.mw-grid{gap:12px}
.mw-card{padding:12px}
.mw-card.expanded{overflow:visible}
.mw-detail{max-height:480px}
.tv-chart-wrap{height:250px}
.subchart-row{grid-template-columns:1fr}
.subchart-canvas,.subchart-canvas.vol{height:80px}
.pos-grid{grid-template-columns:1fr}
.scroll-table{max-height:400px;overflow-x:auto}
table{min-width:600px}
.stats-grid{grid-template-columns:repeat(2,1fr)}
.period-btns{flex-wrap:wrap;gap:6px}
.filter-row{flex-wrap:wrap}
.guide-flow{font-size:11px;padding:12px;overflow-x:auto}
.guide-section{padding:14px}
.guide-card{padding:10px}
}
/* Mobile */
@media(max-width:480px){
.topbar{padding:8px 10px;gap:6px}
.topbar h1{font-size:14px}
.badge{font-size:9px;padding:3px 6px}
.topbar-right{gap:4px}
.btn{padding:5px 8px;font-size:11px}
#uptime{font-size:10px}
.container{padding:8px}
.cards{grid-template-columns:repeat(2,1fr);gap:6px}
.card{padding:8px}
.card-label{font-size:10px}
.card-value{font-size:16px}
.card-sub{font-size:10px}
.tab{padding:8px 10px;font-size:11px}
.mw-card{padding:10px}
.mw-market{font-size:14px}
.mw-price{font-size:13px}
.mw-chart-wrap{height:60px}
.ind-row{gap:4px;font-size:11px}
.ind-label{width:65px;font-size:10px}
.ind-val{width:45px;font-size:11px}
.ind-status{width:32px;font-size:9px}
.sig-row{font-size:11px}
.mw-detail{max-height:420px}
.tv-chart-wrap{height:200px}
.trigger-cond{font-size:10px;gap:4px}
.trigger-ensemble{padding:8px}
.trigger-ensemble-row{font-size:10px}
.pos-card{padding:10px}
.pos-market{font-size:13px}
.pos-row{font-size:11px}
.period-btn{padding:5px 10px;font-size:11px}
.stats-grid{grid-template-columns:1fr 1fr;gap:8px}
.page-btn{padding:4px 8px;font-size:11px}
.guide-section p,.guide-section li{font-size:12px}
.guide-flow{font-size:10px;line-height:1.6}
.guide-card h4{font-size:12px}
.panel-title{font-size:13px}
}
</style>
</head>
<body>
<div class="topbar">
  <h1>Scalper Admin</h1>
  <span id="modeBadge" class="badge badge-paper">PAPER</span>
  <span id="statusBadge" class="badge badge-stopped">STOPPED</span>
  <div class="topbar-right">
    <span id="uptime">00:00:00</span>
    <button class="btn btn-green" onclick="api('/api/bot/start','POST')">Start</button>
    <button class="btn btn-red" onclick="api('/api/bot/stop','POST')">Stop</button>
    <button class="btn" onclick="api('/api/bot/halt','POST')">Halt</button>
    <button class="btn" onclick="api('/api/bot/resume','POST')">Resume</button>
  </div>
</div>
<div class="container">
<div class="cards" id="summaryCards">
  <div class="card"><div class="card-label">Balance</div><div class="card-value" id="sc-balance" style="color:var(--accent)">-</div></div>
  <div class="card"><div class="card-label">Today PnL</div><div class="card-value" id="sc-pnl">-</div><div class="card-sub" id="sc-pnl-sub">-</div></div>
  <div class="card"><div class="card-label">Total Fees</div><div class="card-value" id="sc-fees" style="color:var(--yellow)">-</div></div>
  <div class="card"><div class="card-label">Win Rate</div><div class="card-value" id="sc-wr">-</div><div class="card-sub" id="sc-wr-sub">-</div></div>
  <div class="card"><div class="card-label">Total Trades</div><div class="card-value" id="sc-trades">-</div><div class="card-sub" id="sc-trades-sub">-</div></div>
  <div class="card"><div class="card-label">Circuit Breaker</div><div class="card-value" id="sc-cb">-</div><div class="card-sub" id="sc-cb-sub">-</div></div>
</div>
<!-- Active Markets & Optimizer Status Bar -->
<div class="cards" id="v4StatusBar" style="margin-top:8px">
  <div class="card" style="flex:2"><div class="card-label">Active Markets (Scanner)</div><div class="card-value" id="sc-active-markets" style="font-size:13px;color:var(--accent)">-</div><div class="card-sub" id="sc-scanner-sub">-</div></div>
  <div class="card" style="flex:2"><div class="card-label">Optimizer Status</div><div class="card-value" id="sc-optimizer" style="font-size:13px">-</div><div class="card-sub" id="sc-optimizer-sub">-</div></div>
  <div class="card" style="flex:2"><div class="card-label">Kelly Criterion Risk</div><div class="card-value" id="sc-kelly-risk" style="font-size:16px">-</div><div class="card-sub" id="sc-kelly-sub">-</div></div>
  <div class="card" style="flex:2"><div class="card-label">Portfolio VaR</div><div class="card-value" id="sc-portfolio-var" style="font-size:16px;color:var(--purple)">-</div><div class="card-sub" id="sc-portfolio-var-sub">-</div></div>
</div>
<div class="tabs">
  <div class="tab active" data-tab="realtime">Real-time</div>
  <div class="tab" data-tab="portfolio">Portfolio Risk</div>
  <div class="tab" data-tab="performance">Performance</div>
  <div class="tab" data-tab="analytics">Analytics</div>
  <div class="tab" data-tab="strategy">Strategy</div>
  <div class="tab" data-tab="history">Trade History</div>
  <div class="tab" data-tab="optimizer">전략 최적화</div>
  <div class="tab" data-tab="guide">Guide</div>
</div>

<!-- Tab 1: Real-time -->
<div id="tab-realtime" class="tab-content active">
  <div class="panel-title">Market Watch</div>
  <div class="mw-grid" id="marketWatch"></div>
  <div style="margin-top:20px"><div class="panel-title">Open Positions</div><div id="positions"><p style="color:var(--text2)">No open positions</p></div></div>
</div>

<!-- Tab: Portfolio Risk -->
<div id="tab-portfolio" class="tab-content">
  <div class="pf-panel">
    <div class="pf-title">Portfolio Risk Overview <span class="pf-badge pf-badge-ok" id="pf-status-badge">OK</span></div>
    <div class="pf-row">
      <div class="pf-stat">
        <div class="pf-stat-label">Total Exposure</div>
        <div class="pf-stat-value" id="pf-exposure" style="color:var(--accent)">-</div>
      </div>
      <div class="pf-stat">
        <div class="pf-stat-label">Portfolio VaR (95%)</div>
        <div class="pf-stat-value" id="pf-var-value">-</div>
        <div class="pf-gauge"><div class="pf-gauge-fill" id="pf-var-gauge" style="width:0%;background:var(--green)"></div></div>
        <div style="font-size:10px;color:var(--text2)" id="pf-var-detail">-</div>
      </div>
      <div class="pf-stat">
        <div class="pf-stat-label">Diversification Ratio</div>
        <div class="pf-stat-value" id="pf-div-ratio" style="color:var(--green)">-</div>
        <div style="font-size:10px;color:var(--text2)" id="pf-div-detail">-</div>
      </div>
    </div>
    <div class="pf-row">
      <div class="pf-stat">
        <div class="pf-stat-label">Concentration Risk</div>
        <div class="pf-stat-value" id="pf-conc-status">-</div>
        <div id="pf-conc-groups"></div>
      </div>
      <div class="pf-stat">
        <div class="pf-stat-label">Max Correlated Pair</div>
        <div class="pf-stat-value" id="pf-max-corr" style="font-size:14px">-</div>
      </div>
      <div class="pf-stat">
        <div class="pf-stat-label">Markets Tracked</div>
        <div class="pf-stat-value" id="pf-markets-tracked" style="color:var(--accent)">-</div>
        <div style="font-size:10px;color:var(--text2)" id="pf-data-status">-</div>
      </div>
    </div>
  </div>
  <div class="pf-panel">
    <div class="pf-title">Correlation Heatmap</div>
    <div id="pf-heatmap" style="overflow-x:auto"></div>
  </div>
</div>

<!-- Tab 2: Performance -->
<div id="tab-performance" class="tab-content">
  <div class="period-btns">
    <button class="period-btn active" data-period="today">Today</button>
    <button class="period-btn" data-period="week">7 Days</button>
    <button class="period-btn" data-period="month">30 Days</button>
    <button class="period-btn" data-period="all">All Time</button>
  </div>
  <div class="stats-grid" id="perfStats"></div>
  <div class="chart-row"><div class="chart-box"><canvas id="equityChart"></canvas></div><div class="chart-box"><canvas id="dailyPnlChart"></canvas></div></div>
  <div class="chart-row"><div class="chart-box"><canvas id="exitTypeChart"></canvas></div><div class="chart-box"><canvas id="marketPnlChart"></canvas></div></div>
  <div class="chart-row"><div class="chart-box" id="perfSummaryBox"></div><div class="chart-box" id="perfBlank"></div></div>
</div>

<!-- Tab: Analytics (Trade Performance) -->
<div id="tab-analytics" class="tab-content">
  <!-- Risk Metrics Summary -->
  <div class="panel-title" style="margin-bottom:12px">리스크 지표</div>
  <div class="stats-grid" id="analyticsRiskCards"></div>

  <!-- Row 1: Strategy Performance Comparison + Cumulative P&L by Strategy -->
  <div class="chart-row">
    <div class="chart-box"><canvas id="analyticsStrategyBar"></canvas></div>
    <div class="chart-box"><canvas id="analyticsCumLine"></canvas></div>
  </div>

  <!-- Row 2: Win Rate by Hour Heatmap + Drawdown Chart -->
  <div class="chart-row">
    <div class="chart-box">
      <div class="panel-title" style="margin-bottom:8px">시간대별 승률 히트맵</div>
      <div id="analyticsHourlyHeatmap" style="overflow-x:auto"></div>
    </div>
    <div class="chart-box"><canvas id="analyticsDrawdown"></canvas></div>
  </div>

  <!-- Row 3: Trade Distribution Histogram + Day-of-Week Performance -->
  <div class="chart-row">
    <div class="chart-box"><canvas id="analyticsDistribution"></canvas></div>
    <div class="chart-box"><canvas id="analyticsDowBar"></canvas></div>
  </div>

  <!-- Row 4: Monthly Returns Table + Strategy Attribution -->
  <div class="chart-row">
    <div class="chart-box" id="analyticsMonthlyTable" style="overflow-y:auto;max-height:350px"></div>
    <div class="chart-box" id="analyticsAttribution" style="overflow-y:auto;max-height:350px"></div>
  </div>

  <!-- Row 5: Strategy Correlation + Ensemble Accuracy -->
  <div class="chart-row">
    <div class="chart-box" id="analyticsCorrelation" style="overflow-y:auto;max-height:300px"></div>
    <div class="chart-box" id="analyticsEnsembleAccuracy"></div>
  </div>
</div>

<!-- Tab 3: Strategy -->
<div id="tab-strategy" class="tab-content">
  <div class="chart-row"><div class="chart-box"><canvas id="weightRadar"></canvas></div><div class="chart-box" id="strategyTable"></div></div>
</div>

<!-- Tab 4: History -->
<div id="tab-history" class="tab-content">
  <div class="filter-row">
    <select id="filterMarket"><option value="">All Markets</option></select>
    <select id="filterExit"><option value="">All Exit Types</option></select>
    <button class="btn" onclick="loadHistory(1)">Filter</button>
    <button class="btn" onclick="exportCSV()">Export CSV</button>
  </div>
  <div class="scroll-table"><table>
    <thead><tr><th>Time</th><th>Market</th><th>Entry</th><th>Exit</th><th>PnL %</th><th>PnL KRW</th><th>Fee</th><th>Exit Type</th><th>Duration</th></tr></thead>
    <tbody id="historyBody"></tbody>
  </table></div>
  <div class="pagination" id="pagination"></div>
</div>

<!-- Tab: 전략 최적화 (Adaptive Optimizer) -->
<div id="tab-optimizer" class="tab-content">
  <div class="panel-title" style="margin-bottom:16px">전략 최적화 엔진
    <button class="btn btn-green" style="margin-left:16px;font-size:11px" id="opt-trigger-btn" onclick="triggerOptimization(this)">수동 최적화 실행</button>
    <button class="btn" style="margin-left:8px;font-size:11px" onclick="resetParams('')">전체 초기화</button>
    <span id="opt-last-run" style="margin-left:16px;color:var(--text2);font-size:11px"></span>
  </div>

  <!-- Regime & Status Row -->
  <div class="cards" style="margin-bottom:16px">
    <div class="card"><div class="card-label">시장 레짐</div><div class="card-value" id="opt-regime" style="font-size:16px">-</div></div>
    <div class="card"><div class="card-label">최적화 횟수</div><div class="card-value" id="opt-run-count">0</div></div>
    <div class="card"><div class="card-label">파라미터 잠금</div><div class="card-value" id="opt-locked" style="font-size:14px">-</div></div>
    <div class="card"><div class="card-label">롤백 대기</div><div class="card-value" id="opt-rollback-count" style="font-size:16px">0</div></div>
  </div>

  <!-- Degradation Status -->
  <div class="chart-box" style="margin-bottom:16px">
    <div class="panel-title" style="margin-bottom:8px">성능 저하 감지 (Degradation Detection)</div>
    <table>
      <thead><tr><th>전략</th><th>상태</th><th>승률 Z</th><th>샤프 Z</th><th>평균PnL Z</th><th>기준 승률</th><th>현재 승률</th><th>메시지</th></tr></thead>
      <tbody id="opt-degradation-body"><tr><td colspan="8" style="color:var(--text2);text-align:center">데이터 로딩 중...</td></tr></tbody>
    </table>
  </div>

  <!-- Current Parameters per Strategy -->
  <div class="chart-box" style="margin-bottom:16px">
    <div class="panel-title" style="margin-bottom:8px">전략별 현재 파라미터</div>
    <div id="opt-params-container">
      <table>
        <thead><tr><th>전략</th><th>파라미터</th><th>현재값</th><th>기본값</th><th>범위</th><th>액션</th></tr></thead>
        <tbody id="opt-params-body"><tr><td colspan="6" style="color:var(--text2);text-align:center">데이터 로딩 중...</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- Ensemble Weights -->
  <div class="chart-box" style="margin-bottom:16px">
    <div class="panel-title" style="margin-bottom:8px">앙상블 가중치</div>
    <div class="cards" id="opt-weights-cards"></div>
  </div>

  <!-- Optimization History -->
  <div class="chart-box" style="margin-bottom:16px">
    <div class="panel-title" style="margin-bottom:8px">최적화 이력</div>
    <div style="max-height:400px;overflow-y:auto">
      <table>
        <thead><tr><th>시간</th><th>전략</th><th>액션</th><th>OOS 개선</th><th>과적합 비율</th><th>상세</th></tr></thead>
        <tbody id="opt-history-body"><tr><td colspan="6" style="color:var(--text2);text-align:center">이력 없음</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- Post-Optimization Tracking -->
  <div class="chart-box" style="margin-bottom:16px">
    <div class="panel-title" style="margin-bottom:8px">최적화 후 성과 추적</div>
    <table>
      <thead><tr><th>전략</th><th>거래 수</th><th>승리</th><th>연속 패배</th><th>롤백 준비</th></tr></thead>
      <tbody id="opt-postopt-body"><tr><td colspan="5" style="color:var(--text2);text-align:center">추적 데이터 없음</td></tr></tbody>
    </table>
  </div>
</div>

<!-- Tab 5: Guide -->
<div id="tab-guide" class="tab-content">

  <!-- Live status interpretation -->
  <div class="guide-live" id="guideLiveStatus">
    <h3>현재 상태 해석 (실시간)</h3>
    <div id="guideLiveContent"><p style="color:var(--text2)">데이터 로딩 중...</p></div>
  </div>

  <!-- Ensemble voting flowchart -->
  <div class="guide-section">
    <h3>앙상블 투표 과정 (플로우차트)</h3>
    <div class="guide-flow"><span class="step">[1단계] 4개 전략 독립 분석</span>
  각 전략이 15분봉 데이터를 받아 BUY / SELL / HOLD 판단
  RSI+BB (30%) │ VWAP+Vol (25%) │ StochRSI (25%) │ EMA Cross (20%)
        ↓               ↓               ↓               ↓
<span class="step">[2단계] 쿨다운 체크</span>
  마지막 거래 후 3봉(45분) 경과했는가?
  <span class="yes">→ YES: 다음 단계</span>  <span class="no">→ NO: HOLD (쿨다운 대기)</span>

<span class="step">[3단계] 변동성 레짐 체크</span>
  현재 변동성이 적정 범위(10~95 퍼센타일)인가?
  <span class="yes">→ YES: 다음 단계</span>  <span class="no">→ NO: HOLD (변동성 부적합)</span>

<span class="step">[4단계] 투표 집계</span>
  BUY 투표 수 ≥ 2개? (MIN_AGREEMENT)
  <span class="yes">→ YES: 다음 단계</span>  <span class="no">→ NO: HOLD (합의 부족)</span>

<span class="step">[5단계] 신뢰도 검증</span>
  가중 합산 신뢰도 ≥ 0.25? (가중치 × 개별 신뢰도의 합)
  <span class="yes">→ YES: 다음 단계</span>  <span class="no">→ NO: HOLD (신뢰도 부족)</span>

<span class="step">[6단계] 추세 필터</span>
  EMA50 기울기가 양수인가? (상승추세)
  <span class="yes">→ YES: 다음 단계</span>  <span class="no">→ NO: HOLD (하락/횡보 추세)</span>

<span class="step">[7단계] 가격 위치 필터</span>
  현재 가격 > EMA50? (추세 EMA 위)
  <span class="yes">→ YES: ✅ BUY 실행!</span>  <span class="no">→ NO: HOLD (가격이 추세선 아래)</span></div>
  </div>

  <div class="guide-section">
    <h3>매매 봇 작동 원리</h3>
    <p>이 봇은 <span class="guide-highlight">4개의 전략</span>이 동시에 시장을 분석하고, <span class="guide-highlight">최소 2개 이상</span>이 "매수"에 동의해야 실제 매수가 실행되는 <b>앙상블 투표 시스템</b>입니다.</p>
    <ul>
      <li>각 전략은 독립적으로 BUY / SELL / HOLD 시그널을 생성합니다</li>
      <li>각 전략에는 가중치가 있어, 가중 합산된 신뢰도가 <span class="guide-highlight">25% 이상</span>이어야 합니다</li>
      <li>추가로 <span class="guide-buy">상승추세</span>(EMA50 기울기 양수 + 가격이 EMA50 위)일 때만 매수를 허용합니다</li>
      <li>매매 후 최소 <span class="guide-highlight">3봉(45분) 쿨다운</span> (같은 코인 재진입 방지)</li>
      <li>변동성이 너무 낮거나(횡보장) 너무 높으면(급변장) 자동으로 거래를 쉽니다</li>
    </ul>
  </div>

  <div class="guide-card">
    <h4>1. RSI + Bollinger Band (rsi_bb) - 평균 회귀 전략 [가중치 30%]</h4>
    <p><b>핵심 아이디어:</b> "가격이 너무 빠졌으니 반등할 것이다" - 과매도 구간에서 반등 시작 시 매수</p>
    <p style="margin:8px 0"><b>지표 설명:</b></p>
    <ul>
      <li><b>RSI (상대강도지수, 기간=14)</b>: 최근 14봉간 상승폭 vs 하락폭의 비율. 0~100 범위</li>
      <li>RSI <span class="guide-buy">&lt; 35</span> = 과매도 (최근 하락이 압도적 → 반등 가능성 ↑)</li>
      <li>RSI <span class="guide-sell">&gt; 65</span> = 과매수 (최근 상승이 압도적 → 하락 가능성 ↑)</li>
      <li><b>BB%B (볼린저밴드 위치, 기간=20, 표준편차=2)</b>: 현재 가격이 통계적 밴드의 어디에 있는지</li>
      <li>BB%B = 0% → 하단밴드 (통계적으로 가격이 매우 낮음), 100% → 상단밴드 (매우 높음)</li>
    </ul>
    <p style="margin:8px 0"><b>매수 조건 (3개 모두 충족 필요):</b></p>
    <ul>
      <li>✅ RSI &lt; 35 (과매도 진입)</li>
      <li>✅ BB%B &lt; 15% (밴드 하단 근처 - 통계적으로 '싸다')</li>
      <li>✅ RSI가 전봉 대비 반등 시작 (이전 RSI &lt; 현재 RSI)</li>
    </ul>
    <p style="margin:8px 0"><b>신뢰도:</b> RSI가 35에서 멀수록 높음. 계산: min(1.0, (35-RSI)/35 + 0.2)</p>
  </div>

  <div class="guide-card">
    <h4>2. VWAP + Volume (vwap_volume) - 거래량 돌파 전략 [가중치 25%]</h4>
    <p><b>핵심 아이디어:</b> "큰손(거래량 급등)이 밀어올린다" - 거래량 급등 + VWAP 돌파 시 매수</p>
    <p style="margin:8px 0"><b>지표 설명:</b></p>
    <ul>
      <li><b>VWAP (거래량가중평균가, 기간=14)</b>: 거래량을 가중치로 한 평균 매입 단가. 기관의 기준선</li>
      <li>가격 &gt; VWAP → 대다수가 수익 중 (매수세 우위), 가격 &lt; VWAP → 대다수가 손실 중 (매도세 우위)</li>
      <li><b>거래량 비율</b>: 현재봉 거래량 / 14봉 평균. <span class="guide-highlight">1.3배 이상</span> = "거래량 급증(서지)"</li>
    </ul>
    <p style="margin:8px 0"><b>매수 조건 (3개 모두 충족 필요):</b></p>
    <ul>
      <li>✅ 최근 2봉 내 VWAP 상향돌파 (아래→위)</li>
      <li>✅ 현재 가격이 VWAP 위 유지 중</li>
      <li>✅ 최근 2봉 중 거래량이 평균의 1.3배 이상</li>
    </ul>
    <p style="margin:8px 0"><b>신뢰도:</b> 거래량 급증 강도 + VWAP 대비 가격 차이 기반</p>
  </div>

  <div class="guide-card">
    <h4>3. Stochastic RSI (stoch_rsi) - 모멘텀 전략 [가중치 25%]</h4>
    <p><b>핵심 아이디어:</b> "RSI의 RSI"로 더 민감한 과매수/과매도를 잡아내, 교차 시점에 진입</p>
    <p style="margin:8px 0"><b>지표 설명:</b></p>
    <ul>
      <li><b>K선 (빠른선, 기간=5)</b>: StochRSI의 이동평균. 민감하게 반응</li>
      <li><b>D선 (느린선, 기간=3)</b>: K선의 이동평균. 노이즈 필터링</li>
      <li>0~100 범위. <span class="guide-buy">&lt; 30</span> = 과매도 구간, <span class="guide-sell">&gt; 70</span> = 과매수 구간</li>
      <li><b>골든크로스</b>: K선이 D선을 아래에서 위로 교차 → 상승 모멘텀 전환 신호</li>
    </ul>
    <p style="margin:8px 0"><b>매수 조건 (2개 모두 충족 필요):</b></p>
    <ul>
      <li>✅ K선이 D선을 상향교차 (골든크로스) - 이전봉: K≤D, 현재봉: K&gt;D</li>
      <li>✅ K 또는 D가 30 이하 (과매도 구간에서의 교차만 유효)</li>
    </ul>
    <p style="margin:8px 0"><b>신뢰도:</b> 과매도 깊이에 비례. 계산: min(1.0, (30-min(K,D))/30), 최소 0.3</p>
  </div>

  <div class="guide-card">
    <h4>4. EMA Crossover (ema_cross) - 추세 추종 전략 [가중치 20%]</h4>
    <p><b>핵심 아이디어:</b> "추세가 전환됐다" - 단기 이동평균이 중기를 돌파하면 새 추세에 올라탐</p>
    <p style="margin:8px 0"><b>지표 설명:</b></p>
    <ul>
      <li><b>EMA 5 (단기)</b>: 최근 5봉 지수이동평균. 가격 변화에 가장 빠르게 반응</li>
      <li><b>EMA 13 (중기)</b>: 최근 13봉 지수이동평균. 약간 느리지만 안정적</li>
      <li><b>EMA 34 (추세)</b>: 최근 34봉 지수이동평균. 중기 추세 방향 판단 기준선</li>
      <li>EMA5 &gt; EMA13 → 단기 상승세, EMA5 &lt; EMA13 → 단기 하락세</li>
    </ul>
    <p style="margin:8px 0"><b>매수 조건 (2개 모두 충족 필요):</b></p>
    <ul>
      <li>✅ EMA5이 EMA13을 상향교차 (골든크로스) - 이전봉: EMA5≤EMA13, 현재봉: EMA5&gt;EMA13</li>
      <li>✅ 현재 가격이 EMA34 위 (중기 추세가 상승일 때만)</li>
    </ul>
    <p style="margin:8px 0"><b>신뢰도:</b> EMA5-EMA13 간격(스프레드)에 비례. 벌어질수록 추세가 강함</p>
  </div>

  <div class="guide-section">
    <h3>손절/익절 시스템</h3>
    <ul>
      <li><b>손절 (Stop Loss)</b>: ATR(변동성) × 1.5배 기반 자동 계산. 최소 0.5%, 최대 3.0%</li>
      <li><b>익절 (Take Profit)</b>: ATR × 4.0배 또는 최소 3.0% 도달 시 자동 매도</li>
      <li><b>트레일링 스탑</b>: +0.8% 수익 도달 후 활성화, 고점 대비 0.3% 하락 시 매도 → 수익 극대화</li>
      <li><b>시그널 매도</b>: 진입 후 4봉(1시간) 경과 + 수익 +0.3% 이상일 때, 앙상블이 SELL 판단하면 매도</li>
      <li><b>Breakeven 스탑</b>: 48봉(12시간) 후 BEP+0.2% 버퍼로 손절선 이동</li>
      <li><b>서킷 브레이커</b>: 일일 손실 5% 또는 연속 5패 시 10분간 자동 거래 중지</li>
      <li><b>수수료</b>: 업비트 편도 0.05% (왕복 0.1%). 모든 PnL에 자동 반영됨</li>
    </ul>
  </div>

  <div class="guide-section">
    <h3>상세 차트 읽는 법</h3>
    <p>Market Watch에서 코인 카드를 <b>클릭</b>하면 상세 차트가 열립니다:</p>
    <ul>
      <li><b>메인 캔들스틱 차트</b>: 초록봉=상승(양봉), 빨간봉=하락(음봉). 최근 60개 15분봉</li>
      <li style="color:var(--purple)"><b>보라색 점선</b> = 볼린저밴드 상/하한선 (가격의 통계적 범위)</li>
      <li style="color:var(--orange)"><b>주황선</b> = EMA5 (단기), <span style="color:var(--yellow)">노란선</span> = EMA13 (중기), <span style="color:var(--accent)">파란선</span> = EMA34 (추세)</li>
      <li style="color:var(--green)"><b>연초록 점선</b> = VWAP (거래량가중평균가)</li>
    </ul>
    <p style="margin-top:8px"><b>서브차트:</b></p>
    <ul>
      <li><b>RSI</b>: 보라색 라인. 초록 점선(35)과 빨간 점선(65) 사이가 정상 구간</li>
      <li><b>StochRSI</b>: 파란선(K) + 주황점선(D). 초록 점선(30) 아래에서 K가 D를 상향교차하면 매수 시그널</li>
      <li><b>Volume</b>: 파란 막대=보통, 노란 막대=거래량 서지(1.3x 이상). 노란 점선=서지 기준선</li>
    </ul>
  </div>

  <div class="guide-section">
    <h3>지표 게이지 바 읽는 법</h3>
    <p>각 코인 카드의 게이지 바:</p>
    <ul>
      <li><span style="color:var(--green)">초록 영역</span> = 매수 유리 (과매도), <span style="color:var(--red)">빨간 영역</span> = 매도 유리 (과매수), 가운데 = 중립</li>
      <li><span style="color:var(--accent)">파란 마커(|)</span> = 현재 값 위치. 초록 영역 안에 있으면 해당 지표가 매수 조건 충족</li>
      <li>RSI: 0-35(초록) 35-65(중립) 65-100(빨강) | BB%B: 0-15%(초록) 15-85%(중립) 85-100%(빨강)</li>
      <li>StochRSI K: 0-30(초록) 30-70(중립) 70-100(빨강) | Volume: 1.3x 이상이면 노란색 "SURGE"</li>
    </ul>
  </div>

  <div class="guide-section">
    <h3>매매 조건 체크리스트 읽는 법</h3>
    <p>코인 카드를 클릭하면 하단에 "매매 조건 체크리스트"가 나타납니다:</p>
    <ul>
      <li>✅ = 조건 충족 (초록), ❌ = 조건 미충족 (빨강)</li>
      <li>각 전략별로 모든 조건이 ✅여야 해당 전략이 BUY 투표를 합니다</li>
      <li>"앙상블 최종 판단"에서 투표 수, 신뢰도, 추세를 종합하여 최종 결정</li>
      <li>HOLD = 조건 부족으로 대기 중 (이것이 정상! 무분별한 진입 방지)</li>
    </ul>
  </div>
</div>

</div>

<script>
let charts={},currentPeriod='today',historyPage=1;
const fmt=n=>Math.round(n).toLocaleString('ko-KR');
const fmtPct=n=>(n>=0?'+':'')+n.toFixed(2)+'%';
const cls=n=>n>=0?'positive':'negative';
function fmtDuration(s){if(s<60)return Math.round(s)+'s';if(s<3600)return Math.round(s/60)+'m';return Math.round(s/3600)+'h '+Math.round((s%3600)/60)+'m'}
function fmtUptime(s){const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sc=Math.floor(s%60);return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sc).padStart(2,'0')}`}
async function api(url,method='GET'){try{const r=await fetch(url,{method});return await r.json()}catch(e){console.error(url,e);return null}}

// Tabs
document.querySelectorAll('.tab').forEach(tab=>{
  tab.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-'+tab.dataset.tab).classList.add('active');
    if(tab.dataset.tab==='performance')loadPerformance();
    if(tab.dataset.tab==='analytics')loadAnalytics();
    if(tab.dataset.tab==='strategy')loadStrategy();
    if(tab.dataset.tab==='history')loadHistory(1);
    if(tab.dataset.tab==='optimizer')loadOptimizerTab();
    if(tab.dataset.tab==='guide')refreshGuideLive();
    if(tab.dataset.tab==='portfolio')refreshStatus();
  });
});
document.querySelectorAll('.period-btn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.period-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');currentPeriod=btn.dataset.period;loadPerformance();
  });
});

// ── Status (5s) - targeted DOM updates ──
let _prevStatus=null;
function setEl(id,text,cls){const e=document.getElementById(id);if(!e)return;if(e.textContent!==text)e.textContent=text;if(cls!==undefined)e.className='card-value '+cls}
function applyStatus(d){
  if(!d)return;
  const mb=document.getElementById('modeBadge');mb.textContent=d.paper?'PAPER':'LIVE';mb.className='badge '+(d.paper?'badge-paper':'badge-live');
  const sb=document.getElementById('statusBadge');sb.textContent=d.running?'RUNNING':'STOPPED';sb.className='badge '+(d.running?'badge-running':'badge-stopped');
  document.getElementById('uptime').textContent=fmtUptime(d.uptime_sec||0);
  const cb=d.circuit_breaker||{};
  setEl('sc-balance',fmt(d.balance_krw)+' KRW');
  const pnlEl=document.getElementById('sc-pnl');if(pnlEl){pnlEl.textContent=(d.daily_pnl>=0?'+':'')+fmt(d.daily_pnl);pnlEl.className='card-value '+cls(d.daily_pnl)}
  setEl('sc-pnl-sub',(d.today_trades||0)+' trades today');
  setEl('sc-fees',fmt(d.total_fees_krw||0));
  const wrEl=document.getElementById('sc-wr');if(wrEl){wrEl.textContent=d.win_rate.toFixed(1)+'%';wrEl.className='card-value '+(d.win_rate>=50?'positive':'negative')}
  setEl('sc-wr-sub',d.wins+'W / '+d.losses+'L');
  setEl('sc-trades',String(d.total_trades));
  setEl('sc-trades-sub','Cycle #'+d.cycle_count);
  const cbEl=document.getElementById('sc-cb');if(cbEl){cbEl.textContent=cb.can_trade?'OK':(cb.reason||'OFF');cbEl.className='card-value '+(cb.can_trade?'positive':'negative')}
  setEl('sc-cb-sub','Consec. losses: '+(cb.consecutive_losses||0));
  // v4: Active Markets (scanner)
  const am=d.active_markets||[];
  const amEl=document.getElementById('sc-active-markets');
  if(amEl)amEl.textContent=am.length?am.join(', '):'(static)';
  const ss=d.scanner_status||{};
  const ssSub=document.getElementById('sc-scanner-sub');
  if(ssSub){if(ss.enabled){const ago=ss.last_scan?(Math.round((Date.now()/1000-ss.last_scan)/60))+'m ago':'never';ssSub.textContent='Last scan: '+ago+' | Top '+ss.top_n}else{ssSub.textContent='Scanner disabled'}}
  // v4: Optimizer status
  const os=d.optimizer_status||{};
  const osEl=document.getElementById('sc-optimizer');
  if(osEl){if(os.enabled){osEl.textContent='Score: '+os.best_score+' (#'+os.run_count+')';osEl.className='card-value '+(os.best_score>0?'positive':'')}else{osEl.textContent='Disabled';osEl.className='card-value'}}
  const osSub=document.getElementById('sc-optimizer-sub');
  if(osSub){if(os.enabled&&os.best_profile){const bp=os.best_profile;osSub.textContent='SL:'+((bp.sl_cap||0)*100).toFixed(1)+'% TP:'+((bp.tp||0)*100).toFixed(1)+'% Trail:'+((bp.trail_act||0)*100).toFixed(1)+'%'}else{osSub.textContent=os.enabled?'Waiting for first run...':'Optimizer disabled'}}
  // Kelly Criterion status
  const ks=d.kelly_status||{};
  const kellyEl=document.getElementById('sc-kelly-risk');
  const kellySub=document.getElementById('sc-kelly-sub');
  if(kellyEl){
    if(ks.enabled&&ks.sufficient_data){
      const curRisk=ks.current_risk_pct||0;
      const defRisk=ks.default_risk_pct||0;
      const diff=curRisk-defRisk;
      const kellyColor=diff>=0?'var(--green)':'var(--red)';
      kellyEl.innerHTML=curRisk.toFixed(2)+'% <span style="font-size:11px;color:'+kellyColor+'">'+(diff>=0?'+':'')+diff.toFixed(2)+'%</span>';
      kellyEl.style.color=kellyColor;
    }else if(ks.enabled){
      kellyEl.textContent=ks.default_risk_pct?.toFixed(2)+'%';
      kellyEl.style.color='var(--text2)';
    }else{
      kellyEl.textContent='Disabled';
      kellyEl.style.color='var(--text2)';
    }
  }
  if(kellySub){
    if(ks.enabled&&ks.sufficient_data){
      kellySub.textContent='WR: '+ks.win_rate.toFixed(1)+'% | W/L: '+(ks.avg_win_pct||0).toFixed(1)+'/'+(ks.avg_loss_pct||0).toFixed(1)+'% | '+ks.trades_used+' trades';
    }else if(ks.enabled){
      kellySub.textContent='Waiting for 10+ trades...';
    }else{
      kellySub.textContent='Kelly disabled in config';
    }
  }
  // Portfolio Risk status card + panel
  applyPortfolioRisk(d.portfolio_stats||{});
  renderPositions(d.open_positions||{});
  _prevStatus=d;
}
async function refreshStatus(){
  const d=await api('/api/status');applyStatus(d);
}

function applyPortfolioRisk(ps){
  // Top status card
  const varEl=document.getElementById('sc-portfolio-var');
  const varSub=document.getElementById('sc-portfolio-var-sub');
  if(varEl){
    if(ps.enabled){
      const pct=(ps.var_pct||0)*100;
      const maxPct=(ps.max_var_pct||0.05)*100;
      const color=pct>=maxPct?'var(--red)':pct>=maxPct*0.7?'var(--yellow)':'var(--green)';
      varEl.textContent=pct.toFixed(2)+'%';varEl.style.color=color;
    }else{varEl.textContent='Disabled';varEl.style.color='var(--text2)'}
  }
  if(varSub){
    if(ps.enabled){
      const expStr=fmt(ps.total_exposure_krw||0);
      const conc=ps.is_concentrated?'CONCENTRATED':'OK';
      varSub.textContent='Exp: '+expStr+' | Conc: '+conc;
    }else{varSub.textContent='Portfolio risk disabled'}
  }
  // Tab panel detail
  if(!ps.enabled)return;
  // Exposure
  const expEl=document.getElementById('pf-exposure');
  if(expEl)expEl.textContent=fmt(ps.total_exposure_krw||0)+' KRW';
  // VaR
  const pfVar=document.getElementById('pf-var-value');
  if(pfVar){
    const pct=(ps.var_pct||0)*100;const maxPct=(ps.max_var_pct||5)*100;
    const color=pct>=maxPct?'var(--red)':pct>=maxPct*0.7?'var(--yellow)':'var(--green)';
    pfVar.textContent=pct.toFixed(2)+'% ('+fmt(ps.var_krw||0)+' KRW)';pfVar.style.color=color;pfVar.style.fontSize='15px';
  }
  const pfGauge=document.getElementById('pf-var-gauge');
  if(pfGauge){
    const pct=(ps.var_pct||0)*100;const maxPct=(ps.max_var_pct||5)*100;
    const w=Math.min(100,pct/maxPct*100);
    const gc=pct>=maxPct?'var(--red)':pct>=maxPct*0.7?'var(--yellow)':'var(--green)';
    pfGauge.style.width=w+'%';pfGauge.style.background=gc;
  }
  const pfVarD=document.getElementById('pf-var-detail');
  if(pfVarD)pfVarD.textContent='Limit: '+((ps.max_var_pct||0.05)*100).toFixed(1)+'% | Undiv: '+fmt(ps.undiversified_var_krw||0)+' KRW';
  // Div ratio
  const drEl=document.getElementById('pf-div-ratio');
  if(drEl){const r=ps.diversification_ratio||1;drEl.textContent=r.toFixed(2)+'x';drEl.style.color=r>=1.3?'var(--green)':r>=1.1?'var(--yellow)':'var(--red)'}
  const drD=document.getElementById('pf-div-detail');
  if(drD)drD.textContent=ps.diversification_ratio>=1.1?'Well diversified':'Low diversification';
  // Concentration
  const concEl=document.getElementById('pf-conc-status');
  if(concEl){
    if(ps.is_concentrated){concEl.innerHTML='<span style="color:var(--red)">ALERT</span>';concEl.style.fontSize='18px'}
    else{concEl.innerHTML='<span style="color:var(--green)">OK</span>';concEl.style.fontSize='18px'}
  }
  const concG=document.getElementById('pf-conc-groups');
  if(concG){
    const groups=ps.correlated_groups||[];
    if(groups.length){
      concG.innerHTML=groups.map(g=>'<div class="pf-conc-group"><span style="color:var(--yellow)">'+g.markets.join(' + ')+'</span> corr='+g.max_corr+' ('+Math.round(g.exposure_pct*100)+'% exposure)</div>').join('');
    }else{concG.innerHTML='<div style="font-size:11px;color:var(--text2)">No concentrated groups</div>'}
  }
  // Max corr pair
  const mcEl=document.getElementById('pf-max-corr');
  if(mcEl){
    const mc=ps.max_corr_pair||{};
    if(mc.a&&mc.b){
      const short_a=(mc.a||'').replace('KRW-','');const short_b=(mc.b||'').replace('KRW-','');
      const cc=mc.corr>=0.8?'var(--red)':mc.corr>=0.5?'var(--yellow)':'var(--green)';
      mcEl.innerHTML='<span style="color:'+cc+'">'+short_a+'/'+short_b+': '+mc.corr.toFixed(3)+'</span>';
    }else{mcEl.textContent='N/A'}
  }
  // Markets tracked
  const mtEl=document.getElementById('pf-markets-tracked');
  if(mtEl)mtEl.textContent=String(ps.markets_tracked||0);
  const dsEl=document.getElementById('pf-data-status');
  if(dsEl)dsEl.textContent=(ps.markets_with_data||0)+' with sufficient data';
  // Status badge
  const badge=document.getElementById('pf-status-badge');
  if(badge){
    if(ps.is_concentrated||(ps.var_pct||0)>=(ps.max_var_pct||0.05)){badge.textContent='DANGER';badge.className='pf-badge pf-badge-danger'}
    else if((ps.var_pct||0)>=(ps.max_var_pct||0.05)*0.7){badge.textContent='WARN';badge.className='pf-badge pf-badge-warn'}
    else{badge.textContent='OK';badge.className='pf-badge pf-badge-ok'}
  }
  // Heatmap
  renderCorrelationHeatmap(ps.correlation_matrix||{});
}
function renderCorrelationHeatmap(matrix){
  const el=document.getElementById('pf-heatmap');if(!el)return;
  const mkts=Object.keys(matrix);
  if(!mkts.length){el.innerHTML='<p style="color:var(--text2);font-size:12px">Waiting for correlation data...</p>';return}
  const labels=mkts.map(m=>m.replace('KRW-',''));
  const n=mkts.length;
  // Build grid: (n+1) columns for header col + data cols
  let html='<div class="pf-heatmap" style="grid-template-columns:repeat('+(n+1)+',48px)">';
  // Header row: empty corner + column labels
  html+='<div class="pf-hm-header"></div>';
  for(let j=0;j<n;j++)html+='<div class="pf-hm-header">'+labels[j]+'</div>';
  // Data rows
  for(let i=0;i<n;i++){
    html+='<div class="pf-hm-header" style="text-align:right;padding-right:4px">'+labels[i]+'</div>';
    for(let j=0;j<n;j++){
      const v=matrix[mkts[i]][mkts[j]]||0;
      const abs=Math.abs(v);
      let bg,fg;
      if(i===j){bg='var(--accent)';fg='#fff'}
      else if(abs>=0.8){bg='rgba(248,81,73,'+Math.min(1,abs*0.9)+')';fg='#fff'}
      else if(abs>=0.5){bg='rgba(210,153,34,'+Math.min(1,abs*0.8)+')';fg='#fff'}
      else if(abs>=0.3){bg='rgba(88,166,255,'+Math.min(0.5,abs*0.6)+')';fg='var(--text)'}
      else{bg='var(--bg)';fg='var(--text2)'}
      html+='<div class="pf-hm-cell" style="background:'+bg+';color:'+fg+'">'+v.toFixed(2)+'</div>';
    }
  }
  html+='</div>';
  el.innerHTML=html;
}

function renderPositions(positions){
  const el=document.getElementById('positions');const entries=Object.entries(positions);
  if(!entries.length){el.innerHTML='<p style="color:var(--text2)">No open positions</p>';return}
  el.innerHTML='<div class="pos-grid">'+entries.map(([m,p])=>{
    const pnlCls=p.unrealized_pnl_pct>=0?'positive':'negative';
    const range=p.take_profit-p.stop_loss;const pos=range>0?Math.max(0,Math.min(100,(p.current_price-p.stop_loss)/range*100)):50;
    const barColor=p.unrealized_pnl_pct>=0?'var(--green)':'var(--red)';
    return `<div class="pos-card">
      <div class="pos-header"><span class="pos-market">${m}</span><span class="${pnlCls}" style="font-weight:700">${fmtPct(p.unrealized_pnl_pct)} (${p.unrealized_pnl_pct>=0?'+':''}${fmt(p.unrealized_pnl_krw)})</span></div>
      <div class="pos-row"><span class="pos-label">Entry</span><span>${fmt(p.entry_price)}</span></div>
      <div class="pos-row"><span class="pos-label">Current</span><span style="font-weight:600">${fmt(p.current_price)}</span></div>
      <div class="pos-row"><span class="pos-label">SL / TP</span><span style="color:var(--red)">${fmt(p.stop_loss)}</span> / <span style="color:var(--green)">${fmt(p.take_profit)}</span></div>
      <div class="pos-row"><span class="pos-label">Since</span><span>${p.entry_time}</span></div>
      <div class="pos-bar"><div class="pos-bar-fill" style="width:${pos}%;background:${barColor}"></div></div></div>`
  }).join('')+'</div>';
}

// ── Market Watch (5s) with charts + gauges ──
let miniCharts={},_mwCache={};
function mwHash(m){const i=m.indicators||{};return [m.price,m.trend,m.ensemble_signal,i.rsi?.toFixed(1),i.bb_pctb?.toFixed(3),i.stoch_k?.toFixed(1),i.vol_ratio?.toFixed(2)].join('|')}
function applyMarketWatch(d){
  if(!d)return;
  const el=document.getElementById('marketWatch');const markets=Object.values(d);
  markets.forEach(m=>{_lastMW[m.market]=m});
  if(!markets.length){el.innerHTML='<p style="color:var(--text2)">Waiting for market data...</p>';return}

  // Only rebuild DOM if market count changed
  const ids=markets.map(m=>m.market).join(',');
  if(el.dataset.ids!==ids){
    el.dataset.ids=ids;
    el.innerHTML=markets.map(m=>`<div class="mw-card" id="mw-${m.market}" onclick="toggleExpand('${m.market}')">
      <div class="mw-header"><span class="mw-market">${m.market}</span><span class="mw-trend" id="trend-${m.market}"></span></div>
      <div class="mw-price" id="price-${m.market}"></div>
      <div class="mw-chart-wrap"><canvas id="chart-${m.market}"></canvas></div>
      <div id="sigs-${m.market}"></div>
      <div class="ind-section" id="ind-${m.market}"></div>
      <div class="mtf-panel" id="mtf-${m.market}"></div>
      <div class="mw-expand-hint">클릭하면 상세 차트 열기</div>
      <div class="mw-detail" id="detail-${m.market}">
        <div class="tv-chart-wrap" id="tv-${m.market}"></div>
        <div class="subchart-row">
          <div class="subchart-box"><div class="subchart-label">RSI</div><canvas class="subchart-canvas" id="sc-rsi-${m.market}"></canvas></div>
          <div class="subchart-box"><div class="subchart-label">StochRSI K/D</div><canvas class="subchart-canvas" id="sc-stoch-${m.market}"></canvas></div>
          <div class="subchart-box"><div class="subchart-label">Volume</div><canvas class="subchart-canvas vol" id="sc-vol-${m.market}"></canvas></div>
        </div>
        <div class="trigger-panel" id="trigger-${m.market}"></div>
      </div>
    </div>`).join('');
    // Destroy old mini charts & TV charts
    Object.values(miniCharts).forEach(c=>c.destroy());miniCharts={};
    Object.keys(tvCharts).forEach(k=>{try{tvCharts[k].remove()}catch(e){}});tvCharts={};subCharts={};
  }

  markets.forEach(m=>{
    const ind=m.indicators||{};
    const hash=mwHash(m);const changed=_mwCache[m.market]!==hash;_mwCache[m.market]=hash;
    // Header - always update (cheap)
    const tEl=document.getElementById('trend-'+m.market);
    if(tEl){tEl.textContent=m.trend==='up'?'Uptrend':m.trend==='down'?'Downtrend':'Neutral';
    tEl.className='mw-trend '+(m.trend==='up'?'trend-up':m.trend==='down'?'trend-down':'trend-neutral')}
    // Price
    const prEl=document.getElementById('price-'+m.market);
    if(prEl&&changed)prEl.innerHTML=`${fmt(m.price)} KRW <span style="font-size:11px;color:var(--text2);margin-left:8px">Ensemble: </span><span style="font-size:12px;font-weight:700" class="${m.ensemble_signal==='BUY'?'sig-buy':m.ensemble_signal==='SELL'?'sig-sell':'sig-hold'}">${m.ensemble_signal}</span>`;

    // Mini price chart
    if(ind.chart_close&&ind.chart_close.length>1){
      const cid='chart-'+m.market;
      if(miniCharts[cid]){
        miniCharts[cid].data.labels=ind.chart_time;
        miniCharts[cid].data.datasets[0].data=ind.chart_close;
        miniCharts[cid].update('none');
      } else {
        const ctx=document.getElementById(cid);
        if(ctx){
          miniCharts[cid]=new Chart(ctx,{type:'line',data:{labels:ind.chart_time,datasets:[{data:ind.chart_close,borderColor:'#58a6ff',borderWidth:1.5,pointRadius:0,fill:false,tension:.3}]},
            options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{display:false},y:{display:false}},animation:false}});
        }
      }
    }

    // Strategy signals - only update if data changed
    if(changed){
    const sigRows=(m.strategy_signals||[]).map(s=>{
      const sc=s.signal==='BUY'?'sig-buy':s.signal==='SELL'?'sig-sell':'sig-hold';
      return `<div class="sig-row"><span class="sig-name">${s.name}</span><span class="${sc}">${s.signal}</span><span style="color:var(--text2)">${(s.confidence*100).toFixed(0)}%</span></div>`;
    }).join('');
    document.getElementById('sigs-'+m.market).innerHTML=sigRows;
    }

    // Indicator gauges - only update if data changed
    if(!changed){/* skip gauge rebuild */}else{
    let gaugeHtml='';
    if(ind.rsi!=null) gaugeHtml+=makeGauge('RSI',ind.rsi,0,100,ind.rsi_oversold,ind.rsi_overbought);
    if(ind.bb_pctb!=null) gaugeHtml+=makeGauge('BB%B',ind.bb_pctb*100,0,100,ind.bb_buy_zone*100,ind.bb_sell_zone*100);
    if(ind.stoch_k!=null) gaugeHtml+=makeGauge('StochRSI K',ind.stoch_k,0,100,ind.stoch_oversold,ind.stoch_overbought);
    if(ind.vol_ratio!=null) gaugeHtml+=makeVolGauge('Volume',ind.vol_ratio,ind.vol_surge_threshold);
    if(ind.ema_fast!=null){
      const aboveTrend=m.price>=ind.ema_trend;
      gaugeHtml+=`<div class="ind-row"><span class="ind-label">EMA</span>
        <span style="flex:1;font-size:11px;color:var(--text2)">EMA${ind.ema_fast_period}=<b style="color:var(--text)">${fmt(ind.ema_fast)}</b> / EMA${ind.ema_slow_period}=<b style="color:var(--text)">${fmt(ind.ema_slow)}</b> / EMA${ind.ema_trend_period}=<b style="color:var(--text)">${fmt(ind.ema_trend)}</b></span>
        <span class="ind-status" style="background:${aboveTrend?'#1a3a1a':'#3a1a1a'};color:${aboveTrend?'var(--green)':'var(--red)'}">${aboveTrend?'UP':'DN'}</span></div>`;
    }
    if(ind.vwap!=null){
      const aboveVwap=m.price>=ind.vwap;
      gaugeHtml+=`<div class="ind-row"><span class="ind-label">VWAP</span>
        <span style="flex:1;font-size:11px;color:var(--text2)">VWAP=<b style="color:var(--text)">${fmt(ind.vwap)}</b> (price ${aboveVwap?'above':'below'})</span>
        <span class="ind-status" style="background:${aboveVwap?'#1a3a1a':'#3a1a1a'};color:${aboveVwap?'var(--green)':'var(--red)'}">${aboveVwap?'UP':'DN'}</span></div>`;
    }
    document.getElementById('ind-'+m.market).innerHTML=gaugeHtml;
    } // end gauge changed check

    // MTF confluence panel
    if(changed){renderMTFPanel(m)}

    // Expanded detail: TV candlestick + subcharts + trigger
    const card=document.getElementById('mw-'+m.market);
    if(card&&card.classList.contains('expanded')){
      renderTVChart(m);
      renderSubCharts(m);
      renderTriggerPanel(m);
    }
  });
}
async function refreshMarketWatch(){
  const d=await api('/api/market-watch');applyMarketWatch(d);
}

// MTF panel renderer
function renderMTFPanel(m){
  const el=document.getElementById('mtf-'+m.market);
  if(!el)return;
  const mtf=m.mtf;
  if(!mtf||!mtf.available){el.innerHTML='';return}
  const sc=mtf.confluence_score;
  const badgeCls='mtf-badge-'+sc;
  const recMap={strong_buy:'Strong Buy',buy:'Buy',neutral:'Neutral',sell:'Sell',strong_sell:'Strong Sell'};
  const recLabel=recMap[mtf.recommendation]||mtf.recommendation;
  function tfRow(label,tf){
    if(!tf)return `<div class="mtf-tf-row"><span class="mtf-tf-label">${label}</span><span style="color:var(--text2);font-size:11px">N/A</span></div>`;
    const aCls='mtf-arrow-'+tf.trend;
    return `<div class="mtf-tf-row"><span class="mtf-tf-label">${label}</span><span class="mtf-arrow ${aCls}">${tf.arrow}</span><span class="mtf-tf-detail">EMA: ${tf.ema_direction} | RSI: ${tf.rsi.toFixed(1)} (${tf.rsi_zone}) | VWAP: ${tf.price_vs_vwap}</span></div>`;
  }
  let srHtml='';
  if(mtf.nearest_support>0||mtf.nearest_resistance>0){
    srHtml='<div class="mtf-sr">';
    if(mtf.nearest_support>0)srHtml+=`<span><span class="mtf-sr-label">S: </span><span class="mtf-sr-val" style="color:var(--green)">${fmt(mtf.nearest_support)}</span></span>`;
    if(mtf.nearest_resistance>0)srHtml+=`<span><span class="mtf-sr-label">R: </span><span class="mtf-sr-val" style="color:var(--red)">${fmt(mtf.nearest_resistance)}</span></span>`;
    srHtml+='</div>';
  }
  el.innerHTML=`<div class="mtf-title">Multi-Timeframe <span class="mtf-badge ${badgeCls}">${sc}/3</span> <span style="font-size:10px;font-weight:400;color:var(--text2)">${recLabel}</span></div>${tfRow('15m',mtf.tf_15m)}${tfRow('1h',mtf.tf_1h)}${tfRow('4h',mtf.tf_4h)}${srHtml}`;
}

// Toggle expand
function toggleExpand(market){
  const card=document.getElementById('mw-'+market);
  if(!card)return;
  const wasExpanded=card.classList.contains('expanded');
  // Collapse all
  document.querySelectorAll('.mw-card.expanded').forEach(c=>{c.classList.remove('expanded')});
  if(!wasExpanded){
    card.classList.add('expanded');
    // Force render after DOM display change
    setTimeout(()=>{
      const mData=_lastMW[market];
      if(mData){renderTVChart(mData);renderSubCharts(mData);renderTriggerPanel(mData)}
    },50);
  }
}
let _lastMW={};

// TradingView Lightweight Charts
let tvCharts={},tvSeries={};
function renderTVChart(m){
  const containerId='tv-'+m.market;
  const container=document.getElementById(containerId);
  if(!container)return;
  const ind=m.indicators||{};
  const times=ind.chart_time_iso||ind.chart_time||[];
  const opens=ind.chart_open||[];const highs=ind.chart_high||[];
  const lows=ind.chart_low||[];const closes=ind.chart_close||[];
  if(!closes.length)return;

  // Build time values (use index-based for simplicity)
  const baseTime=Math.floor(Date.now()/1000)-closes.length*60;
  const candleData=closes.map((c,i)=>({time:baseTime+i*60,open:opens[i]||c,high:highs[i]||c,low:lows[i]||c,close:c}));

  if(tvCharts[m.market]){
    // Update existing
    try{
      tvSeries[m.market].candle.setData(candleData);
      if(ind.chart_bb_upper)tvSeries[m.market].bbUp.setData(ind.chart_bb_upper.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
      if(ind.chart_bb_mid)tvSeries[m.market].bbMid.setData(ind.chart_bb_mid.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
      if(ind.chart_bb_lower)tvSeries[m.market].bbLow.setData(ind.chart_bb_lower.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
      if(ind.chart_ema3)tvSeries[m.market].ema3.setData(ind.chart_ema3.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
      if(ind.chart_ema8)tvSeries[m.market].ema8.setData(ind.chart_ema8.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
      if(ind.chart_ema21)tvSeries[m.market].ema21.setData(ind.chart_ema21.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
      if(ind.chart_vwap)tvSeries[m.market].vwap.setData(ind.chart_vwap.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
    }catch(e){console.error('TV update err',e)}
    return;
  }

  // Create new chart
  container.innerHTML='';
  const chart=LightweightCharts.createChart(container,{
    width:container.clientWidth,height:300,
    layout:{background:{type:'solid',color:'#0d1117'},textColor:'#8b949e',fontSize:10},
    grid:{vertLines:{color:'#21262d'},horzLines:{color:'#21262d'}},
    crosshair:{mode:0},
    timeScale:{timeVisible:true,secondsVisible:false,borderColor:'#30363d'},
    rightPriceScale:{borderColor:'#30363d'},
  });

  const candle=chart.addCandlestickSeries({upColor:'#3fb950',downColor:'#f85149',borderUpColor:'#3fb950',borderDownColor:'#f85149',wickUpColor:'#3fb950',wickDownColor:'#f85149'});
  candle.setData(candleData);

  // BB bands
  const bbUp=chart.addLineSeries({color:'rgba(188,140,255,0.4)',lineWidth:1,lineStyle:2,priceLineVisible:false,lastValueVisible:false});
  const bbMid=chart.addLineSeries({color:'rgba(188,140,255,0.3)',lineWidth:1,lineStyle:1,priceLineVisible:false,lastValueVisible:false});
  const bbLow=chart.addLineSeries({color:'rgba(188,140,255,0.4)',lineWidth:1,lineStyle:2,priceLineVisible:false,lastValueVisible:false});
  if(ind.chart_bb_upper)bbUp.setData(ind.chart_bb_upper.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
  if(ind.chart_bb_mid)bbMid.setData(ind.chart_bb_mid.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
  if(ind.chart_bb_lower)bbLow.setData(ind.chart_bb_lower.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));

  // EMA lines
  const ema3=chart.addLineSeries({color:'#f0883e',lineWidth:1,priceLineVisible:false,lastValueVisible:false});
  const ema8=chart.addLineSeries({color:'#d29922',lineWidth:1,priceLineVisible:false,lastValueVisible:false});
  const ema21=chart.addLineSeries({color:'#58a6ff',lineWidth:1,priceLineVisible:false,lastValueVisible:false});
  if(ind.chart_ema3)ema3.setData(ind.chart_ema3.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
  if(ind.chart_ema8)ema8.setData(ind.chart_ema8.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));
  if(ind.chart_ema21)ema21.setData(ind.chart_ema21.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));

  // VWAP
  const vwap=chart.addLineSeries({color:'rgba(63,185,80,0.6)',lineWidth:1,lineStyle:1,priceLineVisible:false,lastValueVisible:false});
  if(ind.chart_vwap)vwap.setData(ind.chart_vwap.map((v,i)=>({time:baseTime+i*60,value:v})).filter(d=>d.value!=null));

  chart.timeScale().fitContent();
  tvCharts[m.market]=chart;
  tvSeries[m.market]={candle,bbUp,bbMid,bbLow,ema3,ema8,ema21,vwap};

  // Resize observer
  new ResizeObserver(()=>{chart.applyOptions({width:container.clientWidth})}).observe(container);
}

// Sub-charts (RSI, StochRSI, Volume) using Chart.js
let subCharts={};
function renderSubCharts(m){
  const ind=m.indicators||{};
  const labels=ind.chart_time||[];
  if(!labels.length)return;

  // RSI
  const rsiOS=ind.rsi_oversold||35,rsiOB=ind.rsi_overbought||65;
  renderSubChart('sc-rsi-'+m.market,m.market+'_rsi',labels,[
    {label:'RSI',data:ind.chart_rsi||[],borderColor:'#bc8cff',borderWidth:1.5,pointRadius:0,fill:false,tension:.2}
  ],{min:0,max:100,thresholds:[{y:rsiOS,color:'rgba(63,185,80,0.15)'},{y:rsiOB,color:'rgba(248,81,73,0.15)'}],
    annotations:[{y:rsiOS,color:'#3fb950',dash:[4,4]},{y:rsiOB,color:'#f85149',dash:[4,4]}]});

  // StochRSI
  const stOS=ind.stoch_oversold||30,stOB=ind.stoch_overbought||70;
  renderSubChart('sc-stoch-'+m.market,m.market+'_stoch',labels,[
    {label:'K',data:ind.chart_stoch_k||[],borderColor:'#58a6ff',borderWidth:1.5,pointRadius:0,fill:false,tension:.2},
    {label:'D',data:ind.chart_stoch_d||[],borderColor:'#f0883e',borderWidth:1,pointRadius:0,fill:false,tension:.2,borderDash:[3,3]}
  ],{min:0,max:100,annotations:[{y:stOS,color:'#3fb950',dash:[4,4]},{y:stOB,color:'#f85149',dash:[4,4]}]});

  // Volume
  const volAvg=ind.chart_vol_avg||[];
  const volSurge=ind.vol_surge_threshold||1.3;
  const surgeLineData=volAvg.map(v=>v!=null?v*volSurge:null);
  renderSubChart('sc-vol-'+m.market,m.market+'_vol',labels,[
    {label:'Vol',data:ind.chart_volume||[],type:'bar',backgroundColor:ind.chart_volume?.map((v,i)=>{
      const avg=volAvg[i];return(avg&&v>=avg*volSurge)?'rgba(210,153,34,0.7)':'rgba(88,166,255,0.4)';
    })||'rgba(88,166,255,0.4)',borderWidth:0},
    {label:volSurge+'x Avg',data:surgeLineData,borderColor:'#d29922',borderWidth:1,borderDash:[4,4],pointRadius:0,fill:false,type:'line'}
  ],{min:0});
}

function renderSubChart(canvasId,key,labels,datasets,opts={}){
  const ctx=document.getElementById(canvasId);
  if(!ctx)return;
  if(subCharts[key]){
    subCharts[key].data.labels=labels;
    datasets.forEach((ds,i)=>{if(subCharts[key].data.datasets[i])subCharts[key].data.datasets[i].data=ds.data;
      if(ds.backgroundColor&&subCharts[key].data.datasets[i])subCharts[key].data.datasets[i].backgroundColor=ds.backgroundColor;});
    subCharts[key].update('none');return;
  }
  const annPlugin={id:'threshLines',beforeDraw(chart){
    const ctx2=chart.ctx;const yScale=chart.scales.y;const area=chart.chartArea;
    (opts.annotations||[]).forEach(a=>{
      const yPos=yScale.getPixelForValue(a.y);
      ctx2.save();ctx2.beginPath();ctx2.setLineDash(a.dash||[]);
      ctx2.strokeStyle=a.color||'#555';ctx2.lineWidth=1;
      ctx2.moveTo(area.left,yPos);ctx2.lineTo(area.right,yPos);ctx2.stroke();ctx2.restore();
    });
  }};
  subCharts[key]=new Chart(ctx,{type:'line',data:{labels,datasets},
    options:{responsive:true,maintainAspectRatio:false,animation:false,
      plugins:{legend:{display:false}},
      scales:{x:{display:false},y:{min:opts.min,max:opts.max,ticks:{color:'#8b949e',font:{size:9},maxTicksLimit:3},grid:{color:'#21262d'}}}},
    plugins:[annPlugin]});
}

// Trigger condition checklist
function renderTriggerPanel(m){
  const el=document.getElementById('trigger-'+m.market);
  if(!el)return;
  const ts=m.trigger_summary;
  if(!ts){el.innerHTML='<p style="color:var(--text2);font-size:12px">트리거 데이터 대기중...</p>';return}

  let html='<div style="font-size:13px;font-weight:700;color:var(--accent);margin-bottom:8px">매매 조건 체크리스트</div>';

  // Per-strategy conditions
  (ts.strategies||[]).forEach(s=>{
    html+=`<div class="trigger-strat">`;
    html+=`<div class="trigger-strat-header">${s.name} <span class="trigger-strat-weight">(가중치 ${s.weight}%)</span></div>`;
    (s.conditions||[]).forEach(c=>{
      const met=c.met;
      html+=`<div class="trigger-cond">
        <span class="trigger-icon ${met?'trigger-met':'trigger-unmet'}">${met?'✅':'❌'}</span>
        <span style="color:${met?'var(--green)':'var(--text)'}">${c.label}</span>
        <span class="trigger-current">${c.current}</span>
      </div>`;
    });
    const fireText=s.would_fire?'<span style="color:var(--green);font-weight:600">→ BUY 발동!</span>':`<span style="color:var(--text2)">→ ${s.met_count}/${s.total_count} 충족, 미발동</span>`;
    html+=`<div class="trigger-result">${fireText}</div></div>`;
  });

  // Ensemble summary
  const ens=ts.ensemble||{};
  const trendOk=ens.trend===ens.trend_required;
  const votesOk=ens.buy_votes>=ens.min_agreement;
  const confOk=ens.buy_weight>=ens.min_confidence;
  const finalCls=ens.final_signal==='BUY'?'positive':ens.final_signal==='SELL'?'negative':'';
  html+=`<div class="trigger-ensemble">
    <div class="trigger-ensemble-title">앙상블 최종 판단</div>
    <div class="trigger-ensemble-row"><span class="label">BUY 투표</span><span class="val ${votesOk?'positive':'negative'}">${ens.buy_votes}/${ens.total_strategies} 전략 (최소 ${ens.min_agreement}개)</span></div>
    <div class="trigger-ensemble-row"><span class="label">가중 신뢰도</span><span class="val ${confOk?'positive':'negative'}">${ens.buy_weight?.toFixed(3)||0} (최소 ${ens.min_confidence})</span></div>
    <div class="trigger-ensemble-row"><span class="label">추세</span><span class="val ${trendOk?'positive':'negative'}">${ens.trend==='up'?'상승중 ✅':ens.trend==='down'?'하락중 ❌':'횡보 ❌'} (${ens.trend_required}필요)</span></div>
    <div class="trigger-final ${finalCls}">→ ${ens.final_signal==='BUY'?'🟢 매수 실행!':ens.final_signal==='SELL'?'🔴 매도 실행!':'⚪ HOLD (대기)'}</div>
    <div style="font-size:10px;color:var(--text2);margin-top:4px">${ens.final_reason||''}</div>
  </div>`;

  el.innerHTML=html;
}

function makeGauge(label,value,min,max,buyThresh,sellThresh){
  const pct=Math.max(0,Math.min(100,(value-min)/(max-min)*100));
  const buyPct=(buyThresh-min)/(max-min)*100;
  const sellPct=(sellThresh-min)/(max-min)*100;
  const inBuy=value<=buyThresh;const inSell=value>=sellThresh;
  const statusColor=inBuy?'var(--green)':inSell?'var(--red)':'var(--text2)';
  const statusBg=inBuy?'#1a3a1a':inSell?'#3a1a1a':'var(--bg)';
  const statusText=inBuy?'BUY':inSell?'SELL':'--';
  return `<div class="ind-row"><span class="ind-label">${label}</span>
    <div class="ind-bar-wrap">
      <div class="ind-bar-zone" style="left:0;width:${buyPct}%;background:var(--green)"></div>
      <div class="ind-bar-zone" style="left:${sellPct}%;width:${100-sellPct}%;background:var(--red)"></div>
      <div class="ind-bar-marker" style="left:${pct}%;background:var(--accent)"></div>
    </div>
    <span class="ind-val" style="color:${statusColor}">${value.toFixed(1)}</span>
    <span class="ind-status" style="background:${statusBg};color:${statusColor}">${statusText}</span></div>`;
}

function makeVolGauge(label,ratio,threshold){
  const maxShow=Math.max(3,ratio+0.5);
  const pct=Math.min(100,ratio/maxShow*100);
  const threshPct=Math.min(100,threshold/maxShow*100);
  const surge=ratio>=threshold;
  return `<div class="ind-row"><span class="ind-label">${label}</span>
    <div class="ind-bar-wrap">
      <div class="ind-bar-zone" style="left:${threshPct}%;width:${100-threshPct}%;background:var(--yellow)"></div>
      <div class="ind-bar-marker" style="left:${pct}%;background:${surge?'var(--yellow)':'var(--accent)'}"></div>
    </div>
    <span class="ind-val" style="color:${surge?'var(--yellow)':'var(--text2)'}">${ratio.toFixed(1)}x</span>
    <span class="ind-status" style="background:${surge?'#2a2a1a':'var(--bg)'};color:${surge?'var(--yellow)':'var(--text2)'}">${surge?'SURGE':'--'}</span></div>`;
}

// ── Performance ──
async function loadPerformance(){
  const d=await api(`/api/trades/stats?period=${currentPeriod}`);if(!d)return;
  if(!d.total_trades||d.total_trades===0){
    document.getElementById('perfStats').innerHTML='<div class="card" style="grid-column:1/-1;text-align:center;padding:24px"><div style="color:var(--text2);font-size:14px">선택한 기간에 거래 기록이 없습니다.</div></div>';
    ['equityChart','dailyPnlChart','exitTypeChart','marketPnlChart'].forEach(id=>{if(charts[id]){charts[id].destroy();delete charts[id]}});
    document.getElementById('perfSummaryBox').innerHTML='<div class="panel-title">Summary ('+currentPeriod+')</div><p style="color:var(--text2);padding:20px;text-align:center">거래 기록 없음</p>';
    if(document.getElementById('perfBlank'))document.getElementById('perfBlank').innerHTML='';
    return;
  }
  document.getElementById('perfStats').innerHTML=`
    <div class="card"><div class="card-label">Total PnL</div><div class="card-value ${cls(d.total_pnl_krw)}">${d.total_pnl_krw>=0?'+':''}${fmt(d.total_pnl_krw)}</div></div>
    <div class="card"><div class="card-label">Win Rate</div><div class="card-value ${d.win_rate>=50?'positive':'negative'}">${d.win_rate}%</div></div>
    <div class="card"><div class="card-label">Profit Factor</div><div class="card-value">${d.profit_factor}</div></div>
    <div class="card"><div class="card-label">Max Drawdown</div><div class="card-value negative">${fmt(d.max_drawdown_krw)}</div></div>
    <div class="card"><div class="card-label">Total Fees</div><div class="card-value" style="color:var(--yellow)">${fmt(d.total_fees_krw)}</div></div>
    <div class="card"><div class="card-label">Avg Duration</div><div class="card-value">${fmtDuration(d.avg_duration_sec)}</div></div>
    <div class="card"><div class="card-label">Best Trade</div><div class="card-value positive">+${fmt(d.best_trade_krw)}</div></div>
    <div class="card"><div class="card-label">Worst Trade</div><div class="card-value negative">${fmt(d.worst_trade_krw)}</div></div>`;

  // ── Equity Curve with green/red gradient + drawdown shading ──
  const eq=d.equity_curve||[];
  const dd=d.drawdown_series||[];
  const eqLabels=eq.map((e,i)=>i+1);
  const eqData=eq.map(e=>e.cumulative_pnl);
  const ddData=dd.map(e=>e.drawdown);

  // Destroy previous chart before creating new one with custom plugin
  if(charts['equityChart']){charts['equityChart'].destroy();delete charts['equityChart']}
  const eqCtx=document.getElementById('equityChart');
  if(eqCtx){
    // Custom plugin: gradient fill green above zero, red below zero
    const equityGradientPlugin={
      id:'equityGradient',
      beforeDraw(chart){
        const ctx2=chart.ctx;
        const area=chart.chartArea;
        const yScale=chart.scales.y;
        if(!area)return;
        const zeroY=yScale.getPixelForValue(0);
        const clampedZero=Math.max(area.top,Math.min(area.bottom,zeroY));
        // Green gradient above zero
        const greenGrad=ctx2.createLinearGradient(0,area.top,0,clampedZero);
        greenGrad.addColorStop(0,'rgba(63,185,80,0.25)');
        greenGrad.addColorStop(1,'rgba(63,185,80,0.02)');
        // Red gradient below zero
        const redGrad=ctx2.createLinearGradient(0,clampedZero,0,area.bottom);
        redGrad.addColorStop(0,'rgba(248,81,73,0.02)');
        redGrad.addColorStop(1,'rgba(248,81,73,0.25)');
        // Apply to datasets
        const ds=chart.data.datasets[0];
        if(ds){
          const meta=chart.getDatasetMeta(0);
          if(meta&&meta.dataset){
            // Use split gradient
            const fullGrad=ctx2.createLinearGradient(0,area.top,0,area.bottom);
            const ratio=(clampedZero-area.top)/(area.bottom-area.top);
            fullGrad.addColorStop(0,'rgba(63,185,80,0.25)');
            fullGrad.addColorStop(Math.max(0,ratio-0.01),'rgba(63,185,80,0.05)');
            fullGrad.addColorStop(ratio,'rgba(128,128,128,0.02)');
            fullGrad.addColorStop(Math.min(1,ratio+0.01),'rgba(248,81,73,0.05)');
            fullGrad.addColorStop(1,'rgba(248,81,73,0.25)');
            ds.backgroundColor=fullGrad;
          }
        }
      }
    };
    const eqDatasets=[
      {label:'Cumulative PnL (KRW)',data:eqData,borderColor:eqData.length>0&&eqData[eqData.length-1]>=0?'#3fb950':'#f85149',backgroundColor:'rgba(88,166,255,.1)',fill:true,tension:.3,pointRadius:eq.length>50?0:3,borderWidth:2,order:1},
    ];
    if(ddData.length>0){
      eqDatasets.push({label:'Drawdown (KRW)',data:ddData,borderColor:'rgba(248,81,73,0.4)',backgroundColor:'rgba(248,81,73,0.08)',fill:true,tension:.3,pointRadius:0,borderWidth:1,borderDash:[4,4],order:2,yAxisID:'y'});
    }
    charts['equityChart']=new Chart(eqCtx,{type:'line',data:{labels:eqLabels,datasets:eqDatasets},
      options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{color:'#c9d1d9',font:{size:11}}},title:{display:true,text:'Equity Curve & Drawdown',color:'#8b949e'}},
        scales:{x:{ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#21262d'}},y:{ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#21262d'}}}},
      plugins:[equityGradientPlugin]});
  }

  // ── Daily PnL Bar Chart (green wins, red losses) ──
  const days=Object.keys(d.daily_pnl||{});const dayVals=days.map(k=>d.daily_pnl[k]);
  renderChart('dailyPnlChart','bar',{labels:days.map(k=>k.slice(5)),datasets:[{label:'Daily PnL (KRW)',data:dayVals,backgroundColor:dayVals.map(v=>v>=0?'rgba(63,185,80,.7)':'rgba(248,81,73,.7)'),borderColor:dayVals.map(v=>v>=0?'#3fb950':'#f85149'),borderWidth:1}]},{plugins:{title:{display:true,text:'Daily PnL Timeline',color:'#8b949e'}}});

  // ── Exit Type Doughnut with specific colors ──
  const exitColorMap={'stop_loss':'#f85149','take_profit':'#3fb950','trailing_stop':'#58a6ff','signal_sell':'#f0883e','breakeven_stop':'#8b949e','breakeven':'#8b949e','unknown':'#6e7681'};
  const etL=Object.keys(d.exit_types||{});const etV=etL.map(k=>d.exit_types[k]);
  const etColors=etL.map(k=>exitColorMap[k]||'#bc8cff');
  renderChart('exitTypeChart','doughnut',{labels:etL,datasets:[{data:etV,backgroundColor:etColors,borderColor:'#161b22',borderWidth:2}]},{plugins:{title:{display:true,text:'Exit Type Distribution',color:'#8b949e'},legend:{labels:{color:'#c9d1d9',font:{size:11},padding:12}}}});

  // ── Market Performance Horizontal Bar Chart ──
  const mktPnl=d.market_pnl||{};
  const mktLabels=Object.keys(mktPnl);const mktVals=mktLabels.map(k=>mktPnl[k]);
  if(mktLabels.length>0){
    renderChart('marketPnlChart','bar',{labels:mktLabels,datasets:[{label:'P&L (KRW)',data:mktVals,backgroundColor:mktVals.map(v=>v>=0?'rgba(63,185,80,.7)':'rgba(248,81,73,.7)'),borderColor:mktVals.map(v=>v>=0?'#3fb950':'#f85149'),borderWidth:1}]},{indexAxis:'y',plugins:{title:{display:true,text:'Market Performance Comparison',color:'#8b949e'},legend:{display:false}},scales:{x:{ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#21262d'}},y:{ticks:{color:'#c9d1d9',font:{size:11}},grid:{color:'#21262d'}}}});
  } else {
    const mpEl=document.getElementById('marketPnlChart');
    if(mpEl){const mpParent=mpEl.parentElement;if(mpParent)mpParent.innerHTML='<div class="panel-title">Market Performance</div><p style="color:var(--text2);padding:20px;text-align:center">No market data available</p>'}
  }

  document.getElementById('perfSummaryBox').innerHTML=`<div class="panel-title">Summary (${currentPeriod})</div><table>
    <tr><td style="color:var(--text2)">Trades</td><td>${d.total_trades}</td></tr>
    <tr><td style="color:var(--text2)">Wins / Losses</td><td>${d.wins} / ${d.losses}</td></tr>
    <tr><td style="color:var(--text2)">Avg PnL</td><td class="${cls(d.avg_pnl_krw)}">${d.avg_pnl_krw>=0?'+':''}${fmt(d.avg_pnl_krw)} KRW (${d.avg_pnl_pct>=0?'+':''}${d.avg_pnl_pct}%)</td></tr>
    <tr><td style="color:var(--text2)">Total PnL</td><td class="${cls(d.total_pnl_krw)}">${d.total_pnl_krw>=0?'+':''}${fmt(d.total_pnl_krw)} KRW</td></tr>
    <tr><td style="color:var(--text2)">Profit Factor</td><td>${d.profit_factor}</td></tr>
    <tr><td style="color:var(--text2)">MDD</td><td class="negative">${fmt(d.max_drawdown_krw)} KRW</td></tr>
    <tr><td style="color:var(--text2)">Fees Paid</td><td style="color:var(--yellow)">${fmt(d.total_fees_krw)} KRW</td></tr></table>`;
}

function renderChart(id,type,data,extra={}){
  const ctx=document.getElementById(id);if(charts[id])charts[id].destroy();
  charts[id]=new Chart(ctx,{type,data,options:{responsive:true,maintainAspectRatio:false,
    scales:type==='doughnut'?{}:{x:{ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#21262d'}},y:{ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#21262d'}}},
    plugins:{legend:{labels:{color:'#c9d1d9',font:{size:11}}},...extra.plugins},...extra}});
}

// ── Analytics ──
const analyticsChartIds=['analyticsStrategyBar','analyticsCumLine','analyticsDrawdown','analyticsDistribution','analyticsDowBar'];
async function loadAnalytics(){
  const d=await api('/api/analytics');if(!d)return;
  if(!d.total_trades||d.total_trades===0){
    document.getElementById('analyticsRiskCards').innerHTML='<div class="card" style="grid-column:1/-1;text-align:center;padding:24px"><div class="card-label">Analytics</div><div style="color:var(--text2);font-size:14px;margin-top:8px">거래 기록이 없습니다. 봇이 거래를 시작하면 분석 데이터가 표시됩니다.</div></div>';
    analyticsChartIds.forEach(id=>{if(charts[id]){charts[id].destroy();delete charts[id]}});
    const emptyBoxes=['analyticsMonthlyTable','analyticsAttribution','analyticsCorrelation','analyticsEnsembleAccuracy','analyticsHourlyHeatmap'];
    emptyBoxes.forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML='<div style="color:var(--text2);text-align:center;padding:20px">데이터 대기중</div>'});
    return;
  }
  const rm=d.risk_metrics||{};
  const ta=d.time_analysis||{};
  const sa=d.strategy_attribution||{};
  const ps=d.per_strategy||{};

  // Risk Metric Cards
  const riskEl=document.getElementById('analyticsRiskCards');
  if(riskEl){
    const sharpeColor=rm.sharpe_ratio>=1?'var(--green)':rm.sharpe_ratio>=0?'var(--yellow)':'var(--red)';
    const sortinoColor=rm.sortino_ratio>=1.5?'var(--green)':rm.sortino_ratio>=0?'var(--yellow)':'var(--red)';
    riskEl.innerHTML=`
      <div class="card"><div class="card-label">Sharpe Ratio</div><div class="card-value" style="color:${sharpeColor}">${rm.sharpe_ratio||0}</div><div class="card-sub">위험조정 수익률</div></div>
      <div class="card"><div class="card-label">Sortino Ratio</div><div class="card-value" style="color:${sortinoColor}">${rm.sortino_ratio===999.99?'∞':rm.sortino_ratio||0}</div><div class="card-sub">하방위험 대비 수익</div></div>
      <div class="card"><div class="card-label">Max Drawdown</div><div class="card-value negative">${fmt(rm.max_drawdown_krw||0)}</div><div class="card-sub">${(rm.max_drawdown_pct||0).toFixed(2)}%</div></div>
      <div class="card"><div class="card-label">Recovery</div><div class="card-value" style="color:var(--accent)">${rm.recovery_time_trades||0} trades</div><div class="card-sub">${rm.recovery_time_hours||0}h</div></div>
      <div class="card"><div class="card-label">Win/Loss Ratio</div><div class="card-value" style="color:var(--accent)">${rm.win_loss_ratio===999.99?'∞':(rm.win_loss_ratio||0)}</div><div class="card-sub">평균 수익/손실 비</div></div>
      <div class="card"><div class="card-label">Expectancy</div><div class="card-value ${(rm.expectancy_krw||0)>=0?'positive':'negative'}">${(rm.expectancy_krw||0)>=0?'+':''}${fmt(rm.expectancy_krw||0)}</div><div class="card-sub">트레이드당 기대수익</div></div>
      <div class="card"><div class="card-label">Total Trades</div><div class="card-value" style="color:var(--accent)">${d.total_trades||0}</div></div>`;
  }

  // Strategy Performance Comparison Bar Chart
  const stratNames=Object.keys(ps).filter(n=>n!=='_all');
  if(stratNames.length>0){
    const stratPnl=stratNames.map(n=>ps[n].total_pnl_krw||0);
    const stratWR=stratNames.map(n=>ps[n].win_rate||0);
    renderChart('analyticsStrategyBar','bar',{
      labels:stratNames,
      datasets:[
        {label:'Total PnL (KRW)',data:stratPnl,backgroundColor:stratPnl.map(v=>v>=0?'rgba(63,185,80,.7)':'rgba(248,81,73,.7)'),borderColor:stratPnl.map(v=>v>=0?'#3fb950':'#f85149'),borderWidth:1,yAxisID:'y'},
        {label:'Win Rate %',data:stratWR,type:'line',borderColor:'#58a6ff',backgroundColor:'rgba(88,166,255,.2)',pointBackgroundColor:'#58a6ff',pointRadius:4,tension:.3,yAxisID:'y1'}
      ]
    },{
      plugins:{title:{display:true,text:'전략별 성과 비교',color:'#8b949e'}},
      scales:{
        x:{ticks:{color:'#c9d1d9',font:{size:11}},grid:{color:'#21262d'}},
        y:{position:'left',ticks:{color:'#8b949e',font:{size:10}},grid:{color:'#21262d'},title:{display:true,text:'PnL (KRW)',color:'#8b949e'}},
        y1:{position:'right',min:0,max:100,ticks:{color:'#58a6ff',font:{size:10}},grid:{drawOnChartArea:false},title:{display:true,text:'Win Rate %',color:'#58a6ff'}}
      }
    });
  }

  // Cumulative P&L by Strategy Line Chart
  const cumData=sa.cumulative_by_strategy||{};
  const cumKeys=Object.keys(cumData).filter(k=>k!=='_unknown');
  const stratColors=['#58a6ff','#3fb950','#f0883e','#bc8cff','#f85149','#d29922'];
  if(cumKeys.length>0){
    const maxLen=Math.max(...cumKeys.map(k=>(cumData[k]||[]).length));
    const cumLabels=Array.from({length:maxLen},(_,i)=>i+1);
    const cumDatasets=cumKeys.map((k,i)=>{
      const series=cumData[k]||[];
      return {label:k,data:series.map(s=>s.cumulative_pnl),borderColor:stratColors[i%stratColors.length],backgroundColor:'transparent',tension:.3,pointRadius:series.length>50?0:2,borderWidth:2};
    });
    renderChart('analyticsCumLine','line',{labels:cumLabels,datasets:cumDatasets},{
      plugins:{title:{display:true,text:'전략별 누적 손익',color:'#8b949e'},legend:{labels:{color:'#c9d1d9',font:{size:11}}}},
      scales:{x:{title:{display:true,text:'Trade #',color:'#8b949e'},ticks:{color:'#8b949e'},grid:{color:'#21262d'}},y:{ticks:{color:'#8b949e'},grid:{color:'#21262d'}}}
    });
  }

  // Hourly Win Rate Heatmap
  const hourly=ta.hourly_win_rate||{};
  const hmEl=document.getElementById('analyticsHourlyHeatmap');
  if(hmEl){
    let hmHtml='<div class="hm-grid" style="grid-template-columns:repeat(25,auto)">';
    // Header row
    hmHtml+='<div class="hm-header"></div>';
    for(let h=0;h<24;h++){hmHtml+=`<div class="hm-header">${String(h).padStart(2,'0')}</div>`}
    // Win rate row
    hmHtml+='<div class="hm-row-label">승률</div>';
    for(let h=0;h<24;h++){
      const hd=hourly[h]||{};
      const wr=hd.win_rate||0;
      const cnt=hd.count||0;
      const bg=cnt===0?'var(--border)':wr>=70?'rgba(63,185,80,.8)':wr>=50?'rgba(63,185,80,.4)':wr>=30?'rgba(210,153,34,.5)':'rgba(248,81,73,.6)';
      hmHtml+=`<div class="hm-cell" style="background:${bg}" title="${h}시: ${wr}% (${cnt}건)">${cnt>0?wr+'%':'-'}</div>`;
    }
    // PnL row
    hmHtml+='<div class="hm-row-label">손익</div>';
    for(let h=0;h<24;h++){
      const hd=hourly[h]||{};
      const pnl=hd.total_pnl||0;
      const cnt=hd.count||0;
      const bg=cnt===0?'var(--border)':pnl>0?'rgba(63,185,80,.4)':'rgba(248,81,73,.4)';
      const txt=cnt===0?'-':((pnl>=0?'+':'')+Math.round(pnl/1000)+'K');
      hmHtml+=`<div class="hm-cell" style="background:${bg}" title="${h}시: ${fmt(pnl)} KRW">${txt}</div>`;
    }
    // Count row
    hmHtml+='<div class="hm-row-label">건수</div>';
    for(let h=0;h<24;h++){
      const hd=hourly[h]||{};
      const cnt=hd.count||0;
      const intensity=Math.min(cnt/10,.8);
      const bg=cnt===0?'var(--border)':`rgba(88,166,255,${intensity})`;
      hmHtml+=`<div class="hm-cell" style="background:${bg}" title="${h}시: ${cnt}건">${cnt||'-'}</div>`;
    }
    hmHtml+='</div>';
    hmEl.innerHTML=hmHtml;
  }

  // Drawdown Chart
  const ddSeries=rm.drawdown_series||[];
  if(ddSeries.length>0){
    renderChart('analyticsDrawdown','line',{
      labels:ddSeries.map(s=>s.trade_num),
      datasets:[{label:'Drawdown (KRW)',data:ddSeries.map(s=>-s.drawdown),borderColor:'rgba(248,81,73,.8)',backgroundColor:'rgba(248,81,73,.15)',fill:true,tension:.3,pointRadius:ddSeries.length>50?0:2,borderWidth:2}]
    },{
      plugins:{title:{display:true,text:'Drawdown (최대 낙폭)',color:'#8b949e'}},
      scales:{x:{title:{display:true,text:'Trade #',color:'#8b949e'},ticks:{color:'#8b949e'},grid:{color:'#21262d'}},y:{ticks:{color:'#8b949e'},grid:{color:'#21262d'}}}
    });
  }

  // Trade Distribution Histogram
  const dist=rm.pnl_distribution||{};
  if((dist.bins||[]).length>0){
    renderChart('analyticsDistribution','bar',{
      labels:dist.bin_labels||[],
      datasets:[{label:'Trade Count',data:dist.counts||[],backgroundColor:dist.bins.map(b=>b>=0?'rgba(63,185,80,.6)':'rgba(248,81,73,.6)'),borderColor:dist.bins.map(b=>b>=0?'#3fb950':'#f85149'),borderWidth:1}]
    },{
      plugins:{title:{display:true,text:'손익 분포 (히스토그램)',color:'#8b949e'},legend:{display:false}},
      scales:{x:{title:{display:true,text:'PnL (KRW)',color:'#8b949e'},ticks:{color:'#8b949e',maxRotation:45},grid:{color:'#21262d'}},y:{title:{display:true,text:'Count',color:'#8b949e'},ticks:{color:'#8b949e'},grid:{color:'#21262d'}}}
    });
  }

  // Day-of-Week Performance Bar
  const dow=ta.daily_performance||{};
  const dowKeys=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const dowLabelsKR=dowKeys.map(k=>(dow[k]||{}).name_kr||k);
  const dowPnl=dowKeys.map(k=>(dow[k]||{}).total_pnl||0);
  const dowWR=dowKeys.map(k=>(dow[k]||{}).win_rate||0);
  renderChart('analyticsDowBar','bar',{
    labels:dowLabelsKR,
    datasets:[
      {label:'Total PnL',data:dowPnl,backgroundColor:dowPnl.map(v=>v>=0?'rgba(63,185,80,.6)':'rgba(248,81,73,.6)'),borderWidth:1,yAxisID:'y'},
      {label:'Win Rate %',data:dowWR,type:'line',borderColor:'#58a6ff',pointBackgroundColor:'#58a6ff',pointRadius:4,tension:.3,yAxisID:'y1'}
    ]
  },{
    plugins:{title:{display:true,text:'요일별 성과',color:'#8b949e'}},
    scales:{
      x:{ticks:{color:'#c9d1d9'},grid:{color:'#21262d'}},
      y:{position:'left',ticks:{color:'#8b949e'},grid:{color:'#21262d'},title:{display:true,text:'PnL',color:'#8b949e'}},
      y1:{position:'right',min:0,max:100,ticks:{color:'#58a6ff'},grid:{drawOnChartArea:false},title:{display:true,text:'Win Rate %',color:'#58a6ff'}}
    }
  });

  // Monthly Returns Table
  const monthly=ta.monthly_returns||{};
  const monthKeys=Object.keys(monthly).sort();
  const mtEl=document.getElementById('analyticsMonthlyTable');
  if(mtEl){
    let mtHtml='<div class="panel-title" style="margin-bottom:8px">월별 수익 현황</div><table><thead><tr><th>월</th><th>거래수</th><th>승률</th><th>Total PnL</th><th>Avg PnL</th><th>Best</th><th>Worst</th></tr></thead><tbody>';
    if(monthKeys.length===0){mtHtml+='<tr><td colspan="7" style="color:var(--text2);text-align:center">데이터 없음</td></tr>'}
    else{monthKeys.forEach(k=>{
      const m=monthly[k];
      const c=m.total_pnl>=0?'positive':'negative';
      mtHtml+=`<tr><td style="font-weight:600">${k}</td><td>${m.count}</td><td class="${m.win_rate>=50?'positive':'negative'}">${m.win_rate}%</td><td class="${c}">${m.total_pnl>=0?'+':''}${fmt(m.total_pnl)}</td><td>${fmt(m.avg_pnl)}</td><td class="positive">+${fmt(m.best_trade)}</td><td class="negative">${fmt(m.worst_trade)}</td></tr>`;
    })}
    mtHtml+='</tbody></table>';
    mtEl.innerHTML=mtHtml;
  }

  // Strategy Attribution
  const contrib=sa.contribution||{};
  const atEl=document.getElementById('analyticsAttribution');
  if(atEl){
    const contribKeys=Object.keys(contrib).filter(k=>k!=='_unknown');
    const maxPnl=Math.max(1,...contribKeys.map(k=>Math.abs(contrib[k].total_pnl_krw||0)));
    let atHtml='<div class="panel-title" style="margin-bottom:8px">전략 기여도</div>';
    if(contribKeys.length===0){atHtml+='<p style="color:var(--text2);text-align:center;padding:20px">전략 기여 데이터 없음<br><span style="font-size:11px">contributing_strategies 필드가 기록되면 표시됩니다</span></p>'}
    else{contribKeys.forEach(k=>{
      const c=contrib[k];
      const pnl=c.total_pnl_krw||0;
      const pct=c.pnl_pct_of_total||0;
      const barW=Math.abs(pnl)/maxPnl*100;
      const barColor=pnl>=0?'var(--green)':'var(--red)';
      atHtml+=`<div class="attr-row"><span class="attr-name">${k}</span><div class="attr-bar"><div class="attr-bar-fill" style="width:${barW}%;background:${barColor}"></div></div><span class="attr-val ${pnl>=0?'positive':'negative'}">${pnl>=0?'+':''}${fmt(pnl)} (${pct}%)</span></div>`;
      atHtml+=`<div style="font-size:10px;color:var(--text2);padding:0 0 4px 4px">${c.trade_count}건 | 승률 ${c.win_rate}%</div>`;
    })}
    atEl.innerHTML=atHtml;
  }

  // Strategy Correlation Table
  const corr=sa.strategy_correlation||{};
  const corrEl=document.getElementById('analyticsCorrelation');
  if(corrEl){
    const corrKeys=Object.keys(corr);
    let corrHtml='<div class="panel-title" style="margin-bottom:8px">전략 상관관계</div>';
    if(corrKeys.length===0){corrHtml+='<p style="color:var(--text2);text-align:center;padding:20px">공동 진입 데이터 없음</p>'}
    else{
      corrHtml+='<table><thead><tr><th>전략 조합</th><th>공동진입</th><th>함께 승리</th><th>함께 패배</th><th>동반승률</th></tr></thead><tbody>';
      corrKeys.forEach(k=>{
        const c=corr[k];
        corrHtml+=`<tr><td style="font-weight:600">${k}</td><td>${c.co_occurrences}</td><td class="positive">${c.both_win}</td><td class="negative">${c.both_lose}</td><td class="${c.agreement_win_rate>=50?'positive':'negative'}">${c.agreement_win_rate}%</td></tr>`;
      });
      corrHtml+='</tbody></table>';
    }
    corrEl.innerHTML=corrHtml;
  }

  // Ensemble Accuracy
  const ensAcc=sa.ensemble_accuracy||{};
  const eaEl=document.getElementById('analyticsEnsembleAccuracy');
  if(eaEl){
    const acc=ensAcc.accuracy_pct||0;
    const accColor=acc>=55?'var(--green)':acc>=45?'var(--yellow)':'var(--red)';
    eaEl.innerHTML=`
      <div class="panel-title" style="margin-bottom:12px">앙상블 투표 정확도</div>
      <div style="text-align:center;padding:20px 0">
        <div style="font-size:48px;font-weight:700;color:${accColor}">${acc}%</div>
        <div style="font-size:13px;color:var(--text2);margin-top:8px">전체 ${ensAcc.total_trades||0}건 중 ${ensAcc.winning_trades||0}건 수익</div>
        <div style="margin-top:16px;height:12px;background:var(--bg);border-radius:6px;overflow:hidden">
          <div style="height:100%;width:${acc}%;background:${accColor};border-radius:6px;transition:width .5s"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text2);margin-top:4px">
          <span>0%</span><span>50%</span><span>100%</span>
        </div>
      </div>
      <div style="margin-top:12px;padding:12px;background:var(--bg);border-radius:6px">
        <div style="font-size:12px;color:var(--text2);margin-bottom:6px">해석 가이드:</div>
        <div style="font-size:11px;line-height:1.6;color:var(--text)">
          <div><span style="color:var(--green)">55%+</span>: 양호 - 앙상블이 시장 방향을 잘 예측</div>
          <div><span style="color:var(--yellow)">45-55%</span>: 보통 - 개선 여지 있음</div>
          <div><span style="color:var(--red)">&lt;45%</span>: 재검토 필요 - 전략 파라미터 조정 권장</div>
        </div>
      </div>`;
  }
}

// ── Strategy ──
async function loadStrategy(){
  const d=await api('/api/status');if(!d||!d.ensemble){
    document.getElementById('strategyTable').innerHTML='<div class="panel-title">Strategy Details</div><p style="color:var(--text2);padding:20px;text-align:center">봇이 초기화되면 전략 데이터가 표시됩니다.</p>';
    return;
  }const ens=d.ensemble;
  const names=Object.keys(ens.weights||{});const weights=names.map(n=>((ens.weights[n]||0)*100).toFixed(1));
  const winRates=names.map(n=>{const tc=ens.trade_counts[n]||0;const wc=ens.win_counts[n]||0;return tc>0?((wc/tc)*100).toFixed(1):'0.0'});
  const emaWr=names.map(n=>((ens.ema_win_rates[n]||0)*100).toFixed(1));
  renderChart('weightRadar','radar',{labels:names,datasets:[
    {label:'Weight %',data:weights,borderColor:'#58a6ff',backgroundColor:'rgba(88,166,255,.2)',pointBackgroundColor:'#58a6ff'},
    {label:'EMA WR %',data:emaWr,borderColor:'#3fb950',backgroundColor:'rgba(63,185,80,.2)',pointBackgroundColor:'#3fb950'}
  ]},{scales:{r:{angleLines:{color:'#30363d'},grid:{color:'#30363d'},pointLabels:{color:'#c9d1d9'},ticks:{display:false}}},plugins:{title:{display:true,text:'Strategy Weights & Win Rates',color:'#8b949e'}}});
  document.getElementById('strategyTable').innerHTML=`<div class="panel-title">Strategy Details</div><table>
    <thead><tr><th>Strategy</th><th>Weight</th><th>Trades</th><th>Wins</th><th>Win Rate</th><th>EMA WR</th></tr></thead>
    <tbody>${names.map((n,i)=>`<tr><td style="font-weight:600">${n}</td><td>${weights[i]}%</td><td>${ens.trade_counts[n]||0}</td><td>${ens.win_counts[n]||0}</td>
    <td class="${parseFloat(winRates[i])>=50?'positive':'negative'}">${winRates[i]}%</td><td class="${parseFloat(emaWr[i])>=50?'positive':'negative'}">${emaWr[i]}%</td></tr>`).join('')}</tbody></table>`;
}

// ── History ──
async function loadHistory(page){
  historyPage=page||1;const market=document.getElementById('filterMarket').value;const exit=document.getElementById('filterExit').value;
  const d=await api(`/api/trades/history?page=${historyPage}&market=${market}&exit_type=${exit}`);if(!d)return;
  const tbody=document.getElementById('historyBody');
  if(!d.trades||!d.trades.length){tbody.innerHTML='<tr><td colspan="9" style="color:var(--text2);text-align:center">No trades found</td></tr>'}
  else{tbody.innerHTML=d.trades.map(t=>{const c=cls(t.pnl_krw||0);return `<tr><td style="font-size:11px">${t.exit_time||''}</td><td>${t.market}</td><td>${fmt(t.entry_price)}</td><td>${fmt(t.exit_price)}</td><td class="${c}">${fmtPct(t.pnl_pct||0)}</td><td class="${c}">${(t.pnl_krw||0)>=0?'+':''}${fmt(t.pnl_krw||0)}</td><td style="color:var(--yellow)">${fmt(t.fee_krw||0)}</td><td>${t.exit_type||''}</td><td>${fmtDuration(t.duration_sec||0)}</td></tr>`}).join('')}
  document.getElementById('pagination').innerHTML=`<button class="page-btn ${d.page<=1?'disabled':''}" onclick="loadHistory(${d.page-1})">Prev</button><span class="page-info">${d.page} / ${d.total_pages} (${d.total} trades)</span><button class="page-btn ${d.page>=d.total_pages?'disabled':''}" onclick="loadHistory(${d.page+1})">Next</button>`;
  populateFilters();
}
async function populateFilters(){
  const ms=document.getElementById('filterMarket');const es=document.getElementById('filterExit');
  if(ms.options.length>1)return;
  const rt=await api('/api/runtime');if(rt&&rt.markets)rt.markets.forEach(m=>{const o=document.createElement('option');o.value=m;o.textContent=m;ms.appendChild(o)});
  ['stop_loss','take_profit','trailing_stop','signal_sell','breakeven_stop'].forEach(et=>{const o=document.createElement('option');o.value=et;o.textContent=et;es.appendChild(o)});
}
function exportCSV(){
  const market=document.getElementById('filterMarket').value;
  const exit=document.getElementById('filterExit').value;
  const params=new URLSearchParams();
  if(market)params.set('market',market);
  if(exit)params.set('exit_type',exit);
  const url='/api/export/csv'+(params.toString()?'?'+params.toString():'');
  const a=document.createElement('a');a.href=url;a.download='';a.click();
}

// ── Guide live status ──
async function refreshGuideLive(){
  const guideTab=document.getElementById('tab-guide');
  if(!guideTab||!guideTab.classList.contains('active'))return;
  const mw=_lastMW;const markets=Object.values(mw);
  if(!markets.length){document.getElementById('guideLiveContent').innerHTML='<p style="color:var(--text2)">봇이 실행되면 실시간 상태가 여기에 표시됩니다.</p>';return}
  let html='';
  markets.forEach(m=>{
    const ts=m.trigger_summary;const ens=ts?.ensemble;
    html+=`<div class="guide-live-item">
      <b style="color:var(--accent)">${m.market}</b> (${fmt(m.price)} KRW) — `;
    if(!ens){html+=`<span style="color:var(--text2)">분석 대기중</span></div>`;return}
    // Explain why it's not trading
    if(ens.final_signal==='BUY'){
      html+=`<span style="color:var(--green);font-weight:700">매수 실행 중! ${ens.buy_votes}개 전략 동의, 신뢰도 ${ens.buy_weight?.toFixed(2)}</span>`;
    } else if(ens.final_signal==='SELL'){
      html+=`<span style="color:var(--red);font-weight:700">매도 시그널!</span>`;
    } else {
      // Explain HOLD reason
      const reasons=[];
      if(ens.buy_votes<ens.min_agreement)reasons.push(`전략 동의 부족 (${ens.buy_votes}/${ens.min_agreement}개)`);
      else if(ens.buy_weight<ens.min_confidence)reasons.push(`신뢰도 부족 (${ens.buy_weight?.toFixed(2)}/${ens.min_confidence})`);
      if(ens.trend!=='up')reasons.push(`추세 비상승 (${ens.trend==='down'?'하락':'횡보'})`);
      // Check strategies
      const firingCount=(ts.strategies||[]).filter(s=>s.would_fire).length;
      if(firingCount===0)reasons.push('개별 전략 조건 미충족');
      if(!reasons.length)reasons.push(ens.final_reason||'조건 미충족');
      html+=`<span style="color:var(--yellow)">HOLD</span> — ${reasons.join(', ')}`;
    }
    html+='</div>';
  });
  document.getElementById('guideLiveContent').innerHTML=html;
}

// ── Optimizer Tab (전략 최적화) ──
async function loadOptimizerTab(){
  const d=await api('/api/optimizer/status');
  if(!d||!d.enabled){
    document.getElementById('opt-regime').textContent='비활성';
    document.getElementById('opt-regime').style.color='var(--text2)';
    document.getElementById('opt-run-count').textContent='0';
    document.getElementById('opt-locked').textContent='-';
    document.getElementById('opt-locked').style.color='var(--text2)';
    document.getElementById('opt-rollback-count').textContent='0';
    document.getElementById('opt-last-run').textContent='적응형 최적화 비활성화됨';
    document.getElementById('opt-degradation-body').innerHTML='<tr><td colspan="8" style="color:var(--text2);text-align:center">적응형 최적화가 비활성화 상태입니다</td></tr>';
    document.getElementById('opt-params-body').innerHTML='<tr><td colspan="6" style="color:var(--text2);text-align:center">적응형 최적화가 비활성화 상태입니다</td></tr>';
    document.getElementById('opt-weights-cards').innerHTML='<div style="color:var(--text2);padding:12px">적응형 최적화가 비활성화 상태입니다</div>';
    document.getElementById('opt-history-body').innerHTML='<tr><td colspan="6" style="color:var(--text2);text-align:center">이력 없음</td></tr>';
    document.getElementById('opt-postopt-body').innerHTML='<tr><td colspan="5" style="color:var(--text2);text-align:center">추적 데이터 없음</td></tr>';
    return;
  }
  // Top cards
  const regimeMap={'trending':'추세장','ranging':'횡보장','volatile':'변동성장','unknown':'미확인'};
  const regimeColors={'trending':'var(--green)','ranging':'var(--yellow)','volatile':'var(--red)','unknown':'var(--text2)'};
  const reg=d.current_regime||'unknown';
  const regEl=document.getElementById('opt-regime');
  regEl.textContent=regimeMap[reg]||reg;
  regEl.style.color=regimeColors[reg]||'var(--text)';
  document.getElementById('opt-run-count').textContent=d.run_count||0;
  const ps=d.param_store||{};
  const lockEl=document.getElementById('opt-locked');
  lockEl.textContent=ps.locked?'잠금':'해제';
  lockEl.style.color=ps.locked?'var(--red)':'var(--green)';
  // Rollback count
  let rbCount=0;
  const postOpt=d.post_optimization||{};
  for(const k in postOpt){if(postOpt[k].has_rollback)rbCount++}
  document.getElementById('opt-rollback-count').textContent=rbCount;
  // Last run
  const lrEl=document.getElementById('opt-last-run');
  if(d.last_run_time>0){
    const dt=new Date(d.last_run_time*1000);
    lrEl.textContent='마지막 실행: '+dt.toLocaleString('ko-KR');
  }else{lrEl.textContent='아직 실행되지 않음'}
  // Degradation table
  renderDegradation(d.degradation||{});
  // Params table
  renderParamsTable(ps);
  // Weights
  renderWeightsCards(ps.weights||{});
  // History
  renderOptHistory(d.history||[]);
  // Post-opt tracking
  renderPostOpt(postOpt);
}

function renderDegradation(deg){
  const tbody=document.getElementById('opt-degradation-body');
  const strategies=['rsi_bb','vwap_volume','stoch_rsi','ema_cross'];
  let html='';
  let hasData=false;
  strategies.forEach(s=>{
    const r=deg[s];
    if(!r){
      html+=`<tr><td>${s}</td><td style="color:var(--text2)">미분석</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td style="color:var(--text2);font-size:11px">최적화 사이클 대기 중</td></tr>`;
      return;
    }
    hasData=true;
    const isDeg=r.is_degraded;
    const stColor=isDeg?'var(--red)':'var(--green)';
    const stText=isDeg?'저하 감지':'정상';
    const zColor=(v)=>v<-2?'var(--red)':v<-1?'var(--yellow)':'var(--green)';
    html+=`<tr>
      <td><b>${s}</b></td>
      <td style="color:${stColor};font-weight:700">${stText}</td>
      <td style="color:${zColor(r.z_win_rate)}">${(r.z_win_rate||0).toFixed(2)}</td>
      <td style="color:${zColor(r.z_sharpe)}">${(r.z_sharpe||0).toFixed(2)}</td>
      <td style="color:${zColor(r.z_avg_pnl)}">${(r.z_avg_pnl||0).toFixed(2)}</td>
      <td>${((r.baseline_win_rate||0)*100).toFixed(1)}%</td>
      <td>${((r.current_win_rate||0)*100).toFixed(1)}%</td>
      <td style="font-size:11px;color:var(--text2)">${r.message||'-'}</td>
    </tr>`;
  });
  if(!hasData)html='<tr><td colspan="8" style="color:var(--text2);text-align:center">아직 성능 저하 분석이 실행되지 않았습니다</td></tr>';
  tbody.innerHTML=html;
}

function renderParamsTable(ps){
  const tbody=document.getElementById('opt-params-body');
  const params=ps.strategy_params||{};
  const defaults=ps.defaults||{};
  const bounds=ps.bounds||{};
  const strategies=['rsi_bb','vwap_volume','stoch_rsi','ema_cross'];
  const nameMap={'rsi_bb':'RSI+BB','vwap_volume':'VWAP+Volume','stoch_rsi':'StochRSI','ema_cross':'EMA Cross'};
  let html='';
  strategies.forEach(s=>{
    const sp=params[s]||{};
    const sd=defaults[s]||{};
    const sb=bounds[s]||{};
    const keys=Object.keys(sd);
    keys.forEach((k,i)=>{
      const cur=sp[k]!==undefined?sp[k]:sd[k];
      const def=sd[k];
      const bnd=sb[k];
      const isChanged=cur!==def;
      const changeColor=isChanged?'var(--yellow)':'var(--text)';
      html+=`<tr>
        <td>${i===0?'<b>'+nameMap[s]+'</b>':''}</td>
        <td style="font-family:monospace;font-size:12px">${k}</td>
        <td style="color:${changeColor};font-weight:${isChanged?700:400};font-family:monospace">${typeof cur==='number'?Number(cur).toFixed(cur%1===0?0:3):cur}</td>
        <td style="color:var(--text2);font-family:monospace">${typeof def==='number'?Number(def).toFixed(def%1===0?0:3):def}</td>
        <td style="color:var(--text2);font-size:11px;font-family:monospace">${bnd?bnd[0]+' ~ '+bnd[1]:'-'}</td>
        <td>${i===0?'<button class="btn" style="font-size:10px;padding:2px 8px" onclick="resetParams(\''+s+'\')">초기화</button>':''}</td>
      </tr>`;
    });
  });
  tbody.innerHTML=html||'<tr><td colspan="6" style="color:var(--text2);text-align:center">파라미터 데이터 없음</td></tr>';
}

function renderWeightsCards(weights){
  const container=document.getElementById('opt-weights-cards');
  const nameMap={'rsi_bb':'RSI+BB','vwap_volume':'VWAP+Volume','stoch_rsi':'StochRSI','ema_cross':'EMA Cross'};
  const defaultW={'rsi_bb':0.30,'vwap_volume':0.25,'stoch_rsi':0.25,'ema_cross':0.20};
  let html='';
  for(const s of ['rsi_bb','vwap_volume','stoch_rsi','ema_cross']){
    const w=(weights[s]||0)*100;
    const dw=(defaultW[s]||0)*100;
    const diff=w-dw;
    const diffColor=diff>0?'var(--green)':diff<0?'var(--red)':'var(--text2)';
    const diffSign=diff>0?'+':'';
    html+=`<div class="card">
      <div class="card-label">${nameMap[s]}</div>
      <div class="card-value" style="font-size:20px">${w.toFixed(1)}%</div>
      <div class="card-sub">기본: ${dw.toFixed(0)}% <span style="color:${diffColor}">(${diffSign}${diff.toFixed(1)})</span></div>
      <div style="margin-top:6px;height:4px;background:var(--border);border-radius:2px;overflow:hidden">
        <div style="width:${Math.min(w/40*100,100)}%;height:100%;background:var(--accent);border-radius:2px"></div>
      </div>
    </div>`;
  }
  container.innerHTML=html;
}

function renderOptHistory(history){
  const tbody=document.getElementById('opt-history-body');
  if(!history.length){
    tbody.innerHTML='<tr><td colspan="6" style="color:var(--text2);text-align:center">최적화 이력 없음</td></tr>';
    return;
  }
  let html='';
  history.forEach(h=>{
    const actionColor={'applied':'var(--green)','rejected':'var(--yellow)','rollback':'var(--red)','not_needed':'var(--text2)','skipped':'var(--text2)','failed':'var(--red)','error':'var(--red)'}[h.action]||'var(--text)';
    const actionText={'applied':'적용됨','rejected':'거부됨','rollback':'롤백','not_needed':'불필요','skipped':'건너뜀','failed':'실패','error':'오류','failed_to_apply':'적용실패'}[h.action]||h.action;
    const wf=h.walk_forward||{};
    const improvement=wf.improvement_pct?wf.improvement_pct.toFixed(1)+'%':'-';
    const overfit=wf.overfitting_ratio?wf.overfitting_ratio.toFixed(2):'-';
    const detail=h.reason||'';
    html+=`<tr>
      <td style="font-size:11px;white-space:nowrap">${h.timestamp||'-'}</td>
      <td><b>${h.strategy||'-'}</b></td>
      <td style="color:${actionColor};font-weight:700">${actionText}</td>
      <td>${improvement}</td>
      <td>${overfit}</td>
      <td style="font-size:11px;color:var(--text2);max-width:200px;overflow:hidden;text-overflow:ellipsis">${detail}</td>
    </tr>`;
  });
  tbody.innerHTML=html;
}

function renderPostOpt(postOpt){
  const tbody=document.getElementById('opt-postopt-body');
  const keys=Object.keys(postOpt);
  if(!keys.length){
    tbody.innerHTML='<tr><td colspan="5" style="color:var(--text2);text-align:center">최적화 후 추적 데이터 없음</td></tr>';
    return;
  }
  let html='';
  keys.forEach(s=>{
    const p=postOpt[s];
    const badColor=p.consecutive_bad>=10?'var(--red)':p.consecutive_bad>=5?'var(--yellow)':'var(--green)';
    html+=`<tr>
      <td><b>${s}</b></td>
      <td>${p.trades||0}</td>
      <td style="color:var(--green)">${p.wins||0}</td>
      <td style="color:${badColor};font-weight:700">${p.consecutive_bad||0} / 20</td>
      <td>${p.has_rollback?'<span style="color:var(--yellow)">롤백 준비됨</span>':'<span style="color:var(--text2)">없음</span>'}</td>
    </tr>`;
  });
  tbody.innerHTML=html;
}

async function triggerOptimization(btn){
  if(!confirm('수동 최적화를 실행하시겠습니까? (현재 열린 포지션에 사용 중인 전략은 건너뜁니다)'))return;
  if(!btn)btn=document.getElementById('opt-trigger-btn');
  if(btn){btn.disabled=true;btn.textContent='최적화 실행 중...'}
  try{
    const r=await api('/api/optimizer/trigger','POST');
    if(r&&r.error){alert('오류: '+r.error)}
    else{alert('최적화 완료. 결과를 확인하세요.');loadOptimizerTab()}
  }catch(e){alert('최적화 실패: '+e)}
  finally{if(btn){btn.disabled=false;btn.textContent='수동 최적화 실행'}}
}

async function resetParams(strategy){
  const target=strategy||'전체';
  if(!confirm(target+' 파라미터를 기본값으로 초기화하시겠습니까?'))return;
  const url='/api/optimizer/reset?strategy='+(strategy||'');
  const r=await api(url,'POST');
  if(r&&r.success)loadOptimizerTab();
  else alert('초기화 실패');
}

// ── WebSocket Client ──
let _ws=null,_wsRetry=0,_wsMaxRetry=30000,_wsTimer=null,_useWS=false;
function connectWS(){
  const proto=location.protocol==='https:'?'wss:':'ws:';
  const url=proto+'//'+location.host+'/ws';
  try{_ws=new WebSocket(url)}catch(e){console.warn('WS connect failed',e);return}
  _ws.onopen=()=>{
    console.log('WS connected');_wsRetry=0;_useWS=true;
    stopPolling();
  };
  _ws.onmessage=(e)=>{
    try{handleWSMessage(JSON.parse(e.data))}catch(err){console.error('WS msg error',err)}
  };
  _ws.onclose=()=>{
    console.log('WS closed');_ws=null;_useWS=false;
    startPolling();
    _wsRetry=Math.min(_wsRetry?_wsRetry*2:1000,_wsMaxRetry);
    _wsTimer=setTimeout(connectWS,_wsRetry);
  };
  _ws.onerror=(e)=>{console.warn('WS error',e)};
}
function handleWSMessage(msg){
  switch(msg.type){
    case 'status_update':applyStatus(msg.data);break;
    case 'market_update':applyMarketWatch(msg.data);break;
    case 'trade_event':showTradeAlert(msg.data);break;
    case 'circuit_event':showCircuitAlert(msg.data);break;
  }
}
function showTradeAlert(data){
  const bar=document.querySelector('.topbar');if(!bar)return;
  const color=data.side==='buy'?'var(--green)':'var(--red)';
  const label=data.side==='buy'?'BUY':'SELL';
  bar.style.transition='box-shadow .3s';
  bar.style.boxShadow='inset 0 -3px 0 0 '+color;
  const el=document.createElement('span');
  el.style.cssText='color:'+color+';font-weight:700;font-size:12px;margin-left:12px';
  el.textContent=label+' '+data.market+' @ '+fmt(data.price);
  const right=document.querySelector('.topbar-right');
  if(right)right.prepend(el);
  setTimeout(()=>{bar.style.boxShadow='none';if(el.parentNode)el.remove()},5000);
}
function showCircuitAlert(data){
  const bar=document.querySelector('.topbar');if(!bar)return;
  bar.style.transition='box-shadow .3s';
  bar.style.boxShadow='inset 0 -3px 0 0 var(--yellow)';
  setTimeout(()=>{bar.style.boxShadow='none'},3000);
}

// ── Init with visibility-aware polling + WebSocket ──
let _timers=[];
function startPolling(){
  if(_useWS)return;
  _timers.forEach(clearInterval);_timers=[];
  _timers.push(setInterval(refreshStatus,5000));
  _timers.push(setInterval(refreshMarketWatch,5000));
  _timers.push(setInterval(refreshGuideLive,5000));
}
function stopPolling(){_timers.forEach(clearInterval);_timers=[]}
document.addEventListener('visibilitychange',()=>{
  if(document.hidden){stopPolling();if(_ws)_ws.close()}
  else{refreshStatus();refreshMarketWatch();if(!_useWS)startPolling();connectWS()}
});
async function init(){await refreshStatus();await refreshMarketWatch();startPolling();connectWS()}
init();
</script>
</body>
</html>"""


def run_dashboard(trader=None):
    """Run the dashboard server."""
    import uvicorn
    if trader:
        set_trader(trader)
    uvicorn.run(app, host="0.0.0.0", port=config.DASHBOARD_PORT)
