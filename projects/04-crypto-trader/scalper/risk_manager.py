"""
ATR-based Risk Manager.

Handles position sizing, stop-loss, take-profit, trailing stop,
and Kelly Criterion adaptive position sizing.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import config

logger = logging.getLogger("scalper.risk")


@dataclass
class KellyResult:
    kelly_risk_pct: float
    stats: dict


@dataclass
class RiskLevels:
    position_size_krw: float
    stop_loss_price: float
    take_profit_price: float
    stop_loss_pct: float
    take_profit_pct: float
    atr: float


class RiskManager:

    def __init__(self):
        self.trailing_highs: dict[str, float] = {}  # market -> highest price since entry
        self.trailing_active: dict[str, bool] = {}

    def calculate_atr(self, df: pd.DataFrame, period: int = None) -> float:
        """Calculate Average True Range."""
        period = period or config.ATR_PERIOD
        if df is None or len(df) < period + 1:
            return 0.0

        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]

        return float(atr) if not pd.isna(atr) else 0.0

    def calculate_kelly_risk(self, trade_history, window: int = None) -> KellyResult:
        """Calculate Kelly Criterion-based optimal risk percentage.

        Args:
            trade_history: list of TradeRecord objects (must have pnl_pct attribute)
            window: number of recent trades to consider

        Returns:
            KellyResult with kelly_risk_pct and stats dict
        """
        window = window or getattr(config, 'KELLY_WINDOW', 50)
        safety = getattr(config, 'KELLY_SAFETY_FACTOR', 0.5)
        min_risk = getattr(config, 'KELLY_MIN_RISK', 0.005)
        max_risk = getattr(config, 'KELLY_MAX_RISK', 0.04)

        default_stats = {
            "trades_used": 0,
            "win_rate": 0.0,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0,
            "raw_kelly": 0.0,
            "half_kelly": 0.0,
            "clamped_kelly": config.RISK_PER_TRADE,
            "sufficient_data": False,
        }

        # Need at least 10 trades for meaningful Kelly calculation
        if len(trade_history) < 10:
            logger.debug("Kelly: insufficient trade history (%d trades), using default risk",
                         len(trade_history))
            return KellyResult(
                kelly_risk_pct=config.RISK_PER_TRADE,
                stats=default_stats,
            )

        # Take the most recent `window` trades
        recent = trade_history[-window:]

        # Separate wins and losses (pnl_pct is in percentage, e.g. +1.5 means +1.5%)
        wins = [t for t in recent if t.pnl_pct > 0]
        losses = [t for t in recent if t.pnl_pct <= 0]

        total = len(recent)
        win_count = len(wins)
        loss_count = len(losses)

        if win_count == 0 or loss_count == 0:
            # Edge cases: all wins or all losses
            if win_count == 0:
                # All losses -> minimum risk
                kelly_clamped = min_risk
            else:
                # All wins -> use max risk
                kelly_clamped = max_risk

            stats = {
                "trades_used": total,
                "win_rate": round(win_count / total * 100, 1),
                "avg_win_pct": round(sum(t.pnl_pct for t in wins) / win_count, 2) if wins else 0.0,
                "avg_loss_pct": round(abs(sum(t.pnl_pct for t in losses) / loss_count), 2) if losses else 0.0,
                "raw_kelly": 0.0 if win_count == 0 else 1.0,
                "half_kelly": 0.0 if win_count == 0 else 0.5,
                "clamped_kelly": round(kelly_clamped, 4),
                "sufficient_data": True,
            }
            return KellyResult(kelly_risk_pct=kelly_clamped, stats=stats)

        # Core Kelly calculation
        p = win_count / total          # win probability
        q = 1 - p                      # loss probability
        avg_win = sum(t.pnl_pct for t in wins) / win_count     # average win % (positive)
        avg_loss = abs(sum(t.pnl_pct for t in losses) / loss_count)  # average loss % (positive)

        b = avg_win / avg_loss if avg_loss > 0 else 0.0  # win/loss ratio

        if b <= 0:
            raw_kelly = 0.0
        else:
            raw_kelly = (b * p - q) / b  # Kelly formula: f* = (b*p - q) / b

        # Apply safety factor (half-Kelly)
        half_kelly = raw_kelly * safety

        # Clamp between min and max risk
        kelly_clamped = max(min_risk, min(max_risk, half_kelly))

        stats = {
            "trades_used": total,
            "win_rate": round(p * 100, 1),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "raw_kelly": round(raw_kelly, 4),
            "half_kelly": round(half_kelly, 4),
            "clamped_kelly": round(kelly_clamped, 4),
            "sufficient_data": True,
        }

        logger.info(
            f"Kelly: p={p:.2f}, b={b:.2f}, raw={raw_kelly:.4f}, "
            f"half={half_kelly:.4f}, clamped={kelly_clamped:.4f} "
            f"(from {total} trades)"
        )

        return KellyResult(kelly_risk_pct=kelly_clamped, stats=stats)

    def calculate_risk_levels(self, df: pd.DataFrame, balance_krw: float,
                              side: str = "buy",
                              risk_override: float = None) -> Optional[RiskLevels]:
        """Calculate position size and risk levels for a new trade.

        Args:
            df: OHLCV DataFrame
            balance_krw: available balance in KRW
            side: "buy" or "sell"
            risk_override: if provided, use this instead of config.RISK_PER_TRADE
        """
        atr = self.calculate_atr(df)
        current_price = float(df["close"].iloc[-1])

        if atr <= 0 or current_price <= 0:
            return None

        # Stop-loss: ATR 기반, 최소 바닥 보장, 하드캡 제한
        # 핵심: min()이 아닌 max()로 최소 스탑 폭 보장 (노이즈 방어)
        atr_stop_distance = atr * config.ATR_STOP_MULTIPLIER
        min_stop_distance = current_price * config.STOP_LOSS_MIN_PCT
        stop_distance = max(atr_stop_distance, min_stop_distance)

        # 하드캡으로 상한 제한
        hard_cap_distance = current_price * config.STOP_LOSS_HARD_CAP
        stop_distance = min(stop_distance, hard_cap_distance)

        stop_loss_pct = stop_distance / current_price

        # Take-profit: ATR*2.0 or 1.0%, whichever is wider (min 0.3%)
        atr_tp_distance = atr * config.ATR_TP_MULTIPLIER
        pct_tp_distance = current_price * config.TAKE_PROFIT_PCT
        tp_distance = max(atr_tp_distance, pct_tp_distance)

        # Minimum 0.3%
        min_tp_distance = current_price * config.TAKE_PROFIT_MIN
        tp_distance = max(tp_distance, min_tp_distance)

        take_profit_pct = tp_distance / current_price

        if side == "buy":
            stop_loss_price = current_price - stop_distance
            take_profit_price = current_price + tp_distance
        else:
            stop_loss_price = current_price + stop_distance
            take_profit_price = current_price - tp_distance

        # Position sizing: risk per trade / stop distance
        risk_pct = risk_override if risk_override is not None else config.RISK_PER_TRADE
        risk_amount_krw = balance_krw * risk_pct
        position_size_krw = risk_amount_krw / stop_loss_pct if stop_loss_pct > 0 else 0

        # Cap at available balance (leave buffer for commission)
        max_position = balance_krw * 0.95
        position_size_krw = min(position_size_krw, max_position)

        return RiskLevels(
            position_size_krw=position_size_krw,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            atr=atr,
        )

    def check_exit(self, market: str, entry_price: float, current_price: float,
                   risk_levels: RiskLevels, bars_held: int = 0) -> Optional[str]:
        """
        Check if position should be exited.

        Returns:
            "stop_loss", "take_profit", "trailing_stop", "breakeven_stop", or None
        """
        pnl_pct = (current_price - entry_price) / entry_price

        # 손익분기 스탑: 충분한 시간 후에도 수익이 없으면 손절 축소
        # 조건: N분 경과 + 진입가 아래 + 트레일링 미활성
        if bars_held >= config.BREAKEVEN_AFTER_BARS:
            if pnl_pct < 0 and not self.trailing_active.get(market, False):
                self._reset_trailing(market)
                return "breakeven_stop"

        # Stop-loss
        if current_price <= risk_levels.stop_loss_price:
            self._reset_trailing(market)
            return "stop_loss"

        # Take-profit
        if current_price >= risk_levels.take_profit_price:
            self._reset_trailing(market)
            return "take_profit"

        # Trailing stop logic
        if pnl_pct >= config.TRAILING_ACTIVATE_PCT:
            if not self.trailing_active.get(market, False):
                self.trailing_active[market] = True
                self.trailing_highs[market] = current_price
                logger.info(f"[{market}] Trailing stop activated at +{pnl_pct*100:.2f}%")

        if self.trailing_active.get(market, False):
            # Update high watermark
            if current_price > self.trailing_highs.get(market, 0):
                self.trailing_highs[market] = current_price

            highest = self.trailing_highs[market]
            trailing_stop_price = highest * (1 - config.TRAILING_STOP_PCT)

            if current_price <= trailing_stop_price:
                pnl_from_high = (current_price - highest) / highest
                logger.info(f"[{market}] Trailing stop hit: high={highest:,.0f}, "
                            f"stop={trailing_stop_price:,.0f}, now={current_price:,.0f}")
                self._reset_trailing(market)
                return "trailing_stop"

        return None

    def _reset_trailing(self, market: str):
        self.trailing_active.pop(market, None)
        self.trailing_highs.pop(market, None)

    def validate_trade(self, position_size_krw: float, balance_krw: float) -> bool:
        """Sanity check before placing trade."""
        if position_size_krw <= 5000:  # 업비트 최소주문 5000원
            logger.warning(f"Position too small: {position_size_krw:,.0f} KRW")
            return False
        if position_size_krw > balance_krw * 0.95:
            logger.warning(f"Position exceeds balance: {position_size_krw:,.0f} > {balance_krw * 0.95:,.0f}")
            return False
        return True
