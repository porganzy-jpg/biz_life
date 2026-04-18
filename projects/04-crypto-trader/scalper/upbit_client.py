"""
Upbit client wrapper with paper trading support.

v5.0 changes:
  - API 호출 타임아웃 (5초) + 지수 백오프 재시도 (최대 3회)
  - Rate limit 모니터링 (초당 호출 수 추적)
  - 실전 주문 후 체결 확인 (잔고 기반 검증)
  - 에러 카운터 (연속 실패 추적)
"""
import logging
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

try:
    import pyupbit
    # pyupbit 내부 requests에 기본 타임아웃 설정
    import requests
    _original_get = requests.Session.get
    _original_post = requests.Session.post

    def _timeout_get(self, *args, **kwargs):
        kwargs.setdefault('timeout', 5)
        return _original_get(self, *args, **kwargs)

    def _timeout_post(self, *args, **kwargs):
        kwargs.setdefault('timeout', 5)
        return _original_post(self, *args, **kwargs)

    requests.Session.get = _timeout_get
    requests.Session.post = _timeout_post
except ImportError:
    pyupbit = None

from . import config

logger = logging.getLogger("scalper.client")

# API 호출 재시도 설정
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # 초 (지수 백오프: 1, 2, 4초)


@dataclass
class PaperPosition:
    market: str
    amount: float
    avg_price: float
    entry_time: float = 0.0


@dataclass
class PaperAccount:
    krw: float = 1_000_000.0
    positions: dict = field(default_factory=dict)  # market -> PaperPosition


