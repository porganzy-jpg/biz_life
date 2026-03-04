# -*- coding: utf-8 -*-
"""
Strategy Lab: KOSPI Optimal Strategy Search
3-dimensional comparison: Entry(5) x Exit(4) x Sizing(3)
Self-contained: data download + strategies + backtest + comparison
"""
import sys
import numpy as np
import pandas as pd
import yfinance as yf
from collections import deque

WATCHLIST = [
    ('005930.KS', 'Samsung'), ('000660.KS', 'SK Hynix'), ('035420.KS', 'NAVER'),
    ('035720.KS', 'Kakao'), ('051910.KS', 'LG Chem'), ('006400.KS', 'Samsung SDI'),
    ('003670.KS', 'POSCO Future M'), ('028260.KS', 'Samsung C&T'), ('105560.KS', 'KB Financial'),
    ('055550.KS', 'Shinhan'), ('005380.KS', 'Hyundai Motor'), ('000270.KS', 'Kia'),
    ('068270.KS', 'Celltrion'), ('086790.KS', 'Hana Financial'), ('017670.KS', 'SK Telecom'),
]

# ====================================================================
# Shared Indicator Functions
# ====================================================================

def compute_rsi(series, period=14):
    """RSI with EWM smoothing, NaN-safe"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_atr(df, period=14):
    """ATR series from OHLC dataframe"""
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


def compute_bollinger(close, period=20, std_mult=2):
    """Returns (ma, upper, lower, %B) series"""
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = ma + std_mult * std
    lower = ma - std_mult * std
    bw = upper - lower
    pband = (close - lower) / bw.replace(0, np.nan)
    pband = pband.replace([np.inf, -np.inf], 0.5).fillna(0.5)
    return ma, upper, lower, pband


def compute_macd(close):
    """Returns (macd_line, signal, histogram)"""
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9).mean()
    histogram = macd_line - signal
    return macd_line, signal, histogram


def z_score(series, value, lookback=60):
    """Z-score of value within recent window of series"""
    if len(series) < lookback:
        return 0.0
    window = series.tail(lookback)
    mean = float(window.mean())
    std = float(window.std())
    if std < 1e-10:
        return 0.0
    return (value - mean) / std


def detect_regime(df):
    """Market regime: BULL / BEAR / SIDEWAYS based on MA50/MA200"""
    close = df['close'].astype(float)
    if len(close) < 200:
        return 'SIDEWAYS'
    ma50 = float(close.rolling(50).mean().iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1])
    cp = float(close.iloc[-1])
    if cp > ma50 > ma200:
        return 'BULL'
    elif cp < ma50 < ma200:
        return 'BEAR'
    return 'SIDEWAYS'


# ====================================================================
# Data Download
# ====================================================================

def download_all_data():
    """Download daily OHLCV for all watchlist stocks via yfinance"""
    print('\n  Downloading data...')
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
                print(f'    OK {name}: {len(df)} days')
            else:
                print(f'    SKIP {name}: {len(df)} days (insufficient)')
    print(f'  -> {len(all_data)} stocks ready\n')
    return all_data


# ====================================================================
# Entry Strategy A: v3.2 Ensemble (Baseline - production logic)
# ====================================================================

def strategy_v32_ensemble(df, regime='BULL', score_history=None):
    """v3.2 ensemble: Z-score RSI(14) + BB %B + tanh MACD + MA alignment + volume + volatility"""
    close = df['close'].astype(float)
    volume = df['volume'].astype(float)
    cp = float(close.iloc[-1])

    REGIME_WEIGHTS = {
        'BULL':     {'mr': 0.15, 'trend': 0.30, 'mom': 0.20, 'vol': 0.20, 'vola': 0.15},
        'BEAR':     {'mr': 0.30, 'trend': 0.15, 'mom': 0.10, 'vol': 0.20, 'vola': 0.25},
        'SIDEWAYS': {'mr': 0.25, 'trend': 0.20, 'mom': 0.15, 'vol': 0.25, 'vola': 0.15},
    }
    w = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS['SIDEWAYS'])
    scores = {}

    # 1. Mean reversion (Z-score RSI + BB)
    rsi = compute_rsi(close, 14)
    rsi_val = float(rsi.iloc[-1])
    rsi_z = z_score(rsi, rsi_val, 60)
    rsi_score = max(10, min(90, 50 - rsi_z * 15))

    _, _, lower, pband = compute_bollinger(close)
    pb = float(pband.iloc[-1])
    bb_z = z_score(pband, pb, 60)
    bb_score = max(10, min(90, 50 - bb_z * 15))
    scores['mr'] = rsi_score * 0.5 + bb_score * 0.5

    # 2. Trend following (tanh MACD + MA alignment)
    _, _, histogram = compute_macd(close)
    hist_val = float(histogram.iloc[-1])
    hist_prev = float(histogram.iloc[-2]) if len(histogram) > 1 else 0
    hist_norm = hist_val / (cp * 0.01) if cp > 0 else 0
    macd_score = 50 + float(np.tanh(hist_norm)) * 30
    if hist_prev <= 0 < hist_val:
        macd_score += 15
    elif hist_prev >= 0 > hist_val:
        macd_score -= 15
    if hist_val > 0 and hist_val > hist_prev:
        macd_score += 5
    elif hist_val < 0 and hist_val < hist_prev:
        macd_score -= 5
    macd_score = max(10, min(90, macd_score))

    ma5 = float(close.rolling(5).mean().iloc[-1])
    ma20 = float(close.rolling(20).mean().iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])
    ma_score = 50
    if ma5 > ma20 > ma60 > ma120: ma_score = 75
    elif ma5 < ma20 < ma60 < ma120: ma_score = 25
    elif ma5 > ma20 > ma60: ma_score = 65
    elif ma5 > ma20: ma_score = 58
    elif ma5 < ma20 < ma60: ma_score = 35
    elif ma5 < ma20: ma_score = 42
    scores['trend'] = macd_score * 0.5 + ma_score * 0.5

    # 3. Korean momentum + crash guard
    ret_20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0
    ret_60 = float((close.iloc[-1] / close.iloc[-61] - 1) * 100) if len(close) > 61 else 0
    reversal = 50 - np.clip(ret_20, -30, 30) * 0.8
    momentum = 50 + np.clip(ret_60, -50, 50) * 0.3
    korea_score = max(10, min(90, reversal * 0.6 + momentum * 0.4))
    if ret_20 < -25:
        korea_score = min(korea_score, 55)
    scores['mom'] = korea_score

    # 4. Volume (OBV fixed)
    vol_ma5 = float(volume.rolling(5).mean().iloc[-1])
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1
    obv = (volume * np.sign(close.diff().fillna(0))).cumsum()
    obv_ma5 = float(obv.rolling(5).mean().iloc[-1])
    obv_current = float(obv.iloc[-1])
    vol_score = 50
    if vol_ratio > 1.5 and close.iloc[-1] > close.iloc[-2]: vol_score += 20
    elif vol_ratio > 1.2 and close.iloc[-1] > close.iloc[-2]: vol_score += 10
    elif vol_ratio > 1.5 and close.iloc[-1] < close.iloc[-2]: vol_score -= 15
    elif vol_ratio < 0.7: vol_score -= 5
    if not (np.isnan(obv_current) or np.isnan(obv_ma5)):
        if obv_current > obv_ma5: vol_score += 10
        elif obv_current < obv_ma5: vol_score -= 10
    recent_vols = volume.tail(5).values
    if len(recent_vols) >= 4 and all(recent_vols[i] > recent_vols[i-1] for i in range(1, min(4, len(recent_vols)))):
        vol_score += 8
    scores['vol'] = max(10, min(90, vol_score))

    # 5. Volatility
    returns = close.pct_change().dropna()
    vol_20 = float(returns.tail(20).std() * np.sqrt(252) * 100) if len(returns) >= 20 else 0
    vol_60 = float(returns.tail(60).std() * np.sqrt(252) * 100) if len(returns) >= 60 else vol_20
    vol_trend = 50
    if vol_60 > 0:
        if vol_20 < vol_60 * 0.7: vol_trend = 72
        elif vol_20 < vol_60 * 0.85: vol_trend = 62
        elif vol_20 > vol_60 * 1.5: vol_trend = 28
        elif vol_20 > vol_60 * 1.2: vol_trend = 38
    scores['vola'] = vol_trend

    for k in scores:
        if np.isnan(scores[k]):
            scores[k] = 50

    final = sum(scores[k] * w[k] for k in scores)
    final = round(max(10, min(90, final)), 1)

    # Adaptive thresholds
    buy_th, sell_th = 58, 42
    if score_history is not None:
        score_history.append(final)
        if len(score_history) >= 50:
            sl = list(score_history)
            buy_th = max(55, min(68, float(np.percentile(sl, 75))))
            sell_th = min(45, max(32, float(np.percentile(sl, 25))))

    confidence = abs(final - 50) / 40  # 0~1 scale
    return {
        'score': final,
        'buy_signal': final >= buy_th,
        'sell_signal': final <= sell_th,
        'confidence': min(1.0, confidence),
        'details': f'score={final:.1f} buy_th={buy_th:.0f}',
    }


# ====================================================================
# Entry Strategy B: Connors RSI(2) Pure Mean Reversion
# ====================================================================

def strategy_connors_rsi2(df, regime='BULL', score_history=None):
    """Connors RSI(2): buy RSI(2)<10 & close>MA200, sell RSI(2)>90"""
    close = df['close'].astype(float)
    if len(close) < 200:
        return {'score': 50, 'buy_signal': False, 'sell_signal': False,
                'confidence': 0, 'details': 'warmup'}

    rsi2 = compute_rsi(close, 2)
    rsi2_val = float(rsi2.iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1])
    cp = float(close.iloc[-1])

    buy = rsi2_val < 10 and cp > ma200
    sell = rsi2_val > 90

    # Score: inversely mapped from RSI(2)
    score = max(10, min(90, 90 - rsi2_val * 0.8))
    confidence = 0.0
    if buy:
        confidence = min(1.0, (10 - rsi2_val) / 10 * 0.8 + 0.2)
    elif sell:
        confidence = min(1.0, (rsi2_val - 90) / 10 * 0.8 + 0.2)

    if score_history is not None:
        score_history.append(score)

    return {
        'score': round(score, 1),
        'buy_signal': buy,
        'sell_signal': sell,
        'confidence': confidence,
        'details': f'RSI2={rsi2_val:.1f} MA200={"above" if cp > ma200 else "below"}',
    }


# ====================================================================
# Entry Strategy C: Enhanced RSI(2)+BB+MACD+Volume Combo
# ====================================================================

def strategy_enhanced_combo(df, regime='BULL', score_history=None):
    """RSI(2) 40% + BB %B 25% + MACD direction 20% + Volume confirm 15%
    Buy: composite>=65 & close>MA200 & volume>20d avg*1.2
    Sell: RSI(2)>90 OR %B>0.95"""
    close = df['close'].astype(float)
    volume = df['volume'].astype(float)
    if len(close) < 200:
        return {'score': 50, 'buy_signal': False, 'sell_signal': False,
                'confidence': 0, 'details': 'warmup'}

    cp = float(close.iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1])

    # RSI(2) component (0-100, inverted: low RSI = high score)
    rsi2 = compute_rsi(close, 2)
    rsi2_val = float(rsi2.iloc[-1])
    rsi2_score = max(0, min(100, 100 - rsi2_val))

    # BB %B component (0-100, inverted: low %B = high score)
    _, _, _, pband = compute_bollinger(close)
    pb = float(pband.iloc[-1])
    bb_score = max(0, min(100, (1 - pb) * 100))

    # MACD direction component
    _, _, histogram = compute_macd(close)
    hist_val = float(histogram.iloc[-1])
    hist_prev = float(histogram.iloc[-2]) if len(histogram) > 1 else 0
    macd_dir = 50
    if hist_val > hist_prev:
        macd_dir = 70
    elif hist_val < hist_prev:
        macd_dir = 30
    if hist_prev <= 0 < hist_val:
        macd_dir = 90
    elif hist_prev >= 0 > hist_val:
        macd_dir = 10

    # Volume confirmation component
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    cur_vol = float(volume.iloc[-1])
    vol_ratio = cur_vol / vol_ma20 if vol_ma20 > 0 else 1.0
    vol_confirm = min(100, max(0, (vol_ratio - 0.5) / 1.5 * 100))
    vol_above_120 = vol_ratio > 1.2

    # Composite score
    composite = rsi2_score * 0.40 + bb_score * 0.25 + macd_dir * 0.20 + vol_confirm * 0.15
    # Remap to 10-90 range
    score = max(10, min(90, composite * 0.8 + 10))

    buy = composite >= 65 and cp > ma200 and vol_above_120
    sell = rsi2_val > 90 or pb > 0.95

    confidence = 0
    if buy:
        confidence = min(1.0, (composite - 65) / 35 * 0.7 + 0.3)

    if score_history is not None:
        score_history.append(score)

    return {
        'score': round(score, 1),
        'buy_signal': buy,
        'sell_signal': sell,
        'confidence': confidence,
        'details': f'comp={composite:.1f} RSI2={rsi2_val:.1f} %B={pb:.2f} volR={vol_ratio:.1f}',
    }


# ====================================================================
# Entry Strategy D: Multi-Timeframe (Daily trend + Short-term entry)
# ====================================================================

def strategy_multi_timeframe(df, regime='BULL', score_history=None):
    """Trend filter: 2+ of MA50/MA200/EMA12/EMA26 bullish
    Entry: RSI(2)<15 & trend bullish
    Exit: RSI(2)>85 OR (trend bearish & RSI(2)>70)"""
    close = df['close'].astype(float)
    if len(close) < 200:
        return {'score': 50, 'buy_signal': False, 'sell_signal': False,
                'confidence': 0, 'details': 'warmup'}

    cp = float(close.iloc[-1])

    # Trend filters
    ma50 = float(close.rolling(50).mean().iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1])
    ema12 = float(close.ewm(span=12).mean().iloc[-1])
    ema26 = float(close.ewm(span=26).mean().iloc[-1])

    bullish_count = sum([
        cp > ma50,
        ma50 > ma200,
        ema12 > ema26,
        cp > ma200,
    ])
    trend_bullish = bullish_count >= 2
    trend_bearish = bullish_count <= 1

    # RSI(2) for entry timing
    rsi2 = compute_rsi(close, 2)
    rsi2_val = float(rsi2.iloc[-1])

    buy = rsi2_val < 15 and trend_bullish
    sell = rsi2_val > 85 or (trend_bearish and rsi2_val > 70)

    # Score based on trend strength + RSI(2)
    trend_score = bullish_count / 4 * 40 + 30  # 30-70 range
    rsi_component = max(0, min(30, (50 - rsi2_val) * 0.6))  # -30 to +30
    score = max(10, min(90, trend_score + rsi_component))

    confidence = 0
    if buy:
        confidence = min(1.0, (15 - rsi2_val) / 15 * 0.5 + bullish_count / 4 * 0.5)

    if score_history is not None:
        score_history.append(score)

    return {
        'score': round(score, 1),
        'buy_signal': buy,
        'sell_signal': sell,
        'confidence': confidence,
        'details': f'RSI2={rsi2_val:.1f} trend={bullish_count}/4',
    }


# ====================================================================
# Entry Strategy E: Best Composite (RSI2 + Multi-Confirmation)
# ====================================================================

def strategy_best_composite(df, regime='BULL', score_history=None):
    """RSI(2)<10 + 4 confirmations (need 3+):
    1. BB lower proximity (%B<0.2)
    2. Volume confirm (>20d avg * 1.2)
    3. Above MA200
    4. Non-bearish regime
    Sell: RSI(2)>90"""
    close = df['close'].astype(float)
    volume = df['volume'].astype(float)
    if len(close) < 200:
        return {'score': 50, 'buy_signal': False, 'sell_signal': False,
                'confidence': 0, 'details': 'warmup'}

    cp = float(close.iloc[-1])

    # RSI(2)
    rsi2 = compute_rsi(close, 2)
    rsi2_val = float(rsi2.iloc[-1])

    # Confirmations
    _, _, _, pband = compute_bollinger(close)
    pb = float(pband.iloc[-1])
    confirm_bb = pb < 0.2

    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    cur_vol = float(volume.iloc[-1])
    confirm_vol = (cur_vol / vol_ma20) > 1.2 if vol_ma20 > 0 else False

    ma200 = float(close.rolling(200).mean().iloc[-1])
    confirm_ma200 = cp > ma200

    confirm_regime = regime != 'BEAR'

    confirms = sum([confirm_bb, confirm_vol, confirm_ma200, confirm_regime])

    buy = rsi2_val < 10 and confirms >= 3
    sell = rsi2_val > 90

    # Score
    base = max(10, min(90, 90 - rsi2_val * 0.8))
    confirm_bonus = confirms * 5
    score = max(10, min(90, base * 0.7 + confirm_bonus + 20))

    confidence = 0
    if buy:
        confidence = min(1.0, confirms / 4 * 0.6 + (10 - rsi2_val) / 10 * 0.4)

    if score_history is not None:
        score_history.append(score)

    return {
        'score': round(score, 1),
        'buy_signal': buy,
        'sell_signal': sell,
        'confidence': confidence,
        'details': f'RSI2={rsi2_val:.1f} confirms={confirms}/4 %B={pb:.2f}',
    }


# ====================================================================
# Strategy Registry
# ====================================================================

STRATEGIES = {
    'A': ('v3.2 Ensemble', strategy_v32_ensemble),
    'B': ('Connors RSI2', strategy_connors_rsi2),
    'C': ('Enhanced Combo', strategy_enhanced_combo),
    'D': ('Multi-TF', strategy_multi_timeframe),
    'E': ('Best Composite', strategy_best_composite),
}


# ====================================================================
# Exit Logic (Unified)
# ====================================================================

def check_exit(pos, cp, atr_val, signal, exit_method, day_idx):
    """Check exit conditions.
    pos: dict with 'price', 'high', 'entry_day'
    Returns: (should_sell: bool, reason: str)
    """
    entry_price = pos['price']
    pnl_pct = (cp - entry_price) / entry_price
    hold_days = day_idx - pos['entry_day']

    # Update trailing high
    if cp > pos.get('high', cp):
        pos['high'] = cp

    if exit_method == 'current':
        # SL -5%, TP +15%, ATR x2 Chandelier
        if pnl_pct <= -0.05:
            return True, 'SL'
        if pnl_pct >= 0.15:
            return True, 'TP'
        if atr_val > 0 and pos['high'] > entry_price:
            chandelier = pos['high'] - 2 * atr_val
            if cp <= chandelier:
                return True, 'Trail'
        if signal.get('sell_signal', False):
            return True, 'Signal'

    elif exit_method.startswith('time_'):
        # Time-based exit: hold N days, no stop loss
        max_days = int(exit_method.split('_')[1].replace('d', ''))
        if hold_days >= max_days:
            return True, f'T{max_days}d'
        # Only sell on signal (RSI > 90 type)
        if signal.get('sell_signal', False):
            return True, 'Signal'

    elif exit_method == 'hybrid':
        # ATR x2 trailing + max 10 day hold
        if atr_val > 0 and pos['high'] > entry_price:
            chandelier = pos['high'] - 2 * atr_val
            if cp <= chandelier:
                return True, 'Trail'
        if hold_days >= 10:
            return True, 'T10d'
        if signal.get('sell_signal', False):
            return True, 'Signal'

    elif exit_method == 'mean_rev':
        # RSI(2)>90 OR middle BB touch + max 15 days
        if signal.get('sell_signal', False):
            return True, 'Signal'
        if hold_days >= 15:
            return True, 'T15d'

    return False, ''


# ====================================================================
# Position Sizing
# ====================================================================

def calc_position_size(cash, cp, atr_val, confidence, sizing_method,
                       capital, max_positions):
    """Calculate number of shares to buy.
    Returns: qty (int)
    """
    if sizing_method == 'equal':
        # Equal allocation: cash / max_positions
        alloc = cash / max_positions
        return int(alloc / cp) if cp > 0 else 0

    elif sizing_method == 'atr':
        # ATR-based: risk 2% of capital per trade
        risk_amount = capital * 0.02
        risk_per_share = 2 * atr_val  # 2x ATR stop distance
        if risk_per_share <= 0:
            return int(cash / max_positions / cp) if cp > 0 else 0
        qty = int(risk_amount / risk_per_share)
        max_qty = int(cash * 0.4 / cp) if cp > 0 else 0  # Max 40% cash per position
        return min(qty, max_qty)

    elif sizing_method == 'atr_conf':
        # Confidence-weighted ATR: 1-3% risk scaling by confidence
        risk_pct = 0.01 + confidence * 0.02  # 1% to 3%
        risk_amount = capital * risk_pct
        risk_per_share = 2 * atr_val
        if risk_per_share <= 0:
            return int(cash / max_positions / cp) if cp > 0 else 0
        qty = int(risk_amount / risk_per_share)
        max_qty = int(cash * 0.5 / cp) if cp > 0 else 0  # Max 50% cash
        return min(qty, max_qty)

    return 0


# ====================================================================
# Modular Backtest Engine
# ====================================================================

def run_backtest(data_dict, test_start, test_end, strategy_key,
                 exit_method, sizing_method, max_positions=4):
    """Run a single backtest with specified entry/exit/sizing combination.

    Returns: dict of performance metrics + trade_log
    """
    capital = 10_000_000
    cash = capital
    positions = {}      # ticker -> {qty, price, name, high, entry_day, atr}
    trades = []
    equity_curve = [capital]
    score_history = deque(maxlen=200)

    _, strategy_func = STRATEGIES[strategy_key]

    # Get date index from first available stock
    sample_df = list(data_dict.values())[0][0]
    dates = sample_df.loc[test_start:test_end].index

    for day_idx, date in enumerate(dates):
        # Daily portfolio equity
        daily_equity = cash
        for ticker in list(positions.keys()):
            if ticker in data_dict:
                df = data_dict[ticker][0]
                if date in df.index:
                    daily_equity += positions[ticker]['qty'] * float(df.loc[date, 'close'])

        for ticker, (df, name) in data_dict.items():
            if date not in df.index:
                continue
            idx = df.index.get_loc(date)
            if idx < 200:  # Need 200 bars for MA200 warmup
                continue
            window = df.iloc[:idx + 1]
            cp = float(window['close'].iloc[-1])

            # Regime detection
            regime = detect_regime(window)

            # ATR
            atr_series = compute_atr(window)
            atr_val = float(atr_series.iloc[-1]) if len(atr_series) > 0 else cp * 0.03

            # Strategy signal
            signal = strategy_func(window, regime, score_history)

            # ---- Check exits for held positions ----
            if ticker in positions:
                pos = positions[ticker]
                should_sell, reason = check_exit(
                    pos, cp, atr_val, signal, exit_method, day_idx)

                if should_sell:
                    proceeds = pos['qty'] * cp * (1 - 0.00315)  # Sell fee
                    cash += proceeds
                    pnl = proceeds - pos['qty'] * pos['price'] * 1.00015
                    hold_days = day_idx - pos['entry_day']
                    trades.append({
                        'type': 'SELL', 'name': name, 'date': date,
                        'price': cp, 'qty': pos['qty'], 'pnl': pnl,
                        'reason': reason, 'hold_days': hold_days,
                    })
                    del positions[ticker]

            # ---- Check entries ----
            elif signal['buy_signal'] and len(positions) < max_positions:
                qty = calc_position_size(
                    cash, cp, atr_val, signal['confidence'],
                    sizing_method, capital, max_positions)

                if qty > 0:
                    cost = qty * cp * 1.00015  # Buy fee
                    if cost <= cash:
                        cash -= cost
                        positions[ticker] = {
                            'qty': qty, 'price': cp, 'name': name,
                            'high': cp, 'entry_day': day_idx, 'atr': atr_val,
                        }
                        trades.append({
                            'type': 'BUY', 'name': name, 'date': date,
                            'price': cp, 'qty': qty, 'score': signal['score'],
                            'confidence': signal['confidence'],
                            'details': signal['details'],
                        })

        equity_curve.append(daily_equity)

    # Mark-to-market open positions
    total = cash
    for ticker, pos in positions.items():
        if ticker in data_dict:
            df = data_dict[ticker][0]
            last = df.loc[:test_end]
            if len(last) > 0:
                total += pos['qty'] * float(last['close'].iloc[-1])

    return compute_metrics(capital, total, equity_curve, trades, positions)


# ====================================================================
# Performance Metrics
# ====================================================================

def compute_metrics(capital, total, equity_curve, trades, open_positions):
    """Compute all performance metrics from backtest results"""
    ret = (total - capital) / capital * 100

    sell_trades = [t for t in trades if t['type'] == 'SELL']
    buy_trades = [t for t in trades if t['type'] == 'BUY']
    wins = [t for t in sell_trades if t['pnl'] > 0]
    losses = [t for t in sell_trades if t['pnl'] <= 0]
    wr = len(wins) / len(sell_trades) * 100 if sell_trades else 0

    # MDD
    peak = capital
    mdd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (eq - peak) / peak * 100
        if dd < mdd:
            mdd = dd

    # Sharpe ratio (daily returns)
    sharpe = 0
    if len(equity_curve) > 2:
        eq_arr = np.array(equity_curve[1:])
        daily_ret = np.diff(eq_arr) / eq_arr[:-1]
        if len(daily_ret) > 0 and daily_ret.std() > 0:
            sharpe = (daily_ret.mean() / daily_ret.std()) * np.sqrt(252)

    # Profit factor
    total_win = abs(sum(t['pnl'] for t in wins)) if wins else 0
    total_loss = abs(sum(t['pnl'] for t in losses)) if losses else 0
    pf = total_win / total_loss if total_loss > 0 else float('inf')

    # Average hold days
    avg_hold = np.mean([t.get('hold_days', 0) for t in sell_trades]) if sell_trades else 0

    # Annualized return (test period ~ 1 year)
    ann_ret = ret  # Assume ~1 year test

    return {
        'return': ret,
        'ann_return': ann_ret,
        'mdd': mdd,
        'sharpe': sharpe,
        'win_rate': wr,
        'profit_factor': pf,
        'trades': len(buy_trades),
        'sells': len(sell_trades),
        'open': len(open_positions),
        'avg_hold': avg_hold,
        'trade_log': trades,
    }


# ====================================================================
# Experiment Matrix
# ====================================================================

def build_experiment_matrix():
    """Build list of (label, strategy, exit, sizing) combos to test"""
    combos = []

    # A (Ensemble) x {current, hybrid} x {equal, atr}
    for ex in ['current', 'hybrid']:
        for sz in ['equal', 'atr']:
            combos.append(('A', ex, sz))

    # B (RSI2) x {time_5d, time_7d, time_10d, mean_rev} x {equal, atr, atr_conf}
    for ex in ['time_5d', 'time_7d', 'time_10d', 'mean_rev']:
        for sz in ['equal', 'atr']:
            combos.append(('B', ex, sz))

    # C (Enhanced) x {current, time_7d, mean_rev} x {equal, atr, atr_conf}
    for ex in ['current', 'time_7d', 'mean_rev']:
        for sz in ['equal', 'atr', 'atr_conf']:
            combos.append(('C', ex, sz))

    # D (Multi-TF) x {current, hybrid} x {equal, atr}
    for ex in ['current', 'hybrid']:
        for sz in ['equal', 'atr']:
            combos.append(('D', ex, sz))

    # E (Best Composite) x {time_7d, time_10d, mean_rev} x {atr, atr_conf}
    for ex in ['time_7d', 'time_10d', 'mean_rev']:
        for sz in ['atr', 'atr_conf']:
            combos.append(('E', ex, sz))

    return combos


def make_label(strat_key, exit_method, sizing_method):
    """Create short label like 'B-t7d-atr'"""
    exit_short = {
        'current': 'curr', 'hybrid': 'hybr',
        'time_5d': 't5d', 'time_7d': 't7d', 'time_10d': 't10d',
        'mean_rev': 'mrev',
    }
    size_short = {'equal': 'eq', 'atr': 'atr', 'atr_conf': 'atrc'}
    return f'{strat_key}-{exit_short.get(exit_method, exit_method)}-{size_short.get(sizing_method, sizing_method)}'


# ====================================================================
# Output
# ====================================================================

def print_comparison_table(results):
    """Print sorted comparison table (cp949-safe ASCII)"""
    print('=' * 100)
    print('  STRATEGY LAB: KOSPI Optimal Strategy Search')
    print('  Test: 2025.01-12, 15 stocks, 10M KRW')
    print('=' * 100)
    header = f'  {"Label":<18} {"Return":>7} {"AnnRet":>7} {"MDD":>7} {"Sharpe":>7} {"WR%":>6} {"PF":>6} {"Trades":>6} {"AvgHold":>7} {"Open":>5}'
    print(header)
    print('  ' + '-' * 96)

    sorted_results = sorted(results.items(), key=lambda x: x[1]['sharpe'], reverse=True)
    best_label = sorted_results[0][0]

    for label, r in sorted_results:
        marker = '*' if label == best_label else ' '
        pf_str = f'{r["profit_factor"]:.2f}' if r["profit_factor"] < 100 else 'INF'
        print(f'{marker} {label:<18} {r["return"]:+6.2f}% {r["ann_return"]:+6.2f}% '
              f'{r["mdd"]:+6.2f}% {r["sharpe"]:7.2f} {r["win_rate"]:5.1f}% '
              f'{pf_str:>6} {r["trades"]:6} {r["avg_hold"]:6.1f}d {r["open"]:5}')

    print('=' * 100)
    return sorted_results


def print_dimension_analysis(results):
    """Analyze best strategy along each dimension"""
    print('\n  [Dimension Analysis]')
    print('  ' + '-' * 60)

    # Parse labels back into components
    parsed = {}
    for label, r in results.items():
        parts = label.split('-')
        if len(parts) == 3:
            parsed[label] = {'strat': parts[0], 'exit': parts[1], 'size': parts[2], 'r': r}

    if not parsed:
        print('  No results to analyze.')
        return

    # Best Entry Strategy (average Sharpe by strategy key)
    strat_groups = {}
    for p in parsed.values():
        strat_groups.setdefault(p['strat'], []).append(p['r']['sharpe'])
    print('\n  -- Best Entry Strategy (avg Sharpe) --')
    strat_avg = {k: np.mean(v) for k, v in strat_groups.items()}
    for k in sorted(strat_avg, key=strat_avg.get, reverse=True):
        name = STRATEGIES.get(k, (k,))[0]
        print(f'    {k} ({name}): avg Sharpe = {strat_avg[k]:.2f}  (n={len(strat_groups[k])})')
    best_strat = max(strat_avg, key=strat_avg.get)
    print(f'  => Best Entry: {best_strat} ({STRATEGIES.get(best_strat, (best_strat,))[0]})')

    # Best Exit Strategy
    exit_groups = {}
    for p in parsed.values():
        exit_groups.setdefault(p['exit'], []).append(p['r']['sharpe'])
    print('\n  -- Best Exit Strategy (avg Sharpe) --')
    exit_avg = {k: np.mean(v) for k, v in exit_groups.items()}
    for k in sorted(exit_avg, key=exit_avg.get, reverse=True):
        print(f'    {k}: avg Sharpe = {exit_avg[k]:.2f}  (n={len(exit_groups[k])})')
    best_exit = max(exit_avg, key=exit_avg.get)
    print(f'  => Best Exit: {best_exit}')

    # Best Sizing
    size_groups = {}
    for p in parsed.values():
        size_groups.setdefault(p['size'], []).append(p['r']['sharpe'])
    print('\n  -- Best Sizing (avg Sharpe) --')
    size_avg = {k: np.mean(v) for k, v in size_groups.items()}
    for k in sorted(size_avg, key=size_avg.get, reverse=True):
        print(f'    {k}: avg Sharpe = {size_avg[k]:.2f}  (n={len(size_groups[k])})')
    best_size = max(size_avg, key=size_avg.get)
    print(f'  => Best Sizing: {best_size}')

    # Best overall combo
    print(f'\n  == OPTIMAL COMBINATION ==')
    best_label = max(results, key=lambda k: results[k]['sharpe'])
    br = results[best_label]
    pf_str = f'{br["profit_factor"]:.2f}' if br["profit_factor"] < 100 else 'INF'
    print(f'  {best_label}: Return={br["return"]:+.2f}%, Sharpe={br["sharpe"]:.2f}, '
          f'MDD={br["mdd"]:+.2f}%, WR={br["win_rate"]:.1f}%, PF={pf_str}')

    # Comparison with baseline
    baseline_label = 'A-curr-eq'
    if baseline_label in results:
        bl = results[baseline_label]
        print(f'\n  [vs Baseline ({baseline_label})]')
        print(f'  Baseline: Return={bl["return"]:+.2f}%, Sharpe={bl["sharpe"]:.2f}, '
              f'MDD={bl["mdd"]:+.2f}%, WR={bl["win_rate"]:.1f}%')
        ret_diff = br['return'] - bl['return']
        sharpe_diff = br['sharpe'] - bl['sharpe']
        mdd_diff = br['mdd'] - bl['mdd']
        print(f'  Delta: Return {ret_diff:+.2f}%p, Sharpe {sharpe_diff:+.2f}, '
              f'MDD {mdd_diff:+.2f}%p')

    print()


def print_top_trades(results, n=3):
    """Print trade log for top N strategies"""
    sorted_r = sorted(results.items(), key=lambda x: x[1]['sharpe'], reverse=True)
    for label, r in sorted_r[:n]:
        print(f'\n  [{label}] Trade Log ({r["trades"]} buys, {r["sells"]} sells)')
        print(f'  Return={r["return"]:+.2f}%, Sharpe={r["sharpe"]:.2f}')
        print('  ' + '-' * 80)
        for t in r['trade_log']:
            date_str = str(t['date'])[:10]
            if t['type'] == 'BUY':
                print(f'    BUY  {t["name"]:>16} {date_str} {t["price"]:>10,.0f} x{t["qty"]:>4}'
                      f'  score={t.get("score",0):.1f} conf={t.get("confidence",0):.2f}')
            else:
                pnl_pct = t['pnl'] / (t['qty'] * t['price']) * 100 if t['qty'] * t['price'] > 0 else 0
                print(f'    SELL {t["name"]:>16} {date_str} {t["price"]:>10,.0f} x{t["qty"]:>4}'
                      f'  pnl={t["pnl"]:+10,.0f} ({pnl_pct:+5.1f}%) [{t["reason"]}] '
                      f'{t.get("hold_days",0)}d')


# ====================================================================
# Main
# ====================================================================

if __name__ == '__main__':
    print('=' * 100)
    print('  STRATEGY LAB: KOSPI Optimal Strategy Search')
    print('  3D Comparison: Entry(5) x Exit(4) x Sizing(3)')
    print('=' * 100)

    # 1. Download data
    all_data = download_all_data()
    if len(all_data) < 5:
        print('  ERROR: Not enough stocks. Need at least 5.')
        sys.exit(1)

    # 2. Build experiment matrix
    combos = build_experiment_matrix()
    print(f'  Experiment matrix: {len(combos)} combinations')
    print(f'  Total backtests: {len(combos)} x {len(all_data)} stocks\n')

    # 3. Run all backtests
    test_start = '2025-01-01'
    test_end = '2025-12-31'
    results = {}

    for i, (strat, exit_m, size_m) in enumerate(combos, 1):
        label = make_label(strat, exit_m, size_m)
        strat_name = STRATEGIES[strat][0]
        print(f'  [{i:2d}/{len(combos)}] {label:<18} ({strat_name})...', end='', flush=True)

        r = run_backtest(all_data, test_start, test_end, strat, exit_m, size_m)
        results[label] = r
        pf_str = f'{r["profit_factor"]:.2f}' if r["profit_factor"] < 100 else 'INF'
        print(f' {r["return"]:+7.2f}% Sharpe={r["sharpe"]:.2f} WR={r["win_rate"]:.0f}% '
              f'PF={pf_str} ({r["trades"]}trades)')

    # 4. Print results
    print('\n')
    sorted_r = print_comparison_table(results)

    # 5. Dimension analysis
    print_dimension_analysis(results)

    # 6. Top 3 trade logs
    print_top_trades(results, n=3)

    print('\n  Done.')
