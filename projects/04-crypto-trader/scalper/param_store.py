"""
Strategy Parameter Store - JSON persistence with history and locking.

Stores per-strategy tunable parameters in data/strategy_params.json.
Provides parameter history, lock mechanism, and safe defaults.
"""
import json
import logging
import threading
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("scalper.param_store")

DATA_DIR = Path(__file__).parent.parent / "data"
PARAMS_FILE = DATA_DIR / "strategy_params.json"
HISTORY_FILE = DATA_DIR / "strategy_params_history.json"
MAX_HISTORY = 200  # Keep last N parameter change records


# ── Default parameter definitions per strategy ──────────────────

STRATEGY_DEFAULTS = {
    "rsi_bb": {
        "rsi_period": 14,
        "rsi_oversold": 35,
        "rsi_overbought": 65,
        "bb_period": 20,
        "bb_std": 2.0,
    },
    "vwap_volume": {
        "vwap_deviation": 0.002,
        "volume_threshold": 1.3,
    },
    "stoch_rsi": {
        "stoch_period": 14,
        "stoch_k": 5,
        "stoch_d": 3,
    },
    "ema_cross": {
        "fast_ema": 5,
        "slow_ema": 13,
        "signal_ema": 34,
    },
}

# Bounds for each parameter (min, max) - used for grid search clamping
PARAM_BOUNDS = {
    "rsi_bb": {
        "rsi_period": (7, 21),
        "rsi_oversold": (20, 45),
        "rsi_overbought": (55, 80),
        "bb_period": (14, 30),
        "bb_std": (1.5, 3.0),
    },
    "vwap_volume": {
        "vwap_deviation": (0.001, 0.005),
        "volume_threshold": (1.0, 2.5),
    },
    "stoch_rsi": {
        "stoch_period": (7, 21),
        "stoch_k": (3, 7),
        "stoch_d": (2, 5),
    },
    "ema_cross": {
        "fast_ema": (3, 8),
        "slow_ema": (8, 21),
        "signal_ema": (21, 55),
    },
}

# Ensemble weight defaults
WEIGHT_DEFAULTS = {
    "rsi_bb": 0.30,
    "vwap_volume": 0.25,
    "stoch_rsi": 0.25,
    "ema_cross": 0.20,
}


