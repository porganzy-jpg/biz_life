"""
StockBot 백테스터

전략의 과거 성과를 검증합니다.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-bot"))
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np

from stock_selector import StockSelectorEnsemble
from broker_client import BrokerClient


class StockBacktester:
    """주식 백테스터"""

    def __init__(self, initial_capital: float = 100_000_000):
        self.initial_capital = initial_capital
        self.client = BrokerClient(paper_trading=True)

    def run_backtest(self, symbol: str, name: str, lookback: int = 200,
                     trade_ratio: float = 0.1, stop_loss: float = -5.0,
                     take_profit: float = 15.0) -> dict:
        """단일 종목 백테스트"""
        df = self.client.fetch_ohlcv(symbol, count=lookback)
        if df is None or len(df) < 60:
            return {"error": "데이터 부족"}

        selector = StockSelectorEnsemble()
        capital = self.initial_capital
        position = None  # {qty, buy_price}
        trades = []
        equity_curve = []

        for i in range(60, len(df)):
            window = df.iloc[:i+1]
            current_price = window.iloc[-1]["close"]

            portfolio_value = capital
            if position:
                portfolio_value += position["qty"] * current_price

            equity_curve.append(portfolio_value)

            # 손절/익절
            if position:
                pnl_pct = (current_price - position["buy_price"]) / position["buy_price"] * 100

                if pnl_pct <= stop_loss:
                    capital += position["qty"] * current_price * 0.998  # 세금+수수료
                    trades.append({"action": "STOP_LOSS", "pnl_pct": round(pnl_pct, 2), "price": current_price})
                    position = None
                    continue

                if pnl_pct >= take_profit:
                    capital += position["qty"] * current_price * 0.998
                    trades.append({"action": "TAKE_PROFIT", "pnl_pct": round(pnl_pct, 2), "price": current_price})
                    position = None
                    continue

            # 전략 분석
            try:
                result = selector.evaluate(window, symbol, name)
            except Exception:
                continue

            if result["action"] == "BUY" and position is None:
                trade_amount = capital * trade_ratio
                qty = int(trade_amount / current_price)
                if qty > 0:
                    capital -= qty * current_price
                    position = {"qty": qty, "buy_price": current_price}
                    trades.append({"action": "BUY", "price": current_price, "qty": qty})

            elif result["action"] == "SELL" and position is not None:
                pnl_pct = (current_price - position["buy_price"]) / position["buy_price"] * 100
                capital += position["qty"] * current_price * 0.998
                trades.append({"action": "SELL", "pnl_pct": round(pnl_pct, 2), "price": current_price})
                position = None

        # 잔여 포지션 정리
        if position:
            final_price = df.iloc[-1]["close"]
            capital += position["qty"] * final_price * 0.998

        total_return = (capital - self.initial_capital) / self.initial_capital * 100
        sell_trades = [t for t in trades if "pnl_pct" in t]
        winning = [t for t in sell_trades if t["pnl_pct"] > 0]

        # 최대 낙폭
        max_drawdown = 0
        if equity_curve:
            peak = equity_curve[0]
            for v in equity_curve:
                if v > peak:
                    peak = v
                dd = (peak - v) / peak * 100
                max_drawdown = max(max_drawdown, dd)

        return {
            "symbol": symbol,
            "name": name,
            "initial_capital": self.initial_capital,
            "final_capital": round(capital),
            "total_return_pct": round(total_return, 2),
            "total_trades": len(sell_trades),
            "win_rate": round(len(winning) / max(len(sell_trades), 1) * 100, 1),
            "max_drawdown_pct": round(max_drawdown, 2),
            "trades": trades[-20:],
        }


def main():
    print("=" * 60)
    print("  StockBot Backtester v1.0")
    print("=" * 60)

    backtester = StockBacktester()
    stocks = [
        ("005930", "삼성전자"),
        ("000660", "SK하이닉스"),
        ("035420", "NAVER"),
    ]

    for code, name in stocks:
        result = backtester.run_backtest(code, name)
        print(f"\n  {name} ({code})")
        print(f"  수익률: {result.get('total_return_pct', 0):+.2f}%")
        print(f"  거래: {result.get('total_trades', 0)}건 | 승률: {result.get('win_rate', 0)}%")
        print(f"  최대낙폭: {result.get('max_drawdown_pct', 0):.2f}%")
        print(f"  최종자산: {result.get('final_capital', 0):,}원")


if __name__ == "__main__":
    main()
