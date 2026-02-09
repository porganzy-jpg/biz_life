"""
Upbit client wrapper with paper trading support.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

try:
    import pyupbit
except ImportError:
    pyupbit = None

from . import config

logger = logging.getLogger("scalper.client")


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

    # ── Market data (always real) ──

    def get_ohlcv(self, market: str, interval: str = "minute1", count: int = 60) -> Optional[pd.DataFrame]:
        """Fetch OHLCV candles from Upbit."""
        try:
            if pyupbit is None:
                return self._fake_ohlcv(market, count)

            df = pyupbit.get_ohlcv(market, interval=interval, count=count)
            if df is None or df.empty:
                return None

            df = df.reset_index()
            # pyupbit returns: index(datetime), open, high, low, close, volume, value
            if "value" in df.columns:
                df = df.drop(columns=["value"])
            df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
            return df
        except Exception as e:
            logger.error(f"OHLCV fetch failed for {market}: {e}")
            return None

    def get_current_price(self, market: str) -> Optional[float]:
        """Get current price."""
        try:
            if pyupbit is None:
                return None
            return pyupbit.get_current_price(market)
        except Exception as e:
            logger.error(f"Price fetch failed for {market}: {e}")
            return None

    def get_orderbook(self, market: str) -> Optional[dict]:
        """Get order book for slippage estimation."""
        try:
            if pyupbit is None:
                return None
            books = pyupbit.get_orderbook(market)
            if books and len(books) > 0:
                return books[0] if isinstance(books, list) else books
            return None
        except Exception as e:
            logger.error(f"Orderbook fetch failed: {e}")
            return None

    # ── Trading ──

    def buy_market(self, market: str, krw_amount: float) -> Optional[dict]:
        """Market buy order."""
        if self.paper:
            return self._paper_buy(market, krw_amount)

        try:
            result = self.upbit.buy_market_order(market, krw_amount)
            logger.info(f"LIVE BUY {market}: {krw_amount:,.0f} KRW -> {result}")
            return result
        except Exception as e:
            logger.error(f"Buy failed {market}: {e}")
            return None

    def sell_market(self, market: str, amount: float) -> Optional[dict]:
        """Market sell order."""
        if self.paper:
            return self._paper_sell(market, amount)

        try:
            result = self.upbit.sell_market_order(market, amount)
            logger.info(f"LIVE SELL {market}: {amount} -> {result}")
            return result
        except Exception as e:
            logger.error(f"Sell failed {market}: {e}")
            return None

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
