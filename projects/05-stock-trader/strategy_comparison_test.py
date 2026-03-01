"""
전략 비교 백테스트: 현행 vs 개선안
- 최근 3개월 (2025.12 ~ 2026.02)
- 하락장 (2025.03 ~ 2025.05, 미국 관세 충격)
두 기간에서 현행 앙상블 vs 개선 앙상블 비교
"""
import sys
import os
from datetime import datetime, timedelta

STRATEGY_DIR = os.path.join(os.path.dirname(__file__), "strategy")
TRADING_DIR = os.path.join(os.path.dirname(__file__), "trading-bot")
sys.path.insert(0, STRATEGY_DIR)
sys.path.insert(0, TRADING_DIR)

import pandas as pd
import numpy as np
import yfinance as yf

from stock_selector import StockSelectorEnsemble
from regime_detector import RegimeDetector

# ── 공통 설정 ──
FEE_RATE = 0.00015
TAX_RATE = 0.0023       # 증권거래세 0.23%
SELL_FEE_RATE = 0.00015
SPREAD_COST = 0.0005    # 스프레드 비용 0.05% (개선안에서 반영)

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
    ("068270", "셀트리온", "바이오"),
    ("086790", "하나금융지주", "금융"),
    ("017670", "SK텔레콤", "통신"),
]


def download_data(code, start_date, end_date):
    """yfinance 데이터 다운로드"""
    ticker = f"{code}.KS"
    try:
        df = yf.download(ticker, start=start_date, end=end_date,
                         progress=False, auto_adjust=True)
        if df is None or len(df) == 0:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume"
        })
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                return None
        df = df[["open", "high", "low", "close", "volume"]].dropna()
        df = df.reset_index(drop=True)
        return df
    except Exception as e:
        print(f"  [WARN] {code} 다운로드 실패: {e}")
        return None


