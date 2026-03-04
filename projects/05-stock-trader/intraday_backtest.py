# -*- coding: utf-8 -*-
"""
분봉 기반 하이브리드 백테스트
- 일봉: v3.2 스코어링 (RSI, BB, MACD, MA 등)
- 시간봉: 장중 체결 시뮬레이션 (손절/익절/트레일링 체크)

시나리오 비교:
  A) 1일 1회 (종가 체크) -기존 일봉 백테스트와 동일
  B) 2시간마다 (하루 3~4회)
  C) 1시간마다 (하루 6~7회, 3분 사이클 프록시)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'strategy'))
import numpy as np
import pandas as pd
import yfinance as yf
from collections import deque
from datetime import time as dtime

WATCHLIST = [
    ('005930.KS', '삼성전자'), ('000660.KS', 'SK하이닉스'), ('035420.KS', 'NAVER'),
    ('035720.KS', '카카오'), ('051910.KS', 'LG화학'), ('006400.KS', '삼성SDI'),
    ('003670.KS', '포스코퓨처엠'), ('028260.KS', '삼성물산'), ('105560.KS', 'KB금융'),
    ('055550.KS', '신한지주'), ('005380.KS', '현대자동차'), ('000270.KS', '기아'),
    ('068270.KS', '셀트리온'), ('086790.KS', '하나금융지주'), ('017670.KS', 'SK텔레콤'),
]

# ====================================================================
# v3.2 스코어링 (full_year_backtest.py에서 재사용)
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
    if ret_20 < -25:
        korea_score = min(korea_score, 55)
    scores['한국형모멘텀'] = korea_score

    # 4. 거래량 (OBV NaN 수정)
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
# 데이터 다운로드
# ====================================================================
def download_data():
    """일봉 + 시간봉 데이터 다운로드"""
    daily_data = {}
    hourly_data = {}

    print('\n  [1/2] 일봉 데이터 다운로드 (스코어링용, 2024-06 ~ 2025-12)...')
    for ticker, name in WATCHLIST:
        df = yf.download(ticker, start='2024-06-01', end='2025-12-31', progress=False)
        if df is not None and len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0].lower() for c in df.columns]
            else:
                df.columns = [c.lower() for c in df.columns]
            if len(df) > 200:
                daily_data[ticker] = (df, name)
                print(f'    OK {name}: {len(df)}일')
            else:
                print(f'    SKIP {name}: {len(df)}일 (부족)')

    print(f'\n  [2/2] 시간봉 데이터 다운로드 (체결용, 60m)...')
    # yfinance 60m 제한: 최대 ~730일(2년) 가능
    # 기간을 분할해서 다운로드 (안정성)
    for ticker, name in WATCHLIST:
        if ticker not in daily_data:
            continue
        try:
            df_h = yf.download(ticker, start='2025-01-01', end='2025-12-31',
                               interval='60m', progress=False)
            if df_h is not None and len(df_h) > 0:
                if isinstance(df_h.columns, pd.MultiIndex):
                    df_h.columns = [c[0].lower() for c in df_h.columns]
                else:
                    df_h.columns = [c.lower() for c in df_h.columns]
                # UTC → KST 변환 후 timezone 제거 (일봉과 맞추기)
                if df_h.index.tz is not None:
                    df_h.index = df_h.index.tz_convert('Asia/Seoul').tz_localize(None)
                hourly_data[ticker] = df_h
                n_days = df_h.index.normalize().nunique()
                print(f'    OK {name}: {len(df_h)}봉 ({n_days}일)')
            else:
                print(f'    SKIP {name}: 시간봉 없음')
        except Exception as e:
            print(f'    ERR {name}: {e}')

    valid_tickers = set(daily_data.keys()) & set(hourly_data.keys())
    print(f'\n  → 일봉+시간봉 모두 있는 종목: {len(valid_tickers)}개')
    return daily_data, hourly_data, valid_tickers


# ====================================================================
# 하이브리드 백테스트 엔진
# ====================================================================
def compute_daily_atr(df, period=14):
    """일봉 기반 ATR 계산 (전체 시리즈 반환)"""
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    return atr


def intraday_backtest(daily_data, hourly_data, valid_tickers,
                      test_start='2025-01-01', test_end='2025-12-31',
                      check_interval_hours=None,
                      buy_th=58, sell_th=42, max_positions=4,
                      sl_pct=-0.05, tp_pct=0.15,
                      trailing_stop=-0.05,
                      trailing_mode='fixed',
                      atr_multiplier=3.0):
    """
    하이브리드 백테스트: 일봉 스코어링 + 시간봉 체결

    check_interval_hours:
        None  -> 1일 1회 (종가만 체크)
        2     -> 2시간마다 체크
        1     -> 1시간마다 체크

    trailing_mode:
        'fixed'      -> 고정 % 트레일링 (trailing_stop 사용)
        'atr'        -> ATR 기반 Chandelier Exit (atr_multiplier 사용)
        'atr_sl'     -> 손절도 ATR 기반 (sl도 ATR로 대체)
    """
    capital = 10_000_000
    cash = capital
    positions = {}   # ticker -> {qty, price, name, high}
    trades = []
    equity_curve = [capital]
    score_history = deque(maxlen=200)

    # 일봉 날짜 목록 (테스트 구간)
    sample_df = list(daily_data.values())[0][0]
    test_dates = sample_df.loc[test_start:test_end].index

    # 사전 계산: 매일의 v3.2 스코어 + 매수/매도 신호
    daily_scores = {}  # (ticker, date) -> score
    daily_regimes = {}  # (ticker, date) -> regime
    daily_buy_th = {}   # date -> adaptive buy threshold
    daily_sell_th = {}  # date -> adaptive sell threshold

    for date in test_dates:
        for ticker in valid_tickers:
            df, name = daily_data[ticker]
            if date not in df.index:
                continue
            idx = df.index.get_loc(date)
            if idx < 130:
                continue
            window = df.iloc[:idx + 1]
            regime = detect_regime(window)
            score = score_v32(window, regime, score_history)
            daily_scores[(ticker, date)] = score
            daily_regimes[(ticker, date)] = regime

        # 적응형 임계값
        if len(score_history) >= 50:
            scores_list = list(score_history)
            daily_buy_th[date] = max(55, min(68, float(np.percentile(scores_list, 75))))
            daily_sell_th[date] = min(45, max(32, float(np.percentile(scores_list, 25))))
        else:
            daily_buy_th[date] = buy_th
            daily_sell_th[date] = sell_th

    # ATR 사전 계산 (ATR 모드일 때)
    daily_atr = {}  # (ticker, date) -> atr value
    if trailing_mode in ('atr', 'atr_sl'):
        for ticker in valid_tickers:
            df, name = daily_data[ticker]
            atr_series = compute_daily_atr(df, period=14)
            for date in test_dates:
                if date in df.index:
                    idx = df.index.get_loc(date)
                    if idx >= 14:
                        daily_atr[(ticker, date)] = float(atr_series.iloc[idx])

    # KRX 장 시간 (09:00 ~ 15:30)
    market_open = dtime(9, 0)
    market_close = dtime(15, 30)

    # 시간봉 체크 시간 결정 (KRX 60m 봉: 09~14시, 마지막 봉=14시=14:00~15:00)
    if check_interval_hours is None:
        # 1일 1회: 14시봉만 (장 마감 직전, 종가 프록시)
        check_hours = [14]
    elif check_interval_hours == 2:
        # 2시간마다: 10, 12, 14 (하루 3회)
        check_hours = [10, 12, 14]
    elif check_interval_hours == 1:
        # 1시간마다: 9, 10, 11, 12, 13, 14 (하루 6회)
        check_hours = [9, 10, 11, 12, 13, 14]
    else:
        check_hours = [14]

    for date in test_dates:
        date_str = date.strftime('%Y-%m-%d')

        # 이 날의 포트폴리오 가치 계산 (일봉 종가 기준)
        daily_equity = cash
        for ticker in list(positions.keys()):
            if ticker in daily_data:
                df = daily_data[ticker][0]
                if date in df.index:
                    daily_equity += positions[ticker]['qty'] * float(df.loc[date, 'close'])

        actual_buy_th = daily_buy_th.get(date, buy_th)
        actual_sell_th = daily_sell_th.get(date, sell_th)

        # 시간봉 순회: 이 날짜의 시간봉들
        for ticker in list(valid_tickers):
            name = daily_data[ticker][1]
            score = daily_scores.get((ticker, date))
            if score is None:
                continue

            df_h = hourly_data[ticker]

            # 이 날짜의 시간봉 필터링 (.date() 비교로 tz 문제 회피)
            day_bars = df_h[df_h.index.date == date.date()]
            if len(day_bars) == 0:
                # 시간봉이 없으면 일봉 종가로 폴백
                df_d = daily_data[ticker][0]
                if date not in df_d.index:
                    continue
                cp = float(df_d.loc[date, 'close'])
                hi = float(df_d.loc[date, 'high'])
                lo = float(df_d.loc[date, 'low'])

                if ticker in positions:
                    pos = positions[ticker]
                    entry_price = pos['price']
                    if hi > pos.get('high', entry_price):
                        pos['high'] = hi
                    # ATR 갱신
                    cur_atr = daily_atr.get((ticker, date), pos.get('atr', entry_price * 0.03))
                    pos['atr'] = cur_atr

                    # 손절 체크
                    if trailing_mode == 'atr_sl':
                        sl_price = entry_price - atr_multiplier * cur_atr
                        if lo <= sl_price:
                            proceeds = pos['qty'] * sl_price * (1 - 0.00315)
                            cash += proceeds
                            pnl = proceeds - pos['qty'] * entry_price * 1.00015
                            trades.append(('SELL', name, date, sl_price, pos['qty'], score, pnl, '손절'))
                            del positions[ticker]
                            continue
                    else:
                        low_pnl = (lo - entry_price) / entry_price
                        if low_pnl <= sl_pct:
                            sell_price = entry_price * (1 + sl_pct)
                            proceeds = pos['qty'] * sell_price * (1 - 0.00315)
                            cash += proceeds
                            pnl = proceeds - pos['qty'] * entry_price * 1.00015
                            trades.append(('SELL', name, date, sell_price, pos['qty'], score, pnl, '손절'))
                            del positions[ticker]
                            continue

                    if not (ticker in positions):
                        continue
                    # 익절 체크
                    if (hi - entry_price) / entry_price >= tp_pct:
                        sell_price = entry_price * (1 + tp_pct)
                        proceeds = pos['qty'] * sell_price * (1 - 0.00315)
                        cash += proceeds
                        pnl = proceeds - pos['qty'] * entry_price * 1.00015
                        trades.append(('SELL', name, date, sell_price, pos['qty'], score, pnl, '익절'))
                        del positions[ticker]
                    # 트레일링 체크
                    elif trailing_mode in ('atr', 'atr_sl'):
                        chandelier = pos['high'] - atr_multiplier * cur_atr
                        if lo <= chandelier:
                            sell_price = chandelier
                            proceeds = pos['qty'] * sell_price * (1 - 0.00315)
                            cash += proceeds
                            pnl = proceeds - pos['qty'] * entry_price * 1.00015
                            trades.append(('SELL', name, date, sell_price, pos['qty'], score, pnl, '트레일링'))
                            del positions[ticker]
                    elif trailing_stop and pos['high'] > entry_price:
                        trail_pnl = (lo - pos['high']) / pos['high']
                        if trail_pnl <= trailing_stop:
                            sell_price = pos['high'] * (1 + trailing_stop)
                            proceeds = pos['qty'] * sell_price * (1 - 0.00315)
                            cash += proceeds
                            pnl = proceeds - pos['qty'] * entry_price * 1.00015
                            trades.append(('SELL', name, date, sell_price, pos['qty'], score, pnl, '트레일링'))
                            del positions[ticker]
                    elif score <= actual_sell_th and ticker in positions:
                        proceeds = pos['qty'] * cp * (1 - 0.00315)
                        cash += proceeds
                        pnl = proceeds - pos['qty'] * entry_price * 1.00015
                        trades.append(('SELL', name, date, cp, pos['qty'], score, pnl, '퀀트SELL'))
                        del positions[ticker]
                elif score >= actual_buy_th and len(positions) < max_positions:
                    qty = int((cash * (1 / max_positions)) / cp)
                    if qty > 0:
                        cost = qty * cp * 1.00015
                        if cost <= cash:
                            cash -= cost
                            atr_val = daily_atr.get((ticker, date), cp * 0.03)
                            positions[ticker] = {'qty': qty, 'price': cp, 'name': name,
                                                 'high': hi, 'atr': atr_val}
                            trades.append(('BUY', name, date, cp, qty, score))
                continue

            # 체크 시간에 해당하는 시간봉만 순회
            for _, bar in day_bars.iterrows():
                bar_hour = bar.name.hour
                if bar_hour not in check_hours:
                    continue

                bar_high = float(bar['high'])
                bar_low = float(bar['low'])
                bar_close = float(bar['close'])

                # 보유 중인 포지션: 손절/익절/트레일링 체크
                if ticker in positions:
                    pos = positions[ticker]
                    entry_price = pos['price']
                    cur_atr = daily_atr.get((ticker, date), pos.get('atr', entry_price * 0.03))
                    pos['atr'] = cur_atr

                    # 시간봉 고가로 최고가 갱신
                    if bar_high > pos.get('high', entry_price):
                        pos['high'] = bar_high

                    # 손절 체크
                    if trailing_mode == 'atr_sl':
                        sl_price = entry_price - atr_multiplier * cur_atr
                        if bar_low <= sl_price:
                            proceeds = pos['qty'] * sl_price * (1 - 0.00315)
                            cash += proceeds
                            pnl = proceeds - pos['qty'] * entry_price * 1.00015
                            trades.append(('SELL', name, date, sl_price, pos['qty'], score, pnl, '손절'))
                            del positions[ticker]
                            continue
                    else:
                        low_pnl = (bar_low - entry_price) / entry_price
                        if low_pnl <= sl_pct:
                            sell_price = entry_price * (1 + sl_pct)
                            proceeds = pos['qty'] * sell_price * (1 - 0.00315)
                            cash += proceeds
                            pnl = proceeds - pos['qty'] * entry_price * 1.00015
                            trades.append(('SELL', name, date, sell_price, pos['qty'], score, pnl, '손절'))
                            del positions[ticker]
                            continue

                    # 익절 체크 (시간봉 고가 기준)
                    high_pnl = (bar_high - entry_price) / entry_price
                    if high_pnl >= tp_pct:
                        sell_price = entry_price * (1 + tp_pct)
                        proceeds = pos['qty'] * sell_price * (1 - 0.00315)
                        cash += proceeds
                        pnl = proceeds - pos['qty'] * entry_price * 1.00015
                        trades.append(('SELL', name, date, sell_price, pos['qty'], score, pnl, '익절'))
                        del positions[ticker]
                        continue

                    # 트레일링 스탑 체크
                    if trailing_mode in ('atr', 'atr_sl'):
                        # Chandelier Exit: 최고가 - N * ATR
                        chandelier = pos['high'] - atr_multiplier * cur_atr
                        if bar_low <= chandelier:
                            sell_price = chandelier
                            proceeds = pos['qty'] * sell_price * (1 - 0.00315)
                            cash += proceeds
                            pnl = proceeds - pos['qty'] * entry_price * 1.00015
                            trades.append(('SELL', name, date, sell_price, pos['qty'], score, pnl, '트레일링'))
                            del positions[ticker]
                            continue
                    elif trailing_stop and pos['high'] > entry_price:
                        trail_pnl = (bar_low - pos['high']) / pos['high']
                        if trail_pnl <= trailing_stop:
                            sell_price = pos['high'] * (1 + trailing_stop)
                            proceeds = pos['qty'] * sell_price * (1 - 0.00315)
                            cash += proceeds
                            pnl = proceeds - pos['qty'] * entry_price * 1.00015
                            trades.append(('SELL', name, date, sell_price, pos['qty'], score, pnl, '트레일링'))
                            del positions[ticker]
                            continue

                    # 퀀트 매도 신호 (마지막 봉에서만 체크)
                    if bar_hour >= 14 and score <= actual_sell_th:
                        proceeds = pos['qty'] * bar_close * (1 - 0.00315)
                        cash += proceeds
                        pnl = proceeds - pos['qty'] * entry_price * 1.00015
                        trades.append(('SELL', name, date, bar_close, pos['qty'], score, pnl, '퀀트SELL'))
                        del positions[ticker]
                        continue

                # 매수 신호 체크
                elif score >= actual_buy_th and len(positions) < max_positions:
                    qty = int((cash * (1 / max_positions)) / bar_close)
                    if qty > 0:
                        cost = qty * bar_close * 1.00015
                        if cost <= cash:
                            cash -= cost
                            atr_val = daily_atr.get((ticker, date), bar_close * 0.03)
                            positions[ticker] = {
                                'qty': qty, 'price': bar_close, 'name': name,
                                'high': bar_high, 'atr': atr_val,
                            }
                            trades.append(('BUY', name, date, bar_close, qty, score))
                            break  # 이 종목은 이 날 매수 완료

        equity_curve.append(daily_equity)

    # 미청산 평가
    total = cash
    for ticker, pos in positions.items():
        if ticker in daily_data:
            df = daily_data[ticker][0]
            last_close = df.loc[:test_end]
            if len(last_close) > 0:
                total += pos['qty'] * float(last_close['close'].iloc[-1])

    ret = (total - capital) / capital * 100
    sell_trades = [t for t in trades if t[0] == 'SELL']
    wins = [t for t in sell_trades if t[6] > 0]
    losses = [t for t in sell_trades if t[6] <= 0]
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

    # Sharpe
    if len(equity_curve) > 2:
        eq_arr = np.array(equity_curve[1:])
        daily_ret = np.diff(eq_arr) / eq_arr[:-1]
        if daily_ret.std() > 0:
            sharpe = (daily_ret.mean() / daily_ret.std()) * np.sqrt(252)
        else:
            sharpe = 0
    else:
        sharpe = 0

    avg_win = np.mean([t[6] for t in wins]) if wins else 0
    avg_loss = np.mean([t[6] for t in losses]) if losses else 0
    pf = abs(sum(t[6] for t in wins)) / abs(sum(t[6] for t in losses)) if losses and sum(t[6] for t in losses) != 0 else float('inf')

    # 매도 유형별 집계
    sell_reasons = {}
    for t in sell_trades:
        reason = t[7]
        sell_reasons[reason] = sell_reasons.get(reason, 0) + 1

    return {
        'return': ret, 'trades': len(trades),
        'buys': len([t for t in trades if t[0] == 'BUY']),
        'sells': len(sell_trades), 'win_rate': wr,
        'open': len(positions), 'mdd': mdd, 'sharpe': sharpe,
        'avg_win': avg_win, 'avg_loss': avg_loss, 'profit_factor': pf,
        'sell_reasons': sell_reasons,
        'trade_log': trades,
    }


def _process_check(ticker, name, close, high, low, score,
                    buy_th, sell_th, positions, trades, cash,
                    max_positions, sl_pct, tp_pct, trailing_stop, date):
    """일봉 폴백용 단순 체크 (시간봉 없을 때)"""
    # 이 함수는 시간봉이 없는 날의 폴백으로만 사용
    # 메인 루프에서 직접 처리하므로 현재는 패스
    pass


# ====================================================================
# 메인 실행
# ====================================================================
if __name__ == '__main__':
    print('=' * 90)
    print('  분봉 기반 하이브리드 백테스트 (일봉 스코어링 + 시간봉 체결)')
    print('  체크 빈도별 수익 영향 비교 (15종목, 2025년)')
    print('=' * 90)

    daily_data, hourly_data, valid_tickers = download_data()

    if len(valid_tickers) == 0:
        print('\n  [ERROR] 시간봉 데이터가 없습니다. yfinance 60m 제한을 확인하세요.')
        print('     (60m 데이터는 최대 ~2년 전까지만 가능)')
        sys.exit(1)

    check_freqs = [
        ('1일1회', None),
        ('2시간',  2),
        ('1시간',  1),
    ]

    base_params = dict(
        buy_th=58, sell_th=42, max_positions=4,
        sl_pct=-0.05, tp_pct=0.15,
    )

    # ============================================================
    # Part 1: 고정% 트레일링 (기존 방식, 대조군)
    # ============================================================
    fixed_configs = [
        ('Fixed-5%',  -0.05),
        ('Fixed-8%',  -0.08),
        ('Fixed-10%', -0.10),
    ]

    results = {}
    print('\n  [Part 1] 고정% 트레일링')
    print('  ' + '-' * 40)
    for trail_name, trail_val in fixed_configs:
        for freq_name, freq_val in check_freqs:
            key = f'{trail_name} / {freq_name}'
            print(f'  {key}...', end='', flush=True)
            r = intraday_backtest(
                daily_data, hourly_data, valid_tickers,
                check_interval_hours=freq_val,
                trailing_stop=trail_val, trailing_mode='fixed',
                **base_params,
            )
            results[key] = r
            print(f' {r["return"]:+.2f}% ({r["trades"]}거래)')

    # ============================================================
    # Part 2: ATR Chandelier Exit (변동성 적응형)
    # ============================================================
    atr_configs = [
        ('ATR x2',  2.0),
        ('ATR x3',  3.0),
        ('ATR x4',  4.0),
    ]

    print('\n  [Part 2] ATR Chandelier Exit (변동성 적응형)')
    print('  ' + '-' * 40)
    for atr_name, atr_mult in atr_configs:
        for freq_name, freq_val in check_freqs:
            key = f'{atr_name} / {freq_name}'
            print(f'  {key}...', end='', flush=True)
            r = intraday_backtest(
                daily_data, hourly_data, valid_tickers,
                check_interval_hours=freq_val,
                trailing_mode='atr', atr_multiplier=atr_mult,
                **base_params,
            )
            results[key] = r
            print(f' {r["return"]:+.2f}% ({r["trades"]}거래)')

    # ============================================================
    # Part 3: ATR 손절+트레일링 (손절도 ATR 기반)
    # ============================================================
    print('\n  [Part 3] ATR 손절+트레일링 (손절도 ATR 기반)')
    print('  ' + '-' * 40)
    for atr_name, atr_mult in atr_configs:
        for freq_name, freq_val in check_freqs:
            key = f'{atr_name}(SL) / {freq_name}'
            print(f'  {key}...', end='', flush=True)
            r = intraday_backtest(
                daily_data, hourly_data, valid_tickers,
                check_interval_hours=freq_val,
                trailing_mode='atr_sl', atr_multiplier=atr_mult,
                **base_params,
            )
            results[key] = r
            print(f' {r["return"]:+.2f}% ({r["trades"]}거래)')

    # ============================================================
    # 전체 결과표
    # ============================================================
    all_groups = [
        ('고정% 트레일링', fixed_configs, 'fixed'),
        ('ATR Chandelier Exit', atr_configs, 'atr'),
        ('ATR 손절+트레일링', atr_configs, 'atr_sl'),
    ]

    print('\n')
    print('=' * 120)
    print('  고정% vs ATR 트레일링 백테스트 결과 비교 (v3.2, TP+15%)')
    print('=' * 120)
    print(f'{"시나리오":>24} {"수익률":>8} {"매매":>5} {"승률":>6} {"MDD":>7} {"샤프":>6} {"PF":>6} {"평균수익":>10} {"평균손실":>10} {"미청산":>5}')
    print('-' * 120)

    for group_name, configs, mode in all_groups:
        print(f'  [{group_name}]')
        for cfg_name, _ in configs:
            suffix = '(SL)' if mode == 'atr_sl' else ''
            for freq_name, _ in check_freqs:
                key = f'{cfg_name}{" " + suffix if suffix else ""} / {freq_name}'.replace('  ', ' ')
                if mode == 'atr_sl':
                    key = f'{cfg_name}(SL) / {freq_name}'
                r = results[key]
                pf_str = f'{r["profit_factor"]:.2f}' if r["profit_factor"] < 100 else 'INF'
                print(f'{key:>24} {r["return"]:+7.2f}% {r["trades"]:5} {r["win_rate"]:5.1f}% {r["mdd"]:+6.2f}% {r["sharpe"]:6.2f} {pf_str:>6} {r["avg_win"]:+10,.0f} {r["avg_loss"]:+10,.0f} {r["open"]:5}')
            print()

    # ============================================================
    # 수익률 매트릭스
    # ============================================================
    all_trail_labels = [c[0] for c in fixed_configs] + [c[0] for c in atr_configs] + [f'{c[0]}(SL)' for c in atr_configs]

    print(f'{"=" * 70}')
    print('  수익률 매트릭스')
    print(f'{"=" * 70}')
    print(f'{"":>14} {"1일1회":>10} {"2시간":>10} {"1시간":>10}')
    print('-' * 70)
    for label in all_trail_labels:
        vals = []
        for freq_name, _ in check_freqs:
            key = f'{label} / {freq_name}'
            vals.append(results[key]['return'])
        print(f'{label:>14} {vals[0]:+9.2f}% {vals[1]:+9.2f}% {vals[2]:+9.2f}%')

    # 샤프 매트릭스
    print(f'\n  샤프비율 매트릭스')
    print(f'{"":>14} {"1일1회":>10} {"2시간":>10} {"1시간":>10}')
    print('-' * 70)
    for label in all_trail_labels:
        vals = []
        for freq_name, _ in check_freqs:
            key = f'{label} / {freq_name}'
            vals.append(results[key]['sharpe'])
        print(f'{label:>14} {vals[0]:>10.2f} {vals[1]:>10.2f} {vals[2]:>10.2f}')

    # 트레일링 횟수 매트릭스
    print(f'\n  트레일링 발동 횟수 매트릭스')
    print(f'{"":>14} {"1일1회":>10} {"2시간":>10} {"1시간":>10}')
    print('-' * 70)
    for label in all_trail_labels:
        vals = []
        for freq_name, _ in check_freqs:
            key = f'{label} / {freq_name}'
            vals.append(results[key]['sell_reasons'].get('트레일링', 0))
        print(f'{label:>14} {vals[0]:>10} {vals[1]:>10} {vals[2]:>10}')

    # ============================================================
    # 핵심 인사이트
    # ============================================================
    print(f'\n{"=" * 80}')
    print('  핵심 인사이트')
    print(f'{"=" * 80}')

    best_key = max(results.keys(), key=lambda k: results[k]['return'])
    best = results[best_key]
    worst_key = min(results.keys(), key=lambda k: results[k]['return'])
    worst = results[worst_key]

    print(f'  - 최고: {best_key} -> {best["return"]:+.2f}% (샤프 {best["sharpe"]:.2f}, MDD {best["mdd"]:+.2f}%)')
    print(f'  - 최저: {worst_key} -> {worst["return"]:+.2f}% (샤프 {worst["sharpe"]:.2f})')

    # 고정% vs ATR 비교 (1시간 체크 기준)
    print(f'\n  [1시간 체크 기준 비교]')
    for label in all_trail_labels:
        key = f'{label} / 1시간'
        r = results[key]
        t_cnt = r['sell_reasons'].get('트레일링', 0)
        print(f'    {label:>14}: {r["return"]:+.2f}% (트레일링 {t_cnt}회, 승률 {r["win_rate"]:.0f}%)')

    # 체크빈도 안정성 (1시간-1일 차이가 적을수록 좋음)
    print(f'\n  [체크빈도 안정성] (1시간 vs 1일 수익률 차이 - 작을수록 안정적)')
    for label in all_trail_labels:
        r_d = results[f'{label} / 1일1회']['return']
        r_h = results[f'{label} / 1시간']['return']
        diff = r_h - r_d
        stability = 'STABLE' if abs(diff) < 5 else ('OK' if abs(diff) < 10 else 'UNSTABLE')
        print(f'    {label:>14}: {diff:+.2f}%p  [{stability}]')

    # 최고 시나리오 매매 내역
    print(f'\n{"=" * 80}')
    print(f'  최고 시나리오: {best_key}')
    print(f'  수익률: {best["return"]:+.2f}%, 샤프: {best["sharpe"]:.2f}, MDD: {best["mdd"]:+.2f}%')
    print(f'  매매: {best["trades"]}회, 승률: {best["win_rate"]:.1f}%')
    print(f'{"=" * 80}')