class UpbitClient:
    """Thin wrapper around pyupbit with paper-trading fallback."""

    def __init__(self, paper: bool = True):
        self.paper = paper
        self.upbit = None

        if not paper:
            if pyupbit is None:
                raise ImportError("pyupbit is not installed. Run: pip install pyupbit")
            if not config.UPBIT_ACCESS_KEY or not config.UPBIT_SECRET_KEY:
                raise ValueError("UPBIT_ACCESS_KEY / UPBIT_SECRET_KEY not set in .env")
            self.upbit = pyupbit.Upbit(config.UPBIT_ACCESS_KEY, config.UPBIT_SECRET_KEY)
            logger.warning("=== LIVE TRADING MODE ===")
        else:
            logger.info("Paper trading mode enabled")

        self.paper_account = PaperAccount(krw=config.PAPER_INITIAL_KRW)

        # v5.0: Rate limit 모니터링
        self._api_call_times = deque(maxlen=600)  # 최근 600건 (10분)
        self._consecutive_errors = 0
        self._total_errors_today = 0
        self._last_error_reset = time.time()

    def _track_api_call(self):
        """API 호출 기록 (rate limit 모니터링)."""
        now = time.time()
        self._api_call_times.append(now)
        # 1분 내 호출 수 체크
        one_min_ago = now - 60
        recent = sum(1 for t in self._api_call_times if t > one_min_ago)
        if recent > 500:  # 600 한도의 83%
            logger.warning(f"API rate limit 경고: {recent}/분 (한도 600/분)")

    def _retry_api(self, func, *args, category="api", **kwargs):
        """API 호출 + 재시도 (지수 백오프)."""
        for attempt in range(MAX_RETRIES):
            try:
                self._track_api_call()
                result = func(*args, **kwargs)
                self._consecutive_errors = 0
                return result
            except Exception as e:
                self._consecutive_errors += 1
                self._total_errors_today += 1
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"API 재시도 {attempt+1}/{MAX_RETRIES}: {e} (대기 {delay:.1f}초)")
                    time.sleep(delay)
                else:
                    logger.error(f"API 최종 실패 ({MAX_RETRIES}회): {e}")
                    return None
        return None

    @property
    def api_calls_per_minute(self) -> int:
        """최근 1분간 API 호출 수."""
        now = time.time()
        return sum(1 for t in self._api_call_times if t > now - 60)

    @property
    def is_rate_limited(self) -> bool:
        """Rate limit에 근접했는지."""
        return self.api_calls_per_minute > 500

    # ── Market data (always real) ──

    def get_ohlcv(self, market: str, interval: str = "minute1", count: int = 60) -> Optional[pd.DataFrame]:
        """Fetch OHLCV candles from Upbit (with retry)."""
        if pyupbit is None:
            return self._fake_ohlcv(market, count)

        if self.is_rate_limited:
            time.sleep(0.5)  # Rate limit 보호

        def _fetch():
            df = pyupbit.get_ohlcv(market, interval=interval, count=count)
            if df is None or df.empty:
                return None
            df = df.reset_index()
            if "value" in df.columns:
                df = df.drop(columns=["value"])
            df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
            return df

        return self._retry_api(_fetch, category="ohlcv")

    def get_current_price(self, market: str) -> Optional[float]:
        """Get current price (with retry)."""
        if pyupbit is None:
            return None
        return self._retry_api(pyupbit.get_current_price, market, category="price")

    def get_orderbook(self, market: str) -> Optional[dict]:
        """Get order book for slippage estimation (with retry)."""
        if pyupbit is None:
            return None

        def _fetch():
            books = pyupbit.get_orderbook(market)
            if books and len(books) > 0:
                return books[0] if isinstance(books, list) else books
            return None

        return self._retry_api(_fetch, category="orderbook")

    # ── Trading ──

    def buy_market(self, market: str, krw_amount: float) -> Optional[dict]:
        """Market buy order (with confirmation for live)."""
        if self.paper:
            return self._paper_buy(market, krw_amount)

        result = self._retry_api(
            self.upbit.buy_market_order, market, krw_amount, category="order"
        )
        if result is None:
            return None

        # v5.0: 체결 확인 (잔고 변동)
        uuid = result.get("uuid")
        if uuid:
            confirmed = self._confirm_order(uuid, max_wait=10)
            result["confirmed"] = confirmed
            if not confirmed:
                logger.warning(f"BUY 체결 미확인 {market}: uuid={uuid}")

        logger.info(f"LIVE BUY {market}: {krw_amount:,.0f} KRW -> confirmed={result.get('confirmed', '?')}")
        return result

    def sell_market(self, market: str, amount: float) -> Optional[dict]:
        """Market sell order (with confirmation for live)."""
        if self.paper:
            return self._paper_sell(market, amount)

        result = self._retry_api(
            self.upbit.sell_market_order, market, amount, category="order"
        )
        if result is None:
            return None

        uuid = result.get("uuid")
        if uuid:
            confirmed = self._confirm_order(uuid, max_wait=10)
            result["confirmed"] = confirmed
            if not confirmed:
                logger.warning(f"SELL 체결 미확인 {market}: uuid={uuid}")

        logger.info(f"LIVE SELL {market}: {amount} -> confirmed={result.get('confirmed', '?')}")
        return result

    def _confirm_order(self, uuid: str, max_wait: int = 10) -> bool:
        """주문 체결 확인 (Upbit order API polling)."""
        if not self.upbit:
            return False

        for i in range(max_wait):
            try:
                order = self.upbit.get_order(uuid)
                if order and order.get("state") == "done":
                    return True
                elif order and order.get("state") == "cancel":
                    logger.error(f"주문 취소됨: {uuid}")
                    return False
            except Exception:
                pass
            time.sleep(1)

        return False

    # ── Balance ──

    def get_krw_balance(self) -> float:
        if self.paper:
            return self.paper_account.krw
        try:
            balances = self.upbit.get_balances()
            for b in balances:
                if b["currency"] == "KRW":
                    return float(b["balance"])
            return 0.0
        except Exception:
            return 0.0

    def get_position(self, market: str) -> Optional[dict]:
        """Get position info: {amount, avg_price, current_price}."""
        ticker = market.split("-")[1]

        if self.paper:
            pos = self.paper_account.positions.get(market)
            if pos and pos.amount > 0:
                price = self.get_current_price(market)
                return {
                    "market": market,
                    "amount": pos.amount,
                    "avg_price": pos.avg_price,
                    "current_price": price or pos.avg_price,
                    "entry_time": pos.entry_time,
                }
            return None

        try:
            balances = self.upbit.get_balances()
            for b in balances:
                if b["currency"] == ticker:
                    amt = float(b["balance"])
                    if amt > 0:
                        price = self.get_current_price(market)
                        return {
                            "market": market,
                            "amount": amt,
                            "avg_price": float(b["avg_buy_price"]),
                            "current_price": price or 0,
                            "entry_time": 0,
                        }
            return None
        except Exception:
            return None

    def get_all_positions(self) -> list[dict]:
        positions = []
        for market in config.MARKETS:
            pos = self.get_position(market)
            if pos:
                positions.append(pos)
        return positions

    # ── Paper trading internals ──

    def _paper_buy(self, market: str, krw_amount: float) -> Optional[dict]:
        price = self.get_current_price(market)
        if price is None:
            # Fallback: use last candle close
            df = self.get_ohlcv(market, count=2)
            if df is not None and len(df) > 0:
                price = float(df["close"].iloc[-1])
            else:
                logger.error(f"Paper buy failed: no price for {market}")
                return None

        commission = krw_amount * config.COMMISSION_RATE
        net_krw = krw_amount - commission

        if self.paper_account.krw < krw_amount:
            logger.warning(f"Paper buy: insufficient KRW ({self.paper_account.krw:,.0f} < {krw_amount:,.0f})")
            return None

        amount = net_krw / price
        self.paper_account.krw -= krw_amount

        existing = self.paper_account.positions.get(market)
        if existing and existing.amount > 0:
            total_cost = existing.avg_price * existing.amount + price * amount
            total_amount = existing.amount + amount
            existing.avg_price = total_cost / total_amount
            existing.amount = total_amount
        else:
            self.paper_account.positions[market] = PaperPosition(
                market=market, amount=amount, avg_price=price, entry_time=time.time()
            )

        logger.info(f"[PAPER] BUY {market}: {krw_amount:,.0f} KRW @ {price:,.0f} = {amount:.8f}")
        return {"market": market, "side": "bid", "price": price, "amount": amount, "paper": True}

    def _paper_sell(self, market: str, amount: float) -> Optional[dict]:
        pos = self.paper_account.positions.get(market)
        if not pos or pos.amount < amount:
            logger.warning(f"Paper sell: no position for {market}")
            return None

        price = self.get_current_price(market)
        if price is None:
            df = self.get_ohlcv(market, count=2)
            if df is not None and len(df) > 0:
                price = float(df["close"].iloc[-1])
            else:
                return None

        gross_krw = amount * price
        commission = gross_krw * config.COMMISSION_RATE
        net_krw = gross_krw - commission

        pos.amount -= amount
        self.paper_account.krw += net_krw

        if pos.amount < 1e-12:
            del self.paper_account.positions[market]

        logger.info(f"[PAPER] SELL {market}: {amount:.8f} @ {price:,.0f} = {net_krw:,.0f} KRW")
        return {"market": market, "side": "ask", "price": price, "amount": amount, "paper": True}

    def _fake_ohlcv(self, market: str, count: int) -> pd.DataFrame:
        """Generate minimal fake data when pyupbit is not installed (for testing)."""
        import numpy as np

        base = {"KRW-BTC": 130_000_000, "KRW-ETH": 5_000_000, "KRW-XRP": 3_200,
                "KRW-SOL": 280_000, "KRW-DOGE": 530}.get(market, 100_000)
        noise = np.random.randn(count) * base * 0.002
        closes = base + np.cumsum(noise)
        highs = closes + abs(noise) * 0.5
        lows = closes - abs(noise) * 0.5
        opens = closes + np.random.randn(count) * base * 0.001
        volumes = np.random.uniform(0.5, 5.0, count) * (base / 100_000)

        now = time.time()
        timestamps = pd.to_datetime([now - (count - i) * 60 for i in range(count)], unit="s")

        return pd.DataFrame({
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        })
