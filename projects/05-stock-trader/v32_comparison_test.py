"""
v3.1 vs v3.2 비교 백테스트
- v3.1: 고정 매핑 + 고정 임계값 (이전 버전)
- v3.2: Z-score 스코어링 + tanh MACD + 폭락가드 + OBV 수정 + 적응형 임계값

기간:
- 최근 3개월 상승장 (2025.12 ~ 2026.02)
- 하락장 (2025.03 ~ 2025.05, 미국 관세 충격)
"""
import sys
import os
from collections import deque

STRATEGY_DIR = os.path.join(os.path.dirname(__file__), "strategy")
TRADING_DIR = os.path.join(os.path.dirname(__file__), "trading-bot")
sys.path.insert(0, STRATEGY_DIR)
sys.path.insert(0, TRADING_DIR)

import pandas as pd
import numpy as np
import yfinance as yf

from regime_detector import RegimeDetector

# ── 공통 설정 ──
FEE_RATE = 0.00015
TAX_RATE = 0.0023
SELL_FEE_RATE = 0.00015
SPREAD_COST = 0.0005

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


# ═══════════════════════════════════════════════
# v3.1 (이전 버전) — 고정 매핑 + 고정 임계값
# ═══════════════════════════════════════════════

def _rsi_wilder_v31(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def v31_score(df, code, name, regime="SIDEWAYS"):
    """v3.1: 고정 매핑, OBV NaN 버그 포함, 고정 임계값 58/42"""
    if df is None or len(df) < 130:
        return {"score": 50, "action": "HOLD", "confidence": 0,
                "symbol": code, "name": name, "reasons": [], "current_price": 0}

    close = df["close"].astype(float)
    volume = df["volume"].astype(float)
    current_price = float(close.iloc[-1])
    scores = {}
    reasons = []

    # 평균회귀 (고정 매핑)
    rsi = _rsi_wilder_v31(close, 14)
    rsi_val = float(rsi.iloc[-1]) if not np.isnan(float(rsi.iloc[-1])) else 50
    rsi_score = max(10, min(90, 50 + (50 - rsi_val) * 0.75))

    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = ma20 + 2 * std20
    lower = ma20 - 2 * std20
    bw = float(upper.iloc[-1]) - float(lower.iloc[-1])
    pband = (close.iloc[-1] - float(lower.iloc[-1])) / bw if bw > 0 else 0.5
    bb_score = max(10, min(90, 50 + (0.5 - pband) * 80))
    scores["평균회귀"] = rsi_score * 0.5 + bb_score * 0.5

    # 추세추종 (고정 매핑, 선형 MACD)
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    hist = (ema12 - ema26) - (ema12 - ema26).ewm(span=9).mean()
    hv = float(hist.iloc[-1])
    hp = float(hist.iloc[-2]) if len(hist) > 1 else 0
    hn = hv / (current_price * 0.01) if current_price > 0 else 0
    macd_s = max(10, min(90, 50 + hn * 25))
    if hp <= 0 < hv: macd_s += 15
    elif hp >= 0 > hv: macd_s -= 15
    macd_s = max(10, min(90, macd_s))

    ma5 = float(close.rolling(5).mean().iloc[-1])
    ma20v = float(ma20.iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])
    ma_s = 50
    if ma5 > ma20v > ma60 > ma120: ma_s = 75
    elif ma5 < ma20v < ma60 < ma120: ma_s = 25
    elif ma5 > ma20v > ma60: ma_s = 65
    elif ma5 > ma20v: ma_s = 58
    elif ma5 < ma20v < ma60: ma_s = 35
    elif ma5 < ma20v: ma_s = 42
    scores["추세추종"] = macd_s * 0.5 + ma_s * 0.5

    # 한국형 모멘텀 (폭락가드 없음)
    r20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0
    r60 = float((close.iloc[-1] / close.iloc[-61] - 1) * 100) if len(close) > 61 else 0
    rev = 50 - r20 * 0.8
    mom = 50 + r60 * 0.3
    scores["한국형모멘텀"] = max(10, min(90, rev * 0.6 + mom * 0.4))

    # 거래량 (OBV NaN 버그 포함 — v3.1 원본 그대로)
    vm5 = float(volume.rolling(5).mean().iloc[-1])
    vm20 = float(volume.rolling(20).mean().iloc[-1])
    vr = vm5 / vm20 if vm20 > 0 else 1
    # 버그: NaN 전파됨
    obv = (volume * np.sign(close.diff())).cumsum()
    obv5 = float(obv.rolling(5).mean().iloc[-1])
    obvc = float(obv.iloc[-1])
    vs = 50
    if vr > 1.5 and close.iloc[-1] > close.iloc[-2]: vs += 20
    elif vr > 1.2 and close.iloc[-1] > close.iloc[-2]: vs += 10
    elif vr > 1.5 and close.iloc[-1] < close.iloc[-2]: vs -= 15
    elif vr < 0.7: vs -= 5
    if obvc > obv5: vs += 10
    elif obvc < obv5: vs -= 10
    scores["거래량"] = max(10, min(90, vs))

    # 변동성
    rets = close.pct_change().dropna()
    v20 = float(rets.tail(20).std() * np.sqrt(252) * 100) if len(rets) >= 20 else 0
    v60 = float(rets.tail(60).std() * np.sqrt(252) * 100) if len(rets) >= 60 else v20
    vts = 50
    if v60 > 0:
        if v20 < v60 * 0.7: vts = 72
        elif v20 < v60 * 0.85: vts = 62
        elif v20 > v60 * 1.5: vts = 28
        elif v20 > v60 * 1.2: vts = 38
    scores["변동성"] = vts

    # 앙상블
    W = {"BULL": {"추세추종": .30, "한국형모멘텀": .20, "거래량": .20, "평균회귀": .15, "변동성": .15},
         "BEAR": {"평균회귀": .30, "변동성": .25, "거래량": .20, "추세추종": .15, "한국형모멘텀": .10},
         "SIDEWAYS": {"평균회귀": .25, "거래량": .25, "추세추종": .20, "변동성": .15, "한국형모멘텀": .15}}
    w = W.get(regime, W["SIDEWAYS"])
    fs = round(max(10, min(90, sum(scores[k] * w[k] for k in scores))), 1)
    action = "BUY" if fs >= 58 else "SELL" if fs <= 42 else "HOLD"
    conf = round(abs(fs - 50) / 50, 2)
    return {"score": fs, "action": action, "confidence": conf,
            "symbol": code, "name": name, "reasons": reasons,
            "current_price": current_price, "sub_scores": scores}


