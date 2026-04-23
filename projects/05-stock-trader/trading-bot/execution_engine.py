"""
스마트 주문 실행 엔진 (Smart Order Execution Engine)

TWAP, VWAP, Smart Execute 알고리즘과 슬리피지 제어,
부모/자식 주문 추적, 실행 분석을 제공한다.

실제 자금 안전을 위한 다층 방어:
  1. 슬리피지 상한 가드 (기본 50bp)
  2. 대량 주문 자동 분할 (일평균 5% 초과 시)
  3. 타임아웃 자동 취소 + 지수 백오프 재시도
  4. 부분 체결 추적 및 잔여 수량 관리
"""
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from volume_profile import VolumeProfile, current_bucket_index, NUM_BUCKETS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & Data classes
# ---------------------------------------------------------------------------

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    TWAP = "TWAP"
    VWAP = "VWAP"
    SMART = "SMART"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class ChildOrder:
    """자식 주문 (개별 슬라이스)."""
    child_id: str
    parent_id: str
    symbol: str
    side: str
    qty: int
    price: int  # 지정가 (0 = 시장가)
    status: str = OrderStatus.PENDING.value
    filled_qty: int = 0
    filled_price: float = 0.0
    created_at: str = ""
    filled_at: str = ""
    retry_count: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParentOrder:
    """부모 주문 (전체 주문)."""
    order_id: str
    symbol: str
    side: str
    total_qty: int
    order_type: str  # TWAP, VWAP, SMART, MARKET
    urgency: str = "normal"  # low, normal, high
    status: str = OrderStatus.PENDING.value
    filled_qty: int = 0
    avg_filled_price: float = 0.0
    target_price: float = 0.0  # 주문 시점 기준가
    slippage_bps: float = 0.0
    max_slippage_bps: float = 50.0
    children: List[ChildOrder] = field(default_factory=list)
    created_at: str = ""
    completed_at: str = ""
    duration_min: float = 0.0
    error: str = ""

    @property
    def remaining_qty(self) -> int:
        return self.total_qty - self.filled_qty

    @property
    def fill_rate(self) -> float:
        if self.total_qty <= 0:
            return 0.0
        return self.filled_qty / self.total_qty

    def to_dict(self) -> dict:
        d = asdict(self)
        d["remaining_qty"] = self.remaining_qty
        d["fill_rate"] = round(self.fill_rate, 4)
        return d


# ---------------------------------------------------------------------------
# Execution Engine
# ---------------------------------------------------------------------------

