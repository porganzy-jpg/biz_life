"""
CryptoBot 비상 정지 시스템 (Circuit Breaker)

시장 급변이나 과도한 손실 발생 시 자동으로 매매를 중지합니다.
- 일간 손실 한도 초과 시 당일 매매 중지
- 연속 손실 시 매매 중지
- 급격한 가격 변동 시 매매 일시 정지
"""
import time
import logging
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """비상 정지 시스템"""

    def __init__(self, config: dict = None):
        default_config = {
            "daily_loss_limit_pct": -5.0,      # 일간 최대 손실 (-5%)
            "monthly_loss_limit_pct": -15.0,    # 월간 최대 손실 (-15%)
            "max_consecutive_losses": 5,        # 최대 연속 손실 횟수
            "price_crash_pct": -10.0,           # 급락 감지 (10분내 -10%)
            "cooldown_minutes": 30,             # 서킷브레이커 발동 후 쿨다운
        }
        self.config = {**default_config, **(config or {})}

        # 상태 추적
        self.is_active = False
        self.activation_time: Optional[datetime] = None
        self.activation_reason: str = ""
        self.daily_pnl_pct: float = 0.0
        self.monthly_pnl_pct: float = 0.0
        self.consecutive_losses: int = 0
        self.today: date = date.today()
        self.trade_log = []  # 당일 거래 기록

    def _reset_daily(self):
        """일간 카운터 리셋"""
        if date.today() != self.today:
            self.daily_pnl_pct = 0.0
            self.today = date.today()
            self.trade_log = []
            logger.info("서킷브레이커: 일간 카운터 리셋")

    def record_trade(self, pnl_pct: float):
        """거래 결과 기록"""
        self._reset_daily()

        self.daily_pnl_pct += pnl_pct
        self.monthly_pnl_pct += pnl_pct

        if pnl_pct < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        self.trade_log.append({
            "time": datetime.now().isoformat(),
            "pnl_pct": pnl_pct,
        })

        # 자동 체크
        self._check_limits()

    def _check_limits(self):
        """한도 체크 및 서킷브레이커 발동"""
        if self.daily_pnl_pct <= self.config["daily_loss_limit_pct"]:
            self.activate(f"일간 손실 한도 초과: {self.daily_pnl_pct:.2f}%")

        elif self.monthly_pnl_pct <= self.config["monthly_loss_limit_pct"]:
            self.activate(f"월간 손실 한도 초과: {self.monthly_pnl_pct:.2f}%")

        elif self.consecutive_losses >= self.config["max_consecutive_losses"]:
            self.activate(f"연속 {self.consecutive_losses}회 손실")

    def check_price_crash(self, symbol: str, current_price: float, price_10min_ago: float) -> bool:
        """급격한 가격 변동 감지"""
        if price_10min_ago <= 0:
            return False

        change_pct = (current_price - price_10min_ago) / price_10min_ago * 100
        if change_pct <= self.config["price_crash_pct"]:
            self.activate(f"{symbol} 급락 감지: {change_pct:.2f}% (10분)")
            return True
        return False

    def activate(self, reason: str):
        """서킷브레이커 발동"""
        self.is_active = True
        self.activation_time = datetime.now()
        self.activation_reason = reason
        logger.warning(f"[CIRCUIT BREAKER] 발동: {reason}")

    def deactivate(self):
        """서킷브레이커 해제"""
        self.is_active = False
        self.activation_time = None
        self.activation_reason = ""
        logger.info("[CIRCUIT BREAKER] 해제")

    def can_trade(self) -> tuple:
        """
        매매 가능 여부 확인

        Returns:
            (bool, str): (매매 가능 여부, 사유)
        """
        self._reset_daily()

        if not self.is_active:
            return True, "정상"

        # 쿨다운 시간 확인
        if self.activation_time:
            elapsed = (datetime.now() - self.activation_time).total_seconds() / 60
            remaining = self.config["cooldown_minutes"] - elapsed
            if elapsed >= self.config["cooldown_minutes"]:
                self.deactivate()
                return True, "쿨다운 완료, 매매 재개"
            else:
                return False, f"서킷브레이커 발동 중: {self.activation_reason} (잔여 {remaining:.0f}분)"

        return False, f"서킷브레이커 발동: {self.activation_reason}"

    def get_status(self) -> dict:
        """현재 상태 반환"""
        return {
            "is_active": self.is_active,
            "reason": self.activation_reason,
            "daily_pnl_pct": round(self.daily_pnl_pct, 2),
            "monthly_pnl_pct": round(self.monthly_pnl_pct, 2),
            "consecutive_losses": self.consecutive_losses,
            "trades_today": len(self.trade_log),
        }
