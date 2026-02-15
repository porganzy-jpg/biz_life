"""Live monitor for CryptoBot - watches for trades in real-time."""
import urllib.request
import json
import time

URL = 'http://localhost:8081'
prev_trades = 0
prev_cycle = 0
start = time.time()

print('=' * 65)
print(' CryptoBot Live Monitor - Waiting for trades...')
print(' Markets: BTC, ETH, XRP | Mode: Paper | Balance: 1,000,000 KRW')
print('=' * 65)
print()

while True:
    try:
        d = json.loads(urllib.request.urlopen(f'{URL}/api/status', timeout=5).read())
        mw = json.loads(urllib.request.urlopen(f'{URL}/api/market-watch', timeout=5).read())

        cycle = d['cycle_count']
        trades = d['total_trades']
        bal = d['balance_krw']
        pnl = d['daily_pnl']
        elapsed = time.time() - start

        # Market summary
        signals = []
        for m, info in mw.items():
            coin = m.split('-')[1]
            trend = info.get('trend', '?')
            sig = info.get('ensemble_signal', '?')
            ts = info.get('trigger_summary', {}).get('ensemble', {})
            votes = ts.get('buy_votes', 0)

            t_icon = 'UP' if trend == 'up' else 'DN' if trend == 'down' else '--'
            s_icon = '*BUY*' if sig == 'BUY' else 'SELL' if sig == 'SELL' else 'hold'
            signals.append(f'{coin}:{t_icon}:{s_icon}(v{votes})')

        sig_str = ' | '.join(signals)

        # Position info
        pos_str = ''
        for m, p in d.get('open_positions', {}).items():
            coin = m.split('-')[1]
            pnl_pct = p['unrealized_pnl_pct']
            icon = '+' if pnl_pct >= 0 else ''
            pos_str += f' [{coin} {icon}{pnl_pct:.2f}%]'

        if not pos_str:
            pos_str = ' [no pos]'

        mins = int(elapsed // 60)
        secs = int(elapsed % 60)

        line = f'[{mins:02d}:{secs:02d}] C#{cycle} | {sig_str} |{pos_str}'

        # Trade happened!
        if trades > prev_trades:
            new = trades - prev_trades
            recent = d.get('recent_trades', [])
            for t in recent[-new:]:
                result = 'WIN' if t.get('pnl_krw', 0) > 0 else 'LOSS'
                print(f'\n  >>> TRADE! {t["market"]} | {t["exit_type"]} | {result} | '
                      f'PnL: {t["pnl_pct"]:.2f}% ({t["pnl_krw"]:+,.0f} KRW)')
            wr = d["win_rate"]
            print(f'  >>> Total: W:{d["wins"]}/L:{d["losses"]} WR:{wr:.1f}% | '
                  f'Balance: {bal:,.0f} KRW | DailyPnL: {pnl:+,.0f}\n')
            prev_trades = trades

        print(f'\r{line}', end='', flush=True)

        # Full status every 30 cycles
        if cycle % 30 == 0 and cycle != prev_cycle:
            ts_str = time.strftime("%H:%M:%S")
            print(f'\n  [{ts_str}] Trades:{trades} W:{d["wins"]}/L:{d["losses"]} '
                  f'PnL:{pnl:+,.0f} Fees:{d["total_fees_krw"]:,.0f} Bal:{bal:,.0f}')
            prev_cycle = cycle

    except Exception as e:
        print(f'\r[ERR] {e}', end='')

    time.sleep(3)