class ParamStore:
    """Thread-safe JSON-persisted strategy parameter store."""

    def __init__(self):
        self._lock = threading.RLock()
        self._params: dict = {}
        self._weights: dict = dict(WEIGHT_DEFAULTS)
        self._locked: bool = False
        self._lock_reason: str = ""
        self._load()

    def _ensure_data_dir(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self):
        """Load parameters from disk, falling back to defaults."""
        self._ensure_data_dir()
        try:
            if PARAMS_FILE.exists():
                raw = json.loads(PARAMS_FILE.read_text(encoding="utf-8"))
                self._params = raw.get("strategy_params", {})
                self._weights = raw.get("weights", dict(WEIGHT_DEFAULTS))
                self._locked = raw.get("locked", False)
                self._lock_reason = raw.get("lock_reason", "")
                logger.info(f"ParamStore loaded from {PARAMS_FILE}")
            else:
                self._params = deepcopy(STRATEGY_DEFAULTS)
                self._weights = dict(WEIGHT_DEFAULTS)
                self._save()
                logger.info("ParamStore initialized with defaults")
        except Exception as e:
            logger.error(f"ParamStore load failed: {e}, using defaults")
            self._params = deepcopy(STRATEGY_DEFAULTS)
            self._weights = dict(WEIGHT_DEFAULTS)

    def _save(self):
        """Persist current state to JSON."""
        self._ensure_data_dir()
        try:
            payload = {
                "strategy_params": self._params,
                "weights": self._weights,
                "locked": self._locked,
                "lock_reason": self._lock_reason,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            PARAMS_FILE.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"ParamStore save failed: {e}")

    def get_params(self, strategy_name: str) -> dict:
        """Get current parameters for a strategy."""
        with self._lock:
            return dict(self._params.get(strategy_name, STRATEGY_DEFAULTS.get(strategy_name, {})))

    def get_all_params(self) -> dict:
        """Get all strategy parameters."""
        with self._lock:
            return deepcopy(self._params)

    def get_weights(self) -> dict:
        """Get current ensemble weights."""
        with self._lock:
            return dict(self._weights)

    def set_params(self, strategy_name: str, params: dict, source: str = "manual") -> bool:
        """Set parameters for a strategy.

        Returns False if store is locked.
        """
        with self._lock:
            if self._locked:
                logger.warning(f"ParamStore locked ({self._lock_reason}), rejecting update for {strategy_name}")
                return False

            old_params = dict(self._params.get(strategy_name, {}))
            # Clamp to bounds
            bounds = PARAM_BOUNDS.get(strategy_name, {})
            clamped = {}
            for k, v in params.items():
                if k in bounds:
                    lo, hi = bounds[k]
                    if isinstance(v, (int, float)):
                        v = max(lo, min(hi, v))
                clamped[k] = v

            self._params[strategy_name] = clamped
            self._save()
            self._record_history(strategy_name, old_params, clamped, source)
            logger.info(f"ParamStore: {strategy_name} updated by {source}: {clamped}")
            return True

    def set_weights(self, weights: dict, source: str = "manual") -> bool:
        """Set ensemble weights."""
        with self._lock:
            if self._locked:
                return False
            old = dict(self._weights)
            self._weights = dict(weights)
            self._save()
            self._record_history("_weights", old, weights, source)
            logger.info(f"ParamStore: weights updated by {source}: {weights}")
            return True

    def reset_to_defaults(self, strategy_name: str = "") -> bool:
        """Reset parameters to defaults."""
        with self._lock:
            if self._locked:
                return False
            if strategy_name:
                defaults = STRATEGY_DEFAULTS.get(strategy_name, {})
                if defaults:
                    old = dict(self._params.get(strategy_name, {}))
                    self._params[strategy_name] = deepcopy(defaults)
                    self._save()
                    self._record_history(strategy_name, old, defaults, "reset")
            else:
                self._params = deepcopy(STRATEGY_DEFAULTS)
                self._weights = dict(WEIGHT_DEFAULTS)
                self._save()
                self._record_history("_all", {}, {}, "full_reset")
            return True

    def lock(self, reason: str = ""):
        """Lock the param store to prevent updates."""
        with self._lock:
            self._locked = True
            self._lock_reason = reason
            self._save()
            logger.info(f"ParamStore LOCKED: {reason}")

    def unlock(self):
        """Unlock the param store."""
        with self._lock:
            self._locked = False
            self._lock_reason = ""
            self._save()
            logger.info("ParamStore UNLOCKED")

    @property
    def is_locked(self) -> bool:
        with self._lock:
            return self._locked

    def _record_history(self, strategy_name: str, old_params: dict,
                        new_params: dict, source: str):
        """Append a change record to the history file."""
        try:
            record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "strategy": strategy_name,
                "source": source,
                "old": old_params,
                "new": new_params,
            }
            history = self._load_history()
            history.append(record)
            # Trim
            if len(history) > MAX_HISTORY:
                history = history[-MAX_HISTORY:]
            self._ensure_data_dir()
            HISTORY_FILE.write_text(
                json.dumps(history, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug(f"History record failed: {e}")

    def _load_history(self) -> list:
        """Load parameter history."""
        try:
            if HISTORY_FILE.exists():
                data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
                return data if isinstance(data, list) else []
        except Exception:
            pass
        return []

    def get_history(self, strategy_name: str = "", limit: int = 50) -> list:
        """Get parameter change history, optionally filtered by strategy."""
        history = self._load_history()
        if strategy_name:
            history = [h for h in history if h.get("strategy") == strategy_name]
        return list(reversed(history[-limit:]))

    def get_status(self) -> dict:
        """Get full store status for API/dashboard."""
        with self._lock:
            return {
                "strategy_params": deepcopy(self._params),
                "weights": dict(self._weights),
                "locked": self._locked,
                "lock_reason": self._lock_reason,
                "defaults": deepcopy(STRATEGY_DEFAULTS),
                "bounds": deepcopy(PARAM_BOUNDS),
            }

    def apply_to_config(self):
        """Apply stored parameters to the runtime config module."""
        from . import config

        with self._lock:
            # RSI+BB
            rsi_bb = self._params.get("rsi_bb", {})
            if "rsi_period" in rsi_bb:
                config.RSI_PERIOD = int(rsi_bb["rsi_period"])
            if "rsi_oversold" in rsi_bb:
                config.RSI_OVERSOLD = int(rsi_bb["rsi_oversold"])
            if "rsi_overbought" in rsi_bb:
                config.RSI_OVERBOUGHT = int(rsi_bb["rsi_overbought"])
            if "bb_period" in rsi_bb:
                config.BB_PERIOD = int(rsi_bb["bb_period"])
            if "bb_std" in rsi_bb:
                config.BB_STD_DEV = float(rsi_bb["bb_std"])

            # VWAP+Volume
            vwap = self._params.get("vwap_volume", {})
            if "volume_threshold" in vwap:
                config.VOLUME_SURGE_MULTIPLIER = float(vwap["volume_threshold"])

            # StochRSI
            stoch = self._params.get("stoch_rsi", {})
            if "stoch_period" in stoch:
                config.STOCH_RSI_PERIOD = int(stoch["stoch_period"])
            if "stoch_k" in stoch:
                config.STOCH_K_PERIOD = int(stoch["stoch_k"])
            if "stoch_d" in stoch:
                config.STOCH_D_PERIOD = int(stoch["stoch_d"])

            # EMA Crossover
            ema = self._params.get("ema_cross", {})
            if "fast_ema" in ema:
                config.EMA_FAST = int(ema["fast_ema"])
            if "slow_ema" in ema:
                config.EMA_SLOW = int(ema["slow_ema"])
            if "signal_ema" in ema:
                config.EMA_TREND = int(ema["signal_ema"])

            # Ensemble weights
            if self._weights:
                config.DEFAULT_WEIGHTS = dict(self._weights)

            logger.info("ParamStore: applied parameters to config")
