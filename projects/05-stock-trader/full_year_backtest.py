# -*- coding: utf-8 -*-
"""
2025년 1년치 종합 백테스트
모든 로직 변형 비교: v3.1 vs v3.2 vs 뉴스부스트 vs 임계값 변형
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'strategy'))
import numpy as np
import pandas as pd
import yfinance as yf
from collections import deque

WATCHLIST = [
    ('005930.KS', '삼성전자'), ('000660.KS', 'SK하이닉스'), ('035420.KS', 'NAVER'),
    ('035720.KS', '카카오'), ('051910.KS', 'LG화학'), ('006400.KS', '삼성SDI'),
    ('003670.KS', '포스코퓨처엠'), ('028260.KS', '삼성물산'), ('105560.KS', 'KB금융'),
    ('055550.KS', '신한지주'), ('005380.KS', '현대자동차'), ('000270.KS', '기아'),
    ('068270.KS', '셀트리온'), ('086790.KS', '하나금융지주'), ('017670.KS', 'SK텔레콤'),
]

# ====================================================================
# v3.1 스코어링 (버그 포함, 고정 매핑)
# ====================================================================
def compute_rsi_v31(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    # v3.1: 0나누기 버그 있음
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def score_v31(df, regime='BULL'):
    """v3.1: 고정 매핑 + OBV NaN 버그 + RSI 0나누기 버그"""
    close = df['close'].astype(float)
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    volume = df['volume'].astype(float)

    REGIME_WEIGHTS = {
        'BULL': {'추세추종': 0.30, '한국형모멘텀': 0.20, '거래량': 0.20, '평균회귀': 0.15, '변동성': 0.15},
        'BEAR': {'평균회귀': 0.30, '변동성': 0.25, '거래량': 0.20, '추세추종': 0.15, '한국형모멘텀': 0.10},
        'SIDEWAYS': {'평균회귀': 0.25, '거래량': 0.25, '추세추종': 0.20, '변동성': 0.15, '한국형모멘텀': 0.15},
    }
    weights = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS['SIDEWAYS'])
    scores = {}

    # 1. 평균회귀 (고정 매핑)
    rsi = compute_rsi_v31(close, 14)
    rsi_val = float(rsi.iloc[-1])
    if np.isnan(rsi_val):
        rsi_val = 50
    rsi_score = max(10, min(90, 50 + (50 - rsi_val) * 0.8))

    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = ma20 + 2 * std20
    lower = ma20 - 2 * std20
    bw = float(upper.iloc[-1]) - float(lower.iloc[-1])
    if bw > float(close.iloc[-1]) * 0.001:
        pband = (float(close.iloc[-1]) - float(lower.iloc[-1])) / bw
    else:
        pband = 0.5
    bb_score = max(10, min(90, 50 + (0.5 - pband) * 60))
    scores['평균회귀'] = rsi_score * 0.5 + bb_score * 0.5

    # 2. 추세추종 (고정 스케일링)
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    histogram = macd_line - signal_line
    hist_val = float(histogram.iloc[-1])
    hist_prev = float(histogram.iloc[-2]) if len(histogram) > 1 else 0
    cp = float(close.iloc[-1])
    hist_norm = hist_val / (cp * 0.01) if cp > 0 else 0
    macd_score = 50 + hist_norm * 25
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
    ma20_val = float(ma20.iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])
    ma_score = 50
    if ma5 > ma20_val > ma60 > ma120: ma_score = 75
    elif ma5 < ma20_val < ma60 < ma120: ma_score = 25
    elif ma5 > ma20_val > ma60: ma_score = 65
    elif ma5 > ma20_val: ma_score = 58
    elif ma5 < ma20_val < ma60: ma_score = 35
    elif ma5 < ma20_val: ma_score = 42
    scores['추세추종'] = macd_score * 0.5 + ma_score * 0.5

    # 3. 한국형 모멘텀
    ret_20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0
    ret_60 = float((close.iloc[-1] / close.iloc[-61] - 1) * 100) if len(close) > 61 else 0
    ret_20_c = np.clip(ret_20, -30, 30)
    ret_60_c = np.clip(ret_60, -50, 50)
    reversal = 50 - ret_20_c * 0.8
    momentum = 50 + ret_60_c * 0.3
    korea_score = max(10, min(90, reversal * 0.6 + momentum * 0.4))
    scores['한국형모멘텀'] = korea_score

    # 4. 거래량 (OBV NaN 버그)
    vol_ma5 = float(volume.rolling(5).mean().iloc[-1])
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1
    # v3.1 버그: close.diff() NaN 전파
    obv = (volume * np.sign(close.diff())).cumsum()
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
    vol_score = max(10, min(90, vol_score))
    scores['거래량'] = vol_score

    # 5. 변동성
    returns = close.pct_change().dropna()
    vol_20 = float(returns.tail(20).std() * np.sqrt(252) * 100) if len(returns) >= 20 else 0
    vol_60 = float(returns.tail(60).std() * np.sqrt(252) * 100) if len(returns) >= 60 else vol_20
    vol_trend = 50
    if vol_60 > 0:
        if vol_20 < vol_60 * 0.7: vol_trend = 72
        elif vol_20 < vol_60 * 0.85: vol_trend = 62
        elif vol_20 > vol_60 * 1.5: vol_trend = 28
        elif vol_20 > vol_60 * 1.2: vol_trend = 38
    scores['변동성'] = vol_trend

    for k, v in scores.items():
        if np.isnan(v):
            scores[k] = 50

    final = sum(scores[k] * weights[k] for k in scores)
    return round(max(10, min(90, final)), 1)


# ====================================================================
# v3.2 스코어링 (버그 수정 + Z-score + tanh + crash guard)
# ====================================================================
def compute_rsi_v32(series, period=14):
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
    window = series.tail(lookback)
    mean = float(window.mean())
    std = float(window.std())
    if std < 1e-10:
        return 0.0
    return (value - mean) / std

def score_v32(df, regime='BULL', score_history=None):
    """v3.2: Z-score + tanh MACD + crash guard + adaptive thresholds"""
    close = df['close'].astype(float)
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    volume = df['volume'].astype(float)

    REGIME_WEIGHTS = {
        'BULL': {'추세추종': 0.30, '한국형모멘텀': 0.20, '거래량': 0.20, '평균회귀': 0.15, '변동성': 0.15},
        'BEAR': {'평균회귀': 0.30, '변동성': 0.25, '거래량': 0.20, '추세추종': 0.15, '한국형모멘텀': 0.10},
        'SIDEWAYS': {'평균회귀': 0.25, '거래량': 0.25, '추세추종': 0.20, '변동성': 0.15, '한국형모멘텀': 0.15},
    }
    weights = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS['SIDEWAYS'])
    scores = {}
    cp = float(close.iloc[-1])

    # 1. 평균회귀 (Z-score)
    rsi = compute_rsi_v32(close, 14)
    rsi_val = float(rsi.iloc[-1])
    rsi_z = _z_score(rsi, rsi_val, 60)
    rsi_score = max(10, min(90, 50 - rsi_z * 15))

    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = ma20 + 2 * std20
    lower = ma20 - 2 * std20
    bw = float(upper.iloc[-1]) - float(lower.iloc[-1])
    if bw > cp * 0.001:
        pband = (cp - float(lower.iloc[-1])) / bw
    else:
        pband = 0.5
    pband_series = (close - lower) / (upper - lower)
    pband_series = pband_series.replace([np.inf, -np.inf], 0.5).fillna(0.5)
    bb_z = _z_score(pband_series, pband, 60)
    bb_score = max(10, min(90, 50 - bb_z * 15))
    scores['평균회귀'] = rsi_score * 0.5 + bb_score * 0.5

    # 2. 추세추종 (tanh MACD)
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    histogram = macd_line - signal_line
    hist_val = float(histogram.iloc[-1])
    hist_prev = float(histogram.iloc[-2]) if len(histogram) > 1 else 0
    hist_norm = hist_val / (cp * 0.01) if cp > 0 else 0
    macd_score = 50 + float(np.tanh(hist_norm)) * 30  # tanh 정규화
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
    ma20_val = float(ma20.iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])
    ma_score = 50
    if ma5 > ma20_val > ma60 > ma120: ma_score = 75
    elif ma5 < ma20_val < ma60 < ma120: ma_score = 25
    elif ma5 > ma20_val > ma60: ma_score = 65
    elif ma5 > ma20_val: ma_score = 58
    elif ma5 < ma20_val < ma60: ma_score = 35
    elif ma5 < ma20_val: ma_score = 42
    scores['추세추종'] = macd_score * 0.5 + ma_score * 0.5

    # 3. 한국형 모멘텀 + 폭락 가드
    ret_20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0
    ret_60 = float((close.iloc[-1] / close.iloc[-61] - 1) * 100) if len(close) > 61 else 0
    ret_20_c = np.clip(ret_20, -30, 30)
    ret_60_c = np.clip(ret_60, -50, 50)
    reversal = 50 - ret_20_c * 0.8
    momentum = 50 + ret_60_c * 0.3
    korea_score = max(10, min(90, reversal * 0.6 + momentum * 0.4))
    # 폭락 가드
    if ret_20 < -25:
        korea_score = min(korea_score, 55)
    scores['한국형모멘텀'] = korea_score

    # 4. 거래량 (OBV NaN 수정)
    vol_ma5 = float(volume.rolling(5).mean().iloc[-1])
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1
    obv = (volume * np.sign(close.diff().fillna(0))).cumsum()  # NaN 수정
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
    vol_score = max(10, min(90, vol_score))
    scores['거래량'] = vol_score

    # 5. 변동성
    returns = close.pct_change().dropna()
    vol_20 = float(returns.tail(20).std() * np.sqrt(252) * 100) if len(returns) >= 20 else 0
    vol_60 = float(returns.tail(60).std() * np.sqrt(252) * 100) if len(returns) >= 60 else vol_20
    vol_trend = 50
    if vol_60 > 0:
        if vol_20 < vol_60 * 0.7: vol_trend = 72
        elif vol_20 < vol_60 * 0.85: vol_trend = 62
        elif vol_20 > vol_60 * 1.5: vol_trend = 28
        elif vol_20 > vol_60 * 1.2: vol_trend = 38
    scores['변동성'] = vol_trend

    for k, v in scores.items():
        if np.isnan(v):
            scores[k] = 50

    final = sum(scores[k] * weights[k] for k in scores)
    final = round(max(10, min(90, final)), 1)

    if score_history is not None:
        score_history.append(final)

    return final


# ====================================================================
# 국면 판단 (간이)
# ====================================================================
def detect_regime(df):
    close = df['close'].astype(float)
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    if len(close) < 200:
        return 'SIDEWAYS'
    m50 = float(ma50.iloc[-1])
    m200 = float(ma200.iloc[-1])
    cp = float(close.iloc[-1])
    if cp > m50 > m200:
        return 'BULL'
    elif cp < m50 < m200:
        return 'BEAR'
    return 'SIDEWAYS'


# ====================================================================
# 백테스트 엔진
# ====================================================================
def backtest(data_dict, test_start, test_end, score_func, buy_th=58, sell_th=42,
             max_positions=4, sl_pct=-0.05, tp_pct=0.10, news_mode='none',
             news_sent=0.3, use_regime=True, trailing_stop=None):
    """통합 백테스트 엔진"""
    capital = 10_000_000
    cash = capital
    positions = {}
    trades = []
    equity_curve = [capital]
    score_history = deque(maxlen=200)

    sample_df = list(data_dict.values())[0][0]
    dates = sample_df.loc[test_start:test_end].index

    for date in dates:
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
            if idx < 130:
                continue
            window = df.iloc[:idx + 1]
            cp = float(window['close'].iloc[-1])

            # 국면 판단
            regime = detect_regime(window) if use_regime else 'SIDEWAYS'

            # 스코어 계산
            if score_func == 'v31':
                raw_score = score_v31(window, regime)
            else:
                raw_score = score_v32(window, regime, score_history)

            # 뉴스 부스트
            if news_mode == 'boost':
                final_score = raw_score * 0.85 + (50 + news_sent * 15) * 0.15
                final_score = round(max(10, min(90, final_score)), 1)
            else:
                final_score = raw_score

            # 적응형 임계값 (v3.2 only)
            actual_buy_th = buy_th
            actual_sell_th = sell_th
            if score_func == 'v32' and len(score_history) >= 50:
                scores_list = list(score_history)
                actual_buy_th = max(55, min(68, float(np.percentile(scores_list, 75))))
                actual_sell_th = min(45, max(32, float(np.percentile(scores_list, 25))))

            # 매수
            if final_score >= actual_buy_th and ticker not in positions and len(positions) < max_positions:
                qty = int((cash * (1 / max_positions)) / cp)
                if qty > 0:
                    cost = qty * cp * 1.00015
                    if cost <= cash:
                        cash -= cost
                        positions[ticker] = {
                            'qty': qty, 'price': cp, 'name': name,
                            'high': cp,  # trailing stop용
                        }
                        trades.append(('BUY', name, date, cp, qty, final_score))

            # 매도
            elif ticker in positions:
                pos = positions[ticker]
                pnl_pct = (cp - pos['price']) / pos['price']

                # trailing stop용 최고가 갱신
                if cp > pos.get('high', cp):
                    pos['high'] = cp

                sell = False
                reason = ''
                if pnl_pct <= sl_pct:
                    sell, reason = True, '손절'
                elif pnl_pct >= tp_pct:
                    sell, reason = True, '익절'
                elif trailing_stop and pos.get('high', cp) > pos['price']:
                    trail_pnl = (cp - pos['high']) / pos['high']
                    if trail_pnl <= trailing_stop:
                        sell, reason = True, '트레일링'
                elif final_score <= actual_sell_th:
                    sell, reason = True, '퀀트SELL'

                if sell:
                    proceeds = pos['qty'] * cp * (1 - 0.00315)
                    cash += proceeds
                    pnl = proceeds - pos['qty'] * pos['price'] * 1.00015
                    trades.append(('SELL', name, date, cp, pos['qty'], final_score, pnl, reason))
                    del positions[ticker]

        equity_curve.append(daily_equity)

    # 미청산 평가
    total = cash
    for ticker, pos in positions.items():
        if ticker in data_dict:
            df = data_dict[ticker][0]
            last_close = df.loc[:test_end]
            if len(last_close) > 0:
                total += pos['qty'] * float(last_close['close'].iloc[-1])

    ret = (total - capital) / capital * 100
    sell_trades = [t for t in trades if t[0] == 'SELL']
    wins = [t for t in sell_trades if t[6] > 0]
    losses = [t for t in sell_trades if t[6] <= 0]
    wr = len(wins) / len(sell_trades) * 100 if sell_trades else 0

    # MDD 계산
    peak = capital
    mdd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (eq - peak) / peak * 100
        if dd < mdd:
            mdd = dd

    # Sharpe (일간 수익률 기준)
    if len(equity_curve) > 2:
        eq_arr = np.array(equity_curve[1:])
        daily_ret = np.diff(eq_arr) / eq_arr[:-1]
        if daily_ret.std() > 0:
            sharpe = (daily_ret.mean() / daily_ret.std()) * np.sqrt(252)
        else:
            sharpe = 0
    else:
        sharpe = 0

    # 평균 수익/손실
    avg_win = np.mean([t[6] for t in wins]) if wins else 0
    avg_loss = np.mean([t[6] for t in losses]) if losses else 0
    pf = abs(sum(t[6] for t in wins)) / abs(sum(t[6] for t in losses)) if losses and sum(t[6] for t in losses) != 0 else float('inf')

    return {
        'return': ret, 'trades': len(trades),
        'buys': len([t for t in trades if t[0] == 'BUY']),
        'sells': len(sell_trades), 'win_rate': wr,
        'open': len(positions), 'mdd': mdd, 'sharpe': sharpe,
        'avg_win': avg_win, 'avg_loss': avg_loss, 'profit_factor': pf,
        'trade_log': trades,
    }


# ====================================================================
# 메인 실행
# ====================================================================
if __name__ == '__main__':
    print('=' * 80)
    print('  2025년 1년치 종합 백테스트 (15종목, 모든 로직 변형 비교)')
    print('=' * 80)

    # 데이터 다운로드 (2024-06 ~ 2025-12, 워밍업 포함)
    print('\n  데이터 다운로드 중...')
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
                print(f'    OK {name}: {len(df)}일')
            else:
                print(f'    SKIP {name}: {len(df)}일')
    print(f'  → {len(all_data)}종목 준비 완료\n')

    test_start = '2025-01-01'
    test_end = '2025-12-31'

    # 테스트할 전략 구성
    configs = [
        # (이름, score_func, buy_th, sell_th, max_pos, sl, tp, news, sent, regime, trail)
        ('A. v3.1 기본',              'v31', 58, 42, 4, -0.05, 0.10, 'none', 0, True, None),
        ('B. v3.2 순수퀀트',          'v32', 58, 42, 4, -0.05, 0.10, 'none', 0, True, None),
        ('C. v3.2+뉴스(0.3)',         'v32', 58, 42, 4, -0.05, 0.10, 'boost', 0.3, True, None),
        ('D. v3.2 공격적(55/45)',     'v32', 55, 45, 4, -0.05, 0.10, 'none', 0, True, None),
        ('E. v3.2 보수적(62/38)',     'v32', 62, 38, 4, -0.05, 0.10, 'none', 0, True, None),
        ('F. v3.2 넓은SL(-7%)',       'v32', 58, 42, 4, -0.07, 0.10, 'none', 0, True, None),
        ('G. v3.2 넓은TP(15%)',       'v32', 58, 42, 4, -0.05, 0.15, 'none', 0, True, None),
        ('H. v3.2 트레일링(-5%)',     'v32', 58, 42, 4, -0.05, 0.15, 'none', 0, True, -0.05),
        ('I. v3.2 5포지션',           'v32', 58, 42, 5, -0.05, 0.10, 'none', 0, True, None),
        ('J. v3.2 3포지션',           'v32', 58, 42, 3, -0.05, 0.10, 'none', 0, True, None),
        ('K. v3.1 공격적(55/45)',     'v31', 55, 45, 4, -0.05, 0.10, 'none', 0, True, None),
        ('L. v3.2 국면무시',          'v32', 58, 42, 4, -0.05, 0.10, 'none', 0, False, None),
    ]

    results = {}
    for cfg in configs:
        name = cfg[0]
        print(f'  {name} 실행 중...', end='', flush=True)
        r = backtest(
            all_data, test_start, test_end,
            score_func=cfg[1], buy_th=cfg[2], sell_th=cfg[3],
            max_positions=cfg[4], sl_pct=cfg[5], tp_pct=cfg[6],
            news_mode=cfg[7], news_sent=cfg[8], use_regime=cfg[9],
            trailing_stop=cfg[10],
        )
        results[name] = r
        print(f' {r["return"]:+.2f}% ({r["trades"]}거래)')

    # 결과 표
    print('\n')
    print('=' * 110)
    print('  2025년 1년치 백테스트 결과 (2025.01 ~ 2025.12)')
    print('=' * 110)
    print(f'{"전략":>28} {"수익률":>8} {"매매":>5} {"승률":>6} {"MDD":>7} {"샤프":>6} {"PF":>6} {"평균수익":>10} {"평균손실":>10} {"미청산":>5}')
    print('-' * 110)

    sorted_results = sorted(results.items(), key=lambda x: x[1]['return'], reverse=True)
    for name, r in sorted_results:
        pf_str = f'{r["profit_factor"]:.2f}' if r["profit_factor"] < 100 else 'INF'
        print(f'{name:>28} {r["return"]:+7.2f}% {r["trades"]:5} {r["win_rate"]:5.1f}% {r["mdd"]:+6.2f}% {r["sharpe"]:6.2f} {pf_str:>6} {r["avg_win"]:+10,.0f} {r["avg_loss"]:+10,.0f} {r["open"]:5}')

    # 1등 상세
    best_name, best = sorted_results[0]
    print(f'\n{"=" * 110}')
    print(f'  1등: {best_name}')
    print(f'  수익률: {best["return"]:+.2f}%, 샤프: {best["sharpe"]:.2f}, MDD: {best["mdd"]:+.2f}%')
    print(f'  매매: {best["trades"]}회 (매수 {best["buys"]}, 매도 {best["sells"]}), 승률: {best["win_rate"]:.1f}%')
    print(f'{"=" * 110}')

    print(f'\n  [1등 매매 내역]')
    for t in best['trade_log']:
        if t[0] == 'BUY':
            print(f'    BUY  {t[1]:12} {str(t[2])[:10]} {t[3]:>10,.0f} x{t[4]} score={t[5]:.1f}')
        else:
            pnl_pct = t[6] / (t[4] * t[3]) * 100 if t[4] * t[3] > 0 else 0
            print(f'    SELL {t[1]:12} {str(t[2])[:10]} {t[3]:>10,.0f} x{t[4]} pnl={t[6]:+10,.0f} ({t[7]:6}) {pnl_pct:+.1f}%')
