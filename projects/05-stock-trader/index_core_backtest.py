# -*- coding: utf-8 -*-
"""
v4.0 지수 코어 전략 백테스트 (KODEX200, 2010~)

비교: A) 단순 보유  B) 오버레이만(BLEND=0)  C) 절충형(BLEND=0.5, 채택)
- 신호는 당일 종가로 판정 → 다음 거래일 수익에 적용 (look-ahead 없음)
- 비용: 매매 비중 변화량 × 편도 0.05% (국내 주식형 ETF 증권거래세 면제)
- 현금 수익률 연 2.5%
- 리밸런스 여부는 strategy/index_core.needs_rebalance() 사용

실행: python index_core_backtest.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'strategy'))
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf

from index_core import SYMBOL, MIN_HISTORY, TRADING_DAYS, target_weight, needs_rebalance

COST = 0.0005
CASH_RATE = 0.025 / TRADING_DAYS


def simulate(close: pd.Series, blend: float) -> tuple:
    r = close.pct_change().fillna(0)
    tgt = target_weight(close, blend)
    dates = close.index
    w, out, trades = None, [], 0
    for i in range(MIN_HISTORY, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cost = 0.0
        if w is None or needs_rebalance(w, tgt.loc[d]):
            cost = abs(tgt.loc[d] - (w or 0.0)) * COST
            w = tgt.loc[d]
            trades += 1
        day = w * r.loc[nxt] + (1 - w) * CASH_RATE - cost
        out.append(day)
        w = w * (1 + r.loc[nxt]) / (1 + day + cost)  # 가격 변동에 따른 비중 drift
    return pd.Series(out, index=dates[MIN_HISTORY + 1:]), trades


def stats(p: pd.Series, trades: int = 0) -> dict:
    eq = (1 + p).cumprod()
    yrs = len(p) / TRADING_DAYS
    yr = (1 + p).groupby(p.index.year).prod() - 1
    return {
        "CAGR%": (eq.iloc[-1] ** (1 / yrs) - 1) * 100,
        "변동성%": p.std() * np.sqrt(TRADING_DAYS) * 100,
        "Sharpe": (p.mean() - CASH_RATE) / p.std() * np.sqrt(TRADING_DAYS),
        "MDD%": (eq / eq.cummax() - 1).min() * 100,
        "최악연도%": yr.min() * 100,
        "연간매매": trades / yrs,
    }


def main():
    close = yf.download(f"{SYMBOL}.KS", period="max", progress=False,
                        auto_adjust=True)["Close"].squeeze().dropna()
    bh = close.pct_change().iloc[MIN_HISTORY + 1:]
    b, tb = simulate(close, blend=0.0)
    c, tc = simulate(close, blend=0.5)

    print(f"기간: {bh.index[0].date()} ~ {bh.index[-1].date()}\n")
    table = pd.DataFrame({"A) 단순 보유": stats(bh), "B) 오버레이만": stats(b, tb),
                          "C) 절충형 (채택)": stats(c, tc)}).T
    print(table.round(2).to_string())

    years = pd.DataFrame({k: (1 + p).groupby(p.index.year).prod() - 1
                          for k, p in [("A 보유", bh), ("B 오버레이", b), ("C 절충", c)]}) * 100
    print("\n연도별 수익률(%)")
    print(years.round(1).to_string())

    t = target_weight(close).iloc[-1]
    print(f"\n최근 종가 {close.index[-1].date()} 기준 절충형 목표 비중: {t:.0%}")


if __name__ == "__main__":
    main()
