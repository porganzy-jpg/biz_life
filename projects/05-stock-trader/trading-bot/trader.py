"""
StockBot v2.0 주식 자동매매 트레이더

8전략 앙상블 + 뉴스 감성분석 + 서킷브레이커 + DB 영속성 + 스케줄러
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
from circuit_breaker import CircuitBreaker
from alert_system import AlertSystem
from database import TradeDB
from scheduler import TradingScheduler, is_market_hours
from config import (
    STOCK_TRADING_CONFIG, WATCHLIST, ANALYSIS_CONFIG,
    CIRCUIT_BREAKER_CONFIG,
)

logger = logging.getLogger(__name__)


def _get_stock_selector():
    from stock_selector import StockSelectorEnsemble
    return StockSelectorEnsemble()


def _get_news_engine():
    from sentiment import SentimentAnalyzer
    from crawler import NewsCrawler
    return NewsCrawler(), SentimentAnalyzer()


class StockTrader:
    """주식 자동매매 트레이더 v2.0"""

    def __init__(self, paper_trading: bool = True):
        self.client = BrokerClient(paper_trading=paper_trading)
        self.risk_manager = StockRiskManager()
        self.circuit_breaker = CircuitBreaker(CIRCUIT_BREAKER_CONFIG)
        self.alert = AlertSystem()
        self.db = TradeDB()
        self.scheduler = TradingScheduler()
        self.paper_trading = paper_trading

        self.trade_history = []
        self._initial_capital = 100_000_000
        self._load_history()

        # 스케줄러 콜백 설정
        self.scheduler.set_callbacks(
            pre_market=self._on_pre_market,
            market_open=self._on_market_open,
            trade_cycle=self.run_cycle,
            market_close=self._on_market_close,
            post_market=self._on_post_market,
        )
        self.scheduler.trade_interval_seconds = STOCK_TRADING_CONFIG["trade_interval_minutes"] * 60

    def _load_history(self):
        trades = self.db.get_trades(limit=500)
        self.trade_history = list(reversed(trades))

    def _on_pre_market(self):
        """장 시작 전 사전 분석"""
        logger.info("=== 사전 분석 시작 (08:30) ===")
        scan = self.scan_watchlist()
        buys = [s for s in scan if s.get("action") == "BUY"]
        if buys:
            msg = "📋 사전 분석 결과:\n" + "\n".join(
                f"  • {s['name']} ({s['symbol']}) 점수:{s['score']}"
                for s in buys[:5]
            )
            self.alert.send(msg)

    def _on_market_open(self):
        """장 시작"""
        mode = "모의투자" if self.paper_trading else "실전투자"
        self.alert.notify_bot_start(mode)

    def _on_market_close(self):
        """장 마감"""
        logger.info("=== 장 마감 ===")

    def _on_post_market(self):
        """장 마감 후 일일 리포트"""
        self._generate_daily_report()

    def analyze_stock(self, symbol: str, name: str) -> dict:
        """개별 종목 분석 (퀀트 + 뉴스 감성)"""
        df = self.client.fetch_ohlcv(symbol, count=200)
        if df is None or df.empty:
            return {"symbol": symbol, "name": name, "action": "HOLD", "score": 0}

        # 퀀트 분석
        selector = _get_stock_selector()
        result = selector.evaluate(df, symbol, name)

        # 뉴스 감성 분석 (점수에 반영)
        try:
            crawler, analyzer = _get_news_engine()
            news = crawler.fetch_all_news(symbol, name)
            if news:
                sentiment = analyzer.analyze_batch(news)
                sentiment_score = sentiment["overall"]
                # 감성 점수를 전체 점수에 15% 반영
                quant_score = result["score"]
                news_adjustment = sentiment_score * 15  # -15 ~ +15
                result["score"] = round(
                    max(10, min(90, quant_score * 0.85 + (50 + news_adjustment) * 0.15)), 1
                )
                result["sentiment"] = sentiment
                # 감성에 따른 액션 재평가
                if result["score"] >= STOCK_TRADING_CONFIG["min_buy_score"]:
                    result["action"] = "BUY"
                elif result["score"] <= 35:
                    result["action"] = "SELL"
                else:
                    result["action"] = "HOLD"
                result["confidence"] = round(abs(result["score"] - 50) / 50, 2)
        except Exception as e:
            logger.debug(f"뉴스 분석 실패 [{name}]: {e}")

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
        if self.circuit_breaker.is_tripped:
            logger.warning(f"서킷브레이커 발동 중: {self.circuit_breaker.trip_reason}")
            return

        balance = self.client.get_balance()
        positions = self.client.get_positions()
        cash = balance.get("cash", 0)

        # 1. 트레일링 스탑 / 손절 / 익절 체크
        for symbol, pos in list(positions.items()):
            price_info = self.client.fetch_price(symbol)
            if not price_info:
                continue
            current_price = price_info["price"]
            avg_price = pos.get("avg_price", current_price)
            pnl_pct = (current_price - avg_price) / avg_price * 100 if avg_price > 0 else 0

            # 고가 업데이트
            self.db.update_highest_price(symbol, current_price)

            # 손절
            if pnl_pct <= STOCK_TRADING_CONFIG["stop_loss_pct"]:
                result = self.client.sell(symbol, pos["qty"])
                if result:
                    pnl = (current_price - avg_price) * pos["qty"]
                    self._record_trade("STOP_LOSS", symbol, pos.get("name", ""),
                                       pos["qty"], current_price, pnl, pnl_pct)
                    self.circuit_breaker.record_trade(pnl_pct)
                continue

            # 익절
            if pnl_pct >= STOCK_TRADING_CONFIG["take_profit_pct"]:
                # 50% 물량 익절, 나머지 트레일링
                sell_qty = max(1, pos["qty"] // 2)
                result = self.client.sell(symbol, sell_qty)
                if result:
                    pnl = (current_price - avg_price) * sell_qty
                    self._record_trade("TAKE_PROFIT", symbol, pos.get("name", ""),
                                       sell_qty, current_price, pnl, pnl_pct)
                    self.circuit_breaker.record_trade(pnl_pct)
                continue

            # 트레일링 스탑 (DB에서 고가 조회)
            db_positions = self.db.get_positions()
            db_pos = next((p for p in db_positions if p["symbol"] == symbol), None)
            if db_pos and db_pos["highest_price"] > 0:
                highest = db_pos["highest_price"]
                drop_from_high = (current_price - highest) / highest * 100
                if drop_from_high <= STOCK_TRADING_CONFIG["trailing_stop_pct"] and pnl_pct > 0:
                    result = self.client.sell(symbol, pos["qty"])
                    if result:
                        pnl = (current_price - avg_price) * pos["qty"]
                        self._record_trade("TRAILING_STOP", symbol, pos.get("name", ""),
                                           pos["qty"], current_price, pnl, pnl_pct)
                        self.circuit_breaker.record_trade(pnl_pct)

        # 2. 매수 (점수 높은 순)
        for result in scan_results:
            if self.circuit_breaker.is_tripped:
                break

            if result.get("action") != "BUY":
                continue
            if result.get("score", 0) < STOCK_TRADING_CONFIG["min_buy_score"]:
                continue

            symbol = result["symbol"]
            if symbol in positions:
                continue

            confidence = result.get("confidence", 0)
            if confidence < STOCK_TRADING_CONFIG["min_confidence"]:
                continue

            total_assets = balance.get("total_eval", cash)
            amount = self.risk_manager.calculate_position_size(
                total_assets, confidence, len(positions)
            )
            if amount <= 0:
                continue

            # 섹터 한도 체크
            sector = result.get("sector", "")
            if not self.risk_manager.check_sector_limit(positions, sector, amount, total_assets):
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
                                   current_price, 0, 0,
                                   result.get("score", 0), confidence,
                                   result.get("reasons", []))
                self.db.save_position(symbol, result["name"], qty, current_price,
                                      sector, result.get("score", 0))

    def _record_trade(self, action, symbol, name, qty, price,
                      pnl=0, pnl_pct=0, score=0, confidence=0, reasons=None):
        """거래 기록 (DB + 메모리 + 알림)"""
        self.db.record_trade(
            action=action, symbol=symbol, name=name,
            qty=qty, price=price, pnl=pnl, pnl_pct=pnl_pct,
            score=score, confidence=confidence,
            reasons=reasons,
            mode="paper" if self.paper_trading else "live",
        )

        if action != "BUY":
            self.db.remove_position(symbol)

        record = {
            "timestamp": datetime.now().isoformat(),
            "action": action, "symbol": symbol, "name": name,
            "qty": qty, "price": price,
            "pnl_pct": round(pnl_pct, 2),
            "reasons": reasons or [],
        }
        self.trade_history.append(record)

        # 알림
        self.alert.notify_trade(action, name, symbol, qty, price,
                                pnl_pct, score, reasons)

        # 서킷브레이커 체크
        if self.circuit_breaker.is_tripped:
            self.alert.notify_circuit_breaker(self.circuit_breaker.trip_reason)

    def run_cycle(self):
        """1회 매매 사이클"""
        logger.info(f"매매 사이클: {datetime.now().strftime('%H:%M:%S')}")

        if self.circuit_breaker.is_tripped:
            logger.warning(f"서킷브레이커: {self.circuit_breaker.trip_reason}")
            return {"skipped": True, "reason": self.circuit_breaker.trip_reason}

        scan_results = self.scan_watchlist()
        self.execute_trades(scan_results)

        return {
            "timestamp": datetime.now().isoformat(),
            "balance": self.client.get_balance(),
            "positions": self.client.get_positions(),
            "scan_results": scan_results,
        }

    def _generate_daily_report(self):
        """일일 리포트 생성"""
        balance = self.client.get_balance()
        total_assets = balance.get("total_eval", 0)
        cash = balance.get("cash", 0)
        invested = total_assets - cash
        positions = self.client.get_positions()

        total_pnl = total_assets - self._initial_capital
        total_pnl_pct = total_pnl / self._initial_capital * 100 if self._initial_capital else 0

        stats = self.db.get_trade_stats(days=1)
        today_trades = stats["total"]

        self.db.record_daily(
            total_assets=total_assets, cash=cash, invested=invested,
            pnl_day=0, pnl_day_pct=0,
            total_pnl=total_pnl, total_pnl_pct=total_pnl_pct,
            trades_count=today_trades, win_count=stats["wins"],
            positions_count=len(positions),
        )

        all_stats = self.db.get_trade_stats(days=30)
        self.alert.notify_daily_report(
            total_assets=total_assets, cash=cash,
            pnl_day=0, pnl_day_pct=0,
            total_pnl_pct=total_pnl_pct,
            positions=len(positions),
            trades_today=today_trades,
            win_rate=all_stats["win_rate"],
        )

    def start_auto(self):
        """자동 매매 시작 (스케줄러)"""
        mode = "모의투자" if self.paper_trading else "실전투자"
        logger.info(f"StockBot v2.0 자동매매 시작 ({mode})")
        self.alert.notify_bot_start(mode)
        self.scheduler.start()

    def stop_auto(self):
        """자동 매매 중지"""
        self.scheduler.stop()
        self.alert.notify_bot_stop()

    def get_status(self) -> dict:
        balance = self.client.get_balance()
        positions = self.client.get_positions()
        stats = self.db.get_trade_stats(days=30)

        total_assets = balance.get("total_eval", 0)
        total_pnl = total_assets - self._initial_capital
        total_pnl_pct = total_pnl / self._initial_capital * 100 if self._initial_capital else 0

        return {
            "mode": "모의투자" if self.paper_trading else "실전투자",
            "balance": balance,
            "positions": positions,
            "total_trades": stats["total"],
            "win_rate": stats["win_rate"],
            "total_pnl": round(total_pnl),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "recent_trades": self.trade_history[-20:],
            "circuit_breaker": self.circuit_breaker.get_status(),
            "scheduler": self.scheduler.get_status(),
        }


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    print("=" * 60)
    print("  StockBot v2.0 - 주식 자동매매")
    print("  8전략 앙상블 + 뉴스감성 + 서킷브레이커")
    print("=" * 60)

    trader = StockTrader(paper_trading=False)
    print(f"\n관심종목: {len(WATCHLIST)}개")
    print(f"매매 간격: {STOCK_TRADING_CONFIG['trade_interval_minutes']}분")
    print(f"손절: {STOCK_TRADING_CONFIG['stop_loss_pct']}% | 익절: {STOCK_TRADING_CONFIG['take_profit_pct']}%")

    try:
        trader.start_auto()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        trader.stop_auto()
        print("\n종료합니다.")
        status = trader.get_status()
        print(f"총 거래: {status['total_trades']}건 | 승률: {status['win_rate']}%")
        print(f"누적 수익: {status['total_pnl']:+,}원 ({status['total_pnl_pct']:+.2f}%)")


if __name__ == "__main__":
    main()
