"""
한국투자증권 API 클라이언트

mojito SDK를 래핑하여 주식 매매 기능 제공.
데이터 소스 우선순위: mojito → yfinance(DataProvider) → 만료캐시.
모의투자 / 실전투자 모드 전환 가능.
"""
import logging
from typing import Optional

import pandas as pd

from config import (
    KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO, KIS_IS_PAPER,
    TRADING_MODE, LIVE_TRADING_CONFIRMED, INITIAL_CAPITAL,
)
from data_provider import DataProvider

logger = logging.getLogger(__name__)


class BrokerClient:
    """한국투자증권 API 클라이언트"""

    def __init__(self, paper_trading: bool = True):
        # 이중 안전장치: TRADING_MODE=live + LIVE_TRADING_CONFIRMED=true 둘 다 충족해야 실전
        is_live = (TRADING_MODE == "live" and LIVE_TRADING_CONFIRMED)
        if is_live:
            self.paper_trading = False
        else:
            self.paper_trading = paper_trading or KIS_IS_PAPER

        # yfinance 데이터 제공자
        self.data_provider = DataProvider()

        # mojito SDK 연동 (API 키가 없으면 yfinance 전용 모드)
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
                mode_str = '모의' if self.paper_trading else '실전'
                logger.info(f"한국투자증권 API 연결 완료 ({mode_str})")
            except Exception as e:
                logger.warning(f"한국투자증권 API 연결 실패: {e} (yfinance 전용 모드)")
        else:
            logger.info("API 키 미설정 - yfinance 데이터 + 시뮬레이션 모드로 실행")

        # 시뮬레이션 상태 (API 키 없을 때 사용)
        self._sim_balance = INITIAL_CAPITAL
        self._sim_positions = {}  # {종목코드: {qty, avg_price, name}}

    def fetch_ohlcv(self, symbol: str, period: str = "D", count: int = 200) -> pd.DataFrame:
        """
        OHLCV 데이터 조회.
        우선순위: mojito API → yfinance → 만료 캐시.
        """
        # 1순위: mojito API
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
                logger.debug(f"mojito OHLCV 실패 [{symbol}]: {e} → yfinance 폴백")

        # 2순위: yfinance (DataProvider)
        df = self.data_provider.fetch_ohlcv(symbol, days=count)
        if df is not None and not df.empty:
            return df.tail(count)

        logger.error(f"OHLCV 데이터 없음 [{symbol}]: mojito, yfinance 모두 실패")
        return pd.DataFrame()

    def fetch_price(self, symbol: str) -> Optional[dict]:
        """현재가 조회"""
        # 1순위: mojito API
        if self.broker:
            try:
                price = self.broker.fetch_price(symbol)
                if price:
                    return price
            except Exception as e:
                logger.debug(f"mojito 현재가 실패 [{symbol}]: {e}")

        # 2순위: yfinance
        return self.data_provider.fetch_current_price(symbol)

    def get_balance(self) -> dict:
        """잔고 조회"""
        # mojito API가 있으면 (페이퍼 모드 포함) API 조회
        if self.broker:
            try:
                bal = self.broker.fetch_balance()
                if bal:
                    # mojito 반환 형식 파싱
                    if isinstance(bal, dict):
                        return bal
                    # 리스트 형태일 경우 파싱
                    if isinstance(bal, list) and len(bal) > 0:
                        return self._parse_kis_balance(bal)
            except Exception as e:
                logger.warning(f"잔고 조회 실패: {e} (시뮬레이션 폴백)")

        # 시뮬레이션
        pos_value = sum(
            p["qty"] * p["avg_price"] for p in self._sim_positions.values()
        )
        return {
            "cash": self._sim_balance,
            "total_eval": self._sim_balance + pos_value,
        }

    def _parse_kis_balance(self, bal_data) -> dict:
        """한투 API 잔고 응답 파싱"""
        try:
            if isinstance(bal_data, dict):
                cash = int(bal_data.get("dnca_tot_amt", 0) or
                          bal_data.get("cash", 0))
                total = int(bal_data.get("tot_evlu_amt", 0) or
                           bal_data.get("total_eval", cash))
                return {"cash": cash, "total_eval": total}
        except Exception:
            pass
        return {"cash": self._sim_balance, "total_eval": self._sim_balance}

    def buy(self, symbol: str, name: str, qty: int, price: int = 0) -> Optional[dict]:
        """매수 주문"""
        if self.broker:
            try:
                if price > 0:
                    result = self.broker.create_limit_buy_order(symbol, qty, price)
                else:
                    result = self.broker.create_market_buy_order(symbol, qty)
                if result:
                    logger.info(f"매수 주문 제출: {name}({symbol}) {qty}주 @ {price if price else '시장가'}")
                return result
            except Exception as e:
                logger.error(f"매수 실패 [{symbol}]: {e}")
                return None

        # 시뮬레이션
        price_info = self.fetch_price(symbol)
        if not price_info:
            return None

        buy_price = price if price > 0 else price_info["price"]
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
                if result:
                    logger.info(f"매도 주문 제출: {symbol} {qty}주 @ {price if price else '시장가'}")
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

        price_info = self.fetch_price(symbol)
        if not price_info:
            return None

        sell_price = price if price > 0 else price_info["price"]
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
        # mojito API가 있으면 (페이퍼 포함) API 조회
        if self.broker:
            try:
                bal = self.broker.fetch_balance()
                if bal:
                    positions = self._parse_kis_positions(bal)
                    if positions is not None:
                        return positions
            except Exception as e:
                logger.debug(f"포지션 조회 실패: {e}")

        return self._sim_positions.copy()

    def _parse_kis_positions(self, bal_data) -> Optional[dict]:
        """한투 API 보유종목 파싱"""
        try:
            positions = {}
            if isinstance(bal_data, list):
                for item in bal_data:
                    if not isinstance(item, dict):
                        continue
                    symbol = item.get("pdno", "")
                    qty = int(item.get("hldg_qty", 0))
                    if symbol and qty > 0:
                        positions[symbol] = {
                            "qty": qty,
                            "avg_price": int(float(item.get("pchs_avg_pric", 0))),
                            "name": item.get("prdt_name", ""),
                        }
            return positions if positions is not None else {}
        except Exception:
            return None

    def preload_data(self, watchlist: list) -> dict:
        """워치리스트 데이터 미리 로드"""
        return self.data_provider.preload_watchlist(watchlist)
