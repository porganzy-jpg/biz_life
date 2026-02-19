"""
Walk-Forward Optimizer: periodic parameter optimization using backtesting.

Runs in a background thread, testing random parameter profiles against
recent market data and applying the best-performing configuration.
"""
import logging
import random
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np

from . import config

logger = logging.getLogger("scalper.optimizer")


@dataclass
class ParamProfile:
    """Runtime-overridable parameter snapshot."""
    candle_interval: str = "minute15"
    min_ensemble_confidence: float = 0.25
    entry_cooldown_bars: int = 3
    risk_per_trade: float = 0.02
    atr_stop_multiplier: float = 1.5
    atr_tp_multiplier: float = 4.0
    stop_loss_hard_cap: float = 0.030
    take_profit_pct: float = 0.030
    trailing_activate_pct: float = 0.008
    trailing_stop_pct: float = 0.003
    breakeven_after_bars: int = 48
    weights: dict = field(default_factory=lambda: {
        "rsi_bb": 0.30, "vwap_volume": 0.25,
        "stoch_rsi": 0.25, "ema_cross": 0.20,
    })

    # Mapping from profile fields to config module attributes
    _CONFIG_MAP = {
        "candle_interval": "CANDLE_INTERVAL",
        "min_ensemble_confidence": "MIN_ENSEMBLE_CONFIDENCE",
        "entry_cooldown_bars": "ENTRY_COOLDOWN_BARS",
        "risk_per_trade": "RISK_PER_TRADE",
        "atr_stop_multiplier": "ATR_STOP_MULTIPLIER",
        "atr_tp_multiplier": "ATR_TP_MULTIPLIER",
        "stop_loss_hard_cap": "STOP_LOSS_HARD_CAP",
        "take_profit_pct": "TAKE_PROFIT_PCT",
        "trailing_activate_pct": "TRAILING_ACTIVATE_PCT",
        "trailing_stop_pct": "TRAILING_STOP_PCT",
        "breakeven_after_bars": "BREAKEVEN_AFTER_BARS",
        "weights": "DEFAULT_WEIGHTS",
    }

    @classmethod
    def from_config(cls) -> "ParamProfile":
        """Create a profile snapshot from current config module values."""
        return cls(
            candle_interval=config.CANDLE_INTERVAL,
            min_ensemble_confidence=config.MIN_ENSEMBLE_CONFIDENCE,
            entry_cooldown_bars=config.ENTRY_COOLDOWN_BARS,
            risk_per_trade=config.RISK_PER_TRADE,
            atr_stop_multiplier=config.ATR_STOP_MULTIPLIER,
            atr_tp_multiplier=config.ATR_TP_MULTIPLIER,
            stop_loss_hard_cap=config.STOP_LOSS_HARD_CAP,
            take_profit_pct=config.TAKE_PROFIT_PCT,
            trailing_activate_pct=config.TRAILING_ACTIVATE_PCT,
            trailing_stop_pct=config.TRAILING_STOP_PCT,
            breakeven_after_bars=config.BREAKEVEN_AFTER_BARS,
            weights=dict(config.DEFAULT_WEIGHTS),
        )

    def apply_to_config(self):
        """Write this profile's values into the config module at runtime."""
        for field_name, config_attr in self._CONFIG_MAP.items():
            val = getattr(self, field_name)
            if field_name == "weights":
                val = dict(val)  # copy
            setattr(config, config_attr, val)

    def summary(self) -> dict:
        """Short summary for dashboard display."""
        return {
            "confidence": self.min_ensemble_confidence,
            "risk": self.risk_per_trade,
            "sl_cap": self.stop_loss_hard_cap,
            "tp": self.take_profit_pct,
            "trail_act": self.trailing_activate_pct,
            "trail_stop": self.trailing_stop_pct,
            "atr_stop": self.atr_stop_multiplier,
            "atr_tp": self.atr_tp_multiplier,
            "weights": {k: round(v, 3) for k, v in self.weights.items()},
        }


def _random_profile(base: ParamProfile) -> ParamProfile:
    """Generate a random ParamProfile within sensible ranges."""
    # Dirichlet for strategy weights (sum=1)
    raw_w = np.random.dirichlet([2, 2, 2, 2])
    keys = ["rsi_bb", "vwap_volume", "stoch_rsi", "ema_cross"]
    weights = {k: round(float(v), 4) for k, v in zip(keys, raw_w)}

    return ParamProfile(
        candle_interval=base.candle_interval,  # keep candle interval fixed
        min_ensemble_confidence=round(random.uniform(0.20, 0.40), 3),
        entry_cooldown_bars=random.randint(2, 6),
        risk_per_trade=round(random.uniform(0.01, 0.03), 4),
        atr_stop_multiplier=round(random.uniform(1.0, 2.5), 2),
        atr_tp_multiplier=round(random.uniform(3.0, 6.0), 2),
        stop_loss_hard_cap=round(random.uniform(0.020, 0.040), 4),
        take_profit_pct=round(random.uniform(0.020, 0.040), 4),
        trailing_activate_pct=round(random.uniform(0.005, 0.012), 4),
        trailing_stop_pct=round(random.uniform(0.002, 0.005), 4),
        breakeven_after_bars=random.randint(32, 64),
        weights=weights,
    )


