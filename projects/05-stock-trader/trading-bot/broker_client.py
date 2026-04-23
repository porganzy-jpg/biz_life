"""
한국투자증권 API 클라이언트 v3.8

mojito SDK를 래핑하여 주식 매매 기능 제공.
데이터 소스 우선순위: mojito → yfinance(DataProvider) → 만료캐시.

v3.8 변경사항:
  - 실전 주문 후 체결 확인 (ACK polling)
  - 부분 체결 추적
  - 주문 거부 시 상세 에러 코드 파싱
  - 슬리피지 허용 범위 사전 검증

연결 모드 (API 키 타입에 따라):
  - 실전투자 키: mock=False (실전 서버 연결)
  - 모의투자 키: mock=True (모의 서버 연결)

매매 모드 (TRADING_MODE에 따라):
  - paper: 데이터는 실제 API, 주문은 시뮬레이션
  - live: 실제 주문 실행 (LIVE_TRADING_CONFIRMED=true 필요)
"""
import logging
import time
from datetime import datetime
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
        # 이중 안전장치: TRADING_MODE=live + LIVE_TRADING_CONFIRMED=true 둘 다 충족해야 실전 주문
        self.live_trading = (TRADING_MODE == "live" and LIVE_TRADING_CONFIRMED)

        # yfinance 데이터 제공자
        self.data_provider = DataProvider()

        # mojito SDK 연동 (API 키가 없으면 yfinance 전용 모드)
        self.broker = None
        if KIS_APP_KEY and KIS_APP_SECRET:
            try:
                import mojito
                # API 키 타입에 맞게 연결 (실전 키 → mock=False, 모의 키 → mock=True)
                self.broker = mojito.KoreaInvestment(
                    api_key=KIS_APP_KEY,
                    api_secret=KIS_APP_SECRET,
                    acc_no=KIS_ACCOUNT_NO,
                    mock=KIS_IS_PAPER,
                )
                api_mode = '모의' if KIS_IS_PAPER else '실전'
                trade_mode = '실전매매' if self.live_trading else '시뮬레이션(주문차단)'
                logger.info(f"한국투자증권 API 연결 완료 (API: {api_mode}, 매매: {trade_mode})")
            except Exception as e:
                logger.warning(f"한국투자증권 API 연결 실패: {e} (yfinance 전용 모드)")
        else:
            logger.info("API 키 미설정 - yfinance 데이터 + 시뮬레이션 모드로 실행")

        # paper_trading: live_trading의 반대 (하위 호환)
        self.paper_trading = not self.live_trading

        # 시뮬레이션 상태 (paper 모드 또는 API 미연결 시 사용)
        self._sim_balance = INITIAL_CAPITAL
        self._sim_positions = {}  # {종목코드: {qty, avg_price, name}}

        # WebSocket 클라이언트 (opt-in, v3.7)
        self._ws_client = None

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

    def enable_websocket(self, watchlist: list = None):
        """
        WebSocket 실시간 데이터 opt-in 활성화 (v3.7).

        기본은 폴링 모드. 이 메서드를 호출해야 WebSocket이 동작.

        Args:
            watchlist: [{"code": "005930", ...}, ...] 또는 ["005930", ...]
        """
        try:
            from websocket_client import KISWebSocketClient
            from config import KIS_APP_KEY, KIS_APP_SECRET

            self._ws_client = KISWebSocketClient(
                app_key=KIS_APP_KEY,
                app_secret=KIS_APP_SECRET,
            )

            # DataProvider 연동
            on_tick = self.data_provider.create_ws_bridge()
            self._ws_client.set_callbacks(on_tick=on_tick)

            # 구독 종목 등록
            if watchlist:
                symbols = []
                for item in watchlist:
                    if isinstance(item, dict):
                        symbols.append(item["code"])
                    else:
                        symbols.append(str(item))
                self._ws_client.subscribe(symbols)

            self._ws_client.start()
            logger.info(f"WebSocket 활성화: {len(watchlist or [])}종목 구독")
        except Exception as e:
            logger.warning(f"WebSocket 활성화 실패: {e} (폴링 모드 유지)")
            self._ws_client = None

    def fetch_price(self, symbol: str) -> Optional[dict]:
        """현재가 조회. 반환: {"price": int, "change": int, "change_pct": float, ...}"""
        # 0순위: WebSocket 틱 데이터 (60초 이내, v3.7)
        if self._ws_client:
            try:
                tick = self._ws_client.get_latest_tick(symbol)
                if tick and (datetime.now() - tick.timestamp).total_seconds() < 60:
                    return {
                        "price": int(tick.price),
                        "change": int(tick.change),
                        "change_pct": float(tick.change_pct),
                        "volume": int(tick.volume),
                        "high": 0, "low": 0, "open": 0,
                    }
            except Exception as e:
                logger.debug(f"WebSocket 틱 조회 실패 [{symbol}]: {e}")

        # 1순위: mojito API (실전/모의 모두)
        if self.broker:
            try:
                resp = self.broker.fetch_price(symbol)
                if resp and isinstance(resp, dict):
                    output = resp.get("output", resp)
                    if isinstance(output, dict) and "stck_prpr" in output:
                        return {
                            "price": int(output.get("stck_prpr", 0)),
                            "change": int(output.get("prdy_vrss", 0)),
                            "change_pct": float(output.get("prdy_ctrt", 0)),
                            "volume": int(output.get("acml_vol", 0)),
                            "high": int(output.get("stck_hgpr", 0)),
                            "low": int(output.get("stck_lwpr", 0)),
                            "open": int(output.get("stck_oprc", 0)),
                        }
            except Exception as e:
                logger.debug(f"mojito 현재가 실패 [{symbol}]: {e}")

        # 2순위: yfinance
        return self.data_provider.fetch_current_price(symbol)

    def get_balance(self) -> dict:
        """잔고 조회. 반환: {"cash": int, "total_eval": int}"""
        # mojito API로 실제 잔고 조회
        if self.broker:
            try:
                resp = self.broker.fetch_balance()
                if resp and isinstance(resp, dict):
                    parsed = self._parse_kis_balance(resp)
                    if parsed:
                        return parsed
            except Exception as e:
                logger.warning(f"잔고 조회 실패: {e} (시뮬레이션 폴백)")

        # 시뮬레이션 폴백
        pos_value = sum(
            p["qty"] * p["avg_price"] for p in self._sim_positions.values()
        )
        return {
            "cash": self._sim_balance,
            "total_eval": self._sim_balance + pos_value,
        }

    def _parse_kis_balance(self, resp: dict) -> Optional[dict]:
        """한투 API 잔고 응답 파싱 (output1: 보유종목, output2: 계좌요약)"""
        try:
            output2 = resp.get("output2", [])
            if isinstance(output2, list) and len(output2) > 0:
                summary = output2[0]
                cash = int(summary.get("dnca_tot_amt", 0))
                total = int(summary.get("tot_evlu_amt", 0))
                return {"cash": cash, "total_eval": total}
        except Exception:
            pass
        return None

    def buy(self, symbol: str, name: str, qty: int, price: int = 0) -> Optional[dict]:
        """
        매수 주문. live_trading=True일 때만 실제 주문, 아니면 시뮬레이션.

        v3.8.1: 시장가 미체결 시 현재가 기준 지정가로 1회 재시도
        """
        # 실전 매매 모드: 실제 주문 실행
        if self.live_trading and self.broker:
            return self._live_buy(symbol, name, qty, price, retry=0)

        # 시뮬레이션 모드: 실제 시세 기반으로 가상 매매
    MAX_BUY_RETRY = 1  # 미체결 시 최대 재시도 횟수

    def _live_buy(self, symbol: str, name: str, qty: int,
                  price: int = 0, retry: int = 0) -> Optional[dict]:
        """
        v3.8.1: 실전 매수 (미체결 시 지정가 재시도 포함)

        1차: 시장가 주문
        미체결 → 취소 → 현재가+1호가 지정가로 재시도 (1회)
        """
        try:
            if price > 0:
                result = self.broker.create_limit_buy_order(symbol, qty, price)
                order_desc = f"{price:,}원 지정가"
            else:
                result = self.broker.create_market_buy_order(symbol, qty)
                order_desc = "시장가"

            if not result:
                logger.error(f"[LIVE] 매수 주문 응답 없음: {name}({symbol})")
                return None

            # 주문 응답 코드 확인
            rt_cd = result.get("rt_cd", "")
            if rt_cd != "0":
                msg = result.get("msg1", result.get("msg", "알 수 없는 오류"))
                logger.error(f"[LIVE] 매수 주문 거부: {name}({symbol}) - {msg}")
                return None

            # 체결 확인
            order_no = self._extract_order_no(result)
            if order_no:
                confirmed = self._confirm_order_fill(
                    symbol, order_no, qty, side="BUY"
                )
                if confirmed:
                    result["confirmed"] = True
                    result["filled_qty"] = confirmed.get("filled_qty", qty)
                    result["filled_price"] = confirmed.get("filled_price", price)
                    if confirmed["filled_qty"] < qty:
                        logger.warning(
                            f"[LIVE] 부분 체결: {name}({symbol}) "
                            f"{confirmed['filled_qty']}/{qty}주"
                        )
                    logger.info(
                        f"[LIVE] 매수 체결 완료: {name}({symbol}) {qty}주 "
                        f"@ {confirmed['filled_price']:,.0f}원"
                    )
                    return result

                # 미체결: 주문 취소 후 재시도
                result["confirmed"] = False
                logger.warning(
                    f"[LIVE] 매수 미체결: {name}({symbol}) {order_desc} "
                    f"주문번호={order_no}"
                )

                # 기존 주문 취소
                try:
                    self.broker.cancel_order(
                        org_no="", order_no=order_no,
                        quantity=qty, total=True,
                    )
                    logger.info(f"[LIVE] 미체결 주문 취소: {name}({symbol})")
                    time.sleep(1)
                except Exception as cancel_err:
                    logger.warning(
                        f"[LIVE] 주문 취소 실패: {name}({symbol}) - {cancel_err}"
                    )

                # 재시도: 현재가 기준 +1% 지정가로 재매수
                if retry < self.MAX_BUY_RETRY:
                    current = self.fetch_price(symbol)
                    if current and current.get("price", 0) > 0:
                        # 현재가 + 1% (호가 단위 올림)
                        retry_price = self._round_to_tick(
                            int(current["price"] * 1.01), symbol
                        )
                        logger.info(
                            f"[LIVE] 매수 재시도 ({retry+1}/{self.MAX_BUY_RETRY}): "
                            f"{name}({symbol}) {qty}주 @ {retry_price:,}원 지정가"
                        )
                        return self._live_buy(
                            symbol, name, qty, retry_price, retry=retry + 1
                        )

                return result

            # 주문번호 추출 실패
            logger.error(
                f"[LIVE] 주문번호 추출 실패: {name}({symbol}) 응답={result}"
            )
            return None

        except Exception as e:
            logger.error(f"[LIVE] 매수 실패 [{symbol}]: {e}")
            return None

    @staticmethod
    def _round_to_tick(price: int, symbol: str = "") -> int:
        """한국 주식 호가 단위에 맞게 올림 처리"""
        if price < 2000:
            return ((price + 0) // 1) * 1
        elif price < 5000:
            return ((price + 4) // 5) * 5
        elif price < 20000:
            return ((price + 9) // 10) * 10
        elif price < 50000:
            return ((price + 49) // 50) * 50
        elif price < 200000:
            return ((price + 99) // 100) * 100
        elif price < 500000:
            return ((price + 499) // 500) * 500
        else:
            return ((price + 999) // 1000) * 1000

    def _live_sell(self, symbol: str, qty: int, price: int = 0,
                   retry: int = 0) -> Optional[dict]:
        """
        v3.8.1: 실전 매도 (미체결 시 현재가-1% 지정가 재시도)
        """
        try:
            if price > 0:
                result = self.broker.create_limit_sell_order(symbol, qty, price)
                order_desc = f"{price:,}원 지정가"
            else:
                result = self.broker.create_market_sell_order(symbol, qty)
                order_desc = "시장가"

            if not result:
                logger.error(f"[LIVE] 매도 주문 응답 없음: {symbol}")
                return None

            rt_cd = result.get("rt_cd", "")
            if rt_cd != "0":
                msg = result.get("msg1", result.get("msg", "알 수 없는 오류"))
                logger.error(f"[LIVE] 매도 주문 거부: {symbol} - {msg}")
                return None

            order_no = self._extract_order_no(result)
            if order_no:
                confirmed = self._confirm_order_fill(
                    symbol, order_no, qty, side="SELL"
                )
                if confirmed:
                    result["confirmed"] = True
                    result["filled_qty"] = confirmed.get("filled_qty", qty)
                    result["filled_price"] = confirmed.get("filled_price", price)
                    logger.info(
                        f"[LIVE] 매도 체결 완료: {symbol} {qty}주 "
                        f"@ {confirmed.get('filled_price', 0):,.0f}원"
                    )
                    return result

                # 미체결: 취소 후 재시도
                result["confirmed"] = False
                logger.warning(
                    f"[LIVE] 매도 미체결: {symbol} {order_desc} "
                    f"주문번호={order_no}"
                )
                try:
                    self.broker.cancel_order(
                        org_no="", order_no=order_no,
                        quantity=qty, total=True,
                    )
                    logger.info(f"[LIVE] 미체결 매도 주문 취소: {symbol}")
                    time.sleep(1)
                except Exception as cancel_err:
                    logger.warning(f"[LIVE] 매도 취소 실패: {symbol} - {cancel_err}")

                # 재시도: 현재가 -1% 지정가
                if retry < self.MAX_BUY_RETRY:
                    current = self.fetch_price(symbol)
                    if current and current.get("price", 0) > 0:
                        retry_price = self._round_to_tick(
                            int(current["price"] * 0.99), symbol
                        )
                        logger.info(
                            f"[LIVE] 매도 재시도 ({retry+1}): "
                            f"{symbol} {qty}주 @ {retry_price:,}원 지정가"
                        )
                        return self._live_sell(
                            symbol, qty, retry_price, retry=retry + 1
                        )

                return result

            logger.error(f"[LIVE] 매도 주문번호 추출 실패: {symbol}")
            return None

        except Exception as e:
            logger.error(f"[LIVE] 매도 실패 [{symbol}]: {e}")
            return None

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
        """매도 주문. live_trading=True일 때만 실제 주문, 아니면 시뮬레이션."""
        # 실전 매매 모드: 실제 주문 실행
        if self.live_trading and self.broker:
            return self._live_sell(symbol, qty, price)

        # 시뮬레이션 모드
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
        """보유 포지션. live 모드에서는 실제 API, paper 모드에서는 시뮬레이션 포지션."""
        # live 모드: 실제 API 보유종목 조회
        if self.live_trading and self.broker:
            try:
                resp = self.broker.fetch_balance()
                if resp and isinstance(resp, dict):
                    positions = self._parse_kis_positions(resp)
                    if positions is not None:
                        return positions
            except Exception as e:
                logger.warning(f"포지션 조회 실패: {e} (DB 포지션 폴백 필요)")

        return self._sim_positions.copy()

    def _parse_kis_positions(self, resp: dict) -> Optional[dict]:
        """한투 API 보유종목 파싱 (output1 리스트)"""
        try:
            positions = {}
            output1 = resp.get("output1", [])
            if isinstance(output1, list):
                for item in output1:
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
            return positions
        except Exception:
            return None

    def preload_data(self, watchlist: list) -> dict:
        """워치리스트 데이터 미리 로드"""
        return self.data_provider.preload_watchlist(watchlist)

    # ── v3.8: 주문 체결 확인 ──

    @staticmethod
    def _extract_order_no(result: dict) -> Optional[str]:
        """API 응답에서 주문번호 추출."""
        if not isinstance(result, dict):
            return None
        # mojito 응답 형식: {"output": {"ODNO": "주문번호", ...}}
        output = result.get("output", result)
        if isinstance(output, dict):
            return output.get("ODNO") or output.get("odno") or output.get("order_no")
        return None

    def _confirm_order_fill(self, symbol: str, order_no: str,
                            expected_qty: int, side: str,
                            max_wait_sec: int = 30) -> Optional[dict]:
        """
        v3.8.1: 주문 체결을 확인한다.

        1차: fetch_open_order로 미체결 주문 존재 여부 확인
        2차: fetch_balance로 잔고 변동 확인 (2회 시도)

        Returns:
            dict: {"filled_qty": int, "filled_price": float} or None (미체결)
        """
        if not self.broker:
            return None

        # 체결 반영 대기 (한투 API는 체결 후 잔고 반영에 1~3초 소요)
        time.sleep(3)

        # 1차: 미체결 주문 조회 — 주문이 남아있으면 아직 미체결
        try:
            open_orders = self.broker.fetch_open_order({
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
                "INQR_DVSN_1": "0",
                "INQR_DVSN_2": "0",
            })
            if open_orders and isinstance(open_orders, dict):
                output = open_orders.get("output", [])
                if isinstance(output, list):
                    for order in output:
                        if (order.get("odno") == order_no or
                                order.get("ODNO") == order_no):
                            remaining = int(order.get("psbl_qty", 0) or
                                           order.get("rmn_qty", 0))
                            if remaining > 0:
                                logger.warning(
                                    f"미체결 주문 발견 [{symbol}] "
                                    f"주문번호={order_no} 잔량={remaining}주"
                                )
                                return None
        except Exception as e:
            logger.debug(f"미체결 조회 오류 [{symbol}]: {e}")

        # 2차: 잔고로 체결 확인 (2회 시도, 간격 3초)
        for attempt in range(2):
            try:
                resp = self.broker.fetch_balance()
                if not resp or not isinstance(resp, dict):
                    time.sleep(3)
                    continue

                positions = self._parse_kis_positions(resp)

                if side == "BUY":
                    if positions and symbol in positions:
                        pos = positions[symbol]
                        if pos["qty"] > 0:
                            logger.info(
                                f"체결 확인 [{symbol}] {pos['qty']}주 "
                                f"@ {pos['avg_price']}원 (잔고 확인)"
                            )
                            return {
                                "filled_qty": min(pos["qty"], expected_qty),
                                "filled_price": pos["avg_price"],
                            }
                elif side == "SELL":
                    if not positions or symbol not in positions:
                        logger.info(f"매도 체결 확인 [{symbol}] (포지션 소멸)")
                        return {"filled_qty": expected_qty, "filled_price": 0}

            except Exception as e:
                logger.debug(f"잔고 확인 시도 {attempt+1} 실패 [{symbol}]: {e}")

            if attempt < 1:
                time.sleep(3)

        logger.warning(f"체결 확인 실패 [{symbol}] 주문번호={order_no}")
        return None
