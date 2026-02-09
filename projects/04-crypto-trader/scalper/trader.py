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
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from . import config
from .upbit_client import UpbitClient
from .strategies.ensemble import EnsembleStrategy
from .strategies.base import SignalType
from .risk_manager import RiskManager, RiskLevels
from .circuit_breaker import CircuitBreaker
from .alert_system import AlertSystem

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

        # Stats
        self.total_wins = 0
        self.total_losses = 0

        logger.info(f"ScalpTrader initialized. Balance: {initial_balance:,.0f} KRW, "
                     f"Paper: {paper}, Markets: {config.MARKETS}")

    def run(self):
        """Main trading loop."""
        self.running = True
        logger.info("=== Scalping Bot Started ===")

        while self.running:
            try:
                self._check_new_day()
                self._tick()
                self.cycle_count += 1

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

    def _tick(self):
        """Single trading cycle."""
        # 1. Circuit breaker
        can_trade, reason = self.circuit.can_trade()
        if not can_trade:
            if self.cycle_count % 100 == 0:
                logger.warning(f"Trading paused: {reason}")
            return

        # 2. Check open positions
        for market in list(self.positions.keys()):
            self._check_position(market)

        # 3. Scan markets
        if not can_trade:
            return

        for market in config.MARKETS:
            if market in self.positions:
                continue  # Already have a position

            self._analyze_market(market)

    def _analyze_market(self, market: str):
        """Analyze a single market for entry signals."""
        df = self.client.get_ohlcv(market, config.CANDLE_INTERVAL, config.CANDLE_COUNT)
        if df is None:
            return

        signal = self.ensemble.analyze(df, market=market, bar_index=self.cycle_count)

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

        # Also check ensemble for sell signal (필터 적용)
        if exit_type is None:
            time_held = time.time() - pos.entry_time
            pnl_pct = (current_price - pos.entry_price) / pos.entry_price
            bars_held = int(time_held / 60)  # 대략 분 단위
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
        pnl_krw = pos.amount * pos.entry_price * net_pnl_pct

        # Record
        won = pnl_krw > 0
        if won:
            self.total_wins += 1
        else:
            self.total_losses += 1

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
        )
        self.trade_history.append(record)
        self._save_trade(record)

        self.alert.exit_alert(
            market=market, exit_type=exit_type,
            entry_price=pos.entry_price, exit_price=actual_exit_price,
            pnl_krw=pnl_krw, pnl_pct=net_pnl_pct * 100,
        )

        del self.positions[market]

    def _check_new_day(self):
        """Reset daily counters at midnight."""
        today = date.today()
        if today != self.today:
            balance = self.client.get_krw_balance()
            self.circuit.reset_daily(balance)
            self.today = today
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
        logger.info("=" * 50)

    def get_status(self) -> dict:
        """Get current bot status (for dashboard)."""
        balance = self.client.get_krw_balance()
        total = self.total_wins + self.total_losses
        return {
            "running": self.running,
            "cycle_count": self.cycle_count,
            "balance_krw": balance,
            "open_positions": {m: {
                "entry_price": p.entry_price,
                "amount": p.amount,
                "entry_time": datetime.fromtimestamp(p.entry_time).strftime("%H:%M:%S"),
            } for m, p in self.positions.items()},
            "total_trades": total,
            "wins": self.total_wins,
            "losses": self.total_losses,
            "win_rate": (self.total_wins / total * 100) if total > 0 else 0,
            "daily_pnl": self.circuit.daily_pnl,
            "circuit_breaker": self.circuit.get_status(),
            "ensemble": self.ensemble.get_status(),
            "recent_trades": [asdict(t) for t in self.trade_history[-20:]],
        }
