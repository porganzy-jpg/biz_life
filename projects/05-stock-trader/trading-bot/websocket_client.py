"""
StockBot 실시간 호가 WebSocket 프레임워크 v3.7

asyncio + threading 기반 WebSocket 클라이언트.
opt-in 방식: 기본은 폴링, WebSocket은 명시적 활성화 시에만 동작.

기능:
  - 자동 재연결 (exponential backoff, max 10회, max 60초)
  - 30초 하트비트
  - 종목별 TickData deque 버퍼 (maxlen=1000)
  - on_tick / on_state_change 콜백
"""
import asyncio
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket 연결 상태"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class TickData:
    """체결 데이터"""
    symbol: str
    price: float
    volume: int
    timestamp: datetime = field(default_factory=datetime.now)
    bid: float = 0
    ask: float = 0
    change: float = 0
    change_pct: float = 0


class WebSocketClient:
    """
    WebSocket 기본 클래스

    별도 스레드에서 asyncio 이벤트 루프를 실행하여
    메인 스레드(동기)와 독립적으로 WebSocket 통신 수행.
    """

    def __init__(self, url: str = "", max_reconnect: int = 10,
                 heartbeat_sec: int = 30, buffer_size: int = 1000):
        self._url = url
        self._max_reconnect = max_reconnect
        self._heartbeat_sec = heartbeat_sec
        self._buffer_size = buffer_size

        self._state = ConnectionState.DISCONNECTED
        self._reconnect_count = 0
        self._ws = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # 종목별 틱 버퍼
        self._tick_buffers: Dict[str, deque] = {}

        # 구독 종목 목록
        self._subscriptions: List[str] = []

        # 콜백
        self._on_tick: Optional[Callable[[TickData], None]] = None
        self._on_state_change: Optional[Callable[[ConnectionState], None]] = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    def _set_state(self, new_state: ConnectionState):
        old_state = self._state
        self._state = new_state
        if old_state != new_state:
            logger.info(f"WebSocket 상태 변경: {old_state.value} → {new_state.value}")
            if self._on_state_change:
                try:
                    self._on_state_change(new_state)
                except Exception as e:
                    logger.error(f"on_state_change 콜백 오류: {e}")

    def set_callbacks(self, on_tick: Callable[[TickData], None] = None,
                      on_state_change: Callable[[ConnectionState], None] = None):
        """콜백 설정"""
        self._on_tick = on_tick
        self._on_state_change = on_state_change

    def subscribe(self, symbols: List[str]):
        """종목 구독 추가"""
        for sym in symbols:
            if sym not in self._subscriptions:
                self._subscriptions.append(sym)
                self._tick_buffers[sym] = deque(maxlen=self._buffer_size)

    def unsubscribe(self, symbols: List[str]):
        """종목 구독 해제"""
        for sym in symbols:
            self._subscriptions = [s for s in self._subscriptions if s != sym]

    def get_latest_tick(self, symbol: str) -> Optional[TickData]:
        """최신 틱 데이터 조회"""
        buf = self._tick_buffers.get(symbol)
        if buf and len(buf) > 0:
            return buf[-1]
        return None

    def get_ticks(self, symbol: str, count: int = 100) -> List[TickData]:
        """최근 N개 틱 데이터 조회"""
        buf = self._tick_buffers.get(symbol)
        if buf:
            return list(buf)[-count:]
        return []

    def _store_tick(self, tick: TickData):
        """틱 데이터 저장 + 콜백 호출"""
        if tick.symbol not in self._tick_buffers:
            self._tick_buffers[tick.symbol] = deque(maxlen=self._buffer_size)
        self._tick_buffers[tick.symbol].append(tick)

        if self._on_tick:
            try:
                self._on_tick(tick)
            except Exception as e:
                logger.error(f"on_tick 콜백 오류: {e}")

    def start(self):
        """WebSocket 연결 시작 (별도 스레드)"""
        if self._running:
            logger.warning("WebSocket 이미 실행 중")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("WebSocket 스레드 시작")

    def stop(self):
        """WebSocket 연결 종료"""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._set_state(ConnectionState.DISCONNECTED)
        logger.info("WebSocket 종료")

    def _run_loop(self):
        """별도 스레드에서 asyncio 이벤트 루프 실행"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as e:
            logger.error(f"WebSocket 루프 오류: {e}")
        finally:
            self._loop.close()

    async def _connect_loop(self):
        """연결 + 자동 재연결 루프"""
        while self._running:
            try:
                self._set_state(ConnectionState.CONNECTING)
                await self._connect()
            except Exception as e:
                logger.warning(f"WebSocket 연결 오류: {e}")
                self._set_state(ConnectionState.ERROR)

            if not self._running:
                break

            # 재연결 시도
            self._reconnect_count += 1
            if self._reconnect_count > self._max_reconnect:
                logger.error(f"WebSocket 최대 재연결 횟수({self._max_reconnect}) 초과")
                self._set_state(ConnectionState.ERROR)
                break

            # Exponential backoff (max 60초)
            delay = min(2 ** self._reconnect_count, 60)
            self._set_state(ConnectionState.RECONNECTING)
            logger.info(f"WebSocket 재연결 대기: {delay}초 (시도 {self._reconnect_count}/{self._max_reconnect})")
            await asyncio.sleep(delay)

    async def _connect(self):
        """WebSocket 연결 (서브클래스에서 오버라이드)"""
        raise NotImplementedError("서브클래스에서 _connect()를 구현하세요")

    async def _send_heartbeat(self):
        """하트비트 전송 (서브클래스에서 오버라이드 가능)"""
        pass

    def get_status(self) -> dict:
        """현재 상태 조회"""
        return {
            "state": self._state.value,
            "subscriptions": len(self._subscriptions),
            "symbols": self._subscriptions[:10],
            "reconnect_count": self._reconnect_count,
            "buffer_sizes": {
                sym: len(buf) for sym, buf in self._tick_buffers.items()
                if len(buf) > 0
            },
        }


class KISWebSocketClient(WebSocketClient):
    """
    한국투자증권 실시간 WebSocket 클라이언트 (구현 스텁)

    URL: wss://ops.koreainvestment.com:21000
    구독 메시지 포맷: H0STCNT0 (체결가)

    주의: 실제 연결에는 유효한 API 키 필요.
    API 키 없으면 NotImplementedError 발생.
    """

    WS_URL = "wss://ops.koreainvestment.com:21000"

    def __init__(self, app_key: str = "", app_secret: str = ""):
        super().__init__(url=self.WS_URL)
        self._app_key = app_key
        self._app_secret = app_secret
        self._approval_key = ""

    async def _connect(self):
        """KIS WebSocket 연결"""
        if not self._app_key or not self._app_secret:
            raise NotImplementedError(
                "KIS WebSocket 연결에는 API 키가 필요합니다. "
                "KIS_APP_KEY, KIS_APP_SECRET 환경변수를 설정하세요."
            )

        try:
            import websockets
        except ImportError:
            raise NotImplementedError(
                "websockets 패키지가 필요합니다. pip install websockets"
            )

        # Approval key 발급
        if not self._approval_key:
            self._approval_key = await self._get_approval_key()

        async with websockets.connect(self._url) as ws:
            self._ws = ws
            self._set_state(ConnectionState.CONNECTED)
            self._reconnect_count = 0

            # 구독 요청
            for symbol in self._subscriptions:
                await self._subscribe_symbol(ws, symbol)

            # 수신 루프
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))
            try:
                async for message in ws:
                    if not self._running:
                        break
                    self._process_message(message)
            finally:
                heartbeat_task.cancel()

    async def _get_approval_key(self) -> str:
        """WebSocket 접속키 발급"""
        import aiohttp
        url = "https://openapi.koreainvestment.com:9443/oauth2/Approval"
        body = {
            "grant_type": "client_credentials",
            "appkey": self._app_key,
            "secretkey": self._app_secret,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body) as resp:
                data = await resp.json()
                return data.get("approval_key", "")

    async def _subscribe_symbol(self, ws, symbol: str):
        """종목 체결가 구독 (H0STCNT0)"""
        msg = json.dumps({
            "header": {
                "approval_key": self._approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": "H0STCNT0",
                    "tr_key": symbol,
                }
            }
        })
        await ws.send(msg)
        logger.info(f"KIS WebSocket 구독: {symbol}")

    async def _heartbeat_loop(self, ws):
        """30초 간격 하트비트"""
        while self._running:
            await asyncio.sleep(self._heartbeat_sec)
            try:
                await ws.ping()
            except Exception:
                break

    def _process_message(self, message: str):
        """수신 메시지 파싱 → TickData 변환"""
        try:
            if message.startswith("{"):
                # JSON 응답 (구독 확인 등)
                data = json.loads(message)
                logger.debug(f"KIS WS JSON: {data}")
                return

            # 파이프 구분 데이터 (체결가)
            parts = message.split("|")
            if len(parts) < 4:
                return

            tr_id = parts[1]
            if tr_id != "H0STCNT0":
                return

            fields = parts[3].split("^")
            if len(fields) < 15:
                return

            tick = TickData(
                symbol=fields[0],
                price=float(fields[2]),
                volume=int(fields[12]),
                change=float(fields[4]),
                change_pct=float(fields[5]),
            )
            self._store_tick(tick)

        except Exception as e:
            logger.debug(f"KIS WS 메시지 파싱 오류: {e}")