class ExecutionEngine:
    """
    스마트 주문 실행 엔진.

    BrokerClient를 통해 실제 주문을 제출하며,
    TWAP/VWAP/Smart 알고리즘으로 대량 주문을 분할 실행한다.
    """

    def __init__(self, broker_client, db_path: Optional[str] = None):
        """
        Args:
            broker_client: BrokerClient 인스턴스
            db_path: 실행 기록 DB 경로 (None이면 기본 stockbot.db)
        """
        self.broker = broker_client
        self.volume_profile = VolumeProfile(lookback_days=20)

        # 주문 추적
        self._orders: Dict[str, ParentOrder] = {}
        self._lock = threading.Lock()
        self._running_tasks: Dict[str, threading.Thread] = {}

        # 설정
        self.default_max_slippage_bps = 50.0
        self.max_retry = 3
        self.retry_base_delay = 2.0  # 초
        self.child_timeout_sec = 60.0

        # 일일 통계
        self._daily_stats = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_orders": 0,
            "filled_orders": 0,
            "failed_orders": 0,
            "total_slippage_bps": 0.0,
            "total_volume": 0,
            "avg_fill_rate": 0.0,
        }

        # DB 초기화
        import os
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "..", "stockbot.db")
        self._db_path = db_path
        self._init_execution_tables()

        logger.info("ExecutionEngine 초기화 완료")

    # ------------------------------------------------------------------
    # DB 초기화
    # ------------------------------------------------------------------

    def _init_execution_tables(self):
        """실행 엔진 전용 DB 테이블 생성."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS execution_orders (
                    order_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    total_qty INTEGER NOT NULL,
                    filled_qty INTEGER DEFAULT 0,
                    order_type TEXT NOT NULL,
                    urgency TEXT DEFAULT 'normal',
                    status TEXT DEFAULT 'PENDING',
                    avg_filled_price REAL DEFAULT 0,
                    target_price REAL DEFAULT 0,
                    slippage_bps REAL DEFAULT 0,
                    max_slippage_bps REAL DEFAULT 50,
                    duration_min REAL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS execution_children (
                    child_id TEXT PRIMARY KEY,
                    parent_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    qty INTEGER NOT NULL,
                    price INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'PENDING',
                    filled_qty INTEGER DEFAULT 0,
                    filled_price REAL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    filled_at TEXT,
                    retry_count INTEGER DEFAULT 0,
                    error TEXT DEFAULT '',
                    FOREIGN KEY (parent_id) REFERENCES execution_orders(order_id)
                );

                CREATE TABLE IF NOT EXISTS execution_daily_stats (
                    date TEXT PRIMARY KEY,
                    total_orders INTEGER DEFAULT 0,
                    filled_orders INTEGER DEFAULT 0,
                    failed_orders INTEGER DEFAULT 0,
                    avg_slippage_bps REAL DEFAULT 0,
                    total_volume INTEGER DEFAULT 0,
                    avg_fill_rate REAL DEFAULT 0,
                    best_slippage_bps REAL DEFAULT 0,
                    worst_slippage_bps REAL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_exec_orders_symbol
                    ON execution_orders(symbol);
                CREATE INDEX IF NOT EXISTS idx_exec_orders_created
                    ON execution_orders(created_at);
                CREATE INDEX IF NOT EXISTS idx_exec_children_parent
                    ON execution_children(parent_id);
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"실행 DB 테이블 생성 실패: {e}")

    # ------------------------------------------------------------------
    # 슬리피지 추정
    # ------------------------------------------------------------------

    def estimate_slippage(self, symbol: str, qty: int) -> dict:
        """
        주문의 예상 슬리피지를 추정한다.

        시장 충격(market impact)을 간이 모델로 추정:
        - 기본 스프레드: 5~10bp (유동주), 15~30bp (비유동주)
        - 시장 충격: sqrt(주문비율) * 상수

        Args:
            symbol: 종목코드
            qty: 주문 수량

        Returns:
            dict: {
                "estimated_bps": float,
                "spread_component": float,
                "impact_component": float,
                "is_large_order": bool,
                "pct_of_daily_volume": float,
            }
        """
        # 일봉 데이터로 거래량 확인
        daily_ohlcv = self.broker.fetch_ohlcv(symbol, count=20)
        if daily_ohlcv is None or daily_ohlcv.empty:
            return {
                "estimated_bps": 30.0,
                "spread_component": 10.0,
                "impact_component": 20.0,
                "is_large_order": False,
                "pct_of_daily_volume": 0.0,
            }

        avg_daily_vol = float(daily_ohlcv["volume"].tail(20).mean())
        avg_price = float(daily_ohlcv["close"].iloc[-1])

        if avg_daily_vol <= 0:
            return {
                "estimated_bps": 50.0,
                "spread_component": 15.0,
                "impact_component": 35.0,
                "is_large_order": True,
                "pct_of_daily_volume": 100.0,
            }

        pct_of_daily = (qty / avg_daily_vol) * 100

        # 스프레드 추정 (거래량 기반)
        if avg_daily_vol > 5_000_000:
            spread_bps = 5.0  # 대형주
        elif avg_daily_vol > 1_000_000:
            spread_bps = 10.0  # 중형주
        elif avg_daily_vol > 200_000:
            spread_bps = 20.0  # 소형주
        else:
            spread_bps = 30.0  # 저유동성

        # 시장 충격 추정: impact = k * sqrt(participation_rate)
        # participation_rate = qty / avg_daily_vol
        participation = qty / avg_daily_vol
        impact_bps = 30.0 * np.sqrt(participation)  # bp 단위 (C4 Fix: *100 제거)

        is_large = pct_of_daily > 5.0

        return {
            "estimated_bps": round(spread_bps + impact_bps, 1),
            "spread_component": round(spread_bps, 1),
            "impact_component": round(impact_bps, 1),
            "is_large_order": is_large,
            "pct_of_daily_volume": round(pct_of_daily, 2),
        }

    def max_slippage_guard(self, max_bps: float = 50.0):
        """
        슬리피지 상한 설정.

        모든 후속 주문에 적용되며, 체결 가격이 상한을 초과하면
        잔여 슬라이스를 취소한다.

        Args:
            max_bps: 최대 허용 슬리피지 (basis points). 기본 50bp (0.5%).
        """
        self.default_max_slippage_bps = max(1.0, min(max_bps, 200.0))
        logger.info(f"슬리피지 상한 설정: {self.default_max_slippage_bps}bp")

    # ------------------------------------------------------------------
    # TWAP 실행
    # ------------------------------------------------------------------

    def execute_twap(self, symbol: str, qty: int, duration_min: float,
                     side: str = Side.BUY.value, interval_sec: float = 30,
                     price_offset_bps: float = 5.0,
                     name: str = "") -> str:
        """
        TWAP (Time-Weighted Average Price) 실행.

        주문을 동일 크기 슬라이스로 분할하여 일정 간격으로 제출한다.
        각 슬라이스는 best bid/ask에 offset을 적용한 지정가 주문.

        Args:
            symbol: 종목코드
            qty: 총 주문 수량
            duration_min: 실행 기간 (분)
            side: BUY 또는 SELL
            interval_sec: 슬라이스 간격 (초). 기본 30초.
            price_offset_bps: 지정가 오프셋 (bp). 기본 5bp.
            name: 종목명 (로깅용)

        Returns:
            str: 부모 주문 ID
        """
        order_id = self._create_parent_order(
            symbol=symbol, qty=qty, side=side,
            order_type=OrderType.TWAP.value,
            urgency="low",
            duration_min=duration_min,
        )

        def _run():
            self._execute_twap_logic(
                order_id, symbol, qty, side, duration_min,
                interval_sec, price_offset_bps, name,
            )

        thread = threading.Thread(target=_run, daemon=True,
                                  name=f"twap-{order_id[:8]}")
        self._running_tasks[order_id] = thread
        thread.start()

        logger.info(
            f"TWAP 시작: {name or symbol} {side} {qty}주 "
            f"/ {duration_min}분 / 간격 {interval_sec}초"
        )
        return order_id

    def _execute_twap_logic(self, order_id: str, symbol: str, total_qty: int,
                            side: str, duration_min: float,
                            interval_sec: float, offset_bps: float,
                            name: str):
        """TWAP 실행 로직 (스레드 내부)."""
        parent = self._orders.get(order_id)
        if not parent:
            return

        total_seconds = duration_min * 60
        num_slices = max(1, int(total_seconds / interval_sec))
        base_slice_qty = total_qty // num_slices
        remainder = total_qty - (base_slice_qty * num_slices)

        parent.status = OrderStatus.ACTIVE.value
        self._update_parent_db(parent)

        for i in range(num_slices):
            if parent.status in (OrderStatus.CANCELLED.value, OrderStatus.FAILED.value):
                break

            # 슬리피지 가드 체크
            if parent.filled_qty > 0 and parent.target_price > 0:
                current_slippage = self._calculate_slippage_bps(
                    parent.target_price, parent.avg_filled_price, side
                )
                if current_slippage > parent.max_slippage_bps:
                    logger.warning(
                        f"TWAP 슬리피지 초과: {current_slippage:.1f}bp > "
                        f"{parent.max_slippage_bps:.1f}bp - 중단"
                    )
                    parent.status = OrderStatus.CANCELLED.value
                    parent.error = f"슬리피지 초과: {current_slippage:.1f}bp"
                    self._update_parent_db(parent)
                    break

            # 슬라이스 수량 (마지막 슬라이스에 나머지 추가)
            slice_qty = base_slice_qty + (remainder if i == num_slices - 1 else 0)
            if slice_qty <= 0:
                continue

            # 잔여 수량으로 보정
            remaining = parent.remaining_qty
            if remaining <= 0:
                break
            slice_qty = min(slice_qty, remaining)

            # 현재가 조회 및 지정가 산출
            price_info = self.broker.fetch_price(symbol)
            if not price_info:
                logger.warning(f"TWAP [{symbol}] 가격 조회 실패 - 슬라이스 {i+1} 건너뜀")
                time.sleep(interval_sec)
                continue

            current_price = price_info.get("price", 0)
            if current_price <= 0:
                time.sleep(interval_sec)
                continue

            # 첫 슬라이스에서 기준가 설정
            if parent.target_price <= 0:
                parent.target_price = float(current_price)

            # 지정가 오프셋 적용
            offset = int(current_price * offset_bps / 10000)
            if side == Side.BUY.value:
                limit_price = current_price + offset  # 매수: 약간 높게
            else:
                limit_price = max(1, current_price - offset)  # 매도: 약간 낮게

            # 자식 주문 생성 및 제출
            child = self._submit_child_order(
                parent=parent, symbol=symbol, side=side,
                qty=slice_qty, price=limit_price, name=name,
            )

            if child and child.status == OrderStatus.FILLED.value:
                self._update_parent_fill(parent, child)

            # 다음 슬라이스까지 대기 (마지막 아님)
            if i < num_slices - 1:
                time.sleep(interval_sec)

        # 완료 처리
        self._finalize_parent(parent)

    # ------------------------------------------------------------------
    # VWAP 실행
    # ------------------------------------------------------------------

    def execute_vwap(self, symbol: str, qty: int, duration_min: float,
                     side: str = Side.BUY.value,
                     name: str = "") -> str:
        """
        VWAP (Volume-Weighted Average Price) 실행.

        과거 거래량 프로파일에 비례하여 슬라이스를 배분한다.
        거래량이 많은 시간대에 더 많은 수량을 집행한다.

        Args:
            symbol: 종목코드
            qty: 총 주문 수량
            duration_min: 실행 기간 (분)
            side: BUY 또는 SELL
            name: 종목명

        Returns:
            str: 부모 주문 ID
        """
        order_id = self._create_parent_order(
            symbol=symbol, qty=qty, side=side,
            order_type=OrderType.VWAP.value,
            urgency="normal",
            duration_min=duration_min,
        )

        def _run():
            self._execute_vwap_logic(
                order_id, symbol, qty, side, duration_min, name,
            )

        thread = threading.Thread(target=_run, daemon=True,
                                  name=f"vwap-{order_id[:8]}")
        self._running_tasks[order_id] = thread
        thread.start()

        logger.info(
            f"VWAP 시작: {name or symbol} {side} {qty}주 / {duration_min}분"
        )
        return order_id

    def _execute_vwap_logic(self, order_id: str, symbol: str, total_qty: int,
                            side: str, duration_min: float, name: str):
        """VWAP 실행 로직 (스레드 내부)."""
        parent = self._orders.get(order_id)
        if not parent:
            return

        # 거래량 프로파일 구축
        daily_ohlcv = self.broker.fetch_ohlcv(symbol, count=30)
        self.volume_profile.get_profile(symbol, daily_ohlcv)

        # 현재 버킷 기준으로 슬라이스 가중치 산출
        cur_bucket = current_bucket_index()
        if cur_bucket is None:
            cur_bucket = 0  # 장 외 시간이면 첫 버킷부터

        # 슬라이스 수 결정 (최소 2분 간격)
        num_slices = max(2, int(duration_min / 2))
        interval_sec = (duration_min * 60) / num_slices

        # 거래량 프로파일 가중치
        weights = self.volume_profile.get_slice_weights(
            symbol, cur_bucket, num_slices
        )

        # 가중치 기반 수량 배분
        slice_qtys = np.round(weights * total_qty).astype(int)
        # 반올림 잔여 보정
        diff = total_qty - slice_qtys.sum()
        if diff != 0:
            max_idx = int(np.argmax(weights))
            slice_qtys[max_idx] += diff

        parent.status = OrderStatus.ACTIVE.value
        self._update_parent_db(parent)

        for i in range(num_slices):
            if parent.status in (OrderStatus.CANCELLED.value, OrderStatus.FAILED.value):
                break

            # 슬리피지 가드
            if parent.filled_qty > 0 and parent.target_price > 0:
                current_slippage = self._calculate_slippage_bps(
                    parent.target_price, parent.avg_filled_price, side
                )
                if current_slippage > parent.max_slippage_bps:
                    logger.warning(
                        f"VWAP 슬리피지 초과: {current_slippage:.1f}bp > "
                        f"{parent.max_slippage_bps:.1f}bp - 중단"
                    )
                    parent.status = OrderStatus.CANCELLED.value
                    parent.error = f"슬리피지 초과: {current_slippage:.1f}bp"
                    self._update_parent_db(parent)
                    break

            slice_qty = int(slice_qtys[i])
            remaining = parent.remaining_qty
            if remaining <= 0:
                break
            slice_qty = min(slice_qty, remaining)
            if slice_qty <= 0:
                time.sleep(interval_sec)
                continue

            # 현재가 조회
            price_info = self.broker.fetch_price(symbol)
            if not price_info:
                time.sleep(interval_sec)
                continue

            current_price = price_info.get("price", 0)
            if current_price <= 0:
                time.sleep(interval_sec)
                continue

            if parent.target_price <= 0:
                parent.target_price = float(current_price)

            # VWAP에서는 시장가에 가까운 지정가 사용 (3bp 오프셋)
            offset = max(1, int(current_price * 3 / 10000))
            if side == Side.BUY.value:
                limit_price = current_price + offset
            else:
                limit_price = max(1, current_price - offset)

            child = self._submit_child_order(
                parent=parent, symbol=symbol, side=side,
                qty=slice_qty, price=limit_price, name=name,
            )

            if child and child.status == OrderStatus.FILLED.value:
                self._update_parent_fill(parent, child)

            if i < num_slices - 1:
                time.sleep(interval_sec)

        self._finalize_parent(parent)

    # ------------------------------------------------------------------
    # Smart Execute
    # ------------------------------------------------------------------

    def smart_execute(self, symbol: str, side: str, qty: int,
                      urgency: str = "normal",
                      name: str = "") -> str:
        """
        스마트 실행: 상황에 따라 최적의 실행 전략을 자동 선택한다.

        판단 기준:
        - qty <= 5 (소규모) -> 직접 시장가 주문 (TWAP/VWAP 분할 무의미)
        - urgency="low"  -> TWAP 30분
        - urgency="normal" -> VWAP 15분
        - urgency="high" -> 시장가 (슬리피지 상한 적용)
        - 대량 주문 (일평균 5% 초과) -> TWAP 30분으로 강제 전환

        Args:
            symbol: 종목코드
            side: "BUY" 또는 "SELL"
            qty: 주문 수량
            urgency: "low", "normal", "high"
            name: 종목명

        Returns:
            str: 부모 주문 ID
        """
        # 소규모 주문 바이패스: 5주 이하는 직접 시장가 주문
        if qty <= 5:
            logger.info(
                f"소규모 주문: {name or symbol} {side} {qty}주 → 직접 시장가"
            )
            return self._execute_market_with_guard(
                symbol=symbol, qty=qty, side=side, name=name,
            )

        # 슬리피지 추정 및 대량 주문 감지
        slip_est = self.estimate_slippage(symbol, qty)
        is_large = slip_est["is_large_order"]
        pct_daily = slip_est["pct_of_daily_volume"]

        logger.info(
            f"Smart Execute 분석: {name or symbol} {side} {qty}주 | "
            f"긴급도={urgency} | 일평균대비={pct_daily:.1f}% | "
            f"대량주문={'예' if is_large else '아니오'}"
        )

        # 대량 주문 -> TWAP 30분 강제
        if is_large:
            logger.info(f"대량 주문 감지 (일평균 {pct_daily:.1f}%) -> TWAP 30분")
            return self.execute_twap(
                symbol=symbol, qty=qty, duration_min=30,
                side=side, interval_sec=30, name=name,
            )

        # 긴급도별 전략 선택
        if urgency == "low":
            return self.execute_twap(
                symbol=symbol, qty=qty, duration_min=30,
                side=side, interval_sec=30, name=name,
            )
        elif urgency == "high":
            return self._execute_market_with_guard(
                symbol=symbol, qty=qty, side=side, name=name,
            )
        else:  # normal
            return self.execute_vwap(
                symbol=symbol, qty=qty, duration_min=15,
                side=side, name=name,
            )

    def _execute_market_with_guard(self, symbol: str, qty: int,
                                   side: str, name: str) -> str:
        """슬리피지 가드가 적용된 시장가 주문."""
        order_id = self._create_parent_order(
            symbol=symbol, qty=qty, side=side,
            order_type=OrderType.MARKET.value,
            urgency="high",
            duration_min=0,
        )

        parent = self._orders[order_id]
        parent.status = OrderStatus.ACTIVE.value

        # 기준가 설정
        price_info = self.broker.fetch_price(symbol)
        if price_info:
            parent.target_price = float(price_info.get("price", 0))

        # 시장가 일괄 주문
        child = self._submit_child_order(
            parent=parent, symbol=symbol, side=side,
            qty=qty, price=0, name=name,  # price=0 -> 시장가
        )

        if child and child.status == OrderStatus.FILLED.value:
            self._update_parent_fill(parent, child)

            # 슬리피지 체크
            if parent.target_price > 0:
                actual_slippage = self._calculate_slippage_bps(
                    parent.target_price, parent.avg_filled_price, side
                )
                parent.slippage_bps = actual_slippage
                if actual_slippage > parent.max_slippage_bps:
                    logger.warning(
                        f"시장가 슬리피지 경고: {actual_slippage:.1f}bp "
                        f"(상한 {parent.max_slippage_bps:.1f}bp)"
                    )

        self._finalize_parent(parent)
        return order_id

    # ------------------------------------------------------------------
    # 자식 주문 제출 / 재시도
    # ------------------------------------------------------------------

    def _submit_child_order(self, parent: ParentOrder, symbol: str,
                            side: str, qty: int, price: int,
                            name: str = "") -> Optional[ChildOrder]:
        """
        자식 주문을 브로커에 제출한다.
        실패 시 지수 백오프로 재시도한다.
        """
        child = ChildOrder(
            child_id=str(uuid.uuid4()),
            parent_id=parent.order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            status=OrderStatus.ACTIVE.value,
            created_at=datetime.now().isoformat(),
        )

        with self._lock:
            parent.children.append(child)

        for attempt in range(self.max_retry + 1):
            try:
                if side == Side.BUY.value:
                    result = self.broker.buy(
                        symbol=symbol, name=name,
                        qty=qty, price=price,
                    )
                else:
                    result = self.broker.sell(
                        symbol=symbol, qty=qty, price=price,
                    )

                if result:
                    # v3.8.1: 체결 미확인 주문은 FILLED로 처리하지 않음
                    if result.get("confirmed") is False:
                        child.status = OrderStatus.FAILED.value
                        child.error = "체결 미확인 (타임아웃)"
                        self._save_child_db(child)
                        logger.warning(
                            f"주문 미체결 처리 [{symbol}]: 체결 확인 실패 → FAILED"
                        )
                        return child

                    child.status = OrderStatus.FILLED.value
                    child.filled_qty = result.get("filled_qty", qty)
                    child.filled_price = float(
                        result.get("filled_price", result.get("price", price))
                    )
                    child.filled_at = datetime.now().isoformat()
                    self._save_child_db(child)
                    return child
                else:
                    child.error = "브로커 응답 없음"

            except Exception as e:
                child.error = str(e)
                logger.error(
                    f"자식 주문 실패 [{symbol}] 시도 {attempt+1}: {e}"
                )

            child.retry_count = attempt + 1

            # 재시도 대기 (지수 백오프)
            if attempt < self.max_retry:
                delay = self.retry_base_delay * (2 ** attempt)
                logger.info(f"재시도 대기: {delay:.1f}초")
                time.sleep(delay)

        # 모든 재시도 실패
        child.status = OrderStatus.FAILED.value
        self._save_child_db(child)
        logger.error(
            f"자식 주문 최종 실패 [{symbol}]: {child.error}"
        )
        return child

    # ------------------------------------------------------------------
    # 부모 주문 관리
    # ------------------------------------------------------------------

    def _create_parent_order(self, symbol: str, qty: int, side: str,
                             order_type: str, urgency: str,
                             duration_min: float) -> str:
        """부모 주문을 생성하고 DB에 기록한다."""
        order_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        parent = ParentOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            total_qty=qty,
            order_type=order_type,
            urgency=urgency,
            status=OrderStatus.PENDING.value,
            max_slippage_bps=self.default_max_slippage_bps,
            created_at=now,
            duration_min=duration_min,
        )

        with self._lock:
            self._orders[order_id] = parent

        self._save_parent_db(parent)
        self._ensure_daily_stats_current()
        self._daily_stats["total_orders"] += 1
        return order_id

    def _update_parent_fill(self, parent: ParentOrder, child: ChildOrder):
        """자식 주문 체결 결과를 부모 주문에 반영한다."""
        with self._lock:
            old_total_cost = parent.avg_filled_price * parent.filled_qty
            new_cost = child.filled_price * child.filled_qty
            parent.filled_qty += child.filled_qty
            if parent.filled_qty > 0:
                parent.avg_filled_price = (
                    (old_total_cost + new_cost) / parent.filled_qty
                )

            if parent.filled_qty >= parent.total_qty:
                parent.status = OrderStatus.FILLED.value
            else:
                parent.status = OrderStatus.PARTIAL.value

            # 슬리피지 계산
            if parent.target_price > 0:
                parent.slippage_bps = self._calculate_slippage_bps(
                    parent.target_price,
                    parent.avg_filled_price,
                    parent.side,
                )

        self._update_parent_db(parent)

    def _finalize_parent(self, parent: ParentOrder):
        """부모 주문을 최종 상태로 전환한다."""
        with self._lock:
            if parent.status == OrderStatus.ACTIVE.value:
                if parent.filled_qty >= parent.total_qty:
                    parent.status = OrderStatus.FILLED.value
                elif parent.filled_qty > 0:
                    parent.status = OrderStatus.PARTIAL.value
                else:
                    parent.status = OrderStatus.FAILED.value

            parent.completed_at = datetime.now().isoformat()

            # 일일 통계 업데이트 (날짜 변경 확인)
            self._ensure_daily_stats_current()
            if parent.status == OrderStatus.FILLED.value:
                self._daily_stats["filled_orders"] += 1
            elif parent.status in (OrderStatus.FAILED.value,
                                   OrderStatus.CANCELLED.value):
                self._daily_stats["failed_orders"] += 1

            self._daily_stats["total_volume"] += parent.filled_qty
            self._daily_stats["total_slippage_bps"] += abs(parent.slippage_bps)

            # 평균 체결률 갱신
            filled = self._daily_stats["filled_orders"]
            total = self._daily_stats["total_orders"]
            if total > 0:
                self._daily_stats["avg_fill_rate"] = filled / total

        self._update_parent_db(parent)
        self._save_daily_stats()

        # 스레드 참조 제거
        self._running_tasks.pop(parent.order_id, None)

        logger.info(
            f"주문 완료: {parent.symbol} {parent.side} "
            f"{parent.filled_qty}/{parent.total_qty}주 "
            f"@ {parent.avg_filled_price:,.0f}원 "
            f"슬리피지={parent.slippage_bps:.1f}bp "
            f"상태={parent.status}"
        )

    # ------------------------------------------------------------------
    # 주문 취소
    # ------------------------------------------------------------------

    def cancel_order(self, order_id: str) -> bool:
        """
        진행 중인 주문을 취소한다.

        Args:
            order_id: 부모 주문 ID

        Returns:
            bool: 취소 성공 여부
        """
        parent = self._orders.get(order_id)
        if not parent:
            logger.warning(f"주문 ID 없음: {order_id}")
            return False

        if parent.status in (OrderStatus.FILLED.value,
                             OrderStatus.CANCELLED.value,
                             OrderStatus.FAILED.value):
            return False

        with self._lock:
            parent.status = OrderStatus.CANCELLED.value
            parent.error = "사용자 취소"
            parent.completed_at = datetime.now().isoformat()

        self._update_parent_db(parent)
        logger.info(f"주문 취소: {order_id}")
        return True

    # ------------------------------------------------------------------
    # 실행 리포트 & 통계
    # ------------------------------------------------------------------

    def get_execution_report(self, order_id: str) -> Optional[dict]:
        """
        개별 주문의 실행 리포트를 반환한다.

        Returns:
            dict: 부모 주문 상세 + 자식 주문 리스트 + 분석
        """
        parent = self._orders.get(order_id)
        if not parent:
            # DB에서 조회 시도
            return self._load_execution_report_from_db(order_id)

        report = parent.to_dict()
        report["children"] = [c.to_dict() for c in parent.children]

        # 실행 분석
        report["analysis"] = {
            "fill_rate_pct": round(parent.fill_rate * 100, 1),
            "slippage_bps": round(parent.slippage_bps, 1),
            "slippage_pct": round(parent.slippage_bps / 100, 4),
            "total_children": len(parent.children),
            "filled_children": sum(
                1 for c in parent.children
                if c.status == OrderStatus.FILLED.value
            ),
            "failed_children": sum(
                1 for c in parent.children
                if c.status == OrderStatus.FAILED.value
            ),
            "avg_retry": (
                sum(c.retry_count for c in parent.children) / max(len(parent.children), 1)
            ),
        }

        # 예상 비용 vs 실제 비용
        if parent.target_price > 0 and parent.filled_qty > 0:
            expected_cost = parent.target_price * parent.total_qty
            actual_cost = parent.avg_filled_price * parent.filled_qty
            report["analysis"]["expected_cost"] = round(expected_cost)
            report["analysis"]["actual_cost"] = round(actual_cost)
            report["analysis"]["cost_difference"] = round(actual_cost - expected_cost)

        return report

    def _load_execution_report_from_db(self, order_id: str) -> Optional[dict]:
        """DB에서 실행 리포트 로드."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM execution_orders WHERE order_id=?", (order_id,)
            ).fetchone()
            if not row:
                conn.close()
                return None

            report = dict(row)
            children = conn.execute(
                "SELECT * FROM execution_children WHERE parent_id=?", (order_id,)
            ).fetchall()
            conn.close()

            report["children"] = [dict(c) for c in children]
            return report
        except Exception as e:
            logger.error(f"실행 리포트 DB 조회 실패: {e}")
            return None

    def _ensure_daily_stats_current(self):
        """날짜가 바뀌었으면 일일 통계를 리셋한다."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._daily_stats["date"] != today:
            self._daily_stats = {
                "date": today,
                "total_orders": 0,
                "filled_orders": 0,
                "failed_orders": 0,
                "total_slippage_bps": 0.0,
                "total_volume": 0,
                "avg_fill_rate": 0.0,
            }

    def get_daily_stats(self) -> dict:
        """오늘의 실행 통계를 반환한다."""
        self._ensure_daily_stats_current()

        stats = self._daily_stats.copy()
        filled = stats["filled_orders"]
        if filled > 0:
            stats["avg_slippage_bps"] = round(
                stats["total_slippage_bps"] / filled, 1
            )
        else:
            stats["avg_slippage_bps"] = 0.0

        # 활성 주문 수
        active = sum(
            1 for o in self._orders.values()
            if o.status in (OrderStatus.ACTIVE.value, OrderStatus.PARTIAL.value)
        )
        stats["active_orders"] = active

        return stats

    def get_fill_price(self, order_id: str) -> float:
        """체결된 주문의 평균 체결가를 반환한다. 미체결이면 0."""
        parent = self._orders.get(order_id)
        if parent and parent.avg_filled_price > 0:
            return parent.avg_filled_price
        return 0.0

    def get_active_orders(self) -> List[dict]:
        """현재 활성 주문 목록을 반환한다."""
        result = []
        for order_id, parent in self._orders.items():
            if parent.status in (OrderStatus.ACTIVE.value,
                                 OrderStatus.PARTIAL.value,
                                 OrderStatus.PENDING.value):
                result.append(parent.to_dict())
        return result

    def get_historical(self, days: int = 30) -> dict:
        """
        과거 실행 이력 통계를 반환한다.

        Args:
            days: 조회 기간 (일)

        Returns:
            dict: {
                "orders": [...],
                "summary": { 평균 슬리피지, 체결률 등 },
                "slippage_distribution": { 히스토그램 데이터 },
                "daily_breakdown": [...]
            }
        """
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            since = (datetime.now() - timedelta(days=days)).isoformat()

            rows = conn.execute(
                "SELECT * FROM execution_orders WHERE created_at >= ? "
                "ORDER BY created_at DESC",
                (since,),
            ).fetchall()

            daily_rows = conn.execute(
                "SELECT * FROM execution_daily_stats WHERE date >= ? "
                "ORDER BY date ASC",
                ((datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),),
            ).fetchall()
            conn.close()

            orders = [dict(r) for r in rows]
            daily = [dict(r) for r in daily_rows]

            # 요약 통계
            total = len(orders)
            filled = [o for o in orders if o["status"] == "FILLED"]
            failed = [o for o in orders if o["status"] in ("FAILED", "CANCELLED")]
            slippages = [o["slippage_bps"] for o in orders if o["slippage_bps"] != 0]

            summary = {
                "total_orders": total,
                "filled_orders": len(filled),
                "failed_orders": len(failed),
                "fill_rate_pct": round(len(filled) / max(total, 1) * 100, 1),
                "avg_slippage_bps": (
                    round(sum(slippages) / len(slippages), 1) if slippages else 0.0
                ),
                "max_slippage_bps": round(max(slippages), 1) if slippages else 0.0,
                "min_slippage_bps": round(min(slippages), 1) if slippages else 0.0,
                "total_volume": sum(o.get("filled_qty", 0) for o in orders),
            }

            # 슬리피지 분포 히스토그램
            bins = {}
            bin_edges = list(range(-50, 55, 5))
            for edge in bin_edges:
                bins[f"{edge:+d}"] = 0
            for s in slippages:
                clamped = max(-50, min(50, s))
                idx = int((clamped + 50) // 5)
                idx = max(0, min(len(bin_edges) - 1, idx))
                bins[f"{bin_edges[idx]:+d}"] += 1

            return {
                "orders": orders[:100],
                "summary": summary,
                "slippage_distribution": {
                    "bins": list(bins.keys()),
                    "counts": list(bins.values()),
                },
                "daily_breakdown": daily,
            }

        except Exception as e:
            logger.error(f"실행 이력 조회 실패: {e}")
            return {
                "orders": [],
                "summary": {},
                "slippage_distribution": {"bins": [], "counts": []},
                "daily_breakdown": [],
            }

    def get_volume_profile(self, symbol: str) -> dict:
        """종목의 거래량 프로파일을 반환한다."""
        daily_ohlcv = self.broker.fetch_ohlcv(symbol, count=30)
        return self.volume_profile.get_profile(symbol, daily_ohlcv)

    # ------------------------------------------------------------------
    # 유틸리티
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_slippage_bps(target_price: float, filled_price: float,
                                side: str) -> float:
        """슬리피지를 basis points로 계산한다."""
        if target_price <= 0:
            return 0.0
        diff = filled_price - target_price
        if side == Side.SELL.value:
            diff = -diff  # 매도는 낮게 체결될수록 불리
        return (diff / target_price) * 10000

    # ------------------------------------------------------------------
    # DB 영속화
    # ------------------------------------------------------------------

    def _save_parent_db(self, parent: ParentOrder):
        """부모 주문을 DB에 저장."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """INSERT OR REPLACE INTO execution_orders
                   (order_id, symbol, side, total_qty, filled_qty, order_type,
                    urgency, status, avg_filled_price, target_price,
                    slippage_bps, max_slippage_bps, duration_min,
                    created_at, completed_at, error)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (parent.order_id, parent.symbol, parent.side,
                 parent.total_qty, parent.filled_qty, parent.order_type,
                 parent.urgency, parent.status,
                 round(parent.avg_filled_price, 2),
                 round(parent.target_price, 2),
                 round(parent.slippage_bps, 2),
                 parent.max_slippage_bps, parent.duration_min,
                 parent.created_at, parent.completed_at, parent.error),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"부모 주문 DB 저장 실패: {e}")

    def _update_parent_db(self, parent: ParentOrder):
        """부모 주문 DB 업데이트 (save와 동일)."""
        self._save_parent_db(parent)

    def _save_child_db(self, child: ChildOrder):
        """자식 주문을 DB에 저장."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """INSERT OR REPLACE INTO execution_children
                   (child_id, parent_id, symbol, side, qty, price, status,
                    filled_qty, filled_price, created_at, filled_at,
                    retry_count, error)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (child.child_id, child.parent_id, child.symbol, child.side,
                 child.qty, child.price, child.status,
                 child.filled_qty, round(child.filled_price, 2),
                 child.created_at, child.filled_at,
                 child.retry_count, child.error),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"자식 주문 DB 저장 실패: {e}")

    def _save_daily_stats(self):
        """일일 통계를 DB에 저장."""
        try:
            stats = self._daily_stats
            filled = max(stats["filled_orders"], 1)
            avg_slip = stats["total_slippage_bps"] / filled

            # 당일 최선/최악 슬리피지
            today = stats["date"]
            today_orders = [
                o for o in self._orders.values()
                if o.created_at.startswith(today) and o.slippage_bps != 0
            ]
            best = min((o.slippage_bps for o in today_orders), default=0)
            worst = max((o.slippage_bps for o in today_orders), default=0)

            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """INSERT OR REPLACE INTO execution_daily_stats
                   (date, total_orders, filled_orders, failed_orders,
                    avg_slippage_bps, total_volume, avg_fill_rate,
                    best_slippage_bps, worst_slippage_bps)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (today, stats["total_orders"], stats["filled_orders"],
                 stats["failed_orders"], round(avg_slip, 2),
                 stats["total_volume"],
                 round(stats["avg_fill_rate"], 4),
                 round(best, 2), round(worst, 2)),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"일일 통계 DB 저장 실패: {e}")
