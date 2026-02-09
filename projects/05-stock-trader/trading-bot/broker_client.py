"""
한국투자증권 API 클라이언트

mojito SDK를 래핑하여 주식 매매 기능 제공
모의투자 / 실전투자 모드 전환 가능
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np

from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO, KIS_IS_PAPER

logger = logging.getLogger(__name__)


class BrokerClient:
    """한국투자증권 API 클라이언트"""

    def __init__(self, paper_trading: bool = True):
        self.paper_trading = paper_trading or KIS_IS_PAPER

        # mojito SDK 연동 (API 키가 없으면 시뮬레이션 모드)
        self.broker = None
        if KIS_APP_KEY and KIS_APP_SECRET:
            try:
                import mojito
                self.broker = mojito.KoreaInvestment(
                    api_key=KIS_APP_KEY,
                    api_secret=KIS_APP_SECRET,
                    acc_no=KIS_ACCOUNT_NO,
                    mock=self.paper_trading,
                )
                logger.info(f"한국투자증권 API 연결 완료 ({'모의' if self.paper_trading else '실전'})")
            except Exception as e:
                logger.warning(f"한국투자증권 API 연결 실패: {e} (시뮬레이션 모드)")
        else:
            logger.info("API 키 미설정 - 시뮬레이션 모드로 실행")

        # 시뮬레이션 상태
        self._sim_balance = 100_000_000  # 1억원 시작
        self._sim_positions = {}  # {종목코드: {qty, avg_price, name}}

    def fetch_ohlcv(self, symbol: str, period: str = "D", count: int = 200) -> pd.DataFrame:
        """
        OHLCV 데이터 조회

        Args:
            symbol: 종목코드 (예: "005930")
            period: 기간 (D:일, W:주, M:월)
            count: 데이터 수

        Returns:
            pd.DataFrame: OHLCV 데이터
        """
        if self.broker:
            try:
                df = self.broker.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=period,
                    adj_price=True,
                )
                if df is not None and not df.empty:
                    df.columns = [c.lower() for c in df.columns]
                    return df.tail(count)
            except Exception as e:
                logger.error(f"OHLCV 조회 실패 [{symbol}]: {e}")

        # 시뮬레이션 데이터 생성
        return self._generate_sim_data(symbol, count)

    def _generate_sim_data(self, symbol: str, count: int) -> pd.DataFrame:
        """시뮬레이션용 OHLCV 데이터"""
        np.random.seed(hash(symbol) % 2**31)
        base_price = 50000 + (hash(symbol) % 100000)
        dates = pd.date_range(end=datetime.now(), periods=count, freq="B")
        n = len(dates)
        prices = base_price + np.cumsum(np.random.randn(n) * (base_price * 0.015))
        prices = np.maximum(prices, base_price * 0.5)

        return pd.DataFrame({
            "open": prices + np.random.randn(n) * (base_price * 0.005),
            "high": prices + abs(np.random.randn(n) * (base_price * 0.01)),
            "low": prices - abs(np.random.randn(n) * (base_price * 0.01)),
            "close": prices,
            "volume": np.random.randint(100000, 10000000, n),
        }, index=dates)

    def fetch_price(self, symbol: str) -> Optional[dict]:
        """현재가 조회"""
        if self.broker:
            try:
                price = self.broker.fetch_price(symbol)
                return price
            except Exception as e:
                logger.error(f"현재가 조회 실패 [{symbol}]: {e}")

        # 시뮬레이션
        df = self._generate_sim_data(symbol, 1)
        return {"price": int(df.iloc[-1]["close"]), "volume": int(df.iloc[-1]["volume"])}

    def get_balance(self) -> dict:
        """잔고 조회"""
        if self.broker and not self.paper_trading:
            try:
                return self.broker.fetch_balance()
            except Exception as e:
                logger.error(f"잔고 조회 실패: {e}")

        return {
            "cash": self._sim_balance,
            "total_eval": self._sim_balance + sum(
                p["qty"] * p["avg_price"] for p in self._sim_positions.values()
            ),
        }

    def buy(self, symbol: str, name: str, qty: int, price: int = 0) -> Optional[dict]:
        """
        매수 주문

        Args:
            symbol: 종목코드
            name: 종목명
            qty: 수량
            price: 지정가 (0이면 시장가)
        """
        if self.broker:
            try:
                if price > 0:
                    result = self.broker.create_limit_buy_order(symbol, qty, price)
                else:
                    result = self.broker.create_market_buy_order(symbol, qty)
                return result
            except Exception as e:
                logger.error(f"매수 실패 [{symbol}]: {e}")
                return None

        # 시뮬레이션
        current = self.fetch_price(symbol)
        if not current:
            return None

        buy_price = price if price > 0 else current["price"]
        total_cost = buy_price * qty
        fee = int(total_cost * 0.00015)  # 수수료 0.015%

        if self._sim_balance < total_cost + fee:
            logger.warning(f"잔고 부족: {self._sim_balance:,} < {total_cost + fee:,}")
            return None

        self._sim_balance -= (total_cost + fee)
        if symbol in self._sim_positions:
            pos = self._sim_positions[symbol]
            old_total = pos["qty"] * pos["avg_price"]
            pos["qty"] += qty
            pos["avg_price"] = int((old_total + total_cost) / pos["qty"])
        else:
            self._sim_positions[symbol] = {
                "qty": qty, "avg_price": buy_price, "name": name
            }

        logger.info(f"[SIM] 매수: {name}({symbol}) {qty}주 @ {buy_price:,}원")
        return {"symbol": symbol, "qty": qty, "price": buy_price, "action": "BUY"}

    def sell(self, symbol: str, qty: int, price: int = 0) -> Optional[dict]:
        """매도 주문"""
        if self.broker:
            try:
                if price > 0:
                    result = self.broker.create_limit_sell_order(symbol, qty, price)
                else:
                    result = self.broker.create_market_sell_order(symbol, qty)
                return result
            except Exception as e:
                logger.error(f"매도 실패 [{symbol}]: {e}")
                return None

        # 시뮬레이션
        if symbol not in self._sim_positions:
            return None

        pos = self._sim_positions[symbol]
        if pos["qty"] < qty:
            return None

        current = self.fetch_price(symbol)
        sell_price = price if price > 0 else current["price"]
        total_amount = sell_price * qty
        fee = int(total_amount * 0.00015)
        tax = int(total_amount * 0.0018)  # 거래세 0.18%

        self._sim_balance += (total_amount - fee - tax)
        pos["qty"] -= qty
        if pos["qty"] <= 0:
            del self._sim_positions[symbol]

        logger.info(f"[SIM] 매도: {symbol} {qty}주 @ {sell_price:,}원")
        return {"symbol": symbol, "qty": qty, "price": sell_price, "action": "SELL"}

    def get_positions(self) -> dict:
        """보유 포지션"""
        if self.broker and not self.paper_trading:
            try:
                return self.broker.fetch_balance()
            except Exception:
                pass
        return self._sim_positions.copy()
