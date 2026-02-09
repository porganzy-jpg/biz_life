"""
CryptoBot 트레이딩 엔진 v2.0
앙상블 전략, 서킷브레이커, 알림 시스템, 리스크 관리 통합
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
from circuit_breaker import CircuitBreaker
from alert_system import AlertSystem
from risk_manager import RiskManager
from base_strategy import Signal
from bollinger_rsi_strategy import BollingerRSIStrategy
from volatility_breakout_strategy import VolatilityBreakoutStrategy
from macd_strategy import MACDStrategy
from moving_average_strategy import MovingAverageStrategy
from strategy_ensemble import StrategyEnsemble

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
    """코인 자동매매 트레이더 v2.0"""

    def __init__(self, paper_trading: bool = True):
        self.client = ExchangeClient(paper_trading=paper_trading)
        self.paper_trading = paper_trading

        # 전략 초기화 (4개 전략)
        self.strategies = [
            BollingerRSIStrategy(STRATEGY_CONFIG),
            VolatilityBreakoutStrategy(),
            MACDStrategy(),
            MovingAverageStrategy(STRATEGY_CONFIG),
        ]

        # 앙상블 초기화 (가중 투표)
        self.ensemble = StrategyEnsemble(
            self.strategies,
            weights={
                "BollingerBand+RSI": 0.30,
                "VolatilityBreakout": 0.25,
                "MACD": 0.25,
                "MovingAverage": 0.20,
            }
        )

        # 서킷브레이커
        self.circuit_breaker = CircuitBreaker()

        # 알림 시스템
        self.alert = AlertSystem()

        # 리스크 관리
        self.risk_manager = RiskManager()

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
        특정 마켓을 앙상블 전략으로 분석

        Returns:
            dict: 앙상블 분석 결과
        """
        ohlcv = self.client.fetch_ohlcv(symbol, timeframe="15m", limit=200)
        if not ohlcv:
            return {"symbol": symbol, "action": "HOLD", "confidence": 0,
                    "signals": [], "vote_detail": {}}

        import pandas as pd
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # 앙상블 분석
        result = self.ensemble.analyze(df, symbol)
        result["symbol"] = symbol
        return result

    def execute_trade(self, analysis: dict):
        """분석 결과에 따라 매매 실행 (리스크 관리 적용)"""
        symbol = analysis["symbol"]
        action = analysis.get("action", "HOLD")
        confidence = analysis.get("confidence", 0)

        # 서킷브레이커 체크
        can_trade, reason = self.circuit_breaker.can_trade()
        if not can_trade:
            logger.info(f"매매 중지 (서킷브레이커): {reason}")
            return None

        if action == "HOLD":
            return None

        balance = self.client.fetch_balance()
        positions = self.client.get_positions()

        if action == Signal.BUY:
            krw_balance = balance.get("KRW", 0)

            # 리스크 관리: 포지션 사이즈 계산
            trade_amount = self.risk_manager.calculate_position_size(
                krw_balance, confidence, len(positions)
            )

            if trade_amount <= 0:
                return None

            # 매매 전 검증
            valid, msg = self.risk_manager.validate_trade(
                "BUY", symbol, trade_amount, krw_balance, positions, confidence
            )
            if not valid:
                logger.info(f"리스크 검증 실패 [{symbol}]: {msg}")
                return None

            result = self.client.buy(symbol, trade_amount)
            if result:
                self.alert.alert_trade("BUY", symbol, trade_amount, result.get("price", 0), confidence)
                trade_record = {
                    "timestamp": datetime.now().isoformat(),
                    "action": "BUY",
                    "symbol": symbol,
                    "amount": trade_amount,
                    "price": result.get("price", 0),
                    "confidence": confidence,
                    "reasons": [s["reason"] for s in analysis.get("signals", [])],
                }
                self.trade_history.append(trade_record)
                self._save_history()
                return trade_record

        elif action == Signal.SELL:
            if symbol not in positions:
                return None

            qty = positions[symbol].get("qty", 0)
            if qty <= 0:
                return None

            result = self.client.sell(symbol, qty)
            if result:
                buy_price = positions[symbol].get("avg_price", 0)
                sell_price = result.get("price", 0)
                pnl_pct = ((sell_price - buy_price) / buy_price * 100) if buy_price > 0 else 0

                # 서킷브레이커에 결과 기록
                self.circuit_breaker.record_trade(pnl_pct)

                # 앙상블 성과 업데이트
                for sig in analysis.get("signals", []):
                    if sig["action"] == Signal.SELL:
                        self.ensemble.update_performance(sig["strategy"], pnl_pct > 0)

                self.alert.alert_trade("SELL", symbol, qty * sell_price, sell_price, confidence)
                trade_record = {
                    "timestamp": datetime.now().isoformat(),
                    "action": "SELL",
                    "symbol": symbol,
                    "qty": qty,
                    "price": sell_price,
                    "buy_price": buy_price,
                    "pnl_pct": round(pnl_pct, 2),
                    "confidence": confidence,
                    "reasons": [s["reason"] for s in analysis.get("signals", [])],
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
                self.circuit_breaker.record_trade(pnl_pct)
                self.alert.alert_stop_loss(symbol, pnl_pct, current_price)
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
                self.circuit_breaker.record_trade(pnl_pct)
                self.alert.alert_take_profit(symbol, pnl_pct, current_price)
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

        # 서킷브레이커 체크
        can_trade, reason = self.circuit_breaker.can_trade()
        if not can_trade:
            logger.warning(f"매매 중지: {reason}")
            return {"timestamp": datetime.now().isoformat(), "status": "paused", "reason": reason}

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
                    "action": analysis.get("action", "HOLD"),
                    "confidence": analysis.get("confidence", 0),
                    "trade": trade,
                })
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"매매 사이클 오류 [{symbol}]: {e}")
                self.alert.alert_error(f"[{symbol}] {e}")

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
            "circuit_breaker": self.circuit_breaker.get_status(),
            "risk_manager": self.risk_manager.get_status(),
            "ensemble_report": self.ensemble.get_strategy_report(),
            "recent_alerts": self.alert.get_recent_alerts(10),
        }


def main():
    """메인 실행"""
    print("=" * 60)
    print("  CryptoBot v2.0 - 코인 자동매매 프로그램")
    print("  모드: 모의투자 (Paper Trading)")
    print("  전략: 앙상블 (4전략 가중 투표)")
    print("  보안: 서킷브레이커 + 리스크관리 + 알림")
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
        print(f"서킷브레이커: {'발동중' if status['circuit_breaker']['is_active'] else '정상'}")


if __name__ == "__main__":
    main()