def compute_rsi_wilder(series, period=14):
    """Wilder EMA 기반 정확한 RSI"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def improved_score(df, code, name, regime="SIDEWAYS"):
    """
    개선된 앙상블 스코어링

    학술 연구 기반 개선사항:
    1. RSI: Wilder EMA 사용 + 연속 그래디언트 (flat 50 zone 제거)
    2. MACD: 히스토그램 크기 반영 + 다이버전스 감지
    3. 모멘텀: 한국 시장 역전 효과 반영 (역모멘텀 가산)
    4. 전략 중복 제거: RSI+BB → 평균회귀 통합, MACD+MA → 추세 통합
    5. 거래량 가중 강화: 외국인/기관 프록시 강화
    6. 변동성 역가중: 저변동성 종목에 더 높은 점수
    """
    if df is None or len(df) < 130:
        return {"score": 50, "action": "HOLD", "confidence": 0,
                "symbol": code, "name": name, "reasons": [],
                "current_price": 0}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)
    current_price = float(close.iloc[-1])

    scores = {}
    reasons = []

    # ── 1. 평균회귀 통합 (RSI + Bollinger 합산) ──
    # RSI (Wilder EMA, 연속 그래디언트)
    rsi = compute_rsi_wilder(close, 14)
    rsi_val = float(rsi.iloc[-1])
    # 연속 매핑: RSI 30→80, RSI 50→50, RSI 70→20 (스케일 업)
    rsi_score = 50 + (50 - rsi_val) * 0.75
    rsi_score = max(10, min(90, rsi_score))

    # Bollinger %B
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = ma20 + 2 * std20
    lower = ma20 - 2 * std20
    pband = (close.iloc[-1] - float(lower.iloc[-1])) / (float(upper.iloc[-1]) - float(lower.iloc[-1])) if (float(upper.iloc[-1]) - float(lower.iloc[-1])) > 0 else 0.5
    bb_score = 50 + (0.5 - pband) * 80
    bb_score = max(10, min(90, bb_score))

    # 통합 평균회귀 점수
    mean_rev_score = rsi_score * 0.5 + bb_score * 0.5
    scores["평균회귀"] = mean_rev_score
    if mean_rev_score >= 65:
        reasons.append(f"평균회귀↑ RSI={rsi_val:.0f} %B={pband:.2f}")
    elif mean_rev_score <= 35:
        reasons.append(f"평균회귀↓ RSI={rsi_val:.0f} %B={pband:.2f}")

    # ── 2. 추세 통합 (MACD + MA 합산) ──
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    histogram = macd_line - signal_line

    hist_val = float(histogram.iloc[-1])
    hist_prev = float(histogram.iloc[-2])

    # MACD 점수: 히스토그램 크기 반영 (학술 개선)
    hist_norm = hist_val / (float(close.iloc[-1]) * 0.01) if close.iloc[-1] > 0 else 0
    macd_score = 50 + hist_norm * 25  # 15→25 스케일 확대
    # 크로스오버 보너스
    if hist_prev <= 0 < hist_val:
        macd_score += 15  # 10→15 골든크로스 보너스 확대
        reasons.append("MACD 골든크로스")
    elif hist_prev >= 0 > hist_val:
        macd_score -= 15
        reasons.append("MACD 데드크로스")
    # MACD 방향성 보너스 (가속/감속)
    if hist_val > 0 and hist_val > hist_prev:
        macd_score += 5  # 양의 히스토그램 + 확대 중
    elif hist_val < 0 and hist_val < hist_prev:
        macd_score -= 5  # 음의 히스토그램 + 확대 중
    macd_score = max(10, min(90, macd_score))

    # MA 정렬
    ma5 = float(close.rolling(5).mean().iloc[-1])
    ma20_val = float(ma20.iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])

    ma_score = 50
    if ma5 > ma20_val > ma60 > ma120:
        ma_score = 75  # 70→75 정배열 보너스 확대
        reasons.append("MA 정배열")
    elif ma5 < ma20_val < ma60 < ma120:
        ma_score = 25  # 30→25 역배열 패널티 확대
        reasons.append("MA 역배열")
    elif ma5 > ma20_val > ma60:
        ma_score = 65  # 부분 정배열
    elif ma5 > ma20_val:
        ma_score = 58
    elif ma5 < ma20_val < ma60:
        ma_score = 35  # 부분 역배열
    elif ma5 < ma20_val:
        ma_score = 42

    # 추세 통합
    trend_score = macd_score * 0.5 + ma_score * 0.5
    scores["추세추종"] = trend_score

    # ── 3. 한국형 모멘텀 (역전 효과 반영) ──
    # Jegadeesh & Titman: 한국 시장은 역전 효과가 지배적
    ret_20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0
    ret_60 = float((close.iloc[-1] / close.iloc[-61] - 1) * 100) if len(close) > 61 else 0

    # 단기(20일)는 역모멘텀, 중기(60일)는 약한 모멘텀
    # 한국 시장 특성: 과도하게 오른 종목은 조정, 과도하게 빠진 종목은 반등
    reversal_score = 50 - ret_20 * 0.8  # 0.3→0.8 역모멘텀 크게 확대
    momentum_score = 50 + ret_60 * 0.3  # 0.15→0.3 중기 모멘텀 확대

    korea_mom_score = reversal_score * 0.6 + momentum_score * 0.4
    korea_mom_score = max(10, min(90, korea_mom_score))
    scores["한국형모멘텀"] = korea_mom_score
    if korea_mom_score >= 65:
        reasons.append(f"역전매수 20d={ret_20:+.1f}%")
    elif korea_mom_score <= 35:
        reasons.append(f"과열경고 20d={ret_20:+.1f}%")

    # ── 4. 거래량 분석 (외국인/기관 프록시 강화) ──
    vol_ma5 = float(volume.rolling(5).mean().iloc[-1])
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1

    # OBV 추세
    obv = (volume * np.sign(close.diff())).cumsum()
    obv_ma5 = float(obv.rolling(5).mean().iloc[-1])
    obv_current = float(obv.iloc[-1])

    vol_score = 50
    # 거래량 급증 + 가격 상승 → 기관 매집 가능성
    if vol_ratio > 1.5 and close.iloc[-1] > close.iloc[-2]:
        vol_score += 20  # 15→20
        reasons.append(f"거래량급증↑ {vol_ratio:.1f}배")
    elif vol_ratio > 1.2 and close.iloc[-1] > close.iloc[-2]:
        vol_score += 10  # 중간 증가도 반영
    elif vol_ratio > 1.5 and close.iloc[-1] < close.iloc[-2]:
        vol_score -= 15  # 10→15
        reasons.append(f"거래량급증↓ {vol_ratio:.1f}배")
    elif vol_ratio < 0.7:
        vol_score -= 5  # 거래량 급감도 음의 신호

    # OBV 방향성
    if obv_current > obv_ma5:
        vol_score += 10  # 8→10
    elif obv_current < obv_ma5:
        vol_score -= 10

    # 연속 거래량 증가 (3일 이상) → 기관 누적 매수 가능성
    recent_vols = volume.tail(5).values
    if all(recent_vols[i] > recent_vols[i-1] for i in range(1, min(4, len(recent_vols)))):
        vol_score += 8  # 5→8
        reasons.append("연속거래량증가")

    vol_score = max(10, min(90, vol_score))
    scores["거래량"] = vol_score

    # ── 5. 변동성 역가중 (저변동성 프리미엄) ──
    returns = close.pct_change().dropna()
    vol_20 = float(returns.tail(20).std() * np.sqrt(252) * 100)  # 연환산 %
    vol_60 = float(returns.tail(60).std() * np.sqrt(252) * 100)

    # 변동성 감소 추세 = 안정적 = 긍정적
    vol_trend_score = 50
    if vol_20 < vol_60 * 0.7:
        vol_trend_score = 72  # 변동성 크게 감소
        reasons.append(f"변동성감소↑ {vol_20:.0f}%→{vol_60:.0f}%")
    elif vol_20 < vol_60 * 0.85:
        vol_trend_score = 62  # 변동성 소폭 감소
        reasons.append(f"변동성감소 {vol_20:.0f}%→{vol_60:.0f}%")
    elif vol_20 > vol_60 * 1.5:
        vol_trend_score = 28  # 변동성 크게 증가
        reasons.append(f"변동성급등↑ {vol_20:.0f}%→{vol_60:.0f}%")
    elif vol_20 > vol_60 * 1.2:
        vol_trend_score = 38
        reasons.append(f"변동성증가 {vol_20:.0f}%→{vol_60:.0f}%")

    scores["변동성"] = vol_trend_score

    # ── 앙상블 집계 ──
    # 가중치: 국면별 차등
    if regime == "BULL":
        weights = {"추세추종": 0.30, "한국형모멘텀": 0.20, "거래량": 0.20,
                   "평균회귀": 0.15, "변동성": 0.15}
    elif regime == "BEAR":
        weights = {"평균회귀": 0.30, "변동성": 0.25, "거래량": 0.20,
                   "추세추종": 0.15, "한국형모멘텀": 0.10}
    else:  # SIDEWAYS
        weights = {"평균회귀": 0.25, "거래량": 0.25, "추세추종": 0.20,
                   "변동성": 0.15, "한국형모멘텀": 0.15}

    final_score = sum(scores[k] * weights[k] for k in scores)
    final_score = round(max(10, min(90, final_score)), 1)

    # 판단 (서브스코어 범위가 넓어졌으므로 임계값 조정)
    if final_score >= 58:
        action = "BUY"
    elif final_score <= 42:
        action = "SELL"
    else:
        action = "HOLD"

    confidence = round(abs(final_score - 50) / 50, 2)

    return {
        "score": final_score,
        "action": action,
        "confidence": confidence,
        "symbol": code,
        "name": name,
        "reasons": reasons,
        "current_price": current_price,
        "sub_scores": scores,
    }


def run_backtest(stock_data, sim_days, initial_capital, strategy_fn,
                 strategy_name, min_buy_score=62, stop_loss=-5.0,
                 take_profit=10.0, realistic_costs=False):
    """단일 백테스트 실행"""
    min_len = min(len(d["df"]) for d in stock_data.values())
    actual_sim_days = min(sim_days, min_len - 130)
    if actual_sim_days <= 0:
        print(f"  [{strategy_name}] 데이터 부족으로 시뮬 불가")
        return None

    cash = float(initial_capital)
    positions = {}
    trade_log = []
    daily_equity = []
    max_equity = initial_capital
    max_drawdown = 0

    regime_detector = RegimeDetector()
    # 국면 감지
    price_series = [d["df"] for d in stock_data.values()]
    regime = regime_detector.detect(price_series)
    regime_str = regime.value

    for day_offset in range(actual_sim_days, 0, -1):
        day_idx = min_len - day_offset

        # 종목별 분석
        signals = []
        for code, info in stock_data.items():
            df = info["df"]
            if day_idx >= len(df):
                continue
            window = df.iloc[:day_idx + 1].copy()
            if len(window) < 130:
                continue
            try:
                result = strategy_fn(window, code, info["name"], regime_str)
                result["sector"] = info["sector"]
                signals.append(result)
            except Exception:
                continue

        # 포트폴리오 가치
        portfolio_value = cash
        for code, pos in positions.items():
            if code in stock_data:
                df = stock_data[code]["df"]
                if day_idx < len(df):
                    portfolio_value += pos["qty"] * float(df.iloc[day_idx]["close"])

        # 최대 낙폭 추적
        max_equity = max(max_equity, portfolio_value)
        dd = (portfolio_value - max_equity) / max_equity * 100
        max_drawdown = min(max_drawdown, dd)

        # 매도 체크
        codes_to_sell = []
        for code, pos in list(positions.items()):
            if code not in stock_data:
                continue
            df = stock_data[code]["df"]
            if day_idx >= len(df):
                continue
            cp = float(df.iloc[day_idx]["close"])
            pnl_pct = (cp - pos["buy_price"]) / pos["buy_price"] * 100

            sell_reason = None
            if pnl_pct <= stop_loss:
                sell_reason = f"손절({pnl_pct:+.1f}%)"
            elif pnl_pct >= take_profit:
                sell_reason = f"익절({pnl_pct:+.1f}%)"
            else:
                for sig in signals:
                    if sig["symbol"] == code and sig["action"] == "SELL":
                        sell_reason = f"전략매도(score:{sig['score']:.1f})"
                        break
            if sell_reason:
                codes_to_sell.append((code, cp, pnl_pct, sell_reason))

        for code, price, pnl_pct, reason in codes_to_sell:
            pos = positions[code]
            sell_amount = pos["qty"] * price
            if realistic_costs:
                fee = sell_amount * (SELL_FEE_RATE + TAX_RATE + SPREAD_COST)
            else:
                fee = sell_amount * (SELL_FEE_RATE + TAX_RATE)
            cash += sell_amount - fee
            realized_pnl = sell_amount - fee - (pos["qty"] * pos["buy_price"])
            trade_log.append({
                "action": "SELL", "code": code, "name": pos["name"],
                "qty": pos["qty"], "price": int(price),
                "pnl": int(realized_pnl), "pnl_pct": round(pnl_pct, 2),
                "reason": reason,
            })
            del positions[code]

        # 매수
        buy_candidates = [
            s for s in signals
            if s["action"] == "BUY"
            and s["score"] >= min_buy_score
            and s.get("confidence", 0) >= 0.15
            and s["symbol"] not in positions
        ]
        buy_candidates.sort(key=lambda x: x["score"], reverse=True)

        max_positions = 4
        for cand in buy_candidates:
            if len(positions) >= max_positions:
                break
            code = cand["symbol"]
            price = cand["current_price"]
            if price <= 0:
                continue

            max_trade = portfolio_value * 0.30
            available = cash * 0.85
            trade_amount = min(max_trade, available)
            if trade_amount < price:
                continue

            qty = int(trade_amount / price)
            if qty <= 0:
                continue

            cost = qty * price
            if realistic_costs:
                fee = cost * (FEE_RATE + SPREAD_COST)
            else:
                fee = cost * FEE_RATE
            total_cost = cost + fee
            if total_cost > cash:
                continue

            cash -= total_cost
            positions[code] = {
                "qty": qty, "buy_price": float(price), "name": cand["name"],
                "sector": cand.get("sector", ""),
            }
            trade_log.append({
                "action": "BUY", "code": code, "name": cand["name"],
                "qty": qty, "price": int(price),
                "score": cand["score"], "reason": f"score={cand['score']:.1f}",
            })

        # 일일 기록
        total_value = cash
        for code, pos in positions.items():
            if code in stock_data:
                df = stock_data[code]["df"]
                if day_idx < len(df):
                    total_value += pos["qty"] * float(df.iloc[day_idx]["close"])
        daily_equity.append(total_value)

    # 최종 가치
    final_value = cash
    for code, pos in positions.items():
        if code in stock_data:
            final_value += pos["qty"] * float(stock_data[code]["df"].iloc[-1]["close"])

    total_return = (final_value - initial_capital) / initial_capital * 100
    buy_trades = [t for t in trade_log if t["action"] == "BUY"]
    sell_trades = [t for t in trade_log if t["action"] == "SELL"]
    winning = [t for t in sell_trades if t.get("pnl", 0) > 0]

    # 샤프비율
    if len(daily_equity) > 1:
        eq_series = pd.Series(daily_equity)
        daily_returns = eq_series.pct_change().dropna()
        sharpe = float(daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    else:
        sharpe = 0

    return {
        "strategy": strategy_name,
        "initial": initial_capital,
        "final": int(final_value),
        "return_pct": round(total_return, 2),
        "buys": len(buy_trades),
        "sells": len(sell_trades),
        "win_rate": round(len(winning) / max(len(sell_trades), 1) * 100, 1),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe": round(sharpe, 2),
        "trade_log": trade_log,
        "daily_equity": daily_equity,
        "regime": regime_str,
        "remaining_positions": len(positions),
    }


def current_strategy_fn(df, code, name, regime_str="SIDEWAYS"):
    """현행 8전략 앙상블"""
    selector = StockSelectorEnsemble()
    regime_detector = RegimeDetector()
    regime_detector._current_regime_value = regime_str
    weights = regime_detector.get_strategy_weights()
    selector.apply_regime_weights(weights)
    return selector.evaluate(df, code, name)


def main():
    INITIAL_CAPITAL = 2_000_000

    # ── 기간 정의 ──
    periods = {
        "최근3개월 (2025.12~2026.02)": {
            "start": "2025-06-01",  # 워밍업 데이터 포함
            "end": "2026-03-01",
            "sim_days": 60,
        },
        "하락장 (2025.03~2025.05 관세충격)": {
            "start": "2024-09-01",  # 워밍업
            "end": "2025-06-01",
            "sim_days": 60,
        },
    }

    print("=" * 75)
    print("  전략 비교 백테스트: 현행 8전략 vs 개선 앙상블")
    print("  학술 연구 기반 개선사항 적용")
    print("=" * 75)

    all_results = {}

    for period_name, period_cfg in periods.items():
        print(f"\n{'='*75}")
        print(f"  기간: {period_name}")
        print(f"  데이터: {period_cfg['start']} ~ {period_cfg['end']}")
        print(f"{'='*75}")

        # 데이터 다운로드
        print("\n  데이터 다운로드 중...")
        stock_data = {}
        for code, name, sector in WATCHLIST:
            df = download_data(code, period_cfg["start"], period_cfg["end"])
            if df is not None and len(df) >= 130:
                stock_data[code] = {"name": name, "sector": sector, "df": df}
                print(f"    OK  {name}({code}): {len(df)}일")
            else:
                cnt = len(df) if df is not None else 0
                print(f"    SKIP {name}({code}): {cnt}일 (부족)")

        if len(stock_data) < 5:
            print("  데이터 부족 - 이 기간 건너뜀")
            continue

        sim_days = period_cfg["sim_days"]

        # ── 전략 A: 현행 8전략 앙상블 ──
        print(f"\n  [A] 현행 8전략 앙상블 실행 중... (sim_days={sim_days})")
        result_a = run_backtest(
            stock_data, sim_days, INITIAL_CAPITAL,
            strategy_fn=current_strategy_fn,
            strategy_name="현행 8전략",
            min_buy_score=65,
            stop_loss=-5.0,
            take_profit=15.0,
            realistic_costs=False,
        )

        # ── 전략 B: 개선 앙상블 ──
        print(f"  [B] 개선 앙상블 실행 중... (sim_days={sim_days})")
        result_b = run_backtest(
            stock_data, sim_days, INITIAL_CAPITAL,
            strategy_fn=improved_score,
            strategy_name="개선 앙상블",
            min_buy_score=58,  # 62→58 임계값 하향 (개별 서브스코어가 넓어졌으므로)
            stop_loss=-5.0,
            take_profit=10.0,
            realistic_costs=True,
        )

        # ── 전략 C: 현행 + 현실적 비용 (공정 비교) ──
        print(f"  [C] 현행 8전략 + 현실적 비용...")
        result_c = run_backtest(
            stock_data, sim_days, INITIAL_CAPITAL,
            strategy_fn=current_strategy_fn,
            strategy_name="현행(현실비용)",
            min_buy_score=65,
            stop_loss=-5.0,
            take_profit=15.0,
            realistic_costs=True,
        )

        all_results[period_name] = {
            "A": result_a,
            "B": result_b,
            "C": result_c,
        }

        # 결과 출력
        print(f"\n  {'─'*70}")
        print(f"  결과 비교: {period_name}")
        print(f"  {'─'*70}")
        print(f"  {'전략':<20} {'수익률':>8} {'매수':>5} {'매도':>5} {'승률':>7} {'MDD':>8} {'샤프':>6} {'국면':<10}")
        print(f"  {'-'*70}")

        for key, label in [("A", "현행 8전략"), ("B", "개선 앙상블"), ("C", "현행(현실비용)")]:
            r = all_results[period_name][key]
            if r:
                print(f"  {r['strategy']:<20} {r['return_pct']:>+7.2f}% {r['buys']:>5} {r['sells']:>5} "
                      f"{r['win_rate']:>6.1f}% {r['max_drawdown']:>+7.2f}% {r['sharpe']:>5.2f}  {r['regime']}")
            else:
                print(f"  {label:<20} 실행 불가")

        # 거래 상세
        for key in ["A", "B"]:
            r = all_results[period_name][key]
            if r and r["trade_log"]:
                label = r["strategy"]
                print(f"\n  [{label}] 거래 내역 (최근 10건):")
                print(f"  {'구분':<6} {'종목':<12} {'수량':>5} {'가격':>10} {'손익':>10} {'사유'}")
                for t in r["trade_log"][-10:]:
                    pnl_str = f"{t.get('pnl', 0):+,}" if "pnl" in t else "-"
                    print(f"  {t['action']:<6} {t['name']:<12} {t['qty']:>5} {t['price']:>10,} {pnl_str:>10} {t['reason']}")

    # ── 종합 비교 ──
    print(f"\n\n{'='*75}")
    print("  종합 비교 요약")
    print(f"{'='*75}")

    for period_name, results in all_results.items():
        print(f"\n  [{period_name}]")
        a = results.get("A")
        b = results.get("B")
        c = results.get("C")
        if a and b:
            diff = b["return_pct"] - a["return_pct"]
            print(f"    현행 8전략:    {a['return_pct']:>+7.2f}% (MDD {a['max_drawdown']:>+.2f}%, 샤프 {a['sharpe']:.2f})")
            print(f"    개선 앙상블:   {b['return_pct']:>+7.2f}% (MDD {b['max_drawdown']:>+.2f}%, 샤프 {b['sharpe']:.2f})")
            if c:
                print(f"    현행(현실비용): {c['return_pct']:>+7.2f}% (MDD {c['max_drawdown']:>+.2f}%, 샤프 {c['sharpe']:.2f})")
            print(f"    차이:          {diff:>+7.2f}%p {'개선↑' if diff > 0 else '열위↓' if diff < 0 else '동일'}")

    print(f"\n{'='*75}")
    print("  분석 완료")
    print(f"{'='*75}")


if __name__ == "__main__":
    main()
