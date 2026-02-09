"""
StockBot 주식 자동매매 트레이더

퀀트 분석 + 뉴스 감성분석 기반 자동매매
"""
import sys
import os
import json
import time
import logging
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "strategy"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "news"))

from broker_client import BrokerClient
from risk_manager import StockRiskManager
from config import STOCK_TRADING_CONFIG, WATCHLIST, ANALYSIS_CONFIG

logger = logging.getLogger(__name__)

# 지연 임포트 (strategy 모듈)
def _get_stock_selector():
    from stock_selector import StockSelectorEnsemble
    return StockSelectorEnsemble()

def _get_news_engine():
    from sentiment import SentimentAnalyzer
    from crawler import NewsCrawler
    return NewsCrawler(), SentimentAnalyzer()


class StockTrader:
    """주식 자동매매 트레이더"""

    def __init__(self, paper_trading: bool = True):
        self.client = BrokerClient(paper_trading=paper_trading)
        self.risk_manager = StockRiskManager()
        self.paper_trading = paper_trading

        self.trade_history = []
        self.log_file = os.path.join(
            os.path.dirname(__file__), "..", "stock_trade_history.json"
        )
        self._load_history()

    def _load_history(self):
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    self.trade_history = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.trade_history = []

    def _save_history(self):
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.trade_history, f, ensure_ascii=False, indent=2, default=str)

    def analyze_stock(self, symbol: str, name: str) -> dict:
        """개별 종목 분석"""
        df = self.client.fetch_ohlcv(symbol, count=200)
        if df is None or df.empty:
            return {"symbol": symbol, "name": name, "action": "HOLD", "score": 0}

        selector = _get_stock_selector()
        result = selector.evaluate(df, symbol, name)
        return result

    def scan_watchlist(self) -> list:
        """관심종목 전체 스캔"""
        results = []
        for stock in WATCHLIST:
            try:
                result = self.analyze_stock(stock["code"], stock["name"])
                result["sector"] = stock["sector"]
                results.append(result)
            except Exception as e:
                logger.error(f"분석 오류 [{stock['name']}]: {e}")
        return sorted(results, key=lambda x: x.get("score", 0), reverse=True)

    def execute_trades(self, scan_results: list):
        """스캔 결과에 따라 매매 실행"""
        balance = self.client.get_balance()
        positions = self.client.get_positions()
        cash = balance.get("cash", 0)

        # 매도 먼저 (손절/익절)
        for symbol, pos in list(positions.items()):
            price_info = self.client.fetch_price(symbol)
            if not price_info:
                continue
            current_price = price_info["price"]
            avg_price = pos.get("avg_price", current_price)
            pnl_pct = (current_price - avg_price) / avg_price * 100 if avg_price > 0 else 0

            if pnl_pct <= STOCK_TRADING_CONFIG["stop_loss_pct"]:
                result = self.client.sell(symbol, pos["qty"])
                if result:
                    self._record_trade("STOP_LOSS", symbol, pos.get("name", ""), pos["qty"],
                                       current_price, pnl_pct)

            elif pnl_pct >= STOCK_TRADING_CONFIG["take_profit_pct"]:
                result = self.client.sell(symbol, pos["qty"])
                if result:
                    self._record_trade("TAKE_PROFIT", symbol, pos.get("name", ""), pos["qty"],
                                       current_price, pnl_pct)

        # 매수 (점수 높은 순)
        for result in scan_results:
            if result.get("action") != "BUY":
                continue

            symbol = result["symbol"]
            if symbol in positions:
                continue

            confidence = result.get("confidence", 0)
            total_assets = balance.get("total_eval", cash)
            amount = self.risk_manager.calculate_position_size(
                total_assets, confidence, len(positions)
            )

            if amount <= 0:
                continue

            valid, msg = self.risk_manager.validate_trade(
                "BUY", amount, cash, positions, confidence
            )
            if not valid:
                continue

            current_price = result.get("current_price", 0)
            if current_price <= 0:
                continue

            qty = int(amount / current_price)
            if qty <= 0:
                continue

            buy_result = self.client.buy(symbol, result["name"], qty)
            if buy_result:
                cash -= qty * current_price
                positions[symbol] = {"qty": qty, "avg_price": current_price}
                self._record_trade("BUY", symbol, result["name"], qty,
                                   current_price, 0, result.get("reasons", []))

    def _record_trade(self, action, symbol, name, qty, price, pnl_pct=0, reasons=None):
        record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "symbol": symbol,
            "name": name,
            "qty": qty,
            "price": price,
            "pnl_pct": round(pnl_pct, 2),
            "reasons": reasons or [],
        }
        self.trade_history.append(record)
        self._save_history()

    def run_cycle(self):
        """1회 매매 사이클"""
        logger.info("=" * 50)
        logger.info(f"StockBot 매매 사이클: {datetime.now()}")

        scan_results = self.scan_watchlist()
        self.execute_trades(scan_results)

        return {
            "timestamp": datetime.now().isoformat(),
            "balance": self.client.get_balance(),
            "positions": self.client.get_positions(),
            "scan_results": scan_results,
        }

    def get_status(self) -> dict:
        balance = self.client.get_balance()
        positions = self.client.get_positions()
        total_trades = len(self.trade_history)
        profitable = sum(1 for t in self.trade_history if t.get("pnl_pct", 0) > 0)

        return {
            "mode": "모의투자" if self.paper_trading else "실전투자",
            "balance": balance,
            "positions": positions,
            "total_trades": total_trades,
            "win_rate": round(profitable / max(total_trades, 1) * 100, 1),
            "recent_trades": self.trade_history[-10:],
        }


def main():
    print("=" * 60)
    print("  StockBot v1.0 - 주식 자동매매")
    print("=" * 60)

    trader = StockTrader(paper_trading=True)
    print(f"\n관심종목: {len(WATCHLIST)}개")
    print(f"매매 간격: {STOCK_TRADING_CONFIG['trade_interval_minutes']}분")

    try:
        while True:
            trader.run_cycle()
            time.sleep(STOCK_TRADING_CONFIG["trade_interval_minutes"] * 60)
    except KeyboardInterrupt:
        print("\n종료합니다.")
        status = trader.get_status()
        print(f"총 거래: {status['total_trades']}건 | 승률: {status['win_rate']}%")


if __name__ == "__main__":
    main()
