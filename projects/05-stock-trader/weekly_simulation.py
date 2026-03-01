"""
코스피 1주일 백테스트 시뮬레이션
- 실제 시세 데이터 (yfinance)
- 8전략 앙상블 + 시장국면 감지
- 100만원 초기 자본
"""
import sys
import os
from datetime import datetime, timedelta

# 전략 모듈 경로 추가
STRATEGY_DIR = os.path.join(os.path.dirname(__file__), "strategy")
TRADING_DIR = os.path.join(os.path.dirname(__file__), "trading-bot")
sys.path.insert(0, STRATEGY_DIR)
sys.path.insert(0, TRADING_DIR)

import pandas as pd
import numpy as np
import yfinance as yf

from stock_selector import StockSelectorEnsemble
from regime_detector import RegimeDetector

# ── 설정 ──
INITIAL_CAPITAL = 1_000_000  # 100만원
FEE_RATE = 0.00015           # 매수 수수료 0.015%
TAX_RATE = 0.0018            # 매도 세금 0.18%
SELL_FEE_RATE = 0.00015      # 매도 수수료

MAX_POSITION_PCT = 0.25      # 종목당 최대 25% (100만원이라 넉넉히)
STOP_LOSS_PCT = -5.0
TAKE_PROFIT_PCT = 10.0
MIN_BUY_SCORE = 62           # 소규모 자본이라 약간 완화
MIN_CONFIDENCE = 0.2

# 시뮬레이션 기간 (거래일 수)
SIM_TRADING_DAYS = 66        # 약 3개월 (5=1주, 22=1개월, 66=3개월)

WATCHLIST = [
    ("005930", "삼성전자", "반도체"),
    ("000660", "SK하이닉스", "반도체"),
    ("035420", "NAVER", "인터넷"),
    ("035720", "카카오", "인터넷"),
    ("051910", "LG화학", "화학"),
    ("006400", "삼성SDI", "2차전지"),
    ("003670", "포스코퓨처엠", "2차전지"),
    ("028260", "삼성물산", "건설"),
    ("105560", "KB금융", "금융"),
    ("055550", "신한지주", "금융"),
    ("005380", "현대자동차", "자동차"),
    ("000270", "기아", "자동차"),
    ("207940", "삼성바이오로직스", "바이오"),
    ("068270", "셀트리온", "바이오"),
    ("373220", "LG에너지솔루션", "2차전지"),
]


def download_stock_data(code: str, days: int = 250) -> pd.DataFrame:
    """yfinance로 코스피 종목 데이터 다운로드"""
    ticker = f"{code}.KS"
    end = datetime.now()
    start = end - timedelta(days=int(days * 1.6))  # 주말/공휴일 감안

    try:
        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
        if df is None or len(df) == 0:
            return None

        # 컬럼 정리: yfinance는 MultiIndex를 반환할 수 있음
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume"
        })

        # 필요한 컬럼만
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                return None

        df = df[["open", "high", "low", "close", "volume"]].dropna()
        df = df.reset_index(drop=True)
        return df
    except Exception as e:
        print(f"  [WARN] {code} 데이터 다운로드 실패: {e}")
        return None


