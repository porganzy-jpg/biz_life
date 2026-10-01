"""
v4.0 지수 코어 실행기 — 하루 1회, 장 마감 후 실행

1) KODEX200 종가 이력으로 목표 비중 계산 (strategy/index_core.py)
2) 현재 비중과 비교해 needs_rebalance()가 True면 목표 비중으로 매매
3) 장부(index_core_state.json)에 기록 + 알림

- 기본은 페이퍼: 당일 종가로 체결한 것으로 장부만 갱신 (백테스트와 동일 가정)
- 실전 주문은 BrokerClient의 이중 안전장치(TRADING_MODE=live + LIVE_TRADING_CONFIRMED=true)를
  통과할 때만 나간다. 실전에서는 다음 날 시가 근처 체결이 되므로 백테스트와 약간 다를 수 있음.
- 같은 날짜를 두 번 처리하지 않음 (재실행 안전)

실행: python index_core_trader.py            # 오늘 신호 계산 + 페이퍼 체결
      python index_core_trader.py --dry-run  # 계산만, 장부 변경 없음
"""
import sys
import os
import json
import logging
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "strategy"))

import pandas as pd

from index_core import SYMBOL, SYMBOL_NAME, MIN_HISTORY, latest_target, needs_rebalance
from config import INDEX_CORE_CONFIG

logger = logging.getLogger(__name__)
STATE_PATH = os.path.join(os.path.dirname(__file__), "index_core_state.json")


def load_close() -> pd.Series:
    """KODEX200 종가 (날짜 인덱스, 당일 포함).
    DataProvider는 end=오늘(미포함)이라 당일 종가가 빠지므로 직접 조회한다."""
    import yfinance as yf
    df = yf.download(f"{SYMBOL}.KS", period="2y", progress=False, auto_adjust=True)
    close = df["Close"].squeeze().dropna()
    now = datetime.now()
    if close.index[-1].date() == now.date() and (now.hour, now.minute) < (15, 35):
        close = close.iloc[:-1]  # 장 마감 전 실행: 미완성 당일 봉 제외
    if len(close) < MIN_HISTORY:
        raise RuntimeError(f"{SYMBOL} 가격 이력 부족: {len(close)}일")
    return close


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"cash": INDEX_CORE_CONFIG["capital"], "units": 0, "last_date": None, "history": []}


def save_state(state: dict):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def run(dry_run: bool = False) -> dict:
    close = load_close()
    sig = latest_target(close)
    day = sig["date"].strftime("%Y-%m-%d")
    price = sig["close"]

    state = load_state()
    equity = state["cash"] + state["units"] * price
    current_w = state["units"] * price / equity if equity > 0 else 0.0

    result = {"date": day, "price": price, "equity": round(equity), "current_w": round(current_w, 4),
              "target_w": round(sig["target"], 4), "trend_ok": sig["trend_ok"],
              "realized_vol": round(sig["realized_vol"], 4), "action": "HOLD", "qty": 0}

    if state["last_date"] == day:
        result["action"] = "SKIP(이미 처리됨)"
        return result

    if needs_rebalance(current_w, sig["target"]):
        target_units = int(equity * sig["target"] // price)
        qty = target_units - state["units"]
        if qty != 0:
            result["action"] = "BUY" if qty > 0 else "SELL"
            result["qty"] = abs(qty)
            if not dry_run:
                state["last_date"] = day  # 실전 주문 직후 저장될 때 당일 처리 완료로 남도록 먼저 기록
                result["qty"] = _execute(result["action"], abs(qty), price, state)

    if not dry_run:
        state["last_date"] = day
        state["history"].append(result)
        save_state(state)
    return result


def _execute(action: str, qty: int, price: float, state: dict):
    """페이퍼: 종가 체결로 장부 갱신. 실전: BrokerClient 주문 후 장부 갱신."""
    from broker_client import BrokerClient
    broker = BrokerClient()
    live = broker.live_trading
    if live:
        order = broker.buy(SYMBOL, SYMBOL_NAME, qty) if action == "BUY" else broker.sell(SYMBOL, qty)
        if not order:
            raise RuntimeError(f"실전 주문 실패: {action} {qty}주")
        # 부분 체결·미체결 반영: 실제 체결 수량/가격만 장부에 기록
        qty = int(order.get("filled_qty", qty if order.get("confirmed", True) else 0))
        price = float(order.get("filled_price") or order.get("price") or price)
        if qty <= 0:
            raise RuntimeError(f"실전 주문 미체결: {action}")
    fee = qty * price * INDEX_CORE_CONFIG["fee_rate"]
    signed = qty if action == "BUY" else -qty
    state["units"] += signed
    state["cash"] -= signed * price + fee
    if live:
        save_state(state)  # 주문 직후 즉시 저장: 이후 크래시로 같은 주문이 재실행되지 않도록
    return qty


def _notify(result: dict):
    try:
        from alert_system import AlertSystem
        AlertSystem().send(
            f"[지수코어] {result['date']} {SYMBOL_NAME} {result['price']:,.0f}원\n"
            f"비중 {result['current_w']:.0%} → 목표 {result['target_w']:.0%} | {result['action']}"
            + (f" {result['qty']}주" if result["qty"] else "")
            + f"\n추세 {'위' if result['trend_ok'] else '아래'}(MA120), 변동성 {result['realized_vol']:.0%}"
            f" | 평가금액 {result['equity']:,}원")
    except Exception as e:
        logger.warning(f"알림 실패: {e}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    result = run(dry_run=args.dry_run)
    logger.info(json.dumps(result, ensure_ascii=False))
    if not args.dry_run and not result["action"].startswith("SKIP"):
        _notify(result)


if __name__ == "__main__":
    main()
