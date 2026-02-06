"""
CryptoBot 트레이딩 엔진
전략 신호에 따라 자동으로 매매를 수행하고, 결과를 기록합니다.
"""
import sys
import os
import time
import json
import logging
from datetime import datetime

# 상위 폴더의 strategy 모듈 참조
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "strategy"))

from exchange_client import ExchangeClient
from config import TRADING_CONFIG, TARGET_MARKETS, STRATEGY_CONFIG
from base_strategy import Signal
from bollinger_rsi_strategy import BollingerRSIStrategy
from volatility_breakout_strategy import VolatilityBreakoutStrategy
from macd_strategy import MACDStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "..", "trading_log.json"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)


class CryptoTrader:
    """코인 자동매매 트레이더"""

    def __init__(self, paper_trading: bool = True):
        self.client = ExchangeClient(paper_trading=paper_trading)
        self.paper_trading = paper_trading

        # 전략 초기화 (복합 사용)
        self.strategies = [
            BollingerRSIStrategy(STRATEGY_CONFIG),
            VolatilityBreakoutStrategy(),
            MACDStrategy(),
        ]

        # 매매 이력
        self.trade_history = []
        self.log_file = os.path.join(
            os.path.dirname(__file__), "..", "trade_history.json"
        )
        self._load_history()

    def _load_history(self):
        """매매 이력 로드"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    self.trade_history = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.trade_history = []

    def _save_history(self):
        """매매 이력 저장"""
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.trade_history, f, ensure_ascii=False, indent=2, default=str)

    def analyze_market(self, symbol: str) -> dict:
        """
        특정 마켓을 모든 전략으로 분석

        Returns:
            dict: {
                "symbol": str,
                "signals": [Signal, ...],
                "consensus": str,  # BUY/SELL/HOLD
                "avg_confidence": float,
            }
        """
        ohlcv = self.client.fetch_ohlcv(symbol, timeframe="15m", limit=200)
        if not ohlcv:
            return {"symbol": symbol, "signals": [], "consensus": "HOLD", "avg_confidence": 0}

        # OHLCV를 DataFrame으로 변환
        import pandas as pd
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # 모든 전략으로 분석
        signals = []
        for strategy in self.strategies:
            try:
                signal = strategy.analyze(df, symbol)
                signals.append(signal)
            except Exception as e:
                logger.error(f"전략 분석 오류 [{strategy.name}][{symbol}]: {e}")

        # 다수결 합의
        buy_count = sum(1 for s in signals if s.action == Signal.BUY)
        sell_count = sum(1 for s in signals if s.action == Signal.SELL)
        total = len(signals)

        if buy_count > total / 2:
            consensus = Signal.BUY
            avg_conf = sum(s.confidence for s in signals if s.action == Signal.BUY) / max(buy_count, 1)
        elif sell_count > total / 2:
            consensus = Signal.SELL
            avg_conf = sum(s.confidence for s in signals if s.action == Signal.SELL) / max(sell_count, 1)
        else:
            consensus = Signal.HOLD
            avg_conf = 0.0

        return {
            "symbol": symbol,
            "signals": signals,
            "consensus": consensus,
            "avg_confidence": avg_conf,
        }

    def execute_trade(self, analysis: dict):
        """분석 결과에 따라 매매 실행"""
        symbol = analysis["symbol"]
        consensus = analysis["consensus"]
        confidence = analysis["avg_confidence"]

        if consensus == Signal.HOLD:
            return None

        balance = self.client.fetch_balance()
        positions = self.client.get_positions()

        if consensus == Signal.BUY:
            # 이미 최대 포지션이면 스킵
            if len(positions) >= TRADING_CONFIG["max_open_positions"]:
                logger.info(f"최대 포지션 초과 - 매수 스킵: {symbol}")
                return None

            # 매수 금액 계산
            krw_balance = balance.get("KRW", 0)
            trade_amount = krw_balance * TRADING_CONFIG["per_trade_ratio"]

            if trade_amount < 5000:  # 최소 주문 금액
                logger.info(f"잔고 부족 - 매수 스킵: {symbol}")
                return None

            result = self.client.buy(symbol, trade_amount)
            if result:
                trade_record = {
                    "timestamp": datetime.now().isoformat(),
                    "action": "BUY",
                    "symbol": symbol,
                    "amount": trade_amount,
                    "price": result.get("price", 0),
                    "confidence": confidence,
                    "reasons": [s.reason for s in analysis["signals"]],
                }
                self.trade_history.append(trade_record)
                self._save_history()
                return trade_record

        elif consensus == Signal.SELL:
            # 보유 중이 아니면 스킵
            if symbol not in positions:
                return None

            qty = positions[symbol].get("qty", 0)
            if qty <= 0:
                return None

            result = self.client.sell(symbol, qty)
            if result:
                # 수익률 계산
                buy_price = positions[symbol].get("avg_price", 0)
                sell_price = result.get("price", 0)
                pnl_pct = ((sell_price - buy_price) / buy_price * 100) if buy_price > 0 else 0

                trade_record = {
                    "timestamp": datetime.now().isoformat(),
                    "action": "SELL",
                    "symbol": symbol,
                    "qty": qty,
                    "price": sell_price,
                    "buy_price": buy_price,
                    "pnl_pct": round(pnl_pct, 2),
                    "confidence": confidence,
                    "reasons": [s.reason for s in analysis["signals"]],
                }
                self.trade_history.append(trade_record)
                self._save_history()
                return trade_record

        return None

    def check_stop_loss_take_profit(self):
        """손절/익절 확인"""
        positions = self.client.get_positions()

        for symbol, pos in list(positions.items()):
            ticker = self.client.fetch_ticker(symbol)
            if not ticker:
                continue

            current_price = ticker["last"]
            avg_price = pos.get("avg_price", 0)
            if avg_price <= 0:
                continue

            pnl_pct = (current_price - avg_price) / avg_price * 100

            # 손절
            if pnl_pct <= TRADING_CONFIG["stop_loss_pct"]:
                logger.warning(f"손절 실행: {symbol} (수익률: {pnl_pct:.2f}%)")
                self.client.sell(symbol, pos["qty"])
                self.trade_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "action": "STOP_LOSS",
                    "symbol": symbol,
                    "pnl_pct": round(pnl_pct, 2),
                    "price": current_price,
                })
                self._save_history()

            # 익절
            elif pnl_pct >= TRADING_CONFIG["take_profit_pct"]:
                logger.info(f"익절 실행: {symbol} (수익률: {pnl_pct:.2f}%)")
                self.client.sell(symbol, pos["qty"])
                self.trade_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "action": "TAKE_PROFIT",
                    "symbol": symbol,
                    "pnl_pct": round(pnl_pct, 2),
                    "price": current_price,
                })
                self._save_history()

    def run_cycle(self):
        """1회 매매 사이클 실행"""
        logger.info("=" * 50)
        logger.info(f"매매 사이클 시작: {datetime.now()}")
        logger.info(f"모드: {'모의투자' if self.paper_trading else '실전투자'}")

        # 손절/익절 체크
        self.check_stop_loss_take_profit()

        # 각 마켓 분석 및 매매
        results = []
        for symbol in TARGET_MARKETS:
            try:
                analysis = self.analyze_market(symbol)
                trade = self.execute_trade(analysis)
                results.append({
                    "symbol": symbol,
                    "consensus": analysis["consensus"],
                    "confidence": analysis["avg_confidence"],
                    "trade": trade,
                })
                time.sleep(0.5)  # API 호출 간격
            except Exception as e:
                logger.error(f"매매 사이클 오류 [{symbol}]: {e}")

        # 현재 상태 로깅
        balance = self.client.fetch_balance()
        positions = self.client.get_positions()
        logger.info(f"잔고: {balance}")
        logger.info(f"포지션: {positions}")
        logger.info(f"매매 사이클 완료")

        return {
            "timestamp": datetime.now().isoformat(),
            "balance": balance,
            "positions": positions,
            "results": results,
        }

    def get_status(self) -> dict:
        """현재 봇 상태 반환 (대시보드용)"""
        balance = self.client.fetch_balance()
        positions = self.client.get_positions()

        # 총 수익률 계산
        total_trades = len(self.trade_history)
        profitable = sum(1 for t in self.trade_history if t.get("pnl_pct", 0) > 0)
        total_pnl = sum(t.get("pnl_pct", 0) for t in self.trade_history if "pnl_pct" in t)

        return {
            "mode": "모의투자" if self.paper_trading else "실전투자",
            "balance": balance,
            "positions": positions,
            "total_trades": total_trades,
            "profitable_trades": profitable,
            "win_rate": (profitable / total_trades * 100) if total_trades > 0 else 0,
            "total_pnl_pct": round(total_pnl, 2),
            "recent_trades": self.trade_history[-10:],
        }


def main():
    """메인 실행"""
    print("=" * 60)
    print("  CryptoBot v1.0 - 코인 자동매매 프로그램")
    print("  모드: 모의투자 (Paper Trading)")
    print("=" * 60)

    trader = CryptoTrader(paper_trading=True)

    print(f"\n대상 마켓: {', '.join(TARGET_MARKETS)}")
    print(f"전략: {', '.join(s.name for s in trader.strategies)}")
    print(f"매매 간격: {TRADING_CONFIG['trade_interval_seconds']}초")
    print(f"손절: {TRADING_CONFIG['stop_loss_pct']}% / 익절: {TRADING_CONFIG['take_profit_pct']}%")
    print(f"\n자동매매를 시작합니다...\n")

    try:
        while True:
            cycle_result = trader.run_cycle()
            time.sleep(TRADING_CONFIG["trade_interval_seconds"])
    except KeyboardInterrupt:
        print("\n\n자동매매를 종료합니다.")
        status = trader.get_status()
        print(f"\n=== 최종 결과 ===")
        print(f"총 거래: {status['total_trades']}건")
        print(f"승률: {status['win_rate']:.1f}%")
        print(f"누적 수익률: {status['total_pnl_pct']:.2f}%")


if __name__ == "__main__":
    main()
