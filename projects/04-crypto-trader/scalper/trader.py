"""
Main Scalping Engine - 3-second cycle.

Loop:
1. Circuit breaker check
2. Check open positions (stop/TP/trailing)
3. Scan markets for signals
4. Ensemble -> Risk -> Execute
5. Auto-adjust weights every 500 cycles
"""
import logging
import time
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from . import config
from .upbit_client import UpbitClient
from .strategies.ensemble import EnsembleStrategy
from .strategies.base import SignalType
from .risk_manager import RiskManager, RiskLevels
from .circuit_breaker import CircuitBreaker
from .alert_system import AlertSystem
from .market_scanner import MarketScanner
from .optimizer import WalkForwardOptimizer

logger = logging.getLogger("scalper.trader")

LOG_FILE = Path(__file__).parent / "scalp_trades.json"


@dataclass
class OpenPosition:
    market: str
    side: str  # "long"
    entry_price: float
    amount: float
    entry_time: float
    risk_levels: RiskLevels
    contributing_strategies: list = field(default_factory=list)


@dataclass
class TradeRecord:
    market: str
    side: str
    entry_price: float
    exit_price: float
    amount: float
    pnl_krw: float
    pnl_pct: float
    exit_type: str
    entry_time: str
    exit_time: str
    duration_sec: float
    fee_krw: float = 0.0


