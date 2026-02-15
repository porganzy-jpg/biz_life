"""
1-minute candle backtester for scalping strategies.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import numpy as np

from . import config
from .strategies.ensemble import EnsembleStrategy
from .strategies.base import SignalType
from .risk_manager import RiskManager
from .optimizer import ParamProfile

logger = logging.getLogger("scalper.backtest")


@dataclass
class BacktestResult:
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl_pct: float
    total_pnl_krw: float
    max_drawdown_pct: float
    sharpe_ratio: float
    avg_trade_duration_min: float
    profit_factor: float
    initial_balance: float
    final_balance: float


class Backtester:

    def __init__(self, initial_balance: float = 1_000_000,
                 param_profile: ParamProfile = None):
        self._original_profile = None
        if param_profile:
            self._original_profile = ParamProfile.from_config()
            param_profile.apply_to_config()

        self.initial_balance = initial_balance
        self.ensemble = EnsembleStrategy()
        self.risk_mgr = RiskManager()

    def run(self, market: str = "KRW-BTC", days: int = 7) -> Optional[BacktestResult]:
        """
        Run backtest on historical 1-minute data.
        """
        logger.info(f"Starting backtest: {market}, {days} days, {self.initial_balance:,.0f} KRW")

        df = self._fetch_data(market, days)
        if df is None or len(df) < 100:
            logger.error("Insufficient data for backtest")
            return None

        balance = self.initial_balance
        position = None  # {entry_price, amount, entry_idx, risk_levels, strategies}
        trades = []
        equity_curve = [balance]
        peak_balance = balance

        window = config.CANDLE_COUNT

        for i in range(window, len(df)):
            candle_slice = df.iloc[i - window:i].reset_index(drop=True)
            current_price = float(df["close"].iloc[i])

            # Check exit if in position
            if position is not None:
                bars_held = i - position["entry_idx"]
                exit_type = self.risk_mgr.check_exit(
                    market, position["entry_price"], current_price,
                    position["risk_levels"], bars_held=bars_held
                )

                # Also check sell signal (필터 적용)
                if exit_type is None:
                    bars_held = i - position["entry_idx"]
                    pnl_pct = (current_price - position["entry_price"]) / position["entry_price"]
                    if bars_held >= config.SIGNAL_EXIT_MIN_BARS and pnl_pct >= config.SIGNAL_EXIT_MIN_PROFIT:
                        signal = self.ensemble.analyze(candle_slice, market=market, bar_index=i)
                        if signal.signal == SignalType.SELL:
                            exit_type = "signal_sell"

                if exit_type:
                    gross_pnl_pct = (current_price - position["entry_price"]) / position["entry_price"]
                    net_pnl_pct = gross_pnl_pct - config.ROUND_TRIP_COMMISSION
                    pnl_krw = position["amount"] * position["entry_price"] * net_pnl_pct
                    balance += position["amount"] * current_price * (1 - config.COMMISSION_RATE)

                    won = pnl_krw > 0
                    self.ensemble.record_trade(market, i, position["strategies"], won)

                    trades.append({
                        "entry_price": position["entry_price"],
                        "exit_price": current_price,
                        "pnl_pct": net_pnl_pct * 100,
                        "pnl_krw": pnl_krw,
                        "exit_type": exit_type,
                        "duration": i - position["entry_idx"],
                        "won": won,
                    })
                    position = None

            # Check entry if no position
            if position is None:
                signal = self.ensemble.analyze(candle_slice, market=market, bar_index=i)

                if signal.signal == SignalType.BUY:
                    risk_levels = self.risk_mgr.calculate_risk_levels(candle_slice, balance)
                    if risk_levels and self.risk_mgr.validate_trade(risk_levels.position_size_krw, balance):
                        invest = risk_levels.position_size_krw
                        commission = invest * config.COMMISSION_RATE
                        amount = (invest - commission) / current_price
                        balance -= invest

                        contributing = []
                        if "signals" in signal.metadata:
                            for s in signal.metadata["signals"]:
                                if s.is_buy:
                                    contributing.append(s.strategy_name)

                        position = {
                            "entry_price": current_price,
                            "amount": amount,
                            "entry_idx": i,
                            "risk_levels": risk_levels,
                            "strategies": contributing,
                        }

            # Equity tracking
            equity = balance
            if position:
                equity += position["amount"] * current_price
            equity_curve.append(equity)
            peak_balance = max(peak_balance, equity)

            # Weight adjustment
            if i % config.WEIGHT_ADJUST_CYCLE == 0 and trades:
                self.ensemble.adjust_weights()

        # Close any remaining position
        if position is not None:
            final_price = float(df["close"].iloc[-1])
            gross_pnl_pct = (final_price - position["entry_price"]) / position["entry_price"]
            net_pnl_pct = gross_pnl_pct - config.ROUND_TRIP_COMMISSION
            pnl_krw = position["amount"] * position["entry_price"] * net_pnl_pct
            balance += position["amount"] * final_price * (1 - config.COMMISSION_RATE)
            trades.append({
                "entry_price": position["entry_price"],
                "exit_price": final_price,
                "pnl_pct": net_pnl_pct * 100,
                "pnl_krw": pnl_krw,
                "exit_type": "end_of_data",
                "duration": len(df) - position["entry_idx"],
                "won": pnl_krw > 0,
            })

        # Restore original config if a param_profile was applied
        if self._original_profile:
            self._original_profile.apply_to_config()

        return self._compile_results(trades, equity_curve, balance)

    def _fetch_data(self, market: str, days: int) -> Optional[pd.DataFrame]:
        """Fetch historical candle data via pyupbit (auto-paginates internally)."""
        try:
            import pyupbit
        except ImportError:
            logger.warning("pyupbit not installed, generating synthetic data")
            return self._generate_synthetic(market, days)

        try:
            interval = config.CANDLE_INTERVAL
            minutes_per_candle = {"minute1": 1, "minute3": 3, "minute5": 5,
                                  "minute10": 10, "minute15": 15, "minute30": 30,
                                  "minute60": 60}.get(interval, 1)
            total_candles = days * 24 * 60 // minutes_per_candle
            api_calls = (total_candles + 199) // 200
            logger.info(f"Fetching {total_candles} {interval} candles for {market} "
                        f"({days} days, ~{api_calls} API calls)...")

            df = pyupbit.get_ohlcv(market, interval=interval,
                                   count=total_candles, period=0.12)

            if df is None or df.empty:
                logger.warning(f"No data returned for {market}, using synthetic")
                return self._generate_synthetic(market, days)

            df = df.reset_index()
            if "value" in df.columns:
                df = df.drop(columns=["value"])
            df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
            logger.info(f"Fetched {len(df)} candles for {market}")
            return df

        except Exception as e:
            logger.error(f"Data fetch failed: {e}")
            return self._generate_synthetic(market, days)

    def _generate_synthetic(self, market: str, days: int) -> pd.DataFrame:
        """Generate synthetic 1-min data for testing when API unavailable."""
        n = days * 24 * 60
        base_prices = {"KRW-BTC": 130_000_000, "KRW-ETH": 5_000_000, "KRW-XRP": 3_200,
                       "KRW-SOL": 280_000, "KRW-DOGE": 530}
        base = base_prices.get(market, 100_000)

        np.random.seed(42)
        # GBM with mean-reverting component
        returns = np.random.normal(0, 0.001, n)
        # Add some trends and reversals
        trend = np.sin(np.linspace(0, 8 * np.pi, n)) * 0.0005
        noise = np.cumsum(returns + trend)
        prices = base * np.exp(noise)

        timestamps = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="1min")
        highs = prices * (1 + np.random.uniform(0, 0.002, n))
        lows = prices * (1 - np.random.uniform(0, 0.002, n))
        opens = prices * (1 + np.random.normal(0, 0.0005, n))
        volumes = np.random.exponential(1.0, n) * (base / 1_000_000)

        logger.info(f"Generated {n} synthetic candles for {market}")
        return pd.DataFrame({
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": volumes,
        })

    def _compile_results(self, trades: list, equity_curve: list, final_balance: float) -> BacktestResult:
        total = len(trades)
        if total == 0:
            return BacktestResult(
                total_trades=0, wins=0, losses=0, win_rate=0, total_pnl_pct=0,
                total_pnl_krw=0, max_drawdown_pct=0, sharpe_ratio=0,
                avg_trade_duration_min=0, profit_factor=0,
                initial_balance=self.initial_balance, final_balance=final_balance,
            )

        wins = sum(1 for t in trades if t["won"])
        losses = total - wins

        gross_wins = sum(t["pnl_krw"] for t in trades if t["won"])
        gross_losses = abs(sum(t["pnl_krw"] for t in trades if not t["won"]))

        total_pnl = final_balance - self.initial_balance
        total_pnl_pct = total_pnl / self.initial_balance * 100

        # Max drawdown
        equity = np.array(equity_curve)
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_dd = abs(drawdown.min()) * 100

        # Sharpe (per-trade returns)
        returns = [t["pnl_pct"] for t in trades]
        avg_ret = np.mean(returns) if returns else 0
        std_ret = np.std(returns) if len(returns) > 1 else 1
        sharpe = (avg_ret / std_ret * np.sqrt(252 * 24 * 60)) if std_ret > 0 else 0

        # Profit factor
        pf = gross_wins / gross_losses if gross_losses > 0 else float("inf")

        avg_duration = np.mean([t["duration"] for t in trades])

        result = BacktestResult(
            total_trades=total,
            wins=wins,
            losses=losses,
            win_rate=wins / total * 100,
            total_pnl_pct=total_pnl_pct,
            total_pnl_krw=total_pnl,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe,
            avg_trade_duration_min=avg_duration,
            profit_factor=pf,
            initial_balance=self.initial_balance,
            final_balance=final_balance,
        )

        logger.info("=" * 60)
        logger.info("BACKTEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"  Trades: {total} (W:{wins} / L:{losses})")
        logger.info(f"  Win Rate: {result.win_rate:.1f}%")
        logger.info(f"  PnL: {total_pnl:+,.0f} KRW ({total_pnl_pct:+.2f}%)")
        logger.info(f"  Max Drawdown: {max_dd:.2f}%")
        logger.info(f"  Sharpe Ratio: {sharpe:.2f}")
        logger.info(f"  Profit Factor: {pf:.2f}")
        logger.info(f"  Avg Duration: {avg_duration:.0f} min")
        logger.info(f"  Final Balance: {final_balance:,.0f} KRW")
        logger.info("=" * 60)

        # Per-exit-type breakdown
        exit_types = {}
        for t in trades:
            et = t["exit_type"]
            if et not in exit_types:
                exit_types[et] = {"count": 0, "pnl": 0}
            exit_types[et]["count"] += 1
            exit_types[et]["pnl"] += t["pnl_krw"]

        logger.info("Exit Type Breakdown:")
        for et, stats in exit_types.items():
            logger.info(f"  {et}: {stats['count']} trades, PnL: {stats['pnl']:+,.0f} KRW")

        return result
