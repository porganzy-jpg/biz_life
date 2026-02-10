"""
StockBot 스케줄러 - 장 시간 기반 자동 실행

한국 주식시장 시간 (09:00 ~ 15:30) 기반 자동화
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# 한국 주식시장 시간
MARKET_OPEN = (9, 0)    # 09:00
MARKET_CLOSE = (15, 30)  # 15:30
PRE_MARKET = (8, 30)     # 사전 분석 08:30
POST_MARKET = (16, 0)    # 사후 리포트 16:00


def is_market_hours() -> bool:
    """현재 장 시간인지 확인"""
    now = datetime.now()
    if now.weekday() >= 5:  # 주말
        return False
    current = (now.hour, now.minute)
    return MARKET_OPEN <= current <= MARKET_CLOSE


def is_trading_day() -> bool:
    """오늘이 거래일인지 확인 (주말 제외, 공휴일은 별도 관리 필요)"""
    return datetime.now().weekday() < 5


def time_until_market_open() -> Optional[timedelta]:
    """장 시작까지 남은 시간"""
    now = datetime.now()
    if now.weekday() >= 5:
        days_until_monday = 7 - now.weekday()
        market_open = now.replace(hour=MARKET_OPEN[0], minute=MARKET_OPEN[1],
                                  second=0, microsecond=0) + timedelta(days=days_until_monday)
        return market_open - now

    market_open = now.replace(hour=MARKET_OPEN[0], minute=MARKET_OPEN[1],
                              second=0, microsecond=0)
    if now < market_open:
        return market_open - now
    return None  # 이미 장 시간 또는 장 마감 후


class TradingScheduler:
    """매매 스케줄러"""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._on_pre_market: Optional[Callable] = None
        self._on_market_open: Optional[Callable] = None
        self._on_trade_cycle: Optional[Callable] = None
        self._on_market_close: Optional[Callable] = None
        self._on_post_market: Optional[Callable] = None

        self.trade_interval_seconds = 300  # 5분
        self._last_states = {}

    def set_callbacks(self, pre_market=None, market_open=None,
                      trade_cycle=None, market_close=None, post_market=None):
        self._on_pre_market = pre_market
        self._on_market_open = market_open
        self._on_trade_cycle = trade_cycle
        self._on_market_close = market_close
        self._on_post_market = post_market

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("스케줄러 시작")

    def stop(self):
        self._running = False
        logger.info("스케줄러 중지")

    @property
    def is_running(self) -> bool:
        return self._running

    def _run_loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"스케줄러 오류: {e}")
            time.sleep(30)  # 30초마다 체크

    def _tick(self):
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current = (now.hour, now.minute)

        if not is_trading_day():
            return

        # 사전 분석 (08:30)
        if current == PRE_MARKET and self._state_check(today, "pre_market"):
            logger.info("사전 분석 시작")
            self._safe_call(self._on_pre_market)

        # 장 시작 (09:00)
        if current == MARKET_OPEN and self._state_check(today, "market_open"):
            logger.info("장 시작 - 매매 시작")
            self._safe_call(self._on_market_open)

        # 매매 사이클 (장중)
        if is_market_hours():
            last_cycle = self._last_states.get("last_cycle_time")
            if last_cycle is None or (now - last_cycle).total_seconds() >= self.trade_interval_seconds:
                self._last_states["last_cycle_time"] = now
                self._safe_call(self._on_trade_cycle)

        # 장 마감 (15:30)
        if current == MARKET_CLOSE and self._state_check(today, "market_close"):
            logger.info("장 마감 - 매매 종료")
            self._safe_call(self._on_market_close)

        # 사후 리포트 (16:00)
        if current == POST_MARKET and self._state_check(today, "post_market"):
            logger.info("일일 리포트 생성")
            self._safe_call(self._on_post_market)

    def _state_check(self, date: str, event: str) -> bool:
        key = f"{date}_{event}"
        if key in self._last_states:
            return False
        self._last_states[key] = True
        return True

    def _safe_call(self, callback: Optional[Callable]):
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error(f"콜백 실행 오류: {e}")

    def get_status(self) -> dict:
        remaining = time_until_market_open()
        return {
            "running": self._running,
            "is_market_hours": is_market_hours(),
            "is_trading_day": is_trading_day(),
            "trade_interval": self.trade_interval_seconds,
            "time_until_open": str(remaining) if remaining else "장중" if is_market_hours() else "장마감",
        }
