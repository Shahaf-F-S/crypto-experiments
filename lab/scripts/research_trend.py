# research_trend.py

import sys

import pandas as pd

from lab.research.stats import deflated_sharpe, summary
from lab.research.trend import Trend, run

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
PERIODS = {'discovery': ('2021-01-01', '2024-01-01'), 'holdout': ('2024-01-01', '2026-10-08')}

# The whole pre-registered family (docs/RESULTS.md): every variant is reported.
RULES = [
    Trend('F1 trend 7/14/28d'),
    Trend('F2 trend, pullback timing', timing=True),
    Trend('F3 trend, long only', long_only=True),
    Trend('F4 trend 3/7/14d', lookbacks=(3, 7, 14)),
]


def daily(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].resample('1D').sum()


if __name__ == '__main__':
    period = sys.argv[1] if len(sys.argv) > 1 else 'discovery'
    start, end = PERIODS[period]
    results, sharpes = {}, []

    for rule in RULES:
        per_symbol = {symbol: run(symbol, rule, start, end) for symbol in SYMBOLS}
        portfolio = sum(daily(f, 'net') for f in per_symbol.values()) / len(SYMBOLS)
        s = summary(portfolio)
        sharpes.append(s['sharpe'])
        parts = {k: sum(daily(f, k) for f in per_symbol.values()).sum() / len(SYMBOLS) / (s['days'] / 365) for k in ('gross', 'costs', 'funding')}
        turnover = sum(f['position'].diff().abs().sum() for f in per_symbol.values()) / len(SYMBOLS) / (s['days'] / 365)
        years = sorted(set(portfolio.index.year))
        results[rule.name] = (portfolio, s, parts, turnover,
                              {k: summary(daily(f, 'net'))['sharpe'] for k, f in per_symbol.items()},
                              {y: summary(portfolio[portfolio.index.year == y])['sharpe'] for y in years})

    print(f'{period} {start} to {end}, equal weight over {len(SYMBOLS)} pairs, net of futures taker costs, slippage and funding:')

    for name, (portfolio, s, parts, turnover, by_symbol, by_year) in results.items():
        print(f'\n{name}: sharpe {s["sharpe"]:.2f}, return {s["annual return"]:.1%}/y (gross {parts["gross"]:.1%}, costs '
              f'{parts["costs"]:.1%}, funding {parts["funding"]:+.1%}), vol {s["annual volatility"]:.1%}, max drawdown '
              f'{s["max drawdown"]:.1%}, positive months {s["positive months"]:.0%}, turnover {turnover:.0f}x/y, '
              f'deflated sharpe {deflated_sharpe(portfolio, len(RULES), sharpes):.2f}')
        print('  by pair: ' + ', '.join(f'{k[:3]} {v:.2f}' for k, v in by_symbol.items()) + '   by year: ' + ', '.join(f'{k} {v:.2f}' for k, v in by_year.items()))