def run_simulation():
    """1주일 포트폴리오 시뮬레이션"""
    print("=" * 70)
    print("  코스피 백테스트 시뮬레이션")
    print(f"  초기 자본: {INITIAL_CAPITAL:,}원")
    print(f"  시뮬레이션 기간: 최근 {SIM_TRADING_DAYS}거래일 (~{SIM_TRADING_DAYS//5}주)")
    print("=" * 70)

    # ── 1단계: 데이터 다운로드 ──
    print("\n[1/4] 시세 데이터 다운로드 중...")
    stock_data = {}
    for code, name, sector in WATCHLIST:
        df = download_stock_data(code)
        if df is not None and len(df) >= 130:
            stock_data[code] = {"name": name, "sector": sector, "df": df}
            print(f"  OK  {name}({code}): {len(df)}일 데이터")
        else:
            print(f"  SKIP {name}({code}): 데이터 부족")

    if not stock_data:
        print("\n데이터를 가져올 수 없습니다. 네트워크 연결을 확인하세요.")
        return

    # ── 2단계: 시장 국면 감지 ──
    print("\n[2/4] 시장 국면 감지...")
    regime_detector = RegimeDetector()
    price_series = [d["df"] for d in stock_data.values()]
    regime = regime_detector.detect(price_series)
    regime_weights = regime_detector.get_strategy_weights()
    details = regime_detector.get_status()["details"]
    print(f"  현재 시장 국면: {regime.value}")
    if details:
        print(f"  MA 단기/장기 차이: {details.get('ma_diff_pct', 0):+.3f}%")
        print(f"  ADX: {details.get('adx', 0):.1f}")
        print(f"  최근 수익률: {details.get('recent_return_pct', 0):+.2f}%")

    # ── 3단계: 일별 시뮬레이션 (최근 5거래일) ──
    print("\n[3/4] 시뮬레이션 실행...")

    # 공통 길이 확인 - 최소 데이터 길이
    min_len = min(len(d["df"]) for d in stock_data.values())
    sim_days = min(SIM_TRADING_DAYS, min_len - 130)  # 워밍업 130일 이후

    if sim_days <= 0:
        print("  시뮬레이션 기간 확보 불가 (데이터 부족)")
        return

    cash = float(INITIAL_CAPITAL)
    positions = {}  # {code: {"qty": int, "buy_price": float, "name": str, "sector": str}}
    trade_log = []
    daily_equity = []

    selector = StockSelectorEnsemble()
    selector.apply_regime_weights(regime_weights)

    # 시뮬레이션 시작 인덱스 (마지막 sim_days일 전부터)
    for day_offset in range(sim_days, 0, -1):
        day_idx = min_len - day_offset
        day_label = f"D-{day_offset}"

        # 이 날의 종목별 분석
        signals = []
        for code, info in stock_data.items():
            df = info["df"]
            if day_idx >= len(df):
                continue
            window = df.iloc[:day_idx + 1].copy()
            if len(window) < 130:
                continue

            try:
                result = selector.evaluate(window, code, info["name"])
                result["sector"] = info["sector"]
                signals.append(result)
            except Exception:
                continue

        # 현재 포트폴리오 가치 계산
        portfolio_value = cash
        for code, pos in positions.items():
            if code in stock_data:
                df = stock_data[code]["df"]
                if day_idx < len(df):
                    current_price = float(df.iloc[day_idx]["close"])
                    portfolio_value += pos["qty"] * current_price

        # 1) 보유 종목 손절/익절 체크
        codes_to_sell = []
        for code, pos in list(positions.items()):
            if code not in stock_data:
                continue
            df = stock_data[code]["df"]
            if day_idx >= len(df):
                continue

            current_price = float(df.iloc[day_idx]["close"])
            pnl_pct = (current_price - pos["buy_price"]) / pos["buy_price"] * 100

            sell_reason = None
            if pnl_pct <= STOP_LOSS_PCT:
                sell_reason = f"손절 ({pnl_pct:+.1f}%)"
            elif pnl_pct >= TAKE_PROFIT_PCT:
                sell_reason = f"익절 ({pnl_pct:+.1f}%)"
            else:
                # 전략 시그널로 매도
                for sig in signals:
                    if sig["symbol"] == code and sig["action"] == "SELL":
                        sell_reason = f"전략매도 (score:{sig['score']:.1f})"
                        break

            if sell_reason:
                codes_to_sell.append((code, current_price, pnl_pct, sell_reason))

        for code, price, pnl_pct, reason in codes_to_sell:
            pos = positions[code]
            sell_amount = pos["qty"] * price
            fee = sell_amount * (SELL_FEE_RATE + TAX_RATE)
            cash += sell_amount - fee
            realized_pnl = sell_amount - fee - (pos["qty"] * pos["buy_price"])

            trade_log.append({
                "day": day_label,
                "action": "SELL",
                "code": code,
                "name": pos["name"],
                "qty": pos["qty"],
                "price": int(price),
                "amount": int(sell_amount),
                "fee": int(fee),
                "pnl": int(realized_pnl),
                "pnl_pct": round(pnl_pct, 2),
                "reason": reason,
            })
            del positions[code]

        # 2) 매수 시그널 처리
        buy_candidates = [
            s for s in signals
            if s["action"] == "BUY"
            and s["score"] >= MIN_BUY_SCORE
            and s["confidence"] >= MIN_CONFIDENCE
            and s["symbol"] not in positions
        ]
        # 점수 높은 순 정렬
        buy_candidates.sort(key=lambda x: x["score"], reverse=True)

        for candidate in buy_candidates:
            code = candidate["symbol"]
            price = candidate["current_price"]
            if price <= 0:
                continue

            # 포지션 크기 계산
            max_trade = portfolio_value * MAX_POSITION_PCT
            available = cash * 0.95  # 현금의 95%까지만 사용
            trade_amount = min(max_trade, available)

            if trade_amount < price:  # 1주도 못 사는 경우
                continue

            qty = int(trade_amount / price)
            if qty <= 0:
                continue

            cost = qty * price
            fee = cost * FEE_RATE
            total_cost = cost + fee

            if total_cost > cash:
                qty = int((cash * 0.99) / (price * (1 + FEE_RATE)))
                if qty <= 0:
                    continue
                cost = qty * price
                fee = cost * FEE_RATE
                total_cost = cost + fee

            cash -= total_cost
            positions[code] = {
                "qty": qty,
                "buy_price": float(price),
                "name": candidate["name"],
                "sector": candidate.get("sector", ""),
            }

            trade_log.append({
                "day": day_label,
                "action": "BUY",
                "code": code,
                "name": candidate["name"],
                "qty": qty,
                "price": int(price),
                "amount": int(cost),
                "fee": int(fee),
                "score": candidate["score"],
                "reason": f"앙상블 score={candidate['score']:.1f}",
            })

        # 일일 포트폴리오 기록
        total_value = cash
        pos_details = []
        for code, pos in positions.items():
            if code in stock_data:
                df = stock_data[code]["df"]
                if day_idx < len(df):
                    cp = float(df.iloc[day_idx]["close"])
                    mv = pos["qty"] * cp
                    total_value += mv
                    unrealized = (cp - pos["buy_price"]) / pos["buy_price"] * 100
                    pos_details.append({
                        "name": pos["name"],
                        "qty": pos["qty"],
                        "buy_price": int(pos["buy_price"]),
                        "current_price": int(cp),
                        "market_value": int(mv),
                        "unrealized_pnl_pct": round(unrealized, 2),
                    })

        daily_equity.append({
            "day": day_label,
            "total": int(total_value),
            "cash": int(cash),
            "invested": int(total_value - cash),
            "positions": len(positions),
            "pos_details": pos_details,
        })

    # ── 마지막 날 잔여 포지션 정리 (결과 계산용) ──
    final_value = cash
    final_positions = []
    for code, pos in positions.items():
        if code in stock_data:
            df = stock_data[code]["df"]
            cp = float(df.iloc[-1]["close"])
            mv = pos["qty"] * cp
            final_value += mv
            unrealized = (cp - pos["buy_price"]) / pos["buy_price"] * 100
            final_positions.append({
                "name": pos["name"],
                "code": code,
                "qty": pos["qty"],
                "buy_price": int(pos["buy_price"]),
                "current_price": int(cp),
                "market_value": int(mv),
                "unrealized_pnl_pct": round(unrealized, 2),
            })

    # ── 4단계: 결과 출력 ──
    print("\n" + "=" * 70)
    print("  시뮬레이션 결과")
    print("=" * 70)

    total_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    print(f"\n  초기 자본:    {INITIAL_CAPITAL:>12,}원")
    print(f"  최종 자산:    {int(final_value):>12,}원")
    print(f"  손익:         {int(final_value - INITIAL_CAPITAL):>+12,}원 ({total_return:+.2f}%)")
    print(f"  현금 잔고:    {int(cash):>12,}원")

    # 매매 내역
    buy_trades = [t for t in trade_log if t["action"] == "BUY"]
    sell_trades = [t for t in trade_log if t["action"] == "SELL"]
    winning = [t for t in sell_trades if t.get("pnl", 0) > 0]
    losing = [t for t in sell_trades if t.get("pnl", 0) <= 0]

    print(f"\n  ── 매매 요약 ──")
    print(f"  총 매수: {len(buy_trades)}건")
    print(f"  총 매도: {len(sell_trades)}건")
    if sell_trades:
        print(f"  승률:    {len(winning)}/{len(sell_trades)} ({len(winning)/len(sell_trades)*100:.0f}%)")
        total_sell_pnl = sum(t.get("pnl", 0) for t in sell_trades)
        print(f"  실현 손익: {total_sell_pnl:+,}원")

    # 거래 상세
    if trade_log:
        print(f"\n  ── 거래 내역 ──")
        print(f"  {'일자':<6} {'구분':<6} {'종목':<12} {'수량':>5} {'가격':>10} {'금액':>12} {'손익':>10} {'사유'}")
        print(f"  {'-'*85}")
        for t in trade_log:
            pnl_str = f"{t.get('pnl', 0):+,}" if "pnl" in t else "-"
            pnl_pct_str = f"({t['pnl_pct']:+.1f}%)" if "pnl_pct" in t else ""
            print(f"  {t['day']:<6} {t['action']:<6} {t['name']:<12} "
                  f"{t['qty']:>5} {t['price']:>10,} {t['amount']:>12,} "
                  f"{pnl_str:>10} {t['reason']}")

    # 보유 중인 포지션
    if final_positions:
        print(f"\n  ── 미정리 포지션 (시뮬레이션 종료 시) ──")
        print(f"  {'종목':<12} {'수량':>5} {'매수가':>10} {'현재가':>10} {'평가액':>12} {'평가손익':>8}")
        print(f"  {'-'*65}")
        for p in final_positions:
            print(f"  {p['name']:<12} {p['qty']:>5} {p['buy_price']:>10,} "
                  f"{p['current_price']:>10,} {p['market_value']:>12,} "
                  f"{p['unrealized_pnl_pct']:>+7.2f}%")

    # 일별 자산 변동
    if daily_equity:
        print(f"\n  ── 일별 자산 변동 ──")
        print(f"  {'일자':<6} {'총자산':>12} {'현금':>12} {'투자':>12} {'보유종목':>8} {'일일수익률':>10}")
        print(f"  {'-'*65}")
        prev_total = INITIAL_CAPITAL
        for eq in daily_equity:
            daily_ret = (eq["total"] - prev_total) / prev_total * 100
            print(f"  {eq['day']:<6} {eq['total']:>12,} {eq['cash']:>12,} "
                  f"{eq['invested']:>12,} {eq['positions']:>8} {daily_ret:>+9.2f}%")
            prev_total = eq["total"]

    # 전략 시그널 현황 (마지막 날)
    print(f"\n  ── 전략 시그널 현황 (마지막 날) ──")
    print(f"  {'종목':<12} {'판단':<6} {'점수':>6} {'신뢰도':>6} {'주요 시그널'}")
    print(f"  {'-'*70}")

    final_signals = []
    for code, info in stock_data.items():
        df = info["df"]
        try:
            result = selector.evaluate(df, code, info["name"])
            final_signals.append(result)
        except Exception:
            continue

    final_signals.sort(key=lambda x: x["score"], reverse=True)
    for sig in final_signals:
        reasons_str = " | ".join(sig["reasons"][:2]) if sig["reasons"] else "-"
        print(f"  {sig['name']:<12} {sig['action']:<6} {sig['score']:>5.1f} "
              f"{sig['confidence']:>5.2f}  {reasons_str[:45]}")

    print("\n" + "=" * 70)
    print(f"  시장 국면: {regime.value} | 시뮬레이션 완료")
    print("=" * 70)


if __name__ == "__main__":
    run_simulation()