class ScalpTrader:

    def __init__(self, paper: bool = True):
        self.client = UpbitClient(paper=paper)
        self.ensemble = EnsembleStrategy()
        self.risk_mgr = RiskManager()
        self.alert = AlertSystem()

        initial_balance = self.client.get_krw_balance()
        self.circuit = CircuitBreaker(initial_balance)

        self.positions: dict[str, OpenPosition] = {}
        self.trade_history: list[TradeRecord] = []
        self.cycle_count = 0
        self.running = False
        self.today = date.today()

        # Dynamic market scanner
        self.scanner = MarketScanner() if config.DYNAMIC_MARKETS_ENABLED else None
        # Walk-forward optimizer
        self.optimizer = WalkForwardOptimizer() if config.OPTIMIZER_ENABLED else None

        # Stats
        self.total_wins = 0
        self.total_losses = 0

        # Dashboard tracking
        self.start_time = time.time()
        self.total_fees_krw = 0.0
        self.today_trades = 0
        self._last_market_analysis: dict[str, dict] = {}  # market -> analysis cache
        self._ws_callback = None
        self._prev_can_trade = True

        mode_info = []
        if self.scanner:
            mode_info.append(f"Scanner(top{config.SCANNER_TOP_N})")
        if self.optimizer:
            mode_info.append("Optimizer")
        logger.info(f"ScalpTrader initialized. Balance: {initial_balance:,.0f} KRW, "
                     f"Paper: {paper}, Markets: {config.MARKETS}, "
                     f"Modules: {', '.join(mode_info) or 'none'}")

    def set_ws_callback(self, push_fn):
        """Set WebSocket push callback (thread-safe queue.put)."""
        self._ws_callback = push_fn

    def _ws_push(self, event: dict):
        """Push event via callback if set."""
        if self._ws_callback:
            try:
                self._ws_callback(event)
            except Exception:
                pass

    def run(self):
        """Main trading loop."""
        self.running = True
        self.start_time = time.time()
        logger.info("=== Scalping Bot Started ===")

        # Start background optimizer
        if self.optimizer:
            self.optimizer.start()
            logger.info("Walk-forward optimizer started (background thread)")

        # Startup alert
        balance = self.client.get_krw_balance()
        markets = self.scanner.get_markets(self.positions) if self.scanner else config.MARKETS
        self.alert.startup_alert(balance, markets, self.client.paper)

        while self.running:
            try:
                self._check_new_day()
                self._tick()
                self.cycle_count += 1

                # Periodic status log (every 20 cycles ~60s)
                if self.cycle_count % 20 == 0:
                    balance = self.client.get_krw_balance()
                    total = self.total_wins + self.total_losses
                    pos_str = ", ".join(self.positions.keys()) if self.positions else "none"
                    logger.info(
                        f"[Cycle {self.cycle_count}] Balance: {balance:,.0f} KRW | "
                        f"Trades: {total} (W:{self.total_wins}/L:{self.total_losses}) | "
                        f"Positions: {pos_str}"
                    )

                # Hourly report
                if self.alert.should_send_hourly_report():
                    self.alert.hourly_report(self.get_status())

                # Auto-adjust weights
                if self.cycle_count % config.WEIGHT_ADJUST_CYCLE == 0 and self.cycle_count > 0:
                    self.ensemble.adjust_weights()
                    logger.info(f"Cycle {self.cycle_count}: weights adjusted")

                time.sleep(config.LOOP_INTERVAL_SEC)

            except KeyboardInterrupt:
                logger.info("Shutdown requested...")
                self.running = False
            except Exception as e:
                logger.error(f"Tick error: {e}", exc_info=True)
                time.sleep(config.LOOP_INTERVAL_SEC)

        logger.info("=== Scalping Bot Stopped ===")
        self._print_summary()

    def stop(self):
        self.running = False
        if self.optimizer:
            self.optimizer.stop()

    def _tick(self):
        """Single trading cycle."""
        # 1. Circuit breaker
        can_trade, reason = self.circuit.can_trade()
        if can_trade != self._prev_can_trade:
            self._ws_push({
                "type": "circuit_event",
                "data": {
                    "can_trade": can_trade,
                    "reason": reason,
                },
            })
            self._prev_can_trade = can_trade
        if not can_trade:
            if self.cycle_count % 100 == 0:
                logger.warning(f"Trading paused: {reason}")
            return

        # 2. Check open positions
        for market in list(self.positions.keys()):
            self._check_position(market)

        # 3. Scan markets (dynamic or static)
        if not can_trade:
            return

        markets = (self.scanner.get_markets(self.positions)
                   if self.scanner else config.MARKETS)
        for market in markets:
            if market in self.positions:
                continue  # Already have a position

            self._analyze_market(market)

    def _analyze_market(self, market: str):
        """Analyze a single market for entry signals."""
        df = self.client.get_ohlcv(market, config.CANDLE_INTERVAL, config.CANDLE_COUNT)
        if df is None:
            return

        signal = self.ensemble.analyze(df, market=market, bar_index=self.cycle_count)

        # Cache analysis for dashboard market watch
        current_price = float(df["close"].iloc[-1])
        trend = self.ensemble._get_trend(df)
        strategy_signals = []
        if "signals" in signal.metadata:
            for s in signal.metadata["signals"]:
                strategy_signals.append({
                    "name": s.strategy_name,
                    "signal": s.signal.value,
                    "confidence": round(s.confidence, 3),
                    "reason": s.reason,
                })

        # Compute raw indicator values for dashboard gauges
        indicators = _compute_indicators(df)

        # Build trigger summary for condition checklist
        trigger_summary = _build_trigger_summary(
            df, indicators, strategy_signals, signal, trend,
            self.ensemble.weights,
        )

        self._last_market_analysis[market] = {
            "market": market,
            "price": current_price,
            "trend": trend,
            "ensemble_signal": signal.signal.value,
            "ensemble_confidence": round(signal.confidence, 3),
            "ensemble_reason": signal.reason,
            "strategy_signals": strategy_signals,
            "buy_weight": signal.metadata.get("buy_weight", 0),
            "sell_weight": signal.metadata.get("sell_weight", 0),
            "indicators": indicators,
            "trigger_summary": trigger_summary,
            "updated_at": datetime.now().strftime("%H:%M:%S"),
        }

        if signal.signal == SignalType.BUY:
            self._execute_buy(market, df, signal)

    def _execute_buy(self, market: str, df, signal):
        """Execute a buy order with risk management."""
        balance = self.client.get_krw_balance()
        risk_levels = self.risk_mgr.calculate_risk_levels(df, balance, side="buy")

        if risk_levels is None:
            return

        if not self.risk_mgr.validate_trade(risk_levels.position_size_krw, balance):
            return

        # Execute
        result = self.client.buy_market(market, risk_levels.position_size_krw)
        if result is None:
            return

        price = result.get("price", float(df["close"].iloc[-1]))
        amount = result.get("amount", risk_levels.position_size_krw / price)

        # Track position
        contributing = []
        if "signals" in signal.metadata:
            for s in signal.metadata["signals"]:
                if s.is_buy:
                    contributing.append(s.strategy_name)

        self.positions[market] = OpenPosition(
            market=market,
            side="long",
            entry_price=price,
            amount=amount,
            entry_time=time.time(),
            risk_levels=risk_levels,
            contributing_strategies=contributing,
        )

        self._ws_push({
            "type": "trade_event",
            "data": {
                "side": "buy", "market": market,
                "price": price, "amount": amount,
                "krw_amount": risk_levels.position_size_krw,
                "reason": signal.reason,
            },
        })

        self.alert.trade_alert(
            market=market, side="buy", price=price, amount=amount,
            krw_amount=risk_levels.position_size_krw, reason=signal.reason,
        )

    def _check_position(self, market: str):
        """Check if an open position should be exited."""
        pos = self.positions.get(market)
        if not pos:
            return

        current_price = self.client.get_current_price(market)
        if current_price is None:
            # Fallback
            df = self.client.get_ohlcv(market, count=2)
            if df is not None and len(df) > 0:
                current_price = float(df["close"].iloc[-1])
            else:
                return

        time_held = time.time() - pos.entry_time
        bars_held = int(time_held / 60)
        exit_type = self.risk_mgr.check_exit(market, pos.entry_price, current_price,
                                             pos.risk_levels, bars_held=bars_held)

        # Also check ensemble for sell signal
        if exit_type is None:
            time_held = time.time() - pos.entry_time
            pnl_pct = (current_price - pos.entry_price) / pos.entry_price
            bars_held = int(time_held / 60)
            if bars_held >= config.SIGNAL_EXIT_MIN_BARS and pnl_pct >= config.SIGNAL_EXIT_MIN_PROFIT:
                df = self.client.get_ohlcv(market, config.CANDLE_INTERVAL, config.CANDLE_COUNT)
                if df is not None:
                    signal = self.ensemble.analyze(df, market=market, bar_index=self.cycle_count)
                    if signal.signal == SignalType.SELL:
                        exit_type = "signal_sell"

        if exit_type:
            self._execute_sell(market, current_price, exit_type)

    def _execute_sell(self, market: str, exit_price: float, exit_type: str):
        """Execute sell and record results."""
        pos = self.positions.get(market)
        if not pos:
            return

        result = self.client.sell_market(market, pos.amount)
        if result is None:
            return

        actual_exit_price = result.get("price", exit_price)

        # PnL calculation (including commission)
        gross_pnl_pct = (actual_exit_price - pos.entry_price) / pos.entry_price
        net_pnl_pct = gross_pnl_pct - config.ROUND_TRIP_COMMISSION
        position_value = pos.amount * pos.entry_price
        pnl_krw = position_value * net_pnl_pct

        # Fee calculation
        fee_krw = position_value * config.ROUND_TRIP_COMMISSION
        self.total_fees_krw += fee_krw

        # Record
        won = pnl_krw > 0
        if won:
            self.total_wins += 1
        else:
            self.total_losses += 1

        self.today_trades += 1
        self.circuit.record_trade(pnl_krw)
        self.ensemble.record_trade(market, self.cycle_count, pos.contributing_strategies, won)

        duration = time.time() - pos.entry_time
        record = TradeRecord(
            market=market,
            side="long",
            entry_price=pos.entry_price,
            exit_price=actual_exit_price,
            amount=pos.amount,
            pnl_krw=pnl_krw,
            pnl_pct=net_pnl_pct * 100,
            exit_type=exit_type,
            entry_time=datetime.fromtimestamp(pos.entry_time).strftime("%Y-%m-%d %H:%M:%S"),
            exit_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration_sec=duration,
            fee_krw=fee_krw,
        )
        self.trade_history.append(record)
        self._save_trade(record)

        self._ws_push({
            "type": "trade_event",
            "data": {
                "side": "sell", "market": market,
                "price": actual_exit_price, "amount": pos.amount,
                "exit_type": exit_type,
                "pnl_krw": round(pnl_krw, 0),
                "pnl_pct": round(net_pnl_pct * 100, 2),
            },
        })

        self.alert.exit_alert(
            market=market, exit_type=exit_type,
            entry_price=pos.entry_price, exit_price=actual_exit_price,
            pnl_krw=pnl_krw, pnl_pct=net_pnl_pct * 100,
        )

        del self.positions[market]

    def _check_new_day(self):
        """Reset daily counters at midnight + send daily summary."""
        today = date.today()
        if today != self.today:
            # Send daily summary before reset
            self.alert.daily_summary(self.get_status())

            balance = self.client.get_krw_balance()
            self.circuit.reset_daily(balance)
            self.today = today
            self.today_trades = 0
            logger.info(f"New trading day: {today}")

    def _save_trade(self, record: TradeRecord):
        """Append trade to JSON log."""
        try:
            trades = []
            if LOG_FILE.exists():
                trades = json.loads(LOG_FILE.read_text(encoding="utf-8"))
            trades.append(asdict(record))
            LOG_FILE.write_text(json.dumps(trades, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")

    def _print_summary(self):
        total = self.total_wins + self.total_losses
        win_rate = (self.total_wins / total * 100) if total > 0 else 0
        balance = self.client.get_krw_balance()

        logger.info("=" * 50)
        logger.info(f"Session Summary")
        logger.info(f"  Cycles: {self.cycle_count}")
        logger.info(f"  Trades: {total} (W:{self.total_wins} / L:{self.total_losses})")
        logger.info(f"  Win Rate: {win_rate:.1f}%")
        logger.info(f"  Balance: {balance:,.0f} KRW")
        logger.info(f"  Daily PnL: {self.circuit.daily_pnl:+,.0f} KRW")
        logger.info(f"  Total Fees: {self.total_fees_krw:,.0f} KRW")
        logger.info("=" * 50)

    def get_status(self) -> dict:
        """Get current bot status (for dashboard)."""
        balance = self.client.get_krw_balance()
        total = self.total_wins + self.total_losses
        uptime_sec = time.time() - self.start_time

        # Build position details with unrealized PnL and SL/TP
        positions_detail = {}
        for m, p in self.positions.items():
            cur_price = self.client.get_current_price(m)
            if cur_price is None:
                cur_price = p.entry_price
            unrealized_pct = (cur_price - p.entry_price) / p.entry_price * 100
            unrealized_krw = p.amount * p.entry_price * (cur_price - p.entry_price) / p.entry_price
            positions_detail[m] = {
                "entry_price": p.entry_price,
                "current_price": cur_price,
                "amount": p.amount,
                "entry_time": datetime.fromtimestamp(p.entry_time).strftime("%H:%M:%S"),
                "unrealized_pnl_pct": round(unrealized_pct, 3),
                "unrealized_pnl_krw": round(unrealized_krw, 0),
                "stop_loss": round(p.risk_levels.stop_loss_price, 0),
                "take_profit": round(p.risk_levels.take_profit_price, 0),
                "stop_loss_pct": round(p.risk_levels.stop_loss_pct * 100, 2),
                "take_profit_pct": round(p.risk_levels.take_profit_pct * 100, 2),
                "contributing_strategies": p.contributing_strategies,
            }

        # Scanner / Optimizer status
        active_markets = (self.scanner.get_active_markets()
                          if self.scanner else list(config.MARKETS))
        scanner_status = self.scanner.get_status() if self.scanner else {"enabled": False}
        optimizer_status = self.optimizer.get_status() if self.optimizer else {"enabled": False}

        return {
            "running": self.running,
            "paper": self.client.paper,
            "cycle_count": self.cycle_count,
            "balance_krw": balance,
            "open_positions": positions_detail,
            "total_trades": total,
            "wins": self.total_wins,
            "losses": self.total_losses,
            "win_rate": (self.total_wins / total * 100) if total > 0 else 0,
            "daily_pnl": self.circuit.daily_pnl,
            "total_fees_krw": round(self.total_fees_krw, 0),
            "today_trades": self.today_trades,
            "uptime_sec": round(uptime_sec, 0),
            "circuit_breaker": self.circuit.get_status(),
            "ensemble": self.ensemble.get_status(),
            "recent_trades": [asdict(t) for t in self.trade_history[-20:]],
            "active_markets": active_markets,
            "scanner_status": scanner_status,
            "optimizer_status": optimizer_status,
        }

    def get_market_watch(self) -> dict:
        """Get cached market analysis data for dashboard."""
        return dict(self._last_market_analysis)


def load_all_trades() -> list[dict]:
    """Load all trades from JSON log file."""
    try:
        if LOG_FILE.exists():
            data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Failed to load trades: {e}")
    return []


def get_trades_stats(period: str = "all") -> dict:
    """Calculate trade statistics for a given period.

    period: 'today', 'week', 'month', 'all'
    """
    all_trades = load_all_trades()
    if not all_trades:
        return _empty_stats()

    now = datetime.now()
    if period == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    else:
        cutoff = datetime.min

    # Filter trades by period
    trades = []
    for t in all_trades:
        try:
            exit_dt = datetime.strptime(t["exit_time"], "%Y-%m-%d %H:%M:%S")
            if exit_dt >= cutoff:
                trades.append(t)
        except (ValueError, KeyError):
            if period == "all":
                trades.append(t)

    if not trades:
        return _empty_stats()

    wins = sum(1 for t in trades if t.get("pnl_krw", 0) > 0)
    losses = len(trades) - wins
    total_pnl = sum(t.get("pnl_krw", 0) for t in trades)
    total_fees = sum(t.get("fee_krw", 0) for t in trades)
    pnl_list = [t.get("pnl_krw", 0) for t in trades]
    pct_list = [t.get("pnl_pct", 0) for t in trades]

    # Profit factor
    gross_profit = sum(p for p in pnl_list if p > 0)
    gross_loss = abs(sum(p for p in pnl_list if p < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    # Max drawdown (cumulative)
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnl_list:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    # Average duration
    durations = [t.get("duration_sec", 0) for t in trades]
    avg_duration = sum(durations) / len(durations) if durations else 0

    # Exit type breakdown
    exit_types: dict[str, int] = {}
    for t in trades:
        et = t.get("exit_type", "unknown")
        exit_types[et] = exit_types.get(et, 0) + 1

    # Daily PnL breakdown (for bar chart)
    daily_pnl: dict[str, float] = {}
    for t in trades:
        try:
            day = t["exit_time"][:10]
            daily_pnl[day] = daily_pnl.get(day, 0) + t.get("pnl_krw", 0)
        except (KeyError, TypeError):
            pass

    # Cumulative PnL series (for equity curve)
    equity_curve = []
    cum = 0.0
    for t in trades:
        cum += t.get("pnl_krw", 0)
        equity_curve.append({
            "time": t.get("exit_time", ""),
            "cumulative_pnl": round(cum, 0),
        })

    # Strategy breakdown
    strategy_stats: dict[str, dict] = {}
    # Note: strategy info not stored in trade log, so we skip per-trade strategy analysis

    return {
        "period": period,
        "total_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(trades) * 100, 1) if trades else 0,
        "total_pnl_krw": round(total_pnl, 0),
        "total_fees_krw": round(total_fees, 0),
        "avg_pnl_krw": round(total_pnl / len(trades), 0) if trades else 0,
        "avg_pnl_pct": round(sum(pct_list) / len(pct_list), 2) if pct_list else 0,
        "best_trade_krw": round(max(pnl_list), 0) if pnl_list else 0,
        "worst_trade_krw": round(min(pnl_list), 0) if pnl_list else 0,
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
        "max_drawdown_krw": round(max_dd, 0),
        "avg_duration_sec": round(avg_duration, 0),
        "exit_types": exit_types,
        "daily_pnl": daily_pnl,
        "equity_curve": equity_curve,
    }


def get_trades_history(page: int = 1, page_size: int = 50,
                       market: str = "", exit_type: str = "") -> dict:
    """Get paginated trade history with filters."""
    all_trades = load_all_trades()

    # Apply filters
    if market:
        all_trades = [t for t in all_trades if t.get("market") == market]
    if exit_type:
        all_trades = [t for t in all_trades if t.get("exit_type") == exit_type]

    # Reverse (newest first)
    all_trades = list(reversed(all_trades))

    total = len(all_trades)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "trades": all_trades[start:end],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


def _empty_stats() -> dict:
    return {
        "period": "all",
        "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0,
        "total_pnl_krw": 0, "total_fees_krw": 0,
        "avg_pnl_krw": 0, "avg_pnl_pct": 0,
        "best_trade_krw": 0, "worst_trade_krw": 0,
        "profit_factor": 0, "max_drawdown_krw": 0,
        "avg_duration_sec": 0, "exit_types": {},
        "daily_pnl": {}, "equity_curve": [],
    }


def _build_trigger_summary(df, indicators: dict, strategy_signals: list,
                           ensemble_signal, trend: str,
                           weights: dict) -> dict:
    """Build per-strategy trigger condition breakdown for dashboard checklist."""
    import pandas as pd
    close = df["close"]
    ind = indicators
    strategies = []

    # --- RSI + BB ---
    rsi_bb_conds = []
    rsi_val = ind.get("rsi")
    rsi_prev = ind.get("rsi_prev")
    bb_pctb = ind.get("bb_pctb")
    if rsi_val is not None:
        rsi_os = rsi_val < config.RSI_OVERSOLD
        rsi_bb_conds.append({
            "label": f"RSI < {config.RSI_OVERSOLD}",
            "met": rsi_os,
            "current": f"현재: {rsi_val:.1f}",
        })
    if bb_pctb is not None:
        bb_low = bb_pctb < 0.15
        rsi_bb_conds.append({
            "label": "BB%B < 15%",
            "met": bb_low,
            "current": f"현재: {bb_pctb*100:.1f}%",
        })
    if rsi_val is not None and rsi_prev is not None:
        recovering = rsi_val > rsi_prev
        rsi_bb_conds.append({
            "label": "RSI 반등 중",
            "met": recovering,
            "current": "상승 중" if recovering else "하락 중",
        })
    met_count = sum(1 for c in rsi_bb_conds if c["met"])
    strategies.append({
        "name": "RSI+BB",
        "key": "rsi_bb",
        "weight": round(weights.get("rsi_bb", 0.3) * 100),
        "conditions": rsi_bb_conds,
        "met_count": met_count,
        "total_count": len(rsi_bb_conds),
        "would_fire": met_count == len(rsi_bb_conds) and len(rsi_bb_conds) > 0,
    })

    # --- VWAP + Volume ---
    vwap_conds = []
    vwap_val = ind.get("vwap")
    vol_ratio = ind.get("vol_ratio")
    cur_price = float(close.iloc[-1])
    if vwap_val is not None:
        above_vwap = cur_price > vwap_val
        vwap_conds.append({
            "label": "가격 > VWAP",
            "met": above_vwap,
            "current": f"가격={cur_price:,.0f}, VWAP={vwap_val:,.0f}",
        })
        # Check recent crossover (simplified)
        try:
            vwap_series = indicators.get("chart_vwap", [])
            close_series = indicators.get("chart_close", [])
            if len(vwap_series) >= 3 and len(close_series) >= 3:
                prev_below = close_series[-2] <= (vwap_series[-2] or 0) or close_series[-3] <= (vwap_series[-3] or 0)
                cur_above = close_series[-1] > (vwap_series[-1] or 0)
                cross_up = prev_below and cur_above
            else:
                cross_up = False
        except Exception:
            cross_up = False
        vwap_conds.append({
            "label": "VWAP 상향돌파",
            "met": cross_up,
            "current": "돌파!" if cross_up else "대기",
        })
    if vol_ratio is not None:
        surge = vol_ratio >= config.VOLUME_SURGE_MULTIPLIER
        vwap_conds.append({
            "label": f"거래량 ≥ {config.VOLUME_SURGE_MULTIPLIER}x",
            "met": surge,
            "current": f"현재: {vol_ratio:.1f}x",
        })
    met_count = sum(1 for c in vwap_conds if c["met"])
    strategies.append({
        "name": "VWAP+Volume",
        "key": "vwap_volume",
        "weight": round(weights.get("vwap_volume", 0.25) * 100),
        "conditions": vwap_conds,
        "met_count": met_count,
        "total_count": len(vwap_conds),
        "would_fire": met_count == len(vwap_conds) and len(vwap_conds) > 0,
    })

    # --- StochRSI ---
    stoch_conds = []
    k_val = ind.get("stoch_k")
    d_val = ind.get("stoch_d")
    if k_val is not None and d_val is not None:
        in_oversold = k_val < config.STOCH_OVERSOLD or d_val < config.STOCH_OVERSOLD
        stoch_conds.append({
            "label": f"K or D < {config.STOCH_OVERSOLD}",
            "met": in_oversold,
            "current": f"K={k_val:.1f}, D={d_val:.1f}",
        })
        # Golden cross check
        try:
            k_series = indicators.get("chart_stoch_k", [])
            d_series = indicators.get("chart_stoch_d", [])
            if len(k_series) >= 2 and len(d_series) >= 2:
                k_prev = k_series[-2] or 0
                d_prev = d_series[-2] or 0
                golden = k_prev <= d_prev and k_val > d_val
            else:
                golden = False
        except Exception:
            golden = False
        stoch_conds.append({
            "label": "K선이 D선 상향교차",
            "met": golden,
            "current": "골든크로스!" if golden else "대기",
        })
    met_count = sum(1 for c in stoch_conds if c["met"])
    strategies.append({
        "name": "StochRSI",
        "key": "stoch_rsi",
        "weight": round(weights.get("stoch_rsi", 0.25) * 100),
        "conditions": stoch_conds,
        "met_count": met_count,
        "total_count": len(stoch_conds),
        "would_fire": met_count == len(stoch_conds) and len(stoch_conds) > 0,
    })

    # --- EMA Crossover ---
    ema_conds = []
    ema_fast = ind.get("ema_fast")
    ema_slow = ind.get("ema_slow")
    ema_trend_val = ind.get("ema_trend")
    ema_fast_prev = ind.get("ema_fast_prev")
    ema_slow_prev = ind.get("ema_slow_prev")
    if ema_fast is not None and ema_slow is not None:
        if ema_fast_prev is not None and ema_slow_prev is not None:
            golden = ema_fast_prev <= ema_slow_prev and ema_fast > ema_slow
            ema_conds.append({
                "label": f"EMA{config.EMA_FAST} > EMA{config.EMA_SLOW} 교차",
                "met": golden,
                "current": "골든크로스!" if golden else f"EMA{config.EMA_FAST}={'위' if ema_fast > ema_slow else '아래'}",
            })
    if ema_trend_val is not None:
        above = cur_price > ema_trend_val
        ema_conds.append({
            "label": f"가격 > EMA{config.EMA_TREND}",
            "met": above,
            "current": f"가격={cur_price:,.0f}, EMA{config.EMA_TREND}={ema_trend_val:,.0f}",
        })
    met_count = sum(1 for c in ema_conds if c["met"])
    strategies.append({
        "name": "EMA Cross",
        "key": "ema_cross",
        "weight": round(weights.get("ema_cross", 0.2) * 100),
        "conditions": ema_conds,
        "met_count": met_count,
        "total_count": len(ema_conds),
        "would_fire": met_count == len(ema_conds) and len(ema_conds) > 0,
    })

    # --- Ensemble summary ---
    buy_votes = sum(1 for s in strategy_signals if s.get("signal") == "BUY")
    sell_votes = sum(1 for s in strategy_signals if s.get("signal") == "SELL")
    buy_w = ensemble_signal.metadata.get("buy_weight", 0)
    sell_w = ensemble_signal.metadata.get("sell_weight", 0)

    ensemble_summary = {
        "buy_votes": buy_votes,
        "sell_votes": sell_votes,
        "total_strategies": len(strategy_signals),
        "min_agreement": config.MIN_AGREEMENT,
        "buy_weight": round(buy_w, 3),
        "sell_weight": round(sell_w, 3),
        "min_confidence": config.MIN_ENSEMBLE_CONFIDENCE,
        "trend": trend,
        "trend_required": "up",
        "final_signal": ensemble_signal.signal.value,
        "final_reason": ensemble_signal.reason,
    }

    return {
        "strategies": strategies,
        "ensemble": ensemble_summary,
    }


def _compute_indicators(df) -> dict:
    """Compute raw indicator values from DataFrame for dashboard gauges."""
    import pandas as pd
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    n = len(close)

    result = {}

    # --- RSI ---
    try:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta.clip(upper=0))
        avg_gain = gain.rolling(window=config.RSI_PERIOD, min_periods=config.RSI_PERIOD).mean()
        avg_loss = loss.rolling(window=config.RSI_PERIOD, min_periods=config.RSI_PERIOD).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = float(rsi.iloc[-1])
        prev_rsi = float(rsi.iloc[-2])
        result["rsi"] = round(rsi_val, 1) if not pd.isna(rsi_val) else None
        result["rsi_prev"] = round(prev_rsi, 1) if not pd.isna(prev_rsi) else None
        result["rsi_oversold"] = config.RSI_OVERSOLD
        result["rsi_overbought"] = config.RSI_OVERBOUGHT
    except Exception:
        result["rsi"] = None

    # --- Bollinger Bands ---
    try:
        bb_mid = close.rolling(window=config.BB_PERIOD).mean()
        bb_std = close.rolling(window=config.BB_PERIOD).std()
        bb_upper = bb_mid + config.BB_STD_DEV * bb_std
        bb_lower = bb_mid - config.BB_STD_DEV * bb_std
        cur_close = float(close.iloc[-1])
        cur_upper = float(bb_upper.iloc[-1])
        cur_lower = float(bb_lower.iloc[-1])
        cur_mid = float(bb_mid.iloc[-1])
        bb_width = cur_upper - cur_lower
        bb_pctb = (cur_close - cur_lower) / bb_width if bb_width > 0 else 0.5
        result["bb_pctb"] = round(bb_pctb, 3) if not pd.isna(bb_pctb) else None
        result["bb_upper"] = round(cur_upper, 0)
        result["bb_mid"] = round(cur_mid, 0)
        result["bb_lower"] = round(cur_lower, 0)
        result["bb_buy_zone"] = 0.15
        result["bb_sell_zone"] = 0.85
    except Exception:
        result["bb_pctb"] = None

    # --- Stochastic RSI ---
    try:
        delta2 = close.diff()
        gain2 = delta2.clip(lower=0)
        loss2 = (-delta2.clip(upper=0))
        ag2 = gain2.rolling(window=config.STOCH_RSI_PERIOD, min_periods=config.STOCH_RSI_PERIOD).mean()
        al2 = loss2.rolling(window=config.STOCH_RSI_PERIOD, min_periods=config.STOCH_RSI_PERIOD).mean()
        rs2 = ag2 / al2.replace(0, 1e-10)
        rsi2 = 100 - (100 / (1 + rs2))
        rsi_min = rsi2.rolling(window=config.STOCH_RSI_PERIOD).min()
        rsi_max = rsi2.rolling(window=config.STOCH_RSI_PERIOD).max()
        rsi_range = rsi_max - rsi_min
        stoch_rsi = ((rsi2 - rsi_min) / rsi_range.replace(0, 1e-10)) * 100
        k_line = stoch_rsi.rolling(window=config.STOCH_K_PERIOD).mean()
        d_line = k_line.rolling(window=config.STOCH_D_PERIOD).mean()
        k_val = float(k_line.iloc[-1])
        d_val = float(d_line.iloc[-1])
        result["stoch_k"] = round(k_val, 1) if not pd.isna(k_val) else None
        result["stoch_d"] = round(d_val, 1) if not pd.isna(d_val) else None
        result["stoch_oversold"] = config.STOCH_OVERSOLD
        result["stoch_overbought"] = config.STOCH_OVERBOUGHT
    except Exception:
        result["stoch_k"] = None
        result["stoch_d"] = None

    # --- EMA Crossover ---
    try:
        ema_fast = close.ewm(span=config.EMA_FAST, adjust=False).mean()
        ema_slow = close.ewm(span=config.EMA_SLOW, adjust=False).mean()
        ema_trend = close.ewm(span=config.EMA_TREND, adjust=False).mean()
        result["ema_fast"] = round(float(ema_fast.iloc[-1]), 0)
        result["ema_slow"] = round(float(ema_slow.iloc[-1]), 0)
        result["ema_trend"] = round(float(ema_trend.iloc[-1]), 0)
        result["ema_fast_prev"] = round(float(ema_fast.iloc[-2]), 0)
        result["ema_slow_prev"] = round(float(ema_slow.iloc[-2]), 0)
        result["ema_fast_period"] = config.EMA_FAST
        result["ema_slow_period"] = config.EMA_SLOW
        result["ema_trend_period"] = config.EMA_TREND
    except Exception:
        result["ema_fast"] = None

    # --- VWAP + Volume ---
    try:
        typical_price = (high + low + close) / 3
        cum_tp_vol = (typical_price * volume).rolling(window=config.VWAP_PERIOD).sum()
        cum_vol = volume.rolling(window=config.VWAP_PERIOD).sum()
        vwap = cum_tp_vol / cum_vol.replace(0, 1e-10)
        avg_volume = volume.rolling(window=config.VWAP_PERIOD).mean()
        volume_ratio = volume / avg_volume.replace(0, 1e-10)
        vwap_val = float(vwap.iloc[-1])
        vol_ratio_val = float(volume_ratio.iloc[-1])
        result["vwap"] = round(vwap_val, 0) if not pd.isna(vwap_val) else None
        result["vol_ratio"] = round(vol_ratio_val, 2) if not pd.isna(vol_ratio_val) else None
        result["vol_surge_threshold"] = config.VOLUME_SURGE_MULTIPLIER
    except Exception:
        result["vwap"] = None
        result["vol_ratio"] = None

    # --- Chart data (last 60 candles) for candlestick + subchart ---
    try:
        tail = min(60, n)
        slc = slice(-tail, None)
        result["chart_close"] = [round(float(v), 0) for v in close.iloc[slc].values]
        result["chart_open"] = [round(float(v), 0) for v in df["open"].iloc[slc].values]
        result["chart_high"] = [round(float(v), 0) for v in high.iloc[slc].values]
        result["chart_low"] = [round(float(v), 0) for v in low.iloc[slc].values]
        result["chart_volume"] = [round(float(v), 4) for v in volume.iloc[slc].values]
        result["chart_time"] = [str(t)[-8:-3] for t in df["timestamp"].iloc[slc].values]

        # ISO timestamps for lightweight-charts (YYYY-MM-DD HH:MM format)
        raw_ts = df["timestamp"].iloc[slc].values
        iso_times = []
        for t in raw_ts:
            ts_str = str(t)
            if len(ts_str) >= 16:
                iso_times.append(ts_str[:16].replace("T", " "))
            else:
                iso_times.append(ts_str)
        result["chart_time_iso"] = iso_times
    except Exception:
        result["chart_close"] = []
        result["chart_open"] = []
        result["chart_high"] = []
        result["chart_low"] = []
        result["chart_volume"] = []
        result["chart_time"] = []
        result["chart_time_iso"] = []

    # --- Indicator time series for subchart overlays ---
    try:
        tail = min(60, n)
        slc = slice(-tail, None)

        # RSI series
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss_s = (-delta.clip(upper=0))
        avg_gain = gain.rolling(window=config.RSI_PERIOD, min_periods=config.RSI_PERIOD).mean()
        avg_loss = loss_s.rolling(window=config.RSI_PERIOD, min_periods=config.RSI_PERIOD).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        rsi_series = 100 - (100 / (1 + rs))
        result["chart_rsi"] = [round(float(v), 1) if not pd.isna(v) else None for v in rsi_series.iloc[slc].values]

        # BB bands series
        bb_mid_s = close.rolling(window=config.BB_PERIOD).mean()
        bb_std_s = close.rolling(window=config.BB_PERIOD).std()
        bb_upper_s = bb_mid_s + config.BB_STD_DEV * bb_std_s
        bb_lower_s = bb_mid_s - config.BB_STD_DEV * bb_std_s
        result["chart_bb_upper"] = [round(float(v), 0) if not pd.isna(v) else None for v in bb_upper_s.iloc[slc].values]
        result["chart_bb_mid"] = [round(float(v), 0) if not pd.isna(v) else None for v in bb_mid_s.iloc[slc].values]
        result["chart_bb_lower"] = [round(float(v), 0) if not pd.isna(v) else None for v in bb_lower_s.iloc[slc].values]

        # EMA series (3, 8, 21)
        ema3 = close.ewm(span=config.EMA_FAST, adjust=False).mean()
        ema8 = close.ewm(span=config.EMA_SLOW, adjust=False).mean()
        ema21 = close.ewm(span=config.EMA_TREND, adjust=False).mean()
        result["chart_ema3"] = [round(float(v), 0) if not pd.isna(v) else None for v in ema3.iloc[slc].values]
        result["chart_ema8"] = [round(float(v), 0) if not pd.isna(v) else None for v in ema8.iloc[slc].values]
        result["chart_ema21"] = [round(float(v), 0) if not pd.isna(v) else None for v in ema21.iloc[slc].values]

        # VWAP series
        typical_price = (high + low + close) / 3
        cum_tp_vol = (typical_price * volume).rolling(window=config.VWAP_PERIOD).sum()
        cum_vol = volume.rolling(window=config.VWAP_PERIOD).sum()
        vwap_s = cum_tp_vol / cum_vol.replace(0, 1e-10)
        result["chart_vwap"] = [round(float(v), 0) if not pd.isna(v) else None for v in vwap_s.iloc[slc].values]

        # StochRSI K/D series
        rsi_min = rsi_series.rolling(window=config.STOCH_RSI_PERIOD).min()
        rsi_max = rsi_series.rolling(window=config.STOCH_RSI_PERIOD).max()
        rsi_range = rsi_max - rsi_min
        stoch_rsi_raw = ((rsi_series - rsi_min) / rsi_range.replace(0, 1e-10)) * 100
        k_series = stoch_rsi_raw.rolling(window=config.STOCH_K_PERIOD).mean()
        d_series = k_series.rolling(window=config.STOCH_D_PERIOD).mean()
        result["chart_stoch_k"] = [round(float(v), 1) if not pd.isna(v) else None for v in k_series.iloc[slc].values]
        result["chart_stoch_d"] = [round(float(v), 1) if not pd.isna(v) else None for v in d_series.iloc[slc].values]

        # Volume average series (for surge line)
        avg_vol = volume.rolling(window=config.VWAP_PERIOD).mean()
        result["chart_vol_avg"] = [round(float(v), 4) if not pd.isna(v) else None for v in avg_vol.iloc[slc].values]
    except Exception:
        result["chart_rsi"] = []
        result["chart_bb_upper"] = []
        result["chart_bb_mid"] = []
        result["chart_bb_lower"] = []
        result["chart_ema3"] = []
        result["chart_ema8"] = []
        result["chart_ema21"] = []
        result["chart_vwap"] = []
        result["chart_stoch_k"] = []
        result["chart_stoch_d"] = []
        result["chart_vol_avg"] = []

    return result
