# -*- coding: utf-8 -*-
"""
v3.8 종합 백테스트: 전략 조합별 최적화

비교 대상:
  A. v3.7 (5전략 앙상블 + RSI2 + ATR + 리밸런싱)
  B. v3.8 기본 (v3.7 + 펀더멘털 10%)
  C. v3.8 F-Score 필터 (B + F-Score<4 매수 차단)
  D. v3.8 공격적 (펀더멘털 17%, BEAR시 가치주 강조)
  E. v3.8 + Half-Kelly (포트폴리오 리스크 버짓)
  F. v3.8 + CVaR 리스크 (꼬리위험 동적 노출)

2025년 전체 시뮬레이션, 200만원 자본
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'strategy'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'trading-bot'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'news'))

import numpy as np
import pandas as pd
import yfinance as yf
from collections import deque

WATCHLIST = [
    ('005930.KS', '삼성전자', '반도체'), ('000660.KS', 'SK하이닉스', '반도체'),
    ('035420.KS', 'NAVER', '인터넷'), ('035720.KS', '카카오', '인터넷'),
    ('051910.KS', 'LG화학', '화학'), ('006400.KS', '삼성SDI', '2차전지'),
    ('003670.KS', '포스코퓨처엠', '2차전지'), ('028260.KS', '삼성물산', '건설'),
    ('105560.KS', 'KB금융', '금융'), ('055550.KS', '신한지주', '금융'),
    ('005380.KS', '현대자동차', '자동차'), ('000270.KS', '기아', '자동차'),
    ('068270.KS', '셀트리온', '바이오'), ('086790.KS', '하나금융지주', '금융'),
    ('017670.KS', 'SK텔레콤', '통신'),
]

print('=== v3.8 종합 백테스트 (전략 조합별 최적화) ===')
print('데이터 다운로드...')

stock_data = {}
for ticker, name, sector in WATCHLIST:
    try:
        df = yf.download(ticker, start='2024-06-01', end='2026-01-01',
                         progress=False, auto_adjust=True)
        if df is not None and len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            })
            df = df[['open', 'high', 'low', 'close', 'volume']].dropna().reset_index(drop=True)
            stock_data[ticker] = (name, sector, df)
    except Exception:
        pass
print(f'로드 완료: {len(stock_data)}/{len(WATCHLIST)}종목\n')

# ── 펀더멘털 데이터 캐시 (백테스트에서는 정적 사용) ──
# yfinance에서 한번만 가져와서 전 기간 동일하게 적용 (분기 데이터이므로)
print('펀더멘털 데이터 로드...')
fundamental_cache = {}
try:
    for ticker, name, sector in WATCHLIST:
        try:
            info = yf.Ticker(ticker).info
            if info:
                fundamental_cache[ticker] = {
                    'per': float(info.get('trailingPE') or info.get('forwardPE') or 0) or None,
                    'pbr': float(info.get('priceToBook') or 0) or None,
                    'roe': float(info.get('returnOnEquity') or 0) or None,
                    'debt_ratio': float(info.get('debtToEquity') or 0) or None,
                    'current_ratio': float(info.get('currentRatio') or 0) or None,
                    'op_margin': float(info.get('operatingMargins') or 0) or None,
                    'div_yield': float(info.get('dividendYield') or 0) or None,
                    'earn_growth': float(info.get('earningsGrowth') or 0) or None,
                    'rev_growth': float(info.get('revenueGrowth') or 0) or None,
                    'fcf': float(info.get('freeCashflow') or 0) or None,
                    'profit_margin': float(info.get('profitMargins') or 0) or None,
                    'ev_ebitda': float(info.get('enterpriseToEbitda') or 0) or None,
                }
        except Exception:
            pass
    print(f'펀더멘털 로드: {len(fundamental_cache)}/{len(WATCHLIST)}종목')
except Exception as e:
    print(f'펀더멘털 로드 실패: {e}')

# 섹터별 PER/PBR 중앙값
SECTOR_PER = {'반도체': 15, '인터넷': 30, '화학': 12, '2차전지': 40,
              '건설': 8, '금융': 6, '자동차': 7, '바이오': 50, '지주': 8,
              '보험': 6, '통신': 10, '기타': 15}
SECTOR_PBR = {'반도체': 1.8, '인터넷': 3.0, '화학': 0.8, '2차전지': 3.5,
              '건설': 0.6, '금융': 0.4, '자동차': 0.7, '바이오': 5.0, '지주': 0.5,
              '보험': 0.4, '통신': 0.8, '기타': 1.0}


def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return (100 - (100 / (1 + rs))).fillna(50)


def compute_atr(df, period=14):
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low, (high - prev_close).abs(), (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def detect_regime(close, idx):
    if idx < 60:
        return 'SIDEWAYS'
    ma20 = close.iloc[max(0, idx - 20):idx + 1].mean()
    ma60 = close.iloc[max(0, idx - 60):idx + 1].mean()
    ret20 = (close.iloc[idx] / close.iloc[max(0, idx - 20)] - 1) * 100
    if ma20 > ma60 and ret20 > 3:
        return 'BULL'
    elif ma20 < ma60 and ret20 < -3:
        return 'BEAR'
    return 'SIDEWAYS'


def z_score(series, value, lookback=60):
    if len(series) < lookback:
        return 0.0
    window = series.tail(lookback)
    mean = float(window.mean())
    std = float(window.std())
    return (value - mean) / std if std > 1e-10 else 0.0


def score_fundamental(ticker, sector):
    """펀더멘털 점수 (10~90)."""
    fd = fundamental_cache.get(ticker)
    if not fd:
        return 50, 0, []  # score, f_score, warnings

    warnings_list = []
    scores = {}

    # 밸류에이션
    per = fd.get('per')
    sector_per = SECTOR_PER.get(sector, 15)
    if per and per > 0:
        ratio = per / sector_per
        if ratio < 0.5:
            scores['val'] = 80
        elif ratio < 0.8:
            scores['val'] = 68
        elif ratio < 1.2:
            scores['val'] = 50
        elif ratio < 2.0:
            scores['val'] = 35
        else:
            scores['val'] = 20
            warnings_list.append('PER과도')
    elif per and per < 0:
        scores['val'] = 15
        warnings_list.append('적자')
    else:
        scores['val'] = 50

    # 수익성
    roe = fd.get('roe')
    if roe and roe > 0.15:
        scores['profit'] = 80
    elif roe and roe > 0.08:
        scores['profit'] = 65
    elif roe and roe > 0:
        scores['profit'] = 45
    elif roe and roe < 0:
        scores['profit'] = 20
        warnings_list.append('ROE음수')
    else:
        scores['profit'] = 50

    # 재무안정성
    debt = fd.get('debt_ratio')
    if debt is not None:
        if debt < 50:
            scores['safety'] = 85
        elif debt < 100:
            scores['safety'] = 65
        elif debt < 200:
            scores['safety'] = 45
        else:
            scores['safety'] = 20
            warnings_list.append('고부채')
    else:
        scores['safety'] = 50

    # Piotroski F-Score (간이)
    f_score = 0
    if roe and roe > 0: f_score += 1
    fcf = fd.get('fcf')
    if fcf and fcf > 0: f_score += 1
    eg = fd.get('earn_growth')
    if eg and eg > 0: f_score += 1
    pm = fd.get('profit_margin')
    if fcf and fcf > 0 and pm and pm > 0: f_score += 1
    if debt is not None and debt < 100: f_score += 1
    cr = fd.get('current_ratio')
    if cr and cr > 1.0: f_score += 1
    f_score += 1  # 희석 없음 기본
    rg = fd.get('rev_growth')
    if rg and rg > 0: f_score += 1
    if rg and rg > 0: f_score += 1

    # F-Score → 점수
    if f_score >= 8:
        scores['fscore'] = 85
    elif f_score >= 6:
        scores['fscore'] = 68
    elif f_score >= 4:
        scores['fscore'] = 50
    else:
        scores['fscore'] = 25
        warnings_list.append('F-Score낮음')

    # GP/A (영업이익률 proxy)
    opm = fd.get('op_margin')
    if opm and opm > 0.20:
        scores['gpa'] = 85
    elif opm and opm > 0.10:
        scores['gpa'] = 68
    elif opm and opm > 0:
        scores['gpa'] = 50
    elif opm and opm < 0:
        scores['gpa'] = 20
        warnings_list.append('영업적자')
    else:
        scores['gpa'] = 50

    # 가중 합산
    total = (scores.get('val', 50) * 0.22 +
             scores.get('profit', 50) * 0.18 +
             scores.get('safety', 50) * 0.18 +
             scores.get('fscore', 50) * 0.20 +
             scores.get('gpa', 50) * 0.12 +
             50 * 0.10)  # 배당+성장 중립

    return max(10, min(90, total)), f_score, warnings_list


def get_weights(regime, fund_weight=0.0):
    """국면별 가중치. fund_weight=0이면 v3.7 호환."""
    base = {
        'BULL': {'추세추종': 0.25, '한국형모멘텀': 0.17, '거래량': 0.17,
                 '평균회귀': 0.13, '변동성': 0.13},
        'BEAR': {'평균회귀': 0.25, '변동성': 0.22, '거래량': 0.17,
                 '추세추종': 0.13, '한국형모멘텀': 0.08},
        'SIDEWAYS': {'평균회귀': 0.22, '거래량': 0.22, '추세추종': 0.17,
                     '변동성': 0.12, '한국형모멘텀': 0.12},
    }[regime]

    if fund_weight > 0:
        # 기존 가중치를 (1 - fund_weight)로 축소하고 펀더멘털 추가
        scale = 1.0 - fund_weight
        w = {k: v * scale for k, v in base.items()}
        w['펀더멘털'] = fund_weight
    else:
        w = dict(base)

    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def score_technical(df, idx, regime='SIDEWAYS'):
    """기술적 5전략 점수 (v3.7과 동일)."""
    if idx < 130:
        return 50, False, {}
    sub = df.iloc[:idx + 1].copy()
    close = sub['close'].astype(float)
    volume = sub['volume'].astype(float)
    current = float(close.iloc[-1])
    scores = {}

    # 1. 평균회귀
    rsi = compute_rsi(close, 14)
    rsi_val = float(rsi.iloc[-1])
    rsi_z = z_score(rsi, rsi_val, 60)
    rsi_score = max(10, min(90, 50 - rsi_z * 15))
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = ma20 + 2 * std20
    lower = ma20 - 2 * std20
    band = float(upper.iloc[-1]) - float(lower.iloc[-1])
    pband = (current - float(lower.iloc[-1])) / band if band > current * 0.001 else 0.5
    pband_s = (close - lower) / (upper - lower)
    pband_s = pband_s.replace([np.inf, -np.inf], 0.5).fillna(0.5)
    bb_z = z_score(pband_s, pband, 60)
    bb_score = max(10, min(90, 50 - bb_z * 15))
    scores['평균회귀'] = rsi_score * 0.5 + bb_score * 0.5

    # 2. 추세추종
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    hist = macd_line - signal_line
    hist_val = float(hist.iloc[-1])
    hist_prev = float(hist.iloc[-2]) if len(hist) > 1 else 0
    hist_norm = hist_val / (current * 0.01) if current > 0 else 0
    macd_score = 50 + float(np.tanh(hist_norm)) * 30
    if hist_prev <= 0 < hist_val: macd_score += 15
    elif hist_prev >= 0 > hist_val: macd_score -= 15
    if hist_val > 0 and hist_val > hist_prev: macd_score += 5
    elif hist_val < 0 and hist_val < hist_prev: macd_score -= 5
    macd_score = max(10, min(90, macd_score))
    ma5 = float(close.rolling(5).mean().iloc[-1])
    ma20v = float(ma20.iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])
    ma_score = 50
    if ma5 > ma20v > ma60 > ma120: ma_score = 75
    elif ma5 < ma20v < ma60 < ma120: ma_score = 25
    elif ma5 > ma20v > ma60: ma_score = 65
    elif ma5 > ma20v: ma_score = 58
    elif ma5 < ma20v < ma60: ma_score = 35
    elif ma5 < ma20v: ma_score = 42
    scores['추세추종'] = macd_score * 0.5 + ma_score * 0.5

    # 3. 한국형 모멘텀
    ret_20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0
    ret_60 = float((close.iloc[-1] / close.iloc[-61] - 1) * 100) if len(close) > 61 else 0
    ret_20_c = np.clip(ret_20, -30, 30)
    ret_60_c = np.clip(ret_60, -50, 50)
    korea = max(10, min(90, (50 - ret_20_c * 0.8) * 0.6 + (50 + ret_60_c * 0.3) * 0.4))
    if ret_20 < -25: korea = min(korea, 55)
    scores['한국형모멘텀'] = korea

    # 4. 거래량
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
    scores['거래량'] = max(10, min(90, vol_score))

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

    for k in scores:
        if np.isnan(scores[k]):
            scores[k] = 50

    # RSI(2)
    rsi2 = float(compute_rsi(close, 2).iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else 0
    rsi2_buy = rsi2 < 10 and ma200 > 0 and current > ma200

    return scores, rsi2_buy


def run_backtest(config):
    """
    통합 백테스트 실행.
    config: {
        'label': str,
        'fund_weight': float (0~0.20),
        'fund_filter': bool (F-Score<4 차단),
        'fund_warning_filter': int (경고 N개 이상 차단),
        'half_kelly': bool,
        'cvar_limit': bool,
    }
    """
    label = config['label']
    fund_weight = config.get('fund_weight', 0.0)
    fund_filter = config.get('fund_filter', False)
    fund_warning_filter = config.get('fund_warning_filter', 0)
    use_half_kelly = config.get('half_kelly', False)
    use_cvar = config.get('cvar_limit', False)

    capital = 2_000_000
    cash = capital
    positions = {}
    trades = []
    equity_curve = []
    max_positions = 4
    max_single_pct = 30.0
    max_sector_pct = 50.0
    stop_loss = -5.0
    take_profit = 15.0
    atr_risk_pct = 2.0
    atr_multiplier = 2.0
    score_history = deque(maxlen=200)

    start_offsets = {}
    for ticker, (name, sector, df) in stock_data.items():
        if len(df) >= 200:
            for i in range(len(df)):
                if i >= 200:
                    start_offsets[ticker] = i
                    break
    if not start_offsets:
        return {'label': label, 'return': 0, 'sharpe': 0, 'mdd': 0,
                'trades': 0, 'sell_trades': 0, 'wins': 0, 'win_rate': 0,
                'final': capital, 'rebalance': 0, 'rsi2_trades': 0, 'rsi2_wins': 0,
                'fund_blocks': 0}

    min_start = min(start_offsets.values())
    max_len = max(len(df) for _, (_, _, df) in stock_data.items())
    fund_blocks = 0

    for day_idx in range(min_start, max_len):
        total_assets = cash
        for ticker, pos in positions.items():
            _, _, df = stock_data[ticker]
            if day_idx < len(df):
                total_assets += pos['qty'] * float(df.iloc[day_idx]['close'])
        equity_curve.append(total_assets)

        # CVaR 리스크 체크 (최근 20일 수익률의 95% CVaR)
        portfolio_exposure_scale = 1.0
        if use_cvar and len(equity_curve) >= 20:
            daily_rets = pd.Series(equity_curve[-21:]).pct_change().dropna()
            if len(daily_rets) >= 10:
                sorted_rets = daily_rets.sort_values()
                worst_5pct = sorted_rets.iloc[:max(1, int(len(sorted_rets) * 0.05) + 1)]
                cvar = float(worst_5pct.mean()) * 100  # 퍼센트
                # CVaR이 -3% 이상이면 노출 축소
                if cvar < -3.0:
                    portfolio_exposure_scale = 0.5  # 반으로 축소
                elif cvar < -2.0:
                    portfolio_exposure_scale = 0.75

        # 1. 청산 체크 (v3.7과 동일)
        for ticker in list(positions.keys()):
            pos = positions[ticker]
            name, sector, df = stock_data[ticker]
            if day_idx >= len(df): continue
            current = float(df.iloc[day_idx]['close'])
            avg = pos['avg_price']
            pnl_pct = (current - avg) / avg * 100
            pos['highest'] = max(pos['highest'], current)

            sell = False
            action = ''

            if pos.get('entry_source') == 'rsi2':
                rsi2_now = float(compute_rsi(
                    df.iloc[:day_idx + 1]['close'].astype(float), 2
                ).iloc[-1])
                days_held = day_idx - pos['bought_idx']
                if rsi2_now > 90: sell, action = True, 'RSI2_90'
                elif days_held >= 7: sell, action = True, 'RSI2_T7'
                elif pnl_pct <= stop_loss: sell, action = True, 'RSI2_SL'
            else:
                if pnl_pct <= stop_loss: sell, action = True, 'STOP_LOSS'
                elif pnl_pct >= take_profit: sell, action = True, 'TAKE_PROFIT'
                else:
                    atr_s = compute_atr(df.iloc[:day_idx + 1], 14)
                    atr_val = float(atr_s.iloc[-1])
                    chandelier = pos['highest'] - atr_multiplier * atr_val
                    if current <= chandelier:
                        sell, action = True, 'TRAILING_STOP'

            if sell:
                pnl = (current - avg) * pos['qty']
                cash += current * pos['qty'] * (1 - 0.00015 - 0.0018)
                trades.append({'action': action, 'name': name,
                              'pnl': pnl, 'pnl_pct': pnl_pct})
                del positions[ticker]

        # 2.5 리밸런싱
        total_for_rebal = cash
        for tk, ps in positions.items():
            _, _, ddf = stock_data[tk]
            if day_idx < len(ddf):
                total_for_rebal += ps['qty'] * float(ddf.iloc[day_idx]['close'])

        for ticker in list(positions.keys()):
            pos = positions[ticker]
            name, sector, df = stock_data[ticker]
            if day_idx >= len(df): continue
            current = float(df.iloc[day_idx]['close'])
            value = pos['qty'] * current
            pct = value / total_for_rebal * 100 if total_for_rebal > 0 else 0
            if pct > max_single_pct * 1.2:
                target_val = total_for_rebal * (max_single_pct / 100)
                excess = value - target_val
                qty_sell = int(excess / current)
                if qty_sell > 0 and pos['qty'] > qty_sell:
                    pnl = (current - pos['avg_price']) * qty_sell
                    pnl_pct = (current - pos['avg_price']) / pos['avg_price'] * 100
                    cash += qty_sell * current * (1 - 0.00015 - 0.0018)
                    pos['qty'] -= qty_sell
                    trades.append({'action': 'REBALANCE', 'name': name,
                                  'pnl': pnl, 'pnl_pct': pnl_pct})

        # 3. 매수 스캔
        candidates = []
        for ticker, (name, sector, df) in stock_data.items():
            if day_idx >= len(df) or day_idx < 200: continue
            if ticker in positions: continue
            regime = detect_regime(df['close'].astype(float), day_idx)
            tech_scores, rsi2_buy = score_technical(df, day_idx, regime)

            # 펀더멘털 점수
            fund_score, f_score_val, fund_warnings = score_fundamental(ticker, sector)

            # 가중 합산
            weights = get_weights(regime, fund_weight)
            if fund_weight > 0:
                all_scores = {**tech_scores, '펀더멘털': fund_score}
            else:
                all_scores = tech_scores

            final_score = sum(all_scores.get(k, 50) * weights.get(k, 0) for k in weights)
            final_score = round(max(10, min(90, final_score)), 1)
            score_history.append(final_score)

            candidates.append((ticker, name, sector, final_score, rsi2_buy,
                              df, f_score_val, fund_warnings))

        buy_th = 58
        if len(score_history) >= 50:
            buy_th = max(55, min(68, float(np.percentile(list(score_history), 75))))

        # 3a. 앙상블 매수
        for ticker, name, sector, score, rsi2_buy, df, f_score_val, fw in sorted(
            candidates, key=lambda x: x[3], reverse=True
        ):
            if len(positions) >= max_positions: break
            if ticker in positions: continue
            if score < buy_th: continue

            # 펀더멘털 필터
            if fund_filter and f_score_val < 4:
                fund_blocks += 1
                continue
            if fund_warning_filter > 0 and len(fw) >= fund_warning_filter:
                fund_blocks += 1
                continue

            current = float(df.iloc[day_idx]['close'])
            total = cash
            for tk, ps in positions.items():
                _, _, ddf = stock_data[tk]
                if day_idx < len(ddf):
                    total += ps['qty'] * float(ddf.iloc[day_idx]['close'])

            atr_s = compute_atr(df.iloc[:day_idx + 1], 14)
            atr_val = float(atr_s.iloc[-1])

            if atr_val > 0 and current > 0:
                risk_pct = atr_risk_pct
                # Half-Kelly: 포트폴리오 승률 기반 리스크 조절
                if use_half_kelly and len(trades) >= 10:
                    recent_sells = [t for t in trades[-30:] if t['action'] not in ('BUY', 'RSI2_BUY')]
                    if recent_sells:
                        wr = sum(1 for t in recent_sells if t['pnl'] > 0) / len(recent_sells)
                        avg_win = np.mean([t['pnl_pct'] for t in recent_sells if t['pnl'] > 0]) if any(t['pnl'] > 0 for t in recent_sells) else 1
                        avg_loss = abs(np.mean([t['pnl_pct'] for t in recent_sells if t['pnl'] <= 0])) if any(t['pnl'] <= 0 for t in recent_sells) else 1
                        if avg_loss > 0:
                            kelly = wr - (1 - wr) / (avg_win / avg_loss)
                            half_kelly = max(0.5, min(3.0, kelly / 2))
                            risk_pct = atr_risk_pct * half_kelly

                risk_pct *= portfolio_exposure_scale  # CVaR 조절

                risk_amount = total * (risk_pct / 100)
                qty = int(risk_amount / (2 * atr_val))
                amount = qty * current
                amount = min(amount, total * 0.40, total * max_single_pct / 100)
                qty = int(amount / current)
            else:
                amount = total * max_single_pct / 100
                qty = int(amount / current)

            if qty <= 0 or current * qty > cash: continue

            sector_val = current * qty
            for tk, ps in positions.items():
                n, s, ddf = stock_data[tk]
                if s == sector and day_idx < len(ddf):
                    sector_val += ps['qty'] * float(ddf.iloc[day_idx]['close'])
            if total > 0 and sector_val / total * 100 > max_sector_pct: continue

            cost = qty * current * (1 + 0.00015)
            if cost > cash: continue
            cash -= cost
            positions[ticker] = {
                'qty': qty, 'avg_price': current, 'bought_idx': day_idx,
                'highest': current, 'sector': sector, 'entry_source': 'ens'
            }
            trades.append({'action': 'BUY', 'name': name, 'pnl': 0, 'pnl_pct': 0})

        # 3b. RSI(2) 급락 매수
        for ticker, name, sector, score, rsi2_buy, df, f_score_val, fw in candidates:
            if not rsi2_buy: continue
            if len(positions) >= max_positions: break
            if ticker in positions: continue

            # F-Score 필터 (RSI2에도 적용)
            if fund_filter and f_score_val < 4:
                fund_blocks += 1
                continue

            current = float(df.iloc[day_idx]['close'])
            total = cash
            for tk, ps in positions.items():
                _, _, ddf = stock_data[tk]
                if day_idx < len(ddf):
                    total += ps['qty'] * float(ddf.iloc[day_idx]['close'])

            atr_s = compute_atr(df.iloc[:day_idx + 1], 14)
            atr_val = float(atr_s.iloc[-1])
            if atr_val > 0 and current > 0:
                risk_amount = total * (atr_risk_pct * portfolio_exposure_scale / 100)
                qty = int(risk_amount / (2 * atr_val))
                amount = qty * current
                amount = min(amount, total * 0.40, total * max_single_pct / 100)
                qty = int(amount / current)
            else:
                amount = total * max_single_pct / 100
                qty = int(amount / current)

            if qty <= 0 or current * qty > cash: continue
            cost = qty * current * (1 + 0.00015)
            if cost > cash: continue
            cash -= cost
            positions[ticker] = {
                'qty': qty, 'avg_price': current, 'bought_idx': day_idx,
                'highest': current, 'sector': sector, 'entry_source': 'rsi2'
            }
            trades.append({'action': 'RSI2_BUY', 'name': name, 'pnl': 0, 'pnl_pct': 0})

    # 최종 평가
    final_assets = cash
    for ticker, pos in positions.items():
        _, _, df = stock_data[ticker]
        final_assets += pos['qty'] * float(df.iloc[-1]['close'])

    ret = (final_assets / capital - 1) * 100
    sell_trades = [t for t in trades if t['action'] not in ('BUY', 'RSI2_BUY')]
    wins = sum(1 for t in sell_trades if t['pnl'] > 0)
    total_trades = len(sell_trades)
    win_rate = wins / total_trades * 100 if total_trades > 0 else 0

    eq = np.array(equity_curve)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak * 100
    mdd = float(dd.min()) if len(dd) > 0 else 0

    sharpe = 0
    if len(equity_curve) > 1:
        daily_ret = pd.Series(equity_curve).pct_change().dropna()
        if daily_ret.std() > 0:
            sharpe = float(daily_ret.mean() / daily_ret.std() * np.sqrt(252))

    rebal_count = sum(1 for t in trades if t['action'] == 'REBALANCE')
    rsi2_trades = sum(1 for t in trades if 'RSI2' in t['action'] and t['action'] != 'RSI2_BUY')
    rsi2_wins = sum(1 for t in trades if 'RSI2' in t['action'] and t['action'] != 'RSI2_BUY' and t['pnl'] > 0)

    return {
        'label': label, 'return': ret, 'sharpe': sharpe, 'mdd': mdd,
        'trades': len(trades), 'sell_trades': total_trades, 'wins': wins,
        'win_rate': win_rate, 'final': final_assets, 'rebalance': rebal_count,
        'rsi2_trades': rsi2_trades, 'rsi2_wins': rsi2_wins,
        'fund_blocks': fund_blocks,
    }


if __name__ == '__main__':
    configs = [
        {'label': 'A. v3.7 베이스라인',
         'fund_weight': 0.0},
        {'label': 'B. v3.8 펀더멘털 10%',
         'fund_weight': 0.10},
        {'label': 'C. v3.8 펀더+F-Score필터',
         'fund_weight': 0.10, 'fund_filter': True},
        {'label': 'D. v3.8 펀더 17% (BEAR강조)',
         'fund_weight': 0.17},
        {'label': 'E. v3.8 + Half-Kelly',
         'fund_weight': 0.10, 'fund_filter': True, 'half_kelly': True},
        {'label': 'F. v3.8 + CVaR 리스크',
         'fund_weight': 0.10, 'fund_filter': True, 'cvar_limit': True},
        {'label': 'G. v3.8 풀옵션 (F+Kelly+CVaR)',
         'fund_weight': 0.12, 'fund_filter': True,
         'half_kelly': True, 'cvar_limit': True},
        {'label': 'H. v3.8 경고3+차단',
         'fund_weight': 0.10, 'fund_warning_filter': 3},
    ]

    print()
    results = []
    for cfg in configs:
        print(f'  백테스트: {cfg["label"]}...')
        r = run_backtest(cfg)
        results.append(r)

    print()
    print('=' * 110)
    print(f'  {"설정":<35} {"수익률":>8} {"Sharpe":>7} {"MDD":>8} {"매매":>5} {"승률":>6} {"리밸":>4} {"차단":>4}')
    print('=' * 110)

    best_sharpe_idx = 0
    best_return_idx = 0
    for i, r in enumerate(results):
        marker = ''
        if r['sharpe'] > results[best_sharpe_idx]['sharpe']:
            best_sharpe_idx = i
        if r['return'] > results[best_return_idx]['return']:
            best_return_idx = i

        print(
            f'  {r["label"]:<35} '
            f'{r["return"]:+7.2f}% '
            f'{r["sharpe"]:7.2f} '
            f'{r["mdd"]:+7.2f}% '
            f'{r["sell_trades"]:5d} '
            f'{r["win_rate"]:5.1f}% '
            f'{r["rebalance"]:4d} '
            f'{r["fund_blocks"]:4d}'
        )
    print('=' * 110)

    best_s = results[best_sharpe_idx]
    best_r = results[best_return_idx]
    print(f'\n  최고 Sharpe: {best_s["label"]} (Sharpe={best_s["sharpe"]:.2f}, 수익={best_s["return"]:+.2f}%)')
    print(f'  최고 수익률: {best_r["label"]} (수익={best_r["return"]:+.2f}%, Sharpe={best_r["sharpe"]:.2f})')
    print(f'\n  추천 설정: Sharpe가 가장 높은 조합이 리스크 대비 최적')

    # 최적 설정 상세
    best = best_s
    print(f'\n  === 최적 설정 상세 ===')
    print(f'  최종 자산: {best["final"]:,.0f}원 (초기 2,000,000원)')
    print(f'  순수익: {best["final"] - 2_000_000:+,.0f}원')
    print(f'  총 거래: {best["trades"]}건 (매도: {best["sell_trades"]}건)')
    print(f'  승률: {best["win_rate"]:.1f}%')
    print(f'  MDD: {best["mdd"]:+.2f}%')
    if best['rsi2_trades'] > 0:
        rsi2_wr = best['rsi2_wins'] / best['rsi2_trades'] * 100
        print(f'  RSI(2) 거래: {best["rsi2_trades"]}건, 승률: {rsi2_wr:.1f}%')
    if best['fund_blocks'] > 0:
        print(f'  펀더멘털 차단: {best["fund_blocks"]}건')
