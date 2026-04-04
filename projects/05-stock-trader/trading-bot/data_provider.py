"""
yfinance 기반 실시간 데이터 제공 모듈

weekly_simulation.py의 검증된 download_stock_data() 로직 재사용.
5분 TTL 캐시로 API 호출 최소화.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 캐시 TTL (초) - 매매 간격(3분)보다 짧게 설정하여 매 사이클 신선한 데이터 사용
CACHE_TTL_SEC = 150  # 2.5분


class DataProvider:
    """yfinance 기반 주식 데이터 제공자"""

    def __init__(self, ttl_sec: int = CACHE_TTL_SEC):
        self._ttl = ttl_sec
        self._ohlcv_cache: dict = {}   # {symbol: {"data": df, "ts": float}}
        self._price_cache: dict = {}   # {symbol: {"price": int, "volume": int, "ts": float}}

    def fetch_ohlcv(self, symbol: str, days: int = 250) -> Optional[pd.DataFrame]:
        """
        종목 OHLCV 데이터 조회 (yfinance).

        Args:
            symbol: 종목코드 (예: "005930")
            days: 거래일 수

        Returns:
            pd.DataFrame: open, high, low, close, volume 컬럼
        """
        now = time.time()
        cached = self._ohlcv_cache.get(symbol)
        if cached and (now - cached["ts"]) < self._ttl:
            logger.debug(f"[캐시] OHLCV {symbol}")
            return cached["data"].copy()

        df = self._download_yfinance(symbol, days)
        if df is not None and not df.empty:
            self._ohlcv_cache[symbol] = {"data": df, "ts": now}
            return df.copy()

        # 캐시에 만료된 데이터라도 있으면 반환
        if cached:
            logger.warning(f"[폴백] 만료 캐시 사용 {symbol}")
            return cached["data"].copy()

        return None

    def fetch_current_price(self, symbol: str) -> Optional[dict]:
        """
        현재가 조회.

        OHLCV 데이터의 마지막 종가를 현재가로 사용.

        Returns:
            dict: {"price": int, "volume": int} 또는 None
        """
        now = time.time()
        cached = self._price_cache.get(symbol)
        if cached and (now - cached["ts"]) < self._ttl:
            return {"price": cached["price"], "volume": cached["volume"]}

        df = self.fetch_ohlcv(symbol, days=10)
        if df is None or df.empty:
            if cached:
                return {"price": cached["price"], "volume": cached["volume"]}
            return None

        price = int(df.iloc[-1]["close"])
        volume = int(df.iloc[-1]["volume"])
        self._price_cache[symbol] = {"price": price, "volume": volume, "ts": now}
        return {"price": price, "volume": volume}

    def preload_watchlist(self, watchlist: list) -> dict:
        """
        워치리스트 전체 데이터를 미리 로드.

        Args:
            watchlist: [{"code": "005930", "name": "삼성전자", ...}, ...]

        Returns:
            dict: {symbol: {"name": name, "loaded": bool, "rows": int}}
        """
        results = {}
        for stock in watchlist:
            code = stock["code"]
            name = stock.get("name", code)
            try:
                df = self.fetch_ohlcv(code)
                if df is not None and not df.empty:
                    results[code] = {"name": name, "loaded": True, "rows": len(df)}
                    logger.info(f"  로드 완료: {name}({code}) {len(df)}일")
                else:
                    results[code] = {"name": name, "loaded": False, "rows": 0}
                    logger.warning(f"  로드 실패: {name}({code})")
            except Exception as e:
                results[code] = {"name": name, "loaded": False, "rows": 0}
                logger.error(f"  로드 에러: {name}({code}): {e}")
        return results

    def invalidate(self, symbol: Optional[str] = None):
        """캐시 무효화. symbol이 None이면 전체 캐시 클리어."""
        if symbol:
            self._ohlcv_cache.pop(symbol, None)
            self._price_cache.pop(symbol, None)
        else:
            self._ohlcv_cache.clear()
            self._price_cache.clear()

    def update_from_tick(self, tick) -> None:
        """
        WebSocket 틱 데이터로 가격 캐시 즉시 업데이트 (v3.7).

        Args:
            tick: TickData(symbol, price, volume, ...)
        """
        now = time.time()
        self._price_cache[tick.symbol] = {
            "price": int(tick.price),
            "volume": int(tick.volume),
            "ts": now,
        }

    def create_ws_bridge(self):
        """
        WebSocket 콜백 생성 (v3.7).

        Returns:
            callable: on_tick 콜백 함수
        """
        def on_tick(tick):
            self.update_from_tick(tick)
        return on_tick

    @staticmethod
    def _download_yfinance(code: str, days: int = 250) -> Optional[pd.DataFrame]:
        """
        yfinance로 코스피 종목 데이터 다운로드.
        weekly_simulation.py의 검증된 로직 재사용.
        """
        try:
            import yfinance as yf
        except ImportError:
            logger.error("yfinance 미설치. pip install yfinance 실행 필요.")
            return None

        ticker = f"{code}.KS"
        end = datetime.now()
        start = end - timedelta(days=int(days * 1.6))  # 주말/공휴일 감안

        try:
            df = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if df is None or len(df) == 0:
                return None

            # 컬럼 정리: yfinance는 MultiIndex를 반환할 수 있음
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.rename(columns={
                "Open": "open", "High": "high", "Low": "low",
                "Close": "close", "Volume": "volume",
            })

            for col in ["open", "high", "low", "close", "volume"]:
                if col not in df.columns:
                    return None

            df = df[["open", "high", "low", "close", "volume"]].dropna()
            df = df.reset_index(drop=True)
            return df

        except Exception as e:
            logger.warning(f"yfinance 다운로드 실패 [{code}]: {e}")
            return None
