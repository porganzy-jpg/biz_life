# -*- coding: utf-8 -*-
"""RSI(2) Crash Buy Test: v3.5 baseline vs v3.5 + RSI(2) crash buy"""
import numpy as np
import pandas as pd
import yfinance as yf
from collections import deque

WATCHLIST = [
    ('005930.KS', 'Samsung'), ('000660.KS', 'SK Hynix'), ('035420.KS', 'NAVER'),
    ('035720.KS', 'Kakao'), ('051910.KS', 'LG Chem'), ('006400.KS', 'Samsung SDI'),
    ('003670.KS', 'POSCO FM'), ('028260.KS', 'Samsung C&T'), ('105560.KS', 'KB Fin'),
    ('055550.KS', 'Shinhan'), ('005380.KS', 'Hyundai'), ('000270.KS', 'Kia'),
    ('068270.KS', 'Celltrion'), ('086790.KS', 'Hana Fin'), ('017670.KS', 'SK Telecom'),
]

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return (100 - (100 / (1 + rs))).fillna(50)

def compute_atr(df, period=14):
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def z_score(series, value, lookback=60):
    if len(series) < lookback:
        return 0.0
    w = series.tail(lookback)
    m = float(w.mean())
    s = float(w.std())
    return (value - m) / s if s > 1e-10 else 0.0

def detect_regime(df):
    close = df['close'].astype(float)
    if len(close) < 200:
        return 'SIDEWAYS'
    m50 = float(close.rolling(50).mean().iloc[-1])
    m200 = float(close.rolling(200).mean().iloc[-1])
    cp = float(close.iloc[-1])
    if cp > m50 > m200:
        return 'BULL'
    elif cp < m50 < m200:
        return 'BEAR'
    return 'SIDEWAYS'

def score_v32(df, regime='BULL', score_history=None):
    close = df['close'].astype(float)
    volume = df['volume'].astype(float)
    cp = float(close.iloc[-1])
    REGIME_WEIGHTS = {
        'BULL': {'mr': 0.15, 'tr': 0.30, 'mo': 0.20, 'vo': 0.20, 'vl': 0.15},
        'BEAR': {'mr': 0.30, 'tr': 0.15, 'mo': 0.10, 'vo': 0.20, 'vl': 0.25},
        'SIDEWAYS': {'mr': 0.25, 'tr': 0.20, 'mo': 0.15, 'vo': 0.25, 'vl': 0.15},
    }
    w = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS['SIDEWAYS'])
    scores = {}

    rsi = compute_rsi(close, 14)
    rsi_val = float(rsi.iloc[-1])
    rsi_z = z_score(rsi, rsi_val, 60)
    rsi_score = max(10, min(90, 50 - rsi_z * 15))
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = ma20 + 2 * std20
    lower = ma20 - 2 * std20
    bw = float(upper.iloc[-1]) - float(lower.iloc[-1])
    pband = (cp - float(lower.iloc[-1])) / bw if bw > cp * 0.001 else 0.5
    pband_s = ((close - lower) / (upper - lower)).replace([np.inf, -np.inf], 0.5).fillna(0.5)
    bb_z = z_score(pband_s, pband, 60)
    bb_score = max(10, min(90, 50 - bb_z * 15))
    scores['mr'] = rsi_score * 0.5 + bb_score * 0.5

    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    hist = ema12 - ema26 - (ema12 - ema26).ewm(span=9).mean()
    hv = float(hist.iloc[-1])
    hp = float(hist.iloc[-2]) if len(hist) > 1 else 0
    hn = hv / (cp * 0.01) if cp > 0 else 0
    ms = 50 + float(np.tanh(hn)) * 30
    if hp <= 0 < hv: ms += 15
    elif hp >= 0 > hv: ms -= 15
    if hv > 0 and hv > hp: ms += 5
    elif hv < 0 and hv < hp: ms -= 5
    ms = max(10, min(90, ms))
    ma5 = float(close.rolling(5).mean().iloc[-1])
    ma20v = float(ma20.iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])
    mas = 50
    if ma5 > ma20v > ma60 > ma120: mas = 75
    elif ma5 < ma20v < ma60 < ma120: mas = 25
    elif ma5 > ma20v > ma60: mas = 65
    elif ma5 > ma20v: mas = 58
    elif ma5 < ma20v < ma60: mas = 35
    elif ma5 < ma20v: mas = 42
    scores['tr'] = ms * 0.5 + mas * 0.5

    r20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0
    r60 = float((close.iloc[-1] / close.iloc[-61] - 1) * 100) if len(close) > 61 else 0
    rev = 50 - np.clip(r20, -30, 30) * 0.8
    mom = 50 + np.clip(r60, -50, 50) * 0.3
    ks = max(10, min(90, rev * 0.6 + mom * 0.4))
    if r20 < -25: ks = min(ks, 55)
    scores['mo'] = ks

    vma5 = float(volume.rolling(5).mean().iloc[-1])
    vma20 = float(volume.rolling(20).mean().iloc[-1])
    vr = vma5 / vma20 if vma20 > 0 else 1
    obv = (volume * np.sign(close.diff().fillna(0))).cumsum()
    obvm5 = float(obv.rolling(5).mean().iloc[-1])
    obvc = float(obv.iloc[-1])
    vs = 50
    if vr > 1.5 and close.iloc[-1] > close.iloc[-2]: vs += 20
    elif vr > 1.2 and close.iloc[-1] > close.iloc[-2]: vs += 10
    elif vr > 1.5 and close.iloc[-1] < close.iloc[-2]: vs -= 15
    elif vr < 0.7: vs -= 5
    if not (np.isnan(obvc) or np.isnan(obvm5)):
        if obvc > obvm5: vs += 10
        elif obvc < obvm5: vs -= 10
    scores['vo'] = max(10, min(90, vs))

    rets = close.pct_change().dropna()
    v20 = float(rets.tail(20).std() * np.sqrt(252) * 100) if len(rets) >= 20 else 0
    v60 = float(rets.tail(60).std() * np.sqrt(252) * 100) if len(rets) >= 60 else v20
    vt = 50
    if v60 > 0:
        if v20 < v60 * 0.7: vt = 72
        elif v20 < v60 * 0.85: vt = 62
        elif v20 > v60 * 1.5: vt = 28
        elif v20 > v60 * 1.2: vt = 38
    scores['vl'] = vt

    for k in scores:
        if np.isnan(scores[k]): scores[k] = 50
    final = round(max(10, min(90, sum(scores[k] * w[k] for k in scores))), 1)
    if score_history is not None:
        score_history.append(final)
    return final


