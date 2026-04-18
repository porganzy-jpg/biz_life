"""
에러 추적기 v1.0 — Silent Failure 방지

기존 57개 try-except 블록이 모두 에러를 삼키고 continue하는 문제 해결.
에러를 카테고리별로 집계하고, 연속 실패 시 알림을 보낸다.

사용법:
    tracker = ErrorTracker(alert_system)
    tracker.record("api_price", symbol="005930", error=e)
    if tracker.is_critical():
        # 매매 중단 등 조치
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ErrorTracker:
    """에러 집계 및 연속 실패 감지"""

    # 에러 카테고리별 임계값 (연속 N회 이상 → 크리티컬)
    THRESHOLDS = {
        "api_price": 5,       # 가격 조회 연속 5회 실패 → 데이터 불능
        "api_order": 2,       # 주문 연속 2회 실패 → 즉시 알림
        "api_balance": 3,     # 잔고 조회 연속 3회 → 포지션 파악 불가
        "api_ohlcv": 5,       # OHLCV 연속 5회 실패
        "strategy": 3,        # 전략 분석 연속 3회 실패
        "execution": 2,       # 실행 엔진 연속 2회 실패
        "db": 2,              # DB 연속 2회 실패 → 기록 유실
        "general": 10,        # 기타 연속 10회
    }

    def __init__(self, alert_callback: Optional[Callable] = None):
        """
        Args:
            alert_callback: 크리티컬 에러 시 호출할 함수
                            (message: str) -> None
        """
        self._alert_callback = alert_callback
        self._consecutive = defaultdict(int)      # {category: 연속 실패 횟수}
        self._daily_counts = defaultdict(int)      # {category: 오늘 총 실패 횟수}
        self._last_error = {}                      # {category: {"time": dt, "msg": str, "symbol": str}}
        self._last_reset_date = datetime.now().date()
        self._critical_notified = set()            # 이미 알림 보낸 카테고리 (중복 방지)
        self._total_errors_today = 0

    def record(self, category: str, symbol: str = "", error: Exception = None,
               message: str = ""):
        """
        에러 발생 기록.

        Args:
            category: 에러 카테고리 (api_price, api_order, execution 등)
            symbol: 관련 종목 코드
            error: 발생한 예외
            message: 추가 메시지
        """
        self._check_daily_reset()

        self._consecutive[category] += 1
        self._daily_counts[category] += 1
        self._total_errors_today += 1

        error_msg = str(error) if error else message
        self._last_error[category] = {
            "time": datetime.now(),
            "msg": error_msg[:200],
            "symbol": symbol,
            "count": self._consecutive[category],
        }

        threshold = self.THRESHOLDS.get(category, 10)
        if self._consecutive[category] >= threshold:
            self._notify_critical(category, symbol, error_msg)

        # 일일 총 에러 50회 이상이면 시스템 전체 경고
        if self._total_errors_today == 50:
            self._notify_critical(
                "system_overload", "",
                f"일일 총 에러 {self._total_errors_today}회 — 시스템 점검 필요"
            )

    def record_success(self, category: str):
        """성공 시 연속 실패 카운터 리셋."""
        self._consecutive[category] = 0
        self._critical_notified.discard(category)

    def is_critical(self, category: str = None) -> bool:
        """크리티컬 상태인지 확인."""
        if category:
            threshold = self.THRESHOLDS.get(category, 10)
            return self._consecutive.get(category, 0) >= threshold

        # 어떤 카테고리든 크리티컬이면 True
        for cat, count in self._consecutive.items():
            threshold = self.THRESHOLDS.get(cat, 10)
            if count >= threshold:
                return True
        return False

    def should_halt_trading(self) -> bool:
        """매매를 중단해야 하는 수준인지 판단."""
        # 주문 실패 연속 2회 이상
        if self._consecutive.get("api_order", 0) >= 2:
            return True
        # 잔고 조회 연속 3회 이상
        if self._consecutive.get("api_balance", 0) >= 3:
            return True
        # 가격 조회 모든 종목 실패 (연속 17회 = 워치리스트 전체)
        if self._consecutive.get("api_price", 0) >= 17:
            return True
        return False

    def _notify_critical(self, category: str, symbol: str, error_msg: str):
        """크리티컬 에러 알림 (카테고리당 1시간 1회 제한)."""
        now = datetime.now()

        # 같은 카테고리 알림 1시간 내 중복 방지
        notify_key = f"{category}_{now.strftime('%Y%m%d%H')}"
        if notify_key in self._critical_notified:
            return
        self._critical_notified.add(notify_key)

        msg = (
            f"[에러 경고] {category}\n"
            f"연속 실패: {self._consecutive.get(category, 0)}회\n"
            f"종목: {symbol or 'N/A'}\n"
            f"내용: {error_msg[:150]}\n"
            f"시간: {now.strftime('%H:%M:%S')}"
        )
        logger.critical(msg)

        if self._alert_callback:
            try:
                self._alert_callback(msg)
            except Exception:
                pass  # 알림 실패는 무시 (무한 루프 방지)

    def _check_daily_reset(self):
        """일일 카운터 리셋."""
        today = datetime.now().date()
        if today != self._last_reset_date:
            self._daily_counts.clear()
            self._total_errors_today = 0
            self._critical_notified.clear()
            self._last_reset_date = today

    def get_status(self) -> dict:
        """현재 에러 상태 요약."""
        self._check_daily_reset()
        return {
            "is_critical": self.is_critical(),
            "should_halt": self.should_halt_trading(),
            "total_errors_today": self._total_errors_today,
            "consecutive": dict(self._consecutive),
            "daily_counts": dict(self._daily_counts),
            "last_errors": {
                cat: {
                    "time": info["time"].strftime("%H:%M:%S"),
                    "msg": info["msg"][:80],
                    "symbol": info["symbol"],
                    "consecutive": info["count"],
                }
                for cat, info in self._last_error.items()
            },
        }
