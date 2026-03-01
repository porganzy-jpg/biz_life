# -*- coding: utf-8 -*-
"""뉴스 부스트 유/무 수익률 비교 백테스트"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'strategy'))
import numpy as np
import pandas as pd
import yfinance as yf
from stock_selector import StockSelectorEnsemble

WATCHLIST = [
    ('005930.KS', '삼성전자'), ('000660.KS', 'SK하이닉스'), ('035420.KS', 'NAVER'),
    ('035720.KS', '카카오'), ('051910.KS', 'LG화학'), ('006400.KS', '삼성SDI'),
    ('003670.KS', '포스코퓨처엠'), ('028260.KS', '삼성물산'), ('105560.KS', 'KB금융'),
    ('055550.KS', '신한지주'), ('005380.KS', '현대자동차'), ('000270.KS', '기아'),
    ('068270.KS', '셀트리온'), ('086790.KS', '하나금융지주'), ('017670.KS', 'SK텔레콤'),
]


def simulate(data_dict, test_start, test_end, news_mode='none', news_sent=0.3):
    capital = 10_000_000
    cash = capital
    positions = {}
    trades = []
    selector = StockSelectorEnsemble()

    sample_df = list(data_dict.values())[0][0]
    dates = sample_df.loc[test_start:test_end].index

    for date in dates:
        for ticker, (df, name) in data_dict.items():
            if date not in df.index:
                continue
            idx = df.index.get_loc(date)
            if idx < 130:
                continue
            window = df.iloc[:idx + 1]

            symbol = ticker.replace('.KS', '')
            result = selector.evaluate(window, symbol, name, regime='BULL')

            quant_score = result['score']

            if news_mode == 'boost':
                final_score = quant_score * 0.85 + (50 + news_sent * 15) * 0.15
                final_score = round(max(10, min(90, final_score)), 1)
            else:
                final_score = quant_score

            buy_th, sell_th = 58, 42

            if final_score >= buy_th and ticker not in positions and len(positions) < 4:
                price = float(window['close'].iloc[-1])
                qty = int((cash * 0.3) / price)
                if qty > 0:
                    cost = qty * price * 1.00015
                    if cost <= cash:
                        cash -= cost
                        positions[ticker] = {'qty': qty, 'price': price, 'name': name}
                        trades.append(('BUY', name, date, price, qty, final_score))

            elif ticker in positions:
                pos = positions[ticker]
                price = float(window['close'].iloc[-1])
                pnl_pct = (price - pos['price']) / pos['price']

                sell = False
                reason = ''
                if pnl_pct <= -0.05:
                    sell, reason = True, '손절'
                elif pnl_pct >= 0.10:
                    sell, reason = True, '익절'
                elif final_score <= sell_th:
                    sell, reason = True, '퀀트SELL'

                if sell:
                    proceeds = pos['qty'] * price * (1 - 0.00315)
                    cash += proceeds
                    pnl = proceeds - pos['qty'] * pos['price'] * 1.00015
                    trades.append(('SELL', name, date, price, pos['qty'], final_score, pnl, reason))
                    del positions[ticker]

    # 미청산 평가
    total = cash
    for ticker, pos in positions.items():
        if ticker in data_dict:
            df = data_dict[ticker][0]
            last_price = float(df.loc[:test_end]['close'].iloc[-1])
            total += pos['qty'] * last_price

    ret = (total - capital) / capital * 100
    buy_trades = [t for t in trades if t[0] == 'BUY']
    sell_trades = [t for t in trades if t[0] == 'SELL']
    wins = [t for t in sell_trades if t[6] > 0]
    wr = len(wins) / len(sell_trades) * 100 if sell_trades else 0

    return {
        'return': ret, 'trades': len(trades), 'buys': len(buy_trades),
        'sells': len(sell_trades), 'win_rate': wr, 'open': len(positions),
        'trade_log': trades,
    }


def print_header(title):
    print()
    print('=' * 70)
    print(f'  {title}')
    print('=' * 70)


def print_results(results_dict):
    print(f"{'모드':>20} {'수익률':>8} {'매매':>6} {'매수':>6} {'매도':>6} {'승률':>6} {'미청산':>6}")
    print('-' * 65)
    for label, r in results_dict.items():
        print(f"{label:>20} {r['return']:+7.2f}% {r['trades']:6} {r['buys']:6} {r['sells']:6} {r['win_rate']:5.1f}% {r['open']:6}")


if __name__ == '__main__':
    # === 상승장 ===
    print_header('상승장 데이터 다운로드 (2025.12~2026.02)')
    start, end = '2025-06-01', '2026-02-28'
    all_data = {}
    for ticker, name in WATCHLIST:
        df = yf.download(ticker, start=start, end=end, progress=False)
        if df is not None and len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0].lower() for c in df.columns]
            else:
                df.columns = [c.lower() for c in df.columns]
            if len(df) > 130:
                all_data[ticker] = (df, name)
                print(f'    OK {name}({ticker}): {len(df)}일')
            else:
                print(f'    SKIP {name}: {len(df)}일 (130일 미만)')
    print(f'  {len(all_data)}종목 OK')

    print_header('상승장 비교 (2025.12~2026.02)')
    bull = {}
    bull['순수 퀀트'] = simulate(all_data, '2025-12-01', '2026-02-28', 'none')
    bull['뉴스+긍정(0.3)'] = simulate(all_data, '2025-12-01', '2026-02-28', 'boost', 0.3)
    bull['뉴스+중립(0.0)'] = simulate(all_data, '2025-12-01', '2026-02-28', 'boost', 0.0)
    bull['뉴스+부정(-0.3)'] = simulate(all_data, '2025-12-01', '2026-02-28', 'boost', -0.3)
    print_results(bull)

    # 매매 내역 비교
    print()
    print('  [순수 퀀트 매매 내역]')
    for t in bull['순수 퀀트']['trade_log']:
        if t[0] == 'BUY':
            print(f"    BUY  {t[1]:12} {str(t[2])[:10]} {t[3]:>10,.0f} x{t[4]} score={t[5]:.1f}")
        else:
            print(f"    SELL {t[1]:12} {str(t[2])[:10]} {t[3]:>10,.0f} x{t[4]} pnl={t[6]:+,.0f} ({t[7]})")

    print()
    print('  [뉴스+긍정(0.3) 매매 내역]')
    for t in bull['뉴스+긍정(0.3)']['trade_log']:
        if t[0] == 'BUY':
            print(f"    BUY  {t[1]:12} {str(t[2])[:10]} {t[3]:>10,.0f} x{t[4]} score={t[5]:.1f}")
        else:
            print(f"    SELL {t[1]:12} {str(t[2])[:10]} {t[3]:>10,.0f} x{t[4]} pnl={t[6]:+,.0f} ({t[7]})")

    # === 하락장 ===
    print_header('하락장 데이터 다운로드 (2025.03~2025.05)')
    start2, end2 = '2024-10-01', '2025-05-31'
    all_data2 = {}
    for ticker, name in WATCHLIST:
        df = yf.download(ticker, start=start2, end=end2, progress=False)
        if df is not None and len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0].lower() for c in df.columns]
            else:
                df.columns = [c.lower() for c in df.columns]
            if len(df) > 130:
                all_data2[ticker] = (df, name)
    print(f'  {len(all_data2)}종목 OK')

    print_header('하락장 비교 (2025.03~2025.05)')
    bear = {}
    bear['순수 퀀트'] = simulate(all_data2, '2025-03-01', '2025-05-31', 'none')
    bear['뉴스+긍정(0.3)'] = simulate(all_data2, '2025-03-01', '2025-05-31', 'boost', 0.3)
    bear['뉴스+중립(0.0)'] = simulate(all_data2, '2025-03-01', '2025-05-31', 'boost', 0.0)
    bear['뉴스+부정(-0.3)'] = simulate(all_data2, '2025-03-01', '2025-05-31', 'boost', -0.3)
    print_results(bear)

    # === 결론 ===
    print_header('결론')
    d1 = bull['순수 퀀트']['return'] - bull['뉴스+긍정(0.3)']['return']
    d2 = bear['순수 퀀트']['return'] - bear['뉴스+긍정(0.3)']['return']
    print(f"  상승장: 순수퀀트 {bull['순수 퀀트']['return']:+.2f}% vs 뉴스부스트 {bull['뉴스+긍정(0.3)']['return']:+.2f}% → 차이 {d1:+.2f}%p")
    print(f"  하락장: 순수퀀트 {bear['순수 퀀트']['return']:+.2f}% vs 뉴스부스트 {bear['뉴스+긍정(0.3)']['return']:+.2f}% → 차이 {d2:+.2f}%p")
    print()
    if d1 > 0 and d2 >= 0:
        print('  → 순수 퀀트가 양쪽 모두 우위. 뉴스 부스트 제거 권장.')
    elif d1 > 0:
        print(f'  → 상승장에서 순수 퀀트 {d1:+.2f}%p 우위, 하락장에서 {d2:+.2f}%p.')
    else:
        print(f'  → 뉴스 부스트가 상승장에서 {-d1:+.2f}%p 우위.')

    print()
    print('  수학적 분석:')
    print('  - 뉴스 부스트 공식: final = quant * 0.85 + (50 + sent*15) * 0.15')
    print('  - BUY 시그널(>=58): 중립 뉴스에도 -1.2p 깎임 → 매수 기회 놓침')
    print('  - SELL 시그널(<=42): 중립 뉴스에도 +1.2p 올림 → 매도 기회 놓침')
    print('  - 근본 원인: 0.85 가중치가 강한 시그널을 50 방향으로 회귀시킴')
