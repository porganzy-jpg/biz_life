"""
StockBot v3.7 주식 자동매매 트레이더

6전략 통합 앙상블 (5전략 Z-score + ML예측) + RSI(2) 급락 매수
+ 멀티채널 알림 + 포트폴리오 자동 리밸런싱 + 기관수급 + WebSocket
+ ATR Chandelier Exit + 서킷브레이커 + DB 영속성 + 스케줄러
+ 시장 국면(Regime) 감지 + 스마트 주문 실행 엔진
+ yfinance 실시간 데이터 + 라이브/페이퍼 이중 안전장치

v3.7 변경사항:
  - 멀티채널 알림 (Telegram + Discord + Email, 우선순위별 자동 선택)
  - 포트폴리오 자동 리밸런싱 (단일종목 36%→30%, 섹터 55%→50%)
  - 기관/외국인 실제 수급 데이터 (네이버 금융 크롤링)
  - 실시간 호가 WebSocket 프레임워크 (opt-in)
  - ML 기반 종목 선정 (XGBoost 22피처, 6번째 전략)
"""
import sys
import os
import time
import logging
import numpy as np
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "strategy"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "news"))

from broker_client import BrokerClient
from risk_manager import StockRiskManager
from circuit_breaker import CircuitBreaker
from alert_system import AlertSystem
from database import TradeDB
from scheduler import TradingScheduler, is_market_hours
from regime_detector import RegimeDetector, MarketRegime
from execution_engine import ExecutionEngine, Side
from config import (
    STOCK_TRADING_CONFIG, WATCHLIST, ANALYSIS_CONFIG,
    CIRCUIT_BREAKER_CONFIG, INITIAL_CAPITAL,
    TRADING_MODE, LIVE_TRADING_CONFIRMED,
)

logger = logging.getLogger(__name__)


def _get_stock_selector():
    from stock_selector import StockSelectorEnsemble
    return StockSelectorEnsemble()


def _confirm_live_trading() -> bool:
    """라이브 모드 시작 시 콘솔 확인 프롬프트"""
    print("\n" + "!" * 60)
    print("  경고: 실전 매매 모드입니다!")
    print(f"  초기 자본: {INITIAL_CAPITAL:,}원")
    print(f"  종목 수: {len(WATCHLIST)}개")
    print("  실제 돈이 사용됩니다. 신중히 확인하세요.")
    print("!" * 60)
    print()
    try:
        answer = input("  실전 매매를 시작하려면 'CONFIRM'을 입력하세요: ").strip()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer == "CONFIRM"


