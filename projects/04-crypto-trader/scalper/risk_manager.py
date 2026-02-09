"""
ATR-based Risk Manager.

Handles position sizing, stop-loss, take-profit, and trailing stop.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import config

logger = logging.getLogger("scalper.risk")


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

    def calculate_risk_levels(self, df: pd.DataFrame, balance_krw: float, side: str = "buy") -> Optional[RiskLevels]:
        """Calculate position size and risk levels for a new trade."""
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
        risk_amount_krw = balance_krw * config.RISK_PER_TRADE
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