def run_backtest(data_dict, test_start, test_end, use_rsi2_crash=False):
    capital = 10_000_000
    cash = capital
    positions = {}
    trades = []
    equity_curve = [capital]
    score_history = deque(maxlen=200)

    sample_df = list(data_dict.values())[0][0]
    dates = sample_df.loc[test_start:test_end].index

    for day_idx, date in enumerate(dates):
        daily_eq = cash
        for tk in list(positions.keys()):
            if tk in data_dict:
                df = data_dict[tk][0]
                if date in df.index:
                    daily_eq += positions[tk]['qty'] * float(df.loc[date, 'close'])

        for ticker, (df, name) in data_dict.items():
            if date not in df.index:
                continue
            idx = df.index.get_loc(date)
            if idx < 200:
                continue
            window = df.iloc[:idx + 1]
            cp = float(window['close'].iloc[-1])
            regime = detect_regime(window)
            atr_s = compute_atr(window)
            atr_val = float(atr_s.iloc[-1]) if len(atr_s) > 0 else cp * 0.03
            score = score_v32(window, regime, score_history)

            buy_th, sell_th = 58, 42
            if len(score_history) >= 50:
                sl = list(score_history)
                buy_th = max(55, min(68, float(np.percentile(sl, 75))))
                sell_th = min(45, max(32, float(np.percentile(sl, 25))))

            rsi2_val = float(compute_rsi(window['close'].astype(float), 2).iloc[-1])
            ma200 = float(window['close'].astype(float).rolling(200).mean().iloc[-1])
            rsi2_buy = use_rsi2_crash and rsi2_val < 10 and cp > ma200
            rsi2_sell = use_rsi2_crash and rsi2_val > 90

            # Exit
            if ticker in positions:
                pos = positions[ticker]
                pnl_pct = (cp - pos['price']) / pos['price']
                if cp > pos.get('high', cp):
                    pos['high'] = cp

                sell = False
                reason = ''

                # RSI2 entries: time-based exit (7d) + RSI2>90
                if pos.get('src') == 'rsi2':
                    hold = day_idx - pos.get('entry_day', day_idx)
                    if rsi2_sell:
                        sell, reason = True, 'RSI2>90'
                    elif hold >= 7:
                        sell, reason = True, 'T7d'
                    elif pnl_pct <= -0.05:
                        sell, reason = True, 'SL'
                else:
                    # Ensemble entries: current exit logic
                    if pnl_pct <= -0.05:
                        sell, reason = True, 'SL'
                    elif pnl_pct >= 0.15:
                        sell, reason = True, 'TP'
                    elif atr_val > 0 and pos['high'] > pos['price']:
                        chan = pos['high'] - 2 * atr_val
                        if cp <= chan:
                            sell, reason = True, 'Trail'
                    elif score <= sell_th:
                        sell, reason = True, 'Signal'

                if sell:
                    proceeds = pos['qty'] * cp * (1 - 0.00315)
                    cash += proceeds
                    pnl = proceeds - pos['qty'] * pos['price'] * 1.00015
                    hold = day_idx - pos.get('entry_day', day_idx)
                    trades.append({
                        'type': 'SELL', 'name': name, 'date': date, 'price': cp,
                        'qty': pos['qty'], 'pnl': pnl, 'reason': reason,
                        'hold_days': hold, 'src': pos.get('src', 'ens'),
                    })
                    del positions[ticker]

            # Entry
            elif len(positions) < 4:
                buy_ensemble = score >= buy_th

                if buy_ensemble or rsi2_buy:
                    src = 'rsi2' if (rsi2_buy and not buy_ensemble) else 'ens'
                    if rsi2_buy and buy_ensemble:
                        src = 'both'
                    # ATR sizing
                    risk_amt = capital * 0.02
                    risk_per = 2 * atr_val
                    qty = int(risk_amt / risk_per) if risk_per > 0 else int(cash / 4 / cp)
                    max_qty = int(cash * 0.4 / cp) if cp > 0 else 0
                    qty = min(qty, max_qty)
                    if qty > 0:
                        cost = qty * cp * 1.00015
                        if cost <= cash:
                            cash -= cost
                            positions[ticker] = {
                                'qty': qty, 'price': cp, 'name': name,
                                'high': cp, 'entry_day': day_idx, 'src': src,
                            }
                            trades.append({
                                'type': 'BUY', 'name': name, 'date': date, 'price': cp,
                                'qty': qty, 'score': score, 'src': src,
                                'rsi2': rsi2_val if rsi2_buy else None,
                            })
        equity_curve.append(daily_eq)

    # Mark-to-market
    total = cash
    for tk, pos in positions.items():
        if tk in data_dict:
            df = data_dict[tk][0]
            last = df.loc[:test_end]
            if len(last) > 0:
                total += pos['qty'] * float(last['close'].iloc[-1])

    ret = (total - capital) / capital * 100
    sell_trades = [t for t in trades if t['type'] == 'SELL']
    buy_trades = [t for t in trades if t['type'] == 'BUY']
    wins = [t for t in sell_trades if t['pnl'] > 0]
    losses = [t for t in sell_trades if t['pnl'] <= 0]
    wr = len(wins) / len(sell_trades) * 100 if sell_trades else 0

    peak = capital
    mdd = 0
    for eq in equity_curve:
        if eq > peak: peak = eq
        dd = (eq - peak) / peak * 100
        if dd < mdd: mdd = dd

    sharpe = 0
    if len(equity_curve) > 2:
        ea = np.array(equity_curve[1:])
        dr = np.diff(ea) / ea[:-1]
        if dr.std() > 0:
            sharpe = (dr.mean() / dr.std()) * np.sqrt(252)

    tw = abs(sum(t['pnl'] for t in wins)) if wins else 0
    tl = abs(sum(t['pnl'] for t in losses)) if losses else 0
    pf = tw / tl if tl > 0 else float('inf')

    rsi2_buys = [t for t in buy_trades if t.get('src') in ('rsi2', 'both')]
    rsi2_sells = [t for t in sell_trades if t.get('src') in ('rsi2', 'both')]
    rsi2_wins = [t for t in rsi2_sells if t['pnl'] > 0]
    rsi2_wr = len(rsi2_wins) / len(rsi2_sells) * 100 if rsi2_sells else 0
    rsi2_pnl = sum(t['pnl'] for t in rsi2_sells)

    avg_hold = np.mean([t['hold_days'] for t in sell_trades]) if sell_trades else 0
    rsi2_avg_hold = np.mean([t['hold_days'] for t in rsi2_sells]) if rsi2_sells else 0

    return {
        'ret': ret, 'sharpe': sharpe, 'mdd': mdd, 'wr': wr, 'pf': pf,
        'buys': len(buy_trades), 'sells': len(sell_trades), 'open': len(positions),
        'avg_hold': avg_hold,
        'rsi2_buys': len(rsi2_buys), 'rsi2_sells': len(rsi2_sells),
        'rsi2_wr': rsi2_wr, 'rsi2_pnl': rsi2_pnl, 'rsi2_avg_hold': rsi2_avg_hold,
        'trades': trades,
    }


