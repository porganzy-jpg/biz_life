"""
CryptoBot 백테스팅 엔진

과거 데이터를 기반으로 전략의 성과를 검증합니다.
실전 매매 전에 반드시 백테스트를 수행하여 전략의 유효성을 확인하세요.
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-bot"))

import pandas as pd
import numpy as np

from base_strategy import BaseStrategy, Signal
from bollinger_rsi_strategy import BollingerRSIStrategy
from volatility_breakout_strategy import VolatilityBreakoutStrategy
from macd_strategy import MACDStrategy
from exchange_client import ExchangeClient


class Backtester:
    """전략 백테스팅 엔진"""

    def __init__(self, initial_capital: float = 10_000_000):
        """
        Args:
            initial_capital: 초기 자본금 (KRW)
        """
        self.initial_capital = initial_capital
        self.client = ExchangeClient(paper_trading=True)

    def fetch_historical_data(self, symbol: str, timeframe: str = "1h",
                               limit: int = 500) -> pd.DataFrame:
        """거래소에서 과거 데이터 조회"""
        ohlcv = self.client.fetch_ohlcv(symbol, timeframe, limit)
        if not ohlcv:
            raise ValueError(f"데이터 조회 실패: {symbol}")

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df

    def run_backtest(self, strategy: BaseStrategy, df: pd.DataFrame,
                     symbol: str, trade_ratio: float = 0.1,
                     stop_loss: float = -3.0, take_profit: float = 5.0) -> dict:
        """
        전략 백테스트 실행

        Args:
            strategy: 테스트할 전략
            df: OHLCV DataFrame
            symbol: 마켓 심볼
            trade_ratio: 1회 매매 비율
            stop_loss: 손절 퍼센트
            take_profit: 익절 퍼센트

        Returns:
            dict: 백테스트 결과
        """
        capital = self.initial_capital
        position = None  # {"qty": float, "buy_price": float}
        trades = []
        equity_curve = []

        for i in range(50, len(df)):  # 최소 50개 데이터 필요
            window = df.iloc[:i+1]
            current_price = window.iloc[-1]["close"]
            current_time = window.index[-1]

            # 현재 포트폴리오 가치
            portfolio_value = capital
            if position:
                portfolio_value += position["qty"] * current_price

            equity_curve.append({
                "timestamp": str(current_time),
                "value": portfolio_value,
            })

            # 포지션이 있으면 손절/익절 체크
            if position:
                pnl_pct = (current_price - position["buy_price"]) / position["buy_price"] * 100

                if pnl_pct <= stop_loss:
                    # 손절
                    sell_amount = position["qty"] * current_price * 0.9995  # 수수료
                    capital += sell_amount
                    trades.append({
                        "timestamp": str(current_time),
                        "action": "STOP_LOSS",
                        "price": current_price,
                        "pnl_pct": round(pnl_pct, 2),
                        "capital": round(capital, 0),
                    })
                    position = None
                    continue

                if pnl_pct >= take_profit:
                    # 익절
                    sell_amount = position["qty"] * current_price * 0.9995
                    capital += sell_amount
                    trades.append({
                        "timestamp": str(current_time),
                        "action": "TAKE_PROFIT",
                        "price": current_price,
                        "pnl_pct": round(pnl_pct, 2),
                        "capital": round(capital, 0),
                    })
                    position = None
                    continue

            # 전략 분석
            try:
                signal = strategy.analyze(window, symbol)
            except Exception:
                continue

            if signal.action == Signal.BUY and position is None:
                # 매수
                trade_amount = capital * trade_ratio
                if trade_amount < 5000:
                    continue
                qty = (trade_amount * 0.9995) / current_price  # 수수료 차감
                capital -= trade_amount
                position = {"qty": qty, "buy_price": current_price}
                trades.append({
                    "timestamp": str(current_time),
                    "action": "BUY",
                    "price": current_price,
                    "amount": trade_amount,
                    "capital": round(capital, 0),
                })

            elif signal.action == Signal.SELL and position is not None:
                # 매도
                pnl_pct = (current_price - position["buy_price"]) / position["buy_price"] * 100
                sell_amount = position["qty"] * current_price * 0.9995
                capital += sell_amount
                trades.append({
                    "timestamp": str(current_time),
                    "action": "SELL",
                    "price": current_price,
                    "pnl_pct": round(pnl_pct, 2),
                    "capital": round(capital, 0),
                })
                position = None

        # 잔여 포지션 정리
        if position:
            final_price = df.iloc[-1]["close"]
            pnl_pct = (final_price - position["buy_price"]) / position["buy_price"] * 100
            capital += position["qty"] * final_price * 0.9995

        # 결과 집계
        total_trades = len([t for t in trades if t["action"] in ("SELL", "STOP_LOSS", "TAKE_PROFIT")])
        winning_trades = len([t for t in trades if t.get("pnl_pct", 0) > 0])
        losing_trades = len([t for t in trades if t.get("pnl_pct", 0) < 0])

        total_return = ((capital - self.initial_capital) / self.initial_capital) * 100

        pnl_list = [t.get("pnl_pct", 0) for t in trades if "pnl_pct" in t]
        avg_pnl = np.mean(pnl_list) if pnl_list else 0
        max_profit = max(pnl_list) if pnl_list else 0
        max_loss = min(pnl_list) if pnl_list else 0

        # 최대 낙폭 계산
        equity_values = [e["value"] for e in equity_curve]
        if equity_values:
            peak = equity_values[0]
            max_drawdown = 0
            for v in equity_values:
                if v > peak:
                    peak = v
                dd = (peak - v) / peak * 100
                if dd > max_drawdown:
                    max_drawdown = dd
        else:
            max_drawdown = 0

        return {
            "strategy": strategy.name,
            "symbol": symbol,
            "period": f"{df.index[0]} ~ {df.index[-1]}",
            "initial_capital": self.initial_capital,
            "final_capital": round(capital, 0),
            "total_return_pct": round(total_return, 2),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(winning_trades / max(total_trades, 1) * 100, 1),
            "avg_pnl_pct": round(avg_pnl, 2),
            "max_profit_pct": round(max_profit, 2),
            "max_loss_pct": round(max_loss, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "trades": trades[-20:],  # 최근 20건만
            "equity_curve_summary": {
                "start": equity_values[0] if equity_values else 0,
                "end": equity_values[-1] if equity_values else 0,
                "min": min(equity_values) if equity_values else 0,
                "max": max(equity_values) if equity_values else 0,
            },
        }

    def compare_strategies(self, symbol: str, timeframe: str = "1h",
                            limit: int = 500) -> list:
        """모든 전략 비교"""
        df = self.fetch_historical_data(symbol, timeframe, limit)

        strategies = [
            BollingerRSIStrategy(),
            VolatilityBreakoutStrategy(),
            MACDStrategy(),
        ]

        results = []
        for strategy in strategies:
            try:
                result = self.run_backtest(strategy, df, symbol)
                results.append(result)
            except Exception as e:
                print(f"전략 [{strategy.name}] 오류: {e}")

        return results


def main():
    """백테스트 실행"""
    print("=" * 60)
    print("  CryptoBot Backtester v1.0")
    print("=" * 60)

    backtester = Backtester(initial_capital=10_000_000)

    symbols = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]

    for symbol in symbols:
        print(f"\n{'─' * 50}")
        print(f"  Backtesting: {symbol}")
        print(f"{'─' * 50}")

        try:
            results = backtester.compare_strategies(symbol, timeframe="1h", limit=500)

            for r in results:
                print(f"\n  Strategy: {r['strategy']}")
                print(f"  Return: {r['total_return_pct']:+.2f}%")
                print(f"  Trades: {r['total_trades']} (Win: {r['winning_trades']}, Loss: {r['losing_trades']})")
                print(f"  Win Rate: {r['win_rate']}%")
                print(f"  Avg PnL: {r['avg_pnl_pct']:+.2f}%")
                print(f"  Max Profit: {r['max_profit_pct']:+.2f}% | Max Loss: {r['max_loss_pct']:.2f}%")
                print(f"  Max Drawdown: {r['max_drawdown_pct']:.2f}%")
                print(f"  Final Capital: {r['final_capital']:,.0f} KRW")

        except Exception as e:
            print(f"  Error: {e}")

    # 결과 저장
    output_file = os.path.join(os.path.dirname(__file__), "..", "backtest_results.json")
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
