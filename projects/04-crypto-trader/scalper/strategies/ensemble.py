"""
Weighted Ensemble Voting System.

Combines 4 strategies with weighted voting.
Requires minimum 2 strategy agreement + confidence threshold.
추세 필터 + 쿨다운으로 허위 진입 차단.
Auto-adjusts weights based on performance (EMA win rate).
"""
import logging
from collections import defaultdict

import pandas as pd

from .. import config
from .base import BaseScalpStrategy, ScalpSignal, SignalType
from .rsi_bb_scalp import RsiBbScalpStrategy
from .vwap_volume import VwapVolumeStrategy
from .stochastic_rsi import StochasticRsiStrategy
from .ema_crossover import EmaCrossoverStrategy

logger = logging.getLogger("scalper.ensemble")


class EnsembleStrategy:
    """Weighted ensemble of all scalping strategies."""

    def __init__(self):
        self.strategies: list[BaseScalpStrategy] = [
            RsiBbScalpStrategy(),
            VwapVolumeStrategy(),
            StochasticRsiStrategy(),
            EmaCrossoverStrategy(),
        ]
        self.weights = dict(config.DEFAULT_WEIGHTS)

        # Performance tracking per strategy
        self.win_counts: dict[str, int] = defaultdict(int)
        self.trade_counts: dict[str, int] = defaultdict(int)
        self.ema_win_rate: dict[str, float] = {s.name: 0.5 for s in self.strategies}

        # Cooldown tracking (market -> last trade bar index)
        self.last_trade_bar: dict[str, int] = {}

    def analyze(self, df: pd.DataFrame, market: str = "", bar_index: int = 0) -> ScalpSignal:
        """Run all strategies and produce weighted ensemble signal."""
        # Run all strategies first (for market watch even during cooldown/vol filter)
        signals: list[ScalpSignal] = []
        for strategy in self.strategies:
            sig = strategy.analyze(df)
            signals.append(sig)

        sig_meta = {"signals": signals}

        # 쿨다운 체크
        if market and market in self.last_trade_bar:
            bars_since = bar_index - self.last_trade_bar[market]
            if bars_since < config.ENTRY_COOLDOWN_BARS:
                return ScalpSignal(
                    signal=SignalType.HOLD, strategy_name="ensemble",
                    reason=f"Cooldown ({bars_since}/{config.ENTRY_COOLDOWN_BARS})",
                    metadata=sig_meta,
                )

        # 변동성 레짐 체크
        if not self._check_volatility_regime(df):
            return ScalpSignal(
                signal=SignalType.HOLD, strategy_name="ensemble",
                reason="Volatility outside optimal range",
                metadata=sig_meta,
            )

        buy_weight = 0.0
        sell_weight = 0.0
        buy_count = 0
        sell_count = 0
        reasons = []

        for sig in signals:
            w = self.weights.get(sig.strategy_name, 0.0)
            if sig.is_buy:
                buy_weight += w * sig.confidence
                buy_count += 1
                reasons.append(f"{sig.strategy_name}:BUY({sig.confidence:.2f})")
            elif sig.is_sell:
                sell_weight += w * sig.confidence
                sell_count += 1
                reasons.append(f"{sig.strategy_name}:SELL({sig.confidence:.2f})")

        reason_str = ", ".join(reasons) if reasons else "all HOLD"

        # 추세 필터: EMA 기울기로 역추세 진입 방지
        trend = self._get_trend(df)

        # BUY 조건: 동의 수 + 신뢰도 문턱 + 추세 필터
        # 단일 전략은 높은 신뢰도 필요, 복수 전략은 낮은 문턱 허용
        single_strategy_min = getattr(config, 'SINGLE_STRATEGY_MIN_CONFIDENCE', 0.50)
        if buy_count >= config.MIN_AGREEMENT and buy_weight > sell_weight:
            # 신뢰도 체크: 단일 전략 시 더 높은 문턱 적용
            if buy_count == 1 and buy_weight < single_strategy_min:
                return ScalpSignal(
                    signal=SignalType.HOLD, strategy_name="ensemble",
                    reason=f"Single strategy BUY confidence too low ({buy_weight:.2f}<{single_strategy_min})",
                    metadata={**sig_meta, "buy_weight": buy_weight, "sell_weight": sell_weight},
                )
            if buy_count >= 2 and buy_weight < config.MIN_ENSEMBLE_CONFIDENCE:
                return ScalpSignal(
                    signal=SignalType.HOLD, strategy_name="ensemble",
                    reason=f"BUY confidence too low ({buy_weight:.2f}<{config.MIN_ENSEMBLE_CONFIDENCE})",
                    metadata={**sig_meta, "buy_weight": buy_weight, "sell_weight": sell_weight},
                )
            # 하락추세에서만 매수 차단 (neutral은 허용)
            if trend == "down":
                return ScalpSignal(
                    signal=SignalType.HOLD, strategy_name="ensemble",
                    reason=f"BUY blocked: downtrend: {reason_str}",
                    metadata={**sig_meta, "buy_weight": buy_weight, "sell_weight": sell_weight},
                )
            if getattr(config, 'TREND_POSITION_FILTER', False):
                if not self._price_above_trend_ema(df):
                    return ScalpSignal(
                        signal=SignalType.HOLD, strategy_name="ensemble",
                        reason=f"BUY blocked: price below EMA({config.TREND_EMA_PERIOD}): {reason_str}",
                        metadata={**sig_meta, "buy_weight": buy_weight, "sell_weight": sell_weight},
                    )
            return ScalpSignal(
                signal=SignalType.BUY,
                strategy_name="ensemble",
                confidence=min(1.0, buy_weight),
                reason=f"Ensemble BUY ({buy_count}/{len(self.strategies)}, trend={trend}): {reason_str}",
                metadata={**sig_meta, "buy_weight": buy_weight, "sell_weight": sell_weight,
                          "buy_count": buy_count},
            )

        # SELL 조건: 단일 전략 허용 + 상승추세에서만 매도 차단
        if sell_count >= config.MIN_AGREEMENT and sell_weight > buy_weight:
            if sell_count == 1 and sell_weight < single_strategy_min:
                return ScalpSignal(
                    signal=SignalType.HOLD, strategy_name="ensemble",
                    reason=f"Single strategy SELL confidence too low ({sell_weight:.2f}<{single_strategy_min})",
                    metadata={**sig_meta, "buy_weight": buy_weight, "sell_weight": sell_weight},
                )
            if sell_count >= 2 and sell_weight < config.MIN_ENSEMBLE_CONFIDENCE:
                return ScalpSignal(
                    signal=SignalType.HOLD, strategy_name="ensemble",
                    reason=f"SELL confidence too low ({sell_weight:.2f}<{config.MIN_ENSEMBLE_CONFIDENCE})",
                    metadata={**sig_meta, "buy_weight": buy_weight, "sell_weight": sell_weight},
                )
            if trend == "up":
                return ScalpSignal(
                    signal=SignalType.HOLD, strategy_name="ensemble",
                    reason=f"SELL blocked by uptrend filter: {reason_str}",
                    metadata={**sig_meta, "buy_weight": buy_weight, "sell_weight": sell_weight},
                )
            return ScalpSignal(
                signal=SignalType.SELL,
                strategy_name="ensemble",
                confidence=min(1.0, sell_weight),
                reason=f"Ensemble SELL ({sell_count}/{len(self.strategies)}, trend={trend}): {reason_str}",
                metadata={**sig_meta, "buy_weight": buy_weight, "sell_weight": sell_weight,
                          "sell_count": sell_count},
            )

        return ScalpSignal(
            signal=SignalType.HOLD,
            strategy_name="ensemble",
            confidence=0.0,
            reason=f"No consensus (buy={buy_count},sell={sell_count}): {reason_str}",
            metadata={**sig_meta, "buy_weight": buy_weight, "sell_weight": sell_weight},
        )

    def _price_above_trend_ema(self, df: pd.DataFrame) -> bool:
        """현재 가격이 장기 EMA 위인지 확인."""
        close = df["close"]
        if len(close) < config.TREND_EMA_PERIOD:
            return True  # 데이터 부족 시 통과
        ema = close.ewm(span=config.TREND_EMA_PERIOD, adjust=False).mean()
        return float(close.iloc[-1]) >= float(ema.iloc[-1])

    def _get_trend(self, df: pd.DataFrame) -> str:
        """EMA 기울기로 추세 판단: 'up', 'down', 'neutral'."""
        close = df["close"]
        if len(close) < config.TREND_EMA_PERIOD + config.TREND_LOOKBACK:
            return "neutral"

        ema = close.ewm(span=config.TREND_EMA_PERIOD, adjust=False).mean()
        current = ema.iloc[-1]
        past = ema.iloc[-1 - config.TREND_LOOKBACK]

        if pd.isna(current) or pd.isna(past):
            return "neutral"

        slope_pct = (current - past) / past
        if slope_pct > 0.0003:   # +0.03% 이상이면 상승
            return "up"
        elif slope_pct < -0.0003:  # -0.03% 이하면 하락
            return "down"
        return "neutral"

    def _check_volatility_regime(self, df: pd.DataFrame) -> bool:
        """변동성이 적정 범위인지 확인. True = 거래 가능."""
        if len(df) < config.VOL_ATR_LOOKBACK + 2:
            return True  # 데이터 부족 시 통과

        close = df["close"]
        high = df["high"]
        low = df["low"]

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)

        # 최근 ATR 분포에서 현재 ATR 위치 확인
        recent_tr = tr.iloc[-config.VOL_ATR_LOOKBACK:]
        current_tr = tr.iloc[-1]

        if pd.isna(current_tr) or recent_tr.isna().all():
            return True

        low_threshold = recent_tr.quantile(config.VOL_LOW_PERCENTILE)
        high_threshold = recent_tr.quantile(config.VOL_HIGH_PERCENTILE)

        return low_threshold <= current_tr <= high_threshold

    def _candle_confirmation(self, df: pd.DataFrame) -> str:
        """현재봉 + 직전봉 방향 확인: 'bullish', 'bearish', 'neutral'."""
        if len(df) < 2:
            return "neutral"
        # 현재봉이 양봉이면 bullish (진입 직전 가격 움직임 확인)
        cur_open = float(df["open"].iloc[-1])
        cur_close = float(df["close"].iloc[-1])
        if cur_close > cur_open:
            return "bullish"
        elif cur_close < cur_open:
            return "bearish"
        return "neutral"

    def record_trade(self, market: str, bar_index: int, contributing_strategies: list[str], won: bool):
        """Record a completed trade for cooldown and weight adjustment."""
        self.last_trade_bar[market] = bar_index

        alpha = config.WEIGHT_EMA_ALPHA
        for name in contributing_strategies:
            self.trade_counts[name] += 1
            if won:
                self.win_counts[name] += 1
            result = 1.0 if won else 0.0
            self.ema_win_rate[name] = alpha * result + (1 - alpha) * self.ema_win_rate.get(name, 0.5)

    def record_result(self, contributing_strategies: list[str], won: bool):
        """Record trade outcome for weight adjustment."""
        alpha = config.WEIGHT_EMA_ALPHA
        for name in contributing_strategies:
            self.trade_counts[name] += 1
            if won:
                self.win_counts[name] += 1
            # Update EMA win rate
            result = 1.0 if won else 0.0
            self.ema_win_rate[name] = alpha * result + (1 - alpha) * self.ema_win_rate.get(name, 0.5)

    def adjust_weights(self):
        """Auto-adjust weights based on EMA win rates."""
        total_wr = sum(self.ema_win_rate.values())
        if total_wr <= 0:
            return

        new_weights = {}
        for name, wr in self.ema_win_rate.items():
            new_weights[name] = wr / total_wr

        # Smoothing: blend 70% new + 30% default to prevent extreme swings
        for name in new_weights:
            default_w = config.DEFAULT_WEIGHTS.get(name, 0.25)
            new_weights[name] = 0.7 * new_weights[name] + 0.3 * default_w

        # Normalize
        total = sum(new_weights.values())
        for name in new_weights:
            new_weights[name] /= total

        old_weights = dict(self.weights)
        self.weights = new_weights
        logger.info(f"Weights adjusted: {old_weights} -> {self.weights}")

    def get_status(self) -> dict:
        return {
            "weights": dict(self.weights),
            "ema_win_rates": dict(self.ema_win_rate),
            "trade_counts": dict(self.trade_counts),
            "win_counts": dict(self.win_counts),
        }
