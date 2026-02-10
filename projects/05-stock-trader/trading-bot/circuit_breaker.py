"""
StockBot 서킷브레이커 - 비상 정지 시스템

일일 손실 한도, 연속 손실, 시장 급변 시 자동 매매 중단
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """서킷브레이커 (비상 정지)"""

    def __init__(self, config: dict = None):
        cfg = config or {}
        self.max_daily_loss_pct = cfg.get("max_daily_loss_pct", -3.0)
        self.max_consecutive_losses = cfg.get("max_consecutive_losses", 5)
        self.max_daily_trades = cfg.get("max_daily_trades", 20)
        self.cooldown_minutes = cfg.get("cooldown_minutes", 30)

        self._tripped = False
        self._trip_reason = ""
        self._trip_time: Optional[datetime] = None
        self._daily_trades = 0
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        self._last_reset_date = datetime.now().date()

    @property
    def is_tripped(self) -> bool:
        self._check_daily_reset()
        if self._tripped and self._trip_time:
            elapsed = (datetime.now() - self._trip_time).total_seconds() / 60
            if elapsed > self.cooldown_minutes:
                logger.info(f"서킷브레이커 쿨다운 종료 ({self.cooldown_minutes}분)")
                self._tripped = False
                self._trip_reason = ""
        return self._tripped

    @property
    def trip_reason(self) -> str:
        return self._trip_reason

    def _check_daily_reset(self):
        today = datetime.now().date()
        if today != self._last_reset_date:
            self._daily_trades = 0
            self._daily_pnl = 0.0
            self._last_reset_date = today
            if self._tripped and "일일" in self._trip_reason:
                self._tripped = False
                self._trip_reason = ""

    def record_trade(self, pnl_pct: float = 0):
        """거래 결과 기록"""
        self._check_daily_reset()
        self._daily_trades += 1
        self._daily_pnl += pnl_pct

        if pnl_pct < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        self._check_conditions()

    def _check_conditions(self):
        if self._daily_pnl <= self.max_daily_loss_pct:
            self._trip(f"일일 손실 한도 도달: {self._daily_pnl:.1f}%")

        if self._consecutive_losses >= self.max_consecutive_losses:
            self._trip(f"연속 손실 {self._consecutive_losses}회")

        if self._daily_trades >= self.max_daily_trades:
            self._trip(f"일일 거래 횟수 초과: {self._daily_trades}회")

    def _trip(self, reason: str):
        self._tripped = True
        self._trip_reason = reason
        self._trip_time = datetime.now()
        logger.warning(f"서킷브레이커 발동: {reason}")

    def force_trip(self, reason: str = "수동 발동"):
        self._trip(reason)

    def reset(self):
        self._tripped = False
        self._trip_reason = ""
        self._trip_time = None
        self._consecutive_losses = 0
        logger.info("서킷브레이커 수동 해제")

    def get_status(self) -> dict:
        return {
            "tripped": self.is_tripped,
            "reason": self._trip_reason,
            "daily_trades": self._daily_trades,
            "daily_pnl": round(self._daily_pnl, 2),
            "consecutive_losses": self._consecutive_losses,
            "cooldown_minutes": self.cooldown_minutes,
        }
