"""
거래소 연결 클라이언트
ccxt 라이브러리를 사용하여 Upbit/Binance 통합 관리
"""
import ccxt
import logging
from config import (
    EXCHANGE, UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY,
    BINANCE_API_KEY, BINANCE_SECRET_KEY
)

logger = logging.getLogger(__name__)


class ExchangeClient:
    """거래소 통합 클라이언트"""

    def __init__(self, exchange_name: str = None, paper_trading: bool = True):
        self.exchange_name = exchange_name or EXCHANGE
        self.paper_trading = paper_trading
        self.exchange = self._create_exchange()
        self._paper_balance = {
            "KRW": 10_000_000,  # 모의투자 시작 자금: 1000만원
        }
        self._paper_positions = {}

    def _create_exchange(self):
        """거래소 인스턴스 생성"""
        if self.exchange_name == "upbit":
            return ccxt.upbit({
                "apiKey": UPBIT_ACCESS_KEY,
                "secret": UPBIT_SECRET_KEY,
                "options": {"defaultType": "spot"},
            })
        elif self.exchange_name == "binance":
            return ccxt.binance({
                "apiKey": BINANCE_API_KEY,
                "secret": BINANCE_SECRET_KEY,
                "options": {"defaultType": "spot"},
            })
        else:
            raise ValueError(f"지원하지 않는 거래소: {self.exchange_name}")

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200):
        """
        캔들(OHLCV) 데이터 조회

        Args:
            symbol: 마켓 심볼 (예: "KRW-BTC" → ccxt 형식으로 변환)
            timeframe: 캔들 단위 ("1m", "5m", "15m", "1h", "4h", "1d")
            limit: 조회할 캔들 수

        Returns:
            list: [[timestamp, open, high, low, close, volume], ...]
        """
        ccxt_symbol = self._convert_symbol(symbol)
        try:
            ohlcv = self.exchange.fetch_ohlcv(ccxt_symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"OHLCV 조회 실패 [{symbol}]: {e}")
            return []

    def fetch_ticker(self, symbol: str):
        """현재가 조회"""
        ccxt_symbol = self._convert_symbol(symbol)
        try:
            return self.exchange.fetch_ticker(ccxt_symbol)
        except Exception as e:
            logger.error(f"현재가 조회 실패 [{symbol}]: {e}")
            return None

    def fetch_balance(self):
        """잔고 조회"""
        if self.paper_trading:
            return self._paper_balance.copy()
        try:
            balance = self.exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            return {}

    def buy(self, symbol: str, amount: float, price: float = None):
        """
        매수 주문

        Args:
            symbol: 마켓 심볼
            amount: 매수 금액 (KRW)
            price: 지정가 (None이면 시장가)
        """
        if self.paper_trading:
            return self._paper_buy(symbol, amount)

        ccxt_symbol = self._convert_symbol(symbol)
        try:
            if price:
                qty = amount / price
                order = self.exchange.create_limit_buy_order(ccxt_symbol, qty, price)
            else:
                order = self.exchange.create_market_buy_order(ccxt_symbol, amount)
            logger.info(f"매수 주문 완료: {symbol} / {amount}원")
            return order
        except Exception as e:
            logger.error(f"매수 주문 실패 [{symbol}]: {e}")
            return None

    def sell(self, symbol: str, qty: float, price: float = None):
        """
        매도 주문

        Args:
            symbol: 마켓 심볼
            qty: 매도 수량
            price: 지정가 (None이면 시장가)
        """
        if self.paper_trading:
            return self._paper_sell(symbol, qty)

        ccxt_symbol = self._convert_symbol(symbol)
        try:
            if price:
                order = self.exchange.create_limit_sell_order(ccxt_symbol, qty, price)
            else:
                order = self.exchange.create_market_sell_order(ccxt_symbol, qty)
            logger.info(f"매도 주문 완료: {symbol} / {qty}개")
            return order
        except Exception as e:
            logger.error(f"매도 주문 실패 [{symbol}]: {e}")
            return None

    def _paper_buy(self, symbol: str, amount: float):
        """모의 매수"""
        ticker = self.fetch_ticker(symbol)
        if not ticker:
            return None

        current_price = ticker["last"]
        qty = amount / current_price
        fee = amount * 0.0005  # 업비트 수수료 0.05%

        if self._paper_balance.get("KRW", 0) < amount + fee:
            logger.warning("모의투자: 잔고 부족")
            return None

        self._paper_balance["KRW"] -= (amount + fee)
        coin = symbol.split("-")[1] if "-" in symbol else symbol
        self._paper_balance[coin] = self._paper_balance.get(coin, 0) + qty
        self._paper_positions[symbol] = {
            "qty": self._paper_positions.get(symbol, {}).get("qty", 0) + qty,
            "avg_price": current_price,
            "buy_amount": amount,
        }

        logger.info(f"[모의] 매수: {symbol} / {qty:.8f}개 @ {current_price:,.0f}원")
        return {"symbol": symbol, "qty": qty, "price": current_price, "type": "buy"}

    def _paper_sell(self, symbol: str, qty: float):
        """모의 매도"""
        ticker = self.fetch_ticker(symbol)
        if not ticker:
            return None

        current_price = ticker["last"]
        amount = qty * current_price
        fee = amount * 0.0005

        coin = symbol.split("-")[1] if "-" in symbol else symbol
        if self._paper_balance.get(coin, 0) < qty:
            logger.warning("모의투자: 보유 수량 부족")
            return None

        self._paper_balance[coin] -= qty
        self._paper_balance["KRW"] += (amount - fee)

        if symbol in self._paper_positions:
            self._paper_positions[symbol]["qty"] -= qty
            if self._paper_positions[symbol]["qty"] <= 0:
                del self._paper_positions[symbol]

        logger.info(f"[모의] 매도: {symbol} / {qty:.8f}개 @ {current_price:,.0f}원")
        return {"symbol": symbol, "qty": qty, "price": current_price, "type": "sell"}

    def _convert_symbol(self, symbol: str) -> str:
        """업비트 형식(KRW-BTC) → ccxt 형식(BTC/KRW) 변환"""
        if "-" in symbol:
            parts = symbol.split("-")
            return f"{parts[1]}/{parts[0]}"
        return symbol

    def get_positions(self):
        """현재 보유 포지션 조회"""
        if self.paper_trading:
            return self._paper_positions.copy()
        # 실전매매 시 구현
        return {}