if __name__ == '__main__':
    print('Downloading data...')
    all_data = {}
    for ticker, name in WATCHLIST:
        df = yf.download(ticker, start='2024-06-01', end='2025-12-31', progress=False)
        if df is not None and len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0].lower() for c in df.columns]
            else:
                df.columns = [c.lower() for c in df.columns]
            if len(df) > 200:
                all_data[ticker] = (df, name)
    print(f'{len(all_data)} stocks ready\n')

    print('=' * 85)
    print('  RSI(2) Crash Buy Test')
    print('  A: v3.5 Baseline (ensemble only)')
    print('  B: v3.5 + RSI(2) Crash Buy (RSI2<10 & MA200 above, exit RSI2>90 or 7d)')
    print('=' * 85)

    r1 = run_backtest(all_data, '2025-01-01', '2025-12-31', use_rsi2_crash=False)
    r2 = run_backtest(all_data, '2025-01-01', '2025-12-31', use_rsi2_crash=True)

    print()
    fmt = '{:<24} {:>8} {:>7} {:>7} {:>6} {:>6} {:>5} {:>5} {:>7}'
    print(fmt.format('', 'Return', 'Sharpe', 'MDD', 'WR%', 'PF', 'Buys', 'Open', 'AvgHold'))
    print('-' * 85)
    for name, r in [('A. v3.5 Baseline', r1), ('B. v3.5 + RSI2 Crash', r2)]:
        pfs = f'{r["pf"]:.2f}' if r['pf'] < 100 else 'INF'
        print(f'{name:<24} {r["ret"]:>+7.2f}% {r["sharpe"]:>7.2f} {r["mdd"]:>+6.2f}% '
              f'{r["wr"]:>5.1f}% {pfs:>6} {r["buys"]:>5} {r["open"]:>5} {r["avg_hold"]:>6.1f}d')

    diff_ret = r2['ret'] - r1['ret']
    diff_sharpe = r2['sharpe'] - r1['sharpe']
    print(f'{"Delta":<24} {diff_ret:>+7.2f}% {diff_sharpe:>+7.2f} {r2["mdd"]-r1["mdd"]:>+6.2f}%')

    print()
    print('  [RSI(2) Crash Buy Contribution]')
    print(f'  RSI2 buys:      {r2["rsi2_buys"]}')
    print(f'  RSI2 closed:    {r2["rsi2_sells"]}')
    print(f'  RSI2 win rate:  {r2["rsi2_wr"]:.1f}%')
    print(f'  RSI2 total PnL: {r2["rsi2_pnl"]:>+,.0f} KRW')
    print(f'  RSI2 avg hold:  {r2["rsi2_avg_hold"]:.1f}d')

    print()
    print('  [RSI(2) Trade Log]')
    rsi2_trades = [t for t in r2['trades'] if t.get('src') in ('rsi2', 'both')]
    for t in rsi2_trades:
        d = str(t['date'])[:10]
        if t['type'] == 'BUY':
            rsi2_str = f' RSI2={t["rsi2"]:.0f}' if t.get('rsi2') is not None else ''
            print(f'    BUY  {t["name"]:>14} {d} {t["price"]:>10,.0f} x{t["qty"]:>3}{rsi2_str}')
        else:
            pnl_pct = t['pnl'] / (t['qty'] * t['price']) * 100 if t['qty'] * t['price'] > 0 else 0
            print(f'    SELL {t["name"]:>14} {d} {t["price"]:>10,.0f} x{t["qty"]:>3} '
                  f'pnl={t["pnl"]:>+10,.0f} ({pnl_pct:>+5.1f}%) [{t["reason"]}] {t["hold_days"]}d')

    print()
    print('  [200M KRW Projection]')
    print(f'  Baseline:    {r1["ret"] * 20000:>+10,.0f} KRW ({r1["ret"]:>+.2f}%)')
    print(f'  + RSI2:      {r2["ret"] * 20000:>+10,.0f} KRW ({r2["ret"]:>+.2f}%)')
    print(f'  Improvement: {(r2["ret"] - r1["ret"]) * 20000:>+10,.0f} KRW ({diff_ret:>+.2f}%p)')
