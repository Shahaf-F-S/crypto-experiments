# research_families.py

import sys

import pandas as pd

from lab.research.families import simulate, target_reversal, target_spike
from lab.research.scan import bars
from lab.research.stats import summary

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
PERIODS = {'discovery': ('2021-01-01', '2024-01-01'), 'holdout': ('2024-01-01', '2026-10-08')}
FAMILIES = {'R1 reversal of the last hour, 24h hold': target_reversal, 'V1 volatility spike, week hold': target_spike}

if __name__ == '__main__':
    period = sys.argv[1] if len(sys.argv) > 1 else 'discovery'
    start, end = PERIODS[period]
    begin = (pd.Timestamp(start) - pd.Timedelta(days=60)).strftime('%Y-%m-%d')
    print(f'{period} {start} to {end}, equal weight over {len(SYMBOLS)} pairs, futures taker costs, slippage, funding:')

    for name, family in FAMILIES.items():
        daily = {}

        for symbol in SYMBOLS:
            b = bars(symbol, begin, end, '1h')
            e = simulate(symbol, family(b), b)['equity']
            e = e[e.index >= pd.Timestamp(start, tz='UTC')].resample('1D').last()
            daily[symbol] = e.pct_change().dropna()

        portfolio = pd.concat(daily, axis=1).fillna(0.0).mean(axis=1)
        s = summary(portfolio)
        print(f'\n{name}: sharpe {s["sharpe"]:.2f}, return {s["annual return"]:.1%}/y, vol {s["annual volatility"]:.1%}, '
              f'max drawdown {s["max drawdown"]:.1%}, positive months {s["positive months"]:.0%}')
        print('  by pair: ' + ', '.join(f'{k[:3]} {summary(v)["sharpe"]:.2f}' for k, v in daily.items()) + '   by year: ' +
              ', '.join(f'{y} {summary(portfolio[portfolio.index.year == y])["sharpe"]:.2f}' for y in sorted(set(portfolio.index.year))))