class WalkForwardOptimizer:
    """Background optimizer that periodically searches for better parameters."""

    def __init__(self, scan_interval_sec: int = None):
        self._scan_interval = scan_interval_sec or config.OPTIMIZER_INTERVAL_SEC
        self._lock = threading.Lock()
        self._best_profile: ParamProfile = ParamProfile.from_config()
        self._best_score: float = 0.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_run: float = 0.0
        self._run_count: int = 0
        self._data_cache: dict = {}  # market -> DataFrame

    def start(self):
        """Launch background optimization thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="optimizer")
        self._thread.start()
        logger.info(f"Optimizer started (interval={self._scan_interval}s, "
                    f"profiles={config.OPTIMIZER_N_PROFILES})")

    def stop(self):
        self._running = False

    def _loop(self):
        # Wait a bit before first run to let trader stabilize
        time.sleep(30)
        while self._running:
            try:
                self._optimize()
            except Exception as e:
                logger.error(f"Optimizer error: {e}", exc_info=True)
            time.sleep(self._scan_interval)

    def _optimize(self):
        """Run one optimization cycle: generate profiles, backtest, apply best."""
        from .backtester import Backtester

        markets = config.OPTIMIZER_MARKETS
        days = config.OPTIMIZER_LOOKBACK_DAYS
        n_profiles = config.OPTIMIZER_N_PROFILES

        logger.info(f"Optimizer: starting cycle #{self._run_count + 1} "
                    f"({n_profiles} profiles, {days}d lookback)")

        # Build candidate profiles: default + current best + random
        default_profile = ParamProfile.from_config()
        candidates = [default_profile]

        with self._lock:
            if self._best_score > 0:
                candidates.append(self._best_profile)

        for _ in range(n_profiles - len(candidates)):
            candidates.append(_random_profile(default_profile))

        # Score each profile
        best_score = -999.0
        best_profile = default_profile
        original_profile = ParamProfile.from_config()

        for idx, profile in enumerate(candidates):
            try:
                score = self._evaluate_profile(profile, markets, days)
                label = "default" if idx == 0 else ("best" if idx == 1 and self._best_score > 0 else f"random-{idx}")
                logger.debug(f"  Profile {label}: score={score:.4f}")
                if score > best_score:
                    best_score = score
                    best_profile = profile
            except Exception as e:
                logger.warning(f"  Profile {idx} eval failed: {e}")

        # Restore original config first (backtests may have modified it)
        original_profile.apply_to_config()

        # Apply best if it improved
        with self._lock:
            if best_score > self._best_score or self._run_count == 0:
                self._best_profile = best_profile
                self._best_score = best_score
                best_profile.apply_to_config()
                logger.info(f"Optimizer: new best score={best_score:.4f}, "
                           f"profile={best_profile.summary()}")
            else:
                logger.info(f"Optimizer: no improvement "
                           f"(best={self._best_score:.4f}, current={best_score:.4f})")

        self._last_run = time.time()
        self._run_count += 1
        self._data_cache.clear()

    def _evaluate_profile(self, profile: ParamProfile,
                          markets: list[str], days: int) -> float:
        """Run backtest with a profile and return composite score."""
        from .backtester import Backtester

        scores = []
        for market in markets:
            bt = Backtester(
                initial_balance=config.PAPER_INITIAL_KRW,
                param_profile=profile,
            )
            result = bt.run(market=market, days=days)
            if result and result.total_trades >= 3:
                # Score: profit_factor*0.4 + win_rate*0.3 - max_dd_penalty*0.3
                pf_score = min(result.profit_factor, 3.0) / 3.0  # normalize to 0-1
                wr_score = result.win_rate / 100.0                # normalize to 0-1
                dd_penalty = min(result.max_drawdown_pct, 10.0) / 10.0  # 0-1
                score = pf_score * 0.4 + wr_score * 0.3 - dd_penalty * 0.3
                scores.append(score)

        if not scores:
            return -1.0
        return sum(scores) / len(scores)

    def get_best_profile(self) -> ParamProfile:
        with self._lock:
            return self._best_profile

    def get_status(self) -> dict:
        """Status for dashboard display."""
        with self._lock:
            return {
                "enabled": True,
                "running": self._running,
                "last_run": self._last_run,
                "run_count": self._run_count,
                "best_score": round(self._best_score, 4),
                "best_profile": self._best_profile.summary(),
                "interval_sec": self._scan_interval,
            }