# ═══════════════════════════════════════════════
# v3.2 (개선 버전) — Z-score + tanh + 폭락가드 + OBV수정
# ═══════════════════════════════════════════════

def _rsi_wilder_v32(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _z_score(series, value, lookback=60):
    if len(series) < lookback:
        return 0.0
    w = series.tail(lookback)
    m, s = float(w.mean()), float(w.std())
    return (value - m) / s if s > 1e-10 else 0.0


# 적응형 임계값용 전역 히스토리
_v32_score_history = deque(maxlen=200)


def v32_score(df, code, name, regime="SIDEWAYS"):
    """v3.2: Z-score + tanh + 폭락가드 + OBV수정 + 적응형 임계값"""
    global _v32_score_history

    if df is None or len(df) < 130:
        return {"score": 50, "action": "HOLD", "confidence": 0,
                "symbol": code, "name": name, "reasons": [], "current_price": 0}

    close = df["close"].astype(float)
    volume = df["volume"].astype(float)
    current_price = float(close.iloc[-1])
    scores = {}
    reasons = []

    # ── 1. 평균회귀 (Z-score 기반) ──
    rsi = _rsi_wilder_v32(close, 14)
    rsi_val = float(rsi.iloc[-1])
    rsi_z = _z_score(rsi, rsi_val, 60)
    rsi_score = max(10, min(90, 50 - rsi_z * 15))

    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = ma20 + 2 * std20
    lower = ma20 - 2 * std20
    min_bw = current_price * 0.001
    bw = float(upper.iloc[-1]) - float(lower.iloc[-1])
    pband = (close.iloc[-1] - float(lower.iloc[-1])) / bw if bw > min_bw else 0.5
    pb_series = ((close - lower) / (upper - lower)).replace([np.inf, -np.inf], 0.5).fillna(0.5)
    bb_z = _z_score(pb_series, pband, 60)
    bb_score = max(10, min(90, 50 - bb_z * 15))

    scores["평균회귀"] = rsi_score * 0.5 + bb_score * 0.5
    if scores["평균회귀"] >= 65:
        reasons.append(f"평균회귀↑ RSI={rsi_val:.0f}")
    elif scores["평균회귀"] <= 35:
        reasons.append(f"평균회귀↓ RSI={rsi_val:.0f}")

    # ── 2. 추세추종 (tanh MACD) ──
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    hist = (ema12 - ema26) - (ema12 - ema26).ewm(span=9).mean()
    hv = float(hist.iloc[-1])
    hp = float(hist.iloc[-2]) if len(hist) > 1 else 0
    hn = hv / (current_price * 0.01) if current_price > 0 else 0
    macd_s = 50 + float(np.tanh(hn)) * 30
    if hp <= 0 < hv: macd_s += 15; reasons.append("MACD 골든크로스")
    elif hp >= 0 > hv: macd_s -= 15; reasons.append("MACD 데드크로스")
    if hv > 0 and hv > hp: macd_s += 5
    elif hv < 0 and hv < hp: macd_s -= 5
    macd_s = max(10, min(90, macd_s))

    ma5 = float(close.rolling(5).mean().iloc[-1])
    ma20v = float(ma20.iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])
    ma_s = 50
    if ma5 > ma20v > ma60 > ma120: ma_s = 75; reasons.append("MA 정배열")
    elif ma5 < ma20v < ma60 < ma120: ma_s = 25; reasons.append("MA 역배열")
    elif ma5 > ma20v > ma60: ma_s = 65
    elif ma5 > ma20v: ma_s = 58
    elif ma5 < ma20v < ma60: ma_s = 35
    elif ma5 < ma20v: ma_s = 42
    scores["추세추종"] = macd_s * 0.5 + ma_s * 0.5

    # ── 3. 한국형 모멘텀 (폭락 가드 포함) ──
    r20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0
    r60 = float((close.iloc[-1] / close.iloc[-61] - 1) * 100) if len(close) > 61 else 0
    r20c = np.clip(r20, -30, 30)
    r60c = np.clip(r60, -50, 50)
    rev = 50 - r20c * 0.8
    mom = 50 + r60c * 0.3
    km = max(10, min(90, rev * 0.6 + mom * 0.4))
    if r20 < -25:
        km = min(km, 55)
        reasons.append(f"폭락가드 20d={r20:+.1f}%")
    scores["한국형모멘텀"] = km

    # ── 4. 거래량 (OBV NaN 수정) ──
    vm5 = float(volume.rolling(5).mean().iloc[-1])
    vm20 = float(volume.rolling(20).mean().iloc[-1])
    vr = vm5 / vm20 if vm20 > 0 else 1
    obv = (volume * np.sign(close.diff().fillna(0))).cumsum()
    obv5 = float(obv.rolling(5).mean().iloc[-1])
    obvc = float(obv.iloc[-1])
    vs = 50
    if vr > 1.5 and close.iloc[-1] > close.iloc[-2]: vs += 20
    elif vr > 1.2 and close.iloc[-1] > close.iloc[-2]: vs += 10
    elif vr > 1.5 and close.iloc[-1] < close.iloc[-2]: vs -= 15
    elif vr < 0.7: vs -= 5
    if not (np.isnan(obvc) or np.isnan(obv5)):
        if obvc > obv5: vs += 10
        elif obvc < obv5: vs -= 10
    rv = volume.tail(5).values
    if len(rv) >= 4 and all(rv[i] > rv[i-1] for i in range(1, min(4, len(rv)))):
        vs += 8
    scores["거래량"] = max(10, min(90, vs))

    # ── 5. 변동성 ──
    rets = close.pct_change().dropna()
    v20 = float(rets.tail(20).std() * np.sqrt(252) * 100) if len(rets) >= 20 else 0
    v60 = float(rets.tail(60).std() * np.sqrt(252) * 100) if len(rets) >= 60 else v20
    vts = 50
    if v60 > 0:
        if v20 < v60 * 0.7: vts = 72
        elif v20 < v60 * 0.85: vts = 62
        elif v20 > v60 * 1.5: vts = 28
        elif v20 > v60 * 1.2: vts = 38
    scores["변동성"] = vts

    # NaN 가드
    for k, v in scores.items():
        if np.isnan(v):
            scores[k] = 50

    # 앙상블
    W = {"BULL": {"추세추종": .30, "한국형모멘텀": .20, "거래량": .20, "평균회귀": .15, "변동성": .15},
         "BEAR": {"평균회귀": .30, "변동성": .25, "거래량": .20, "추세추종": .15, "한국형모멘텀": .10},
         "SIDEWAYS": {"평균회귀": .25, "거래량": .25, "추세추종": .20, "변동성": .15, "한국형모멘텀": .15}}
    w = W.get(regime, W["SIDEWAYS"])
    fs = round(max(10, min(90, sum(scores[k] * w[k] for k in scores))), 1)

    _v32_score_history.append(fs)

    # 적응형 임계값
    if len(_v32_score_history) >= 50:
        buy_th = max(55, min(68, float(np.percentile(list(_v32_score_history), 75))))
        sell_th = min(45, max(32, float(np.percentile(list(_v32_score_history), 25))))
    else:
        buy_th, sell_th = 58, 42

    action = "BUY" if fs >= buy_th else "SELL" if fs <= sell_th else "HOLD"
    conf = round(abs(fs - 50) / 50, 2)
    return {"score": fs, "action": action, "confidence": conf,
            "symbol": code, "name": name, "reasons": reasons,
            "current_price": current_price, "sub_scores": scores}