def compute_atr(df, period=14):
    """ATR(Average True Range) 계산. df는 high/low/close 컬럼 필요."""
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def compute_rsi(series, period=14):
    """RSI 계산 (EWM 방식)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return (100 - (100 / (1 + rs))).fillna(50)


# RSI(2) Crash Buy 설정
RSI2_BUY_THRESHOLD = 10     # RSI(2) < 10 매수
RSI2_SELL_THRESHOLD = 90    # RSI(2) > 90 청산
RSI2_MAX_HOLD_DAYS = 7      # 최대 보유일

# ATR Chandelier Exit 설정 (config.py에서 읽기)
ATR_MULTIPLIER = STOCK_TRADING_CONFIG.get("atr_multiplier", 2.0)
ATR_PERIOD = STOCK_TRADING_CONFIG.get("atr_period", 14)


class StockTrader:
    """주식 자동매매 트레이더 v3.7"""

    def __init__(self, paper_trading: bool = True):
        self.client = BrokerClient(paper_trading=paper_trading)
        self.risk_manager = StockRiskManager()
        self.circuit_breaker = CircuitBreaker(CIRCUIT_BREAKER_CONFIG)
        self.alert = AlertSystem()
        self.db = TradeDB()
        self.scheduler = TradingScheduler()
        self.regime_detector = RegimeDetector()
        self.execution_engine = ExecutionEngine(broker_client=self.client)
        self.paper_trading = self.client.paper_trading

        self.trade_history = []
        self._initial_capital = INITIAL_CAPITAL
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
        """장 시작 전 사전 분석 (시장 국면 감지 + 데이터 프리로드)"""
        logger.info("=== 사전 분석 시작 (08:30) ===")

        # 데이터 프리로드
        logger.info("워치리스트 데이터 프리로드...")
        load_result = self.client.preload_data(WATCHLIST)
        loaded = sum(1 for v in load_result.values() if v["loaded"])
        logger.info(f"프리로드 완료: {loaded}/{len(WATCHLIST)}종목")

        # 시장 국면 감지
        regime = self._update_regime()
        regime_status = self.regime_detector.get_status()
        logger.info(f"사전분석 시장 국면: {regime.value}")
        self.alert.send(
            f"[사전분석] 시장 국면: {regime.value}\n"
            f"ADX: {regime_status['details'].get('adx', '-')}\n"
            f"변동성: {regime_status['details'].get('recent_volatility', '-')}%\n"
            f"20일 수익률: {regime_status['details'].get('recent_return_pct', '-')}%\n"
            f"데이터 로드: {loaded}/{len(WATCHLIST)}종목"
        )

        scan = self.scan_watchlist()
        buys = [s for s in scan if s.get("action") == "BUY"]
        if buys:
            msg = "사전 분석 결과:\n" + "\n".join(
                f"  - {s['name']} ({s['symbol']}) 점수:{s['score']}"
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

    def _get_atr(self, symbol: str, period: int = ATR_PERIOD) -> float:
        """종목의 현재 ATR 값을 계산. OHLCV 데이터 필요."""
        try:
            df = self.client.fetch_ohlcv(symbol, count=max(60, period * 3))
            if df is not None and len(df) >= period + 1:
                atr_series = compute_atr(df, period)
                return float(atr_series.iloc[-1])
        except Exception as e:
            logger.warning(f"ATR 계산 실패 [{symbol}]: {e}")

        # 폴백: 현재가의 3% (보수적 기본값)
        try:
            price_info = self.client.fetch_price(symbol)
            if price_info:
                return price_info["price"] * 0.03
        except Exception:
            pass
        return 0

    def _update_regime(self) -> MarketRegime:
        """워치리스트 종목의 OHLCV를 수집하여 시장 국면을 감지합니다."""
        price_data_list = []
        for stock in WATCHLIST:
            try:
                df = self.client.fetch_ohlcv(stock["code"], count=200)
                if df is not None and len(df) >= 60:
                    price_data_list.append(df)
            except Exception as e:
                logger.debug(f"국면감지 데이터 수집 실패 [{stock['name']}]: {e}")

        regime = self.regime_detector.detect(price_data_list)
        return regime

    def analyze_stock(self, symbol: str, name: str) -> dict:
        """개별 종목 분석 (순수 퀀트 + 시장국면 적응형 가중치 + RSI(2) 급락감지)"""
        df = self.client.fetch_ohlcv(symbol, count=200)
        if df is None or df.empty:
            return {"symbol": symbol, "name": name, "action": "HOLD", "score": 0}

        # 순수 퀀트 분석 (국면 직접 전달 → 내부 가중치 자동 적용)
        selector = _get_stock_selector()
        regime_str = self.regime_detector.current_regime.value
        result = selector.evaluate(df, symbol, name, regime=regime_str)
        result["regime"] = regime_str

        # RSI(2) 급락 매수 감지
        close = df["close"].astype(float)
        rsi2_val = float(compute_rsi(close, 2).iloc[-1])
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else 0
        result["rsi2"] = round(rsi2_val, 1)
        result["ma200"] = round(ma200)
        result["rsi2_buy"] = rsi2_val < RSI2_BUY_THRESHOLD and ma200 > 0 and float(close.iloc[-1]) > ma200

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
        db_positions = self.db.get_positions()
        for symbol, pos in list(positions.items()):
          try:
            price_info = self.client.fetch_price(symbol)
            if not price_info:
                continue
            current_price = price_info["price"]
            avg_price = pos.get("avg_price", current_price)
            pnl_pct = (current_price - avg_price) / avg_price * 100 if avg_price > 0 else 0

            # 고가 업데이트
            self.db.update_highest_price(symbol, current_price)

            # DB에서 진입 소스 확인
            db_pos = next((p for p in db_positions if p["symbol"] == symbol), None)
            entry_source = db_pos.get("entry_source", "ens") if db_pos else "ens"

            # RSI(2) 진입 포지션: 청산 로직 (익절/트레일링 포함)
            if entry_source == "rsi2":
                sell_rsi2 = False
                rsi2_reason = ""

                # 손절 -5%
                if pnl_pct <= STOCK_TRADING_CONFIG["stop_loss_pct"]:
                    sell_rsi2, rsi2_reason = True, "SL"

                # 익절 +15%
                if not sell_rsi2 and pnl_pct >= STOCK_TRADING_CONFIG["take_profit_pct"]:
                    sell_rsi2, rsi2_reason = True, "TP"

                # ATR Chandelier Exit 트레일링 스탑
                if not sell_rsi2 and db_pos and db_pos["highest_price"] > 0:
                    atr_val = self._get_atr(symbol)
                    chandelier_stop = db_pos["highest_price"] - ATR_MULTIPLIER * atr_val
                    if current_price <= chandelier_stop:
                        sell_rsi2, rsi2_reason = True, "TRAIL"

                # RSI(2) > 90 청산
                if not sell_rsi2:
                    df = self.client.fetch_ohlcv(symbol, count=60)
                    if df is not None and len(df) > 2:
                        rsi2_now = float(compute_rsi(df["close"].astype(float), 2).iloc[-1])
                        if rsi2_now > RSI2_SELL_THRESHOLD:
                            sell_rsi2, rsi2_reason = True, "RSI2>90"

                # 7일 보유 시간기반 청산
                if not sell_rsi2 and db_pos and db_pos.get("bought_at"):
                    from datetime import datetime as dt
                    try:
                        bought = dt.fromisoformat(db_pos["bought_at"])
                        days_held = (datetime.now() - bought).days
                        if days_held >= RSI2_MAX_HOLD_DAYS:
                            sell_rsi2, rsi2_reason = True, f"T{days_held}d"
                    except (ValueError, TypeError):
                        pass

                if sell_rsi2:
                    urgency = "high" if rsi2_reason in ("SL", "TRAIL") else "normal"
                    exec_id = self.execution_engine.smart_execute(
                        symbol=symbol, side=Side.SELL.value,
                        qty=pos["qty"], urgency=urgency,
                        name=pos.get("name", ""),
                    )
                    fill_price = self.execution_engine.get_fill_price(exec_id) or current_price
                    pnl = (fill_price - avg_price) * pos["qty"]
                    pnl_pct = (fill_price - avg_price) / avg_price * 100 if avg_price > 0 else 0
                    self._record_trade(f"RSI2_{rsi2_reason}", symbol, pos.get("name", ""),
                                       pos["qty"], fill_price, pnl, pnl_pct)
                    self.circuit_breaker.record_trade(pnl_pct)
                    logger.info(f"RSI(2) 청산 [{pos.get('name', symbol)}] {rsi2_reason} pnl={pnl_pct:+.1f}% exec_id={exec_id}")
                continue  # RSI(2) 포지션은 앙상블 청산 로직 스킵

            # === 앙상블 진입 포지션: 기존 청산 로직 ===

            # 손절 - 긴급: 시장가 즉시 실행
            if pnl_pct <= STOCK_TRADING_CONFIG["stop_loss_pct"]:
                exec_id = self.execution_engine.smart_execute(
                    symbol=symbol, side=Side.SELL.value,
                    qty=pos["qty"], urgency="high",
                    name=pos.get("name", ""),
                )
                fill_price = self.execution_engine.get_fill_price(exec_id) or current_price
                pnl = (fill_price - avg_price) * pos["qty"]
                pnl_pct = (fill_price - avg_price) / avg_price * 100 if avg_price > 0 else 0
                self._record_trade("STOP_LOSS", symbol, pos.get("name", ""),
                                   pos["qty"], fill_price, pnl, pnl_pct)
                self.circuit_breaker.record_trade(pnl_pct)
                logger.info(f"손절 실행 [{symbol}] exec_id={exec_id}")
                continue

            # 익절 - 전량 매도
            if pnl_pct >= STOCK_TRADING_CONFIG["take_profit_pct"]:
                exec_id = self.execution_engine.smart_execute(
                    symbol=symbol, side=Side.SELL.value,
                    qty=pos["qty"], urgency="normal",
                    name=pos.get("name", ""),
                )
                fill_price = self.execution_engine.get_fill_price(exec_id) or current_price
                pnl = (fill_price - avg_price) * pos["qty"]
                pnl_pct = (fill_price - avg_price) / avg_price * 100 if avg_price > 0 else 0
                self._record_trade("TAKE_PROFIT", symbol, pos.get("name", ""),
                                   pos["qty"], fill_price, pnl, pnl_pct)
                self.circuit_breaker.record_trade(pnl_pct)
                logger.info(f"익절 실행 [{symbol}] exec_id={exec_id}")
                continue

            # ATR Chandelier Exit 트레일링 스탑
            if db_pos and db_pos["highest_price"] > 0:
                highest = db_pos["highest_price"]

                # ATR 계산: 종목의 일봉 데이터로 현재 ATR 산출
                atr_val = self._get_atr(symbol)
                chandelier_stop = highest - ATR_MULTIPLIER * atr_val

                if current_price <= chandelier_stop:
                    exec_id = self.execution_engine.smart_execute(
                        symbol=symbol, side=Side.SELL.value,
                        qty=pos["qty"], urgency="high",
                        name=pos.get("name", ""),
                    )
                    fill_price = self.execution_engine.get_fill_price(exec_id) or current_price
                    pnl = (fill_price - avg_price) * pos["qty"]
                    pnl_pct = (fill_price - avg_price) / avg_price * 100 if avg_price > 0 else 0
                    self._record_trade("TRAILING_STOP", symbol, pos.get("name", ""),
                                       pos["qty"], fill_price, pnl, pnl_pct)
                    self.circuit_breaker.record_trade(pnl_pct)
                    drop_pct = (fill_price - highest) / highest * 100
                    logger.info(
                        f"ATR 트레일링 [{symbol}] "
                        f"고가={highest:,.0f} ATR={atr_val:,.0f} "
                        f"스탑={chandelier_stop:,.0f} 현재={current_price:,.0f} "
                        f"({drop_pct:+.1f}%) exec_id={exec_id}"
                    )
          except Exception as e:
            logger.error(f"청산 체크 오류 [{symbol}]: {e}")

        # 2. 퀀트 기반 매도 (C3 Fix: SELL 신호 실행)
        for result in scan_results:
          try:
            if result.get("action") != "SELL":
                continue
            symbol = result["symbol"]
            if symbol not in positions:
                continue
            pos = positions[symbol]
            current_price = result.get("current_price", 0)
            if current_price <= 0:
                continue
            avg_price = pos.get("avg_price", current_price)
            pnl_pct = (current_price - avg_price) / avg_price * 100 if avg_price > 0 else 0
            exec_id = self.execution_engine.smart_execute(
                symbol=symbol, side=Side.SELL.value,
                qty=pos["qty"], urgency="normal",
                name=pos.get("name", ""),
            )
            if exec_id:
                fill_price = self.execution_engine.get_fill_price(exec_id) or current_price
                pnl = (fill_price - avg_price) * pos["qty"]
                pnl_pct = (fill_price - avg_price) / avg_price * 100 if avg_price > 0 else 0
                self._record_trade("QUANT_SELL", symbol, pos.get("name", ""),
                                   pos["qty"], fill_price, pnl, pnl_pct,
                                   result.get("score", 0), result.get("confidence", 0),
                                   result.get("reasons", []))
                self.circuit_breaker.record_trade(pnl_pct)
                del positions[symbol]
                logger.info(f"퀀트 매도 [{pos.get('name', symbol)}] score={result.get('score'):.1f} exec_id={exec_id}")
          except Exception as e:
            logger.error(f"퀀트 매도 오류 [{result.get('symbol', '?')}]: {e}")

        # 2.5 리밸런싱: 단일종목 36% 초과 → 30%, 섹터 55% 초과 → 50%
        try:
            total_assets = balance.get("total_eval", cash)
            # 현재가 조회
            current_prices = {}
            for sym in list(positions.keys()):
                price_info = self.client.fetch_price(sym)
                if price_info:
                    current_prices[sym] = price_info["price"]

            # 단일종목 리밸런싱
            rebalance_list = self.risk_manager.should_rebalance(
                positions, total_assets, current_prices
            )
            for rb in rebalance_list:
                sym = rb["symbol"]
                qty_sell = rb["qty_to_sell"]
                rb_price = rb["price"]
                rb_name = rb["name"]

                exec_id = self.execution_engine.smart_execute(
                    symbol=sym, side=Side.SELL.value,
                    qty=qty_sell, urgency="normal",
                    name=rb_name,
                )
                if exec_id:
                    fill_price = self.execution_engine.get_fill_price(exec_id) or rb_price
                    avg_p = positions[sym].get("avg_price", fill_price)
                    pnl = (fill_price - avg_p) * qty_sell
                    pnl_pct = (fill_price - avg_p) / avg_p * 100 if avg_p > 0 else 0
                    self._record_rebalance(
                        sym, rb_name, qty_sell, fill_price, pnl, pnl_pct,
                        f"단일종목 {rb['current_pct']:.0f}%→{rb['target_pct']:.0f}%"
                    )
                    # 포지션 수량 업데이트 (삭제하지 않음)
                    positions[sym]["qty"] -= qty_sell
                    cash += qty_sell * fill_price
                    logger.info(
                        f"리밸런싱 [{rb_name}] {rb['current_pct']:.0f}%→{rb['target_pct']:.0f}% "
                        f"{qty_sell}주 매도 exec_id={exec_id}"
                    )

            # 섹터 집중도 리밸런싱
            sector_rebalance = self.risk_manager.should_rebalance_sector(
                positions, total_assets, current_prices
            )
            for rb in sector_rebalance:
                sym = rb["symbol"]
                if sym not in positions:
                    continue
                qty_sell = rb["qty_to_sell"]
                rb_price = rb["price"]
                rb_name = rb["name"]

                exec_id = self.execution_engine.smart_execute(
                    symbol=sym, side=Side.SELL.value,
                    qty=qty_sell, urgency="normal",
                    name=rb_name,
                )
                if exec_id:
                    fill_price = self.execution_engine.get_fill_price(exec_id) or rb_price
                    avg_p = positions[sym].get("avg_price", fill_price)
                    pnl = (fill_price - avg_p) * qty_sell
                    pnl_pct = (fill_price - avg_p) / avg_p * 100 if avg_p > 0 else 0
                    self._record_rebalance(
                        sym, rb_name, qty_sell, fill_price, pnl, pnl_pct,
                        f"섹터({rb['sector']}) {rb['sector_pct']:.0f}%→{rb['target_sector_pct']:.0f}%"
                    )
                    positions[sym]["qty"] -= qty_sell
                    cash += qty_sell * fill_price
                    logger.info(
                        f"섹터 리밸런싱 [{rb_name}] {rb['sector']} "
                        f"{rb['sector_pct']:.0f}%→{rb['target_sector_pct']:.0f}% "
                        f"{qty_sell}주 매도 exec_id={exec_id}"
                    )
        except Exception as e:
            logger.error(f"리밸런싱 오류: {e}")

        # 3. 앙상블 매수 (점수 높은 순)
        for result in scan_results:
          try:
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

            current_price = result.get("current_price", 0)
            if current_price <= 0:
                logger.warning(f"가격 데이터 없음 [{result.get('name', symbol)}]: price={current_price} - 매수 건너뜀")
                continue

            total_assets = balance.get("total_eval", cash)

            # ATR 기반 포지션 사이징
            atr_val = self._get_atr(symbol)
            amount = self.risk_manager.calculate_position_size(
                total_assets, confidence, len(positions),
                current_price=current_price, atr=atr_val,
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

            # 어포더빌리티 체크: 1주 가격이 포지션 한도 내인지 확인
            if not self.risk_manager.can_afford_stock(current_price, total_assets):
                logger.warning(
                    f"주가 과다 [{result.get('name', symbol)}]: "
                    f"{current_price:,}원 > 포지션한도 - 매수 건너뜀"
                )
                continue

            qty = int(amount / current_price)
            if qty <= 0:
                logger.warning(f"수량 부족 [{result.get('name', symbol)}]: amount={amount:,.0f}, price={current_price:,.0f} - 매수 건너뜀")
                continue

            # 스마트 실행 엔진을 통한 매수
            exec_id = self.execution_engine.smart_execute(
                symbol=symbol, side=Side.BUY.value,
                qty=qty, urgency="normal",
                name=result["name"],
            )
            if exec_id:
                fill_price = self.execution_engine.get_fill_price(exec_id) or current_price
                cash -= qty * fill_price
                positions[symbol] = {"qty": qty, "avg_price": fill_price, "sector": sector, "name": result["name"]}
                self._record_trade("BUY", symbol, result["name"], qty,
                                   fill_price, 0, 0,
                                   result.get("score", 0), confidence,
                                   result.get("reasons", []))
                self.db.save_position(symbol, result["name"], qty, fill_price,
                                      sector, result.get("score", 0), entry_source="ens")
                logger.info(f"앙상블 매수 [{result['name']}] score={result.get('score', 0):.1f} @{fill_price:,.0f}원 exec_id={exec_id}")
          except Exception as e:
            logger.error(f"앙상블 매수 오류 [{result.get('symbol', '?')}]: {e}")

        # 4. RSI(2) 급락 매수 (앙상블과 독립적으로 작동)
        for result in scan_results:
          try:
            if self.circuit_breaker.is_tripped:
                break
            if len(positions) >= STOCK_TRADING_CONFIG["max_positions"]:
                break

            symbol = result["symbol"]
            if symbol in positions:
                continue

            # RSI(2) 급락 매수 조건: RSI(2) < 10 AND 종가 > MA200
            if not result.get("rsi2_buy", False):
                continue

            current_price = result.get("current_price", 0)
            if current_price <= 0:
                continue

            total_assets = balance.get("total_eval", cash)

            # ATR 기반 포지션 사이징
            atr_val = self._get_atr(symbol)
            amount = self.risk_manager.calculate_position_size(
                total_assets, 0.5, len(positions),
                current_price=current_price, atr=atr_val,
            )
            if amount <= 0:
                continue

            # 섹터 한도 체크
            sector = result.get("sector", "")
            if not self.risk_manager.check_sector_limit(positions, sector, amount, total_assets):
                continue

            valid, msg = self.risk_manager.validate_trade(
                "BUY", amount, cash, positions, 0.5
            )
            if not valid:
                continue

            if not self.risk_manager.can_afford_stock(current_price, total_assets):
                continue

            qty = int(amount / current_price)
            if qty <= 0:
                continue

            exec_id = self.execution_engine.smart_execute(
                symbol=symbol, side=Side.BUY.value,
                qty=qty, urgency="normal",
                name=result.get("name", ""),
            )
            if exec_id:
                fill_price = self.execution_engine.get_fill_price(exec_id) or current_price
                cash -= qty * fill_price
                positions[symbol] = {"qty": qty, "avg_price": fill_price, "sector": sector, "name": result.get("name", "")}
                self._record_trade("RSI2_BUY", symbol, result.get("name", ""), qty,
                                   fill_price, 0, 0,
                                   result.get("score", 0), 0.5,
                                   [f"RSI(2)={result.get('rsi2', 0):.0f}", f"MA200={result.get('ma200', 0):,.0f}"])
                self.db.save_position(symbol, result.get("name", ""), qty, fill_price,
                                      sector, result.get("score", 0), entry_source="rsi2")
                logger.info(
                    f"RSI(2) 급락매수 [{result.get('name', symbol)}] "
                    f"@{fill_price:,.0f}원 RSI2={result.get('rsi2', 0):.1f} MA200={result.get('ma200', 0):,.0f} "
                    f"exec_id={exec_id}"
                )
          except Exception as e:
            logger.error(f"RSI(2) 매수 오류 [{result.get('symbol', '?')}]: {e}")

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

    def _record_rebalance(self, symbol, name, qty, price, pnl, pnl_pct, reason):
        """리밸런싱 기록 (DB + 알림, 포지션 삭제 안 함)"""
        self.db.record_trade(
            action="REBALANCE", symbol=symbol, name=name,
            qty=qty, price=price, pnl=pnl, pnl_pct=pnl_pct,
            score=0, confidence=0, reasons=[reason],
            mode="paper" if self.paper_trading else "live",
        )
        # REBALANCE는 부분매도이므로 포지션 삭제하지 않음
        # DB 포지션 수량 직접 업데이트
        try:
            from database import get_connection
            conn = get_connection()
            conn.execute(
                "UPDATE positions SET qty = qty - ? WHERE symbol = ? AND qty > ?",
                (qty, symbol, qty)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"리밸런싱 DB 업데이트 실패 [{symbol}]: {e}")

        record = {
            "timestamp": datetime.now().isoformat(),
            "action": "REBALANCE", "symbol": symbol, "name": name,
            "qty": qty, "price": price,
            "pnl_pct": round(pnl_pct, 2),
            "reasons": [reason],
        }
        self.trade_history.append(record)
        self.alert.notify_rebalance(symbol, name, qty, price, reason)

    def run_cycle(self):
        """1회 매매 사이클 (시장 국면 감지 포함)"""
        logger.info(f"매매 사이클: {datetime.now().strftime('%H:%M:%S')}")

        if self.circuit_breaker.is_tripped:
            logger.warning(f"서킷브레이커: {self.circuit_breaker.trip_reason}")
            return {"skipped": True, "reason": self.circuit_breaker.trip_reason}

        # 시장 국면 감지 (전략 가중치 갱신)
        regime = self._update_regime()
        logger.info(
            f"시장 국면: {regime.value} | "
            f"상세: {self.regime_detector.get_status().get('details', {})}"
        )

        scan_results = self.scan_watchlist()
        self.execute_trades(scan_results)

        return {
            "timestamp": datetime.now().isoformat(),
            "regime": self.regime_detector.get_status(),
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
        logger.info(f"StockBot v3.7 자동매매 시작 ({mode})")
        logger.info(f"초기 자본: {self._initial_capital:,}원")
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
            "initial_capital": self._initial_capital,
            "balance": balance,
            "positions": positions,
            "total_trades": stats["total"],
            "win_rate": stats["win_rate"],
            "total_pnl": round(total_pnl),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "recent_trades": self.trade_history[-20:],
            "circuit_breaker": self.circuit_breaker.get_status(),
            "scheduler": self.scheduler.get_status(),
            "regime": self.regime_detector.get_status(),
            "execution": self.execution_engine.get_daily_stats(),
        }


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    print("=" * 60)
    print("  StockBot v3.7 - 주식 자동매매")
    print("  6전략앙상블 + ML예측 + 멀티알림 + 리밸런싱 + 수급 + WebSocket")
    print("=" * 60)

    # 트레이딩 모드 결정
    is_live = (TRADING_MODE == "live" and LIVE_TRADING_CONFIRMED)

    if is_live:
        # 라이브 모드: 콘솔에서 최종 확인
        if not _confirm_live_trading():
            print("\n실전 매매가 취소되었습니다. 페이퍼 모드로 전환합니다.")
            is_live = False

    paper_trading = not is_live
    mode_str = "실전투자" if is_live else "모의투자"

    print(f"\n모드: {mode_str}")
    print(f"초기 자본: {INITIAL_CAPITAL:,}원")
    print(f"관심종목: {len(WATCHLIST)}개")
    print(f"매매 간격: {STOCK_TRADING_CONFIG['trade_interval_minutes']}분")
    print(f"최대 보유: {STOCK_TRADING_CONFIG['max_positions']}종목")
    print(f"손절: {STOCK_TRADING_CONFIG['stop_loss_pct']}% | 익절: {STOCK_TRADING_CONFIG['take_profit_pct']}% | 트레일링: ATR({ATR_PERIOD}) x{ATR_MULTIPLIER:.0f} Chandelier Exit")
    print(f"포지션사이징: ATR 기반 (거래당 {STOCK_TRADING_CONFIG.get('atr_risk_pct', 2.0)}% 리스크)")
    print(f"RSI(2) 급락매수: RSI2<{RSI2_BUY_THRESHOLD} & MA200위 | 청산: RSI2>{RSI2_SELL_THRESHOLD} or {RSI2_MAX_HOLD_DAYS}일")
    print(f"종목당 최대: {STOCK_TRADING_CONFIG['max_single_pct']}% | 섹터 최대: {STOCK_TRADING_CONFIG['max_sector_pct']}%")

    # 데이터 프리로드
    print("\n데이터 프리로드 중...")
    trader = StockTrader(paper_trading=paper_trading)
    load_result = trader.client.preload_data(WATCHLIST)
    loaded = sum(1 for v in load_result.values() if v["loaded"])
    print(f"로드 완료: {loaded}/{len(WATCHLIST)}종목\n")

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
