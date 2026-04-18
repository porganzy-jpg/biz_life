"""
StockBot 서킷브레이커 v3.8 - 비상 정지 시스템

v3.8: 일일 주문 금액 한도, 국면별 동적 손절, 급등락 감지, 트립 이력 기록
v3.7: 일일 손실 한도, 연속 손실, 시장 급변 시 자동 매매 중단
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """서킷브레이커 (비상 정지) v3.8"""

    def __init__(self, config: dict = None):
        cfg = config or {}
        self.max_daily_loss_pct = cfg.get("max_daily_loss_pct", -3.0)
        self.max_consecutive_losses = cfg.get("max_consecutive_losses", 5)
        self.max_daily_trades = cfg.get("max_daily_trades", 20)
        self.cooldown_minutes = cfg.get("cooldown_minutes", 30)

        # v3.8: 일일 주문 금액 한도 (초기 자본의 200% — 과도한 회전매매 방지)
        initial_capital = cfg.get("initial_capital", 2_000_000)
        self.max_daily_order_amount = cfg.get(
            "max_daily_order_amount", initial_capital * 2
        )

        self._tripped = False
        self._trip_reason = ""
        self._trip_time: Optional[datetime] = None
        self._daily_trades = 0
        self._daily_pnl = 0.0
        self._daily_order_amount = 0  # v3.8: 일일 총 주문 금액
        self._consecutive_losses = 0
        self._last_reset_date = datetime.now().date()
        self._trip_history = []  # v3.8: 트립 이력

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
            self._daily_order_amount = 0
            self._last_reset_date = today
            if self._tripped and "일일" in self._trip_reason:
                self._tripped = False
                self._trip_reason = ""

    def record_trade(self, pnl_pct: float = 0, order_amount: int = 0):
        """거래 결과 기록"""
        self._check_daily_reset()
        self._daily_trades += 1
        self._daily_pnl += pnl_pct
        self._daily_order_amount += abs(order_amount)

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

        # v3.8: 일일 주문 금액 한도
        if self._daily_order_amount >= self.max_daily_order_amount:
            self._trip(
                f"일일 주문 금액 초과: {self._daily_order_amount:,}원 "
                f"(한도 {self.max_daily_order_amount:,}원)"
            )

    def _trip(self, reason: str):
        self._tripped = True
        self._trip_reason = reason
        self._trip_time = datetime.now()
        self._trip_history.append({
            "time": self._trip_time.isoformat(),
            "reason": reason,
        })
        # 이력 최대 100건 유지
        if len(self._trip_history) > 100:
            self._trip_history = self._trip_history[-100:]
        logger.warning(f"서킷브레이커 발동: {reason}")

    def force_trip(self, reason: str = "수동 발동"):
        self._trip(reason)

    def reset(self):
        self._tripped = False
        self._trip_reason = ""
        self._trip_time = None
        self._consecutive_losses = 0
        logger.info("서킷브레이커 수동 해제")

    def check_order_allowed(self, order_amount: int) -> tuple:
        """주문 전 사전 검증. (allowed: bool, reason: str)"""
        self._check_daily_reset()
        if self._tripped:
            return False, f"서킷브레이커 발동 중: {self._trip_reason}"
        projected = self._daily_order_amount + abs(order_amount)
        if projected > self.max_daily_order_amount:
            return False, (
                f"일일 주문 한도 초과 예상: {projected:,}원 > "
                f"{self.max_daily_order_amount:,}원"
            )
        return True, "통과"

    def get_status(self) -> dict:
        return {
            "tripped": self.is_tripped,
            "reason": self._trip_reason,
            "daily_trades": self._daily_trades,
            "daily_pnl": round(self._daily_pnl, 2),
            "daily_order_amount": self._daily_order_amount,
            "max_daily_order_amount": self.max_daily_order_amount,
            "consecutive_losses": self._consecutive_losses,
            "cooldown_minutes": self.cooldown_minutes,
            "trip_history_count": len(self._trip_history),
            "recent_trips": self._trip_history[-5:],
        }