# ═══════════════════════════════════════════════
# 백테스트 엔진
# ═══════════════════════════════════════════════

def run_backtest(stock_data, sim_days, initial_capital, strategy_fn,
                 strategy_name, min_buy_score=58, stop_loss=-5.0,
                 take_profit=10.0):
    min_len = min(len(d["df"]) for d in stock_data.values())
    actual = min(sim_days, min_len - 130)
    if actual <= 0:
        return None

    cash = float(initial_capital)
    positions = {}
    trade_log = []
    daily_equity = []
    max_equity = initial_capital
    max_drawdown = 0

    rd = RegimeDetector()
    regime = rd.detect([d["df"] for d in stock_data.values()])
    regime_str = regime.value

    for day_off in range(actual, 0, -1):
        day_idx = min_len - day_off
        signals = []
        for code, info in stock_data.items():
            df = info["df"]
            if day_idx >= len(df):
                continue
            window = df.iloc[:day_idx + 1].copy()
            if len(window) < 130:
                continue
            try:
                r = strategy_fn(window, code, info["name"], regime_str)
                r["sector"] = info["sector"]
                signals.append(r)
            except Exception:
                continue

        pv = cash
        for c, p in positions.items():
            if c in stock_data:
                df = stock_data[c]["df"]
                if day_idx < len(df):
                    pv += p["qty"] * float(df.iloc[day_idx]["close"])
        max_equity = max(max_equity, pv)
        dd = (pv - max_equity) / max_equity * 100
        max_drawdown = min(max_drawdown, dd)

        # 매도
        to_sell = []
        for c, p in list(positions.items()):
            if c not in stock_data: continue
            df = stock_data[c]["df"]
            if day_idx >= len(df): continue
            cp = float(df.iloc[day_idx]["close"])
            pnl = (cp - p["buy_price"]) / p["buy_price"] * 100
            reason = None
            if pnl <= stop_loss: reason = f"손절({pnl:+.1f}%)"
            elif pnl >= take_profit: reason = f"익절({pnl:+.1f}%)"
            else:
                for s in signals:
                    if s["symbol"] == c and s["action"] == "SELL":
                        reason = f"퀀트매도(score:{s['score']:.1f})"
                        break
            if reason:
                to_sell.append((c, cp, pnl, reason))

        for c, price, pnl, reason in to_sell:
            p = positions[c]
            amt = p["qty"] * price
            fee = amt * (SELL_FEE_RATE + TAX_RATE + SPREAD_COST)
            cash += amt - fee
            rpnl = amt - fee - (p["qty"] * p["buy_price"])
            trade_log.append({"action": "SELL", "code": c, "name": p["name"],
                              "qty": p["qty"], "price": int(price),
                              "pnl": int(rpnl), "pnl_pct": round(pnl, 2),
                              "reason": reason})
            del positions[c]

        # 매수
        buys = [s for s in signals if s["action"] == "BUY"
                and s["score"] >= min_buy_score
                and s.get("confidence", 0) >= 0.15
                and s["symbol"] not in positions]
        buys.sort(key=lambda x: x["score"], reverse=True)

        for cand in buys:
            if len(positions) >= 4: break
            c = cand["symbol"]
            price = cand["current_price"]
            if price <= 0: continue
            trade_amt = min(pv * 0.30, cash * 0.85)
            if trade_amt < price: continue
            qty = int(trade_amt / price)
            if qty <= 0: continue
            cost = qty * price
            fee = cost * (FEE_RATE + SPREAD_COST)
            if cost + fee > cash: continue
            cash -= cost + fee
            positions[c] = {"qty": qty, "buy_price": float(price), "name": cand["name"],
                            "sector": cand.get("sector", "")}
            trade_log.append({"action": "BUY", "code": c, "name": cand["name"],
                              "qty": qty, "price": int(price),
                              "score": cand["score"], "reason": f"score={cand['score']:.1f}"})

        tv = cash
        for c, p in positions.items():
            if c in stock_data:
                df = stock_data[c]["df"]
                if day_idx < len(df):
                    tv += p["qty"] * float(df.iloc[day_idx]["close"])
        daily_equity.append(tv)

    fv = cash
    for c, p in positions.items():
        if c in stock_data:
            fv += p["qty"] * float(stock_data[c]["df"].iloc[-1]["close"])

    ret = (fv - initial_capital) / initial_capital * 100
    bt = [t for t in trade_log if t["action"] == "BUY"]
    st = [t for t in trade_log if t["action"] == "SELL"]
    wt = [t for t in st if t.get("pnl", 0) > 0]

    if len(daily_equity) > 1:
        eq = pd.Series(daily_equity)
        dr = eq.pct_change().dropna()
        sharpe = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0
    else:
        sharpe = 0

    return {
        "strategy": strategy_name,
        "initial": initial_capital, "final": int(fv),
        "return_pct": round(ret, 2),
        "buys": len(bt), "sells": len(st),
        "win_rate": round(len(wt) / max(len(st), 1) * 100, 1),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe": round(sharpe, 2),
        "trade_log": trade_log,
        "regime": regime_str,
        "remaining_positions": len(positions),
    }


def main():
    global _v32_score_history
    CAPITAL = 2_000_000

    periods = {
        "상승장 (2025.12~2026.02)": {
            "start": "2025-06-01", "end": "2026-03-02", "sim_days": 60,
        },
        "하락장 (2025.03~2025.05 관세충격)": {
            "start": "2024-09-01", "end": "2025-06-01", "sim_days": 60,
        },
    }

    print("=" * 75)
    print("  v3.1 vs v3.2 비교 백테스트")
    print("  v3.1: 고정매핑 + OBV NaN + 고정임계값")
    print("  v3.2: Z-score + tanh + 폭락가드 + OBV수정 + 적응형임계값")
    print("=" * 75)

    all_results = {}

    for period_name, pcfg in periods.items():
        print(f"\n{'='*75}")
        print(f"  기간: {period_name}")
        print(f"{'='*75}")

        print("\n  데이터 다운로드...")
        stock_data = {}
        for code, name, sector in WATCHLIST:
            df = download_data(code, pcfg["start"], pcfg["end"])
            if df is not None and len(df) >= 130:
                stock_data[code] = {"name": name, "sector": sector, "df": df}
                print(f"    OK  {name}({code}): {len(df)}일")
            else:
                print(f"    SKIP {name}({code})")

        if len(stock_data) < 5:
            print("  데이터 부족")
            continue

        sd = pcfg["sim_days"]

        # v3.1
        print(f"\n  [A] v3.1 실행...")
        ra = run_backtest(stock_data, sd, CAPITAL, v31_score, "v3.1 (이전)", min_buy_score=58)

        # v3.2
        _v32_score_history.clear()
        print(f"  [B] v3.2 실행...")
        rb = run_backtest(stock_data, sd, CAPITAL, v32_score, "v3.2 (개선)", min_buy_score=58)

        all_results[period_name] = {"A": ra, "B": rb}

        # 결과
        print(f"\n  {'─'*70}")
        print(f"  결과: {period_name}")
        print(f"  {'─'*70}")
        print(f"  {'전략':<20} {'수익률':>8} {'매수':>5} {'매도':>5} {'승률':>7} {'MDD':>8} {'샤프':>6}")
        print(f"  {'-'*70}")
        for key, r in [("A", ra), ("B", rb)]:
            if r:
                print(f"  {r['strategy']:<20} {r['return_pct']:>+7.2f}% {r['buys']:>5} {r['sells']:>5} "
                      f"{r['win_rate']:>6.1f}% {r['max_drawdown']:>+7.2f}% {r['sharpe']:>5.2f}")

        # 거래 상세
        for key in ["A", "B"]:
            r = all_results[period_name][key]
            if r and r["trade_log"]:
                print(f"\n  [{r['strategy']}] 거래 내역:")
                print(f"  {'구분':<6} {'종목':<12} {'수량':>5} {'가격':>10} {'손익':>10} {'사유'}")
                for t in r["trade_log"][-10:]:
                    ps = f"{t.get('pnl', 0):+,}" if "pnl" in t else "-"
                    print(f"  {t['action']:<6} {t['name']:<12} {t['qty']:>5} {t['price']:>10,} {ps:>10} {t['reason']}")

    # 종합
    print(f"\n\n{'='*75}")
    print("  종합 비교")
    print(f"{'='*75}")
    for pn, res in all_results.items():
        a, b = res.get("A"), res.get("B")
        if a and b:
            diff = b["return_pct"] - a["return_pct"]
            print(f"\n  [{pn}]")
            print(f"    v3.1: {a['return_pct']:>+7.2f}% (MDD {a['max_drawdown']:>+.2f}%, 샤프 {a['sharpe']:.2f}, 거래 {a['buys']+a['sells']}건)")
            print(f"    v3.2: {b['return_pct']:>+7.2f}% (MDD {b['max_drawdown']:>+.2f}%, 샤프 {b['sharpe']:.2f}, 거래 {b['buys']+b['sells']}건)")
            print(f"    차이: {diff:>+7.2f}%p {'개선↑' if diff > 0 else '열위↓' if diff < 0 else '동일'}")

    print(f"\n{'='*75}")
    print("  비교 완료")
    print(f"{'='*75}")


if __name__ == "__main__":
    main()
