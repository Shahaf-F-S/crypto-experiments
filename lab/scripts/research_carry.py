# research_carry.py

import sys

import numpy as np
import pandas as pd

from system.history import load_funding
from lab.research.stats import summary

PAIRS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
PERIODS = {'discovery': ('2021-01-01', '2024-01-01'), 'holdout': ('2024-01-01', '2026-10-08')}

# C1, pre-registered: hold long spot / short perpetual (delta neutral) while the trailing 7-day funding is above
# ENTER per year; leave below LEAVE. Each round trip costs both legs both ways at taker fees (spot 10 bps, futures 5
# bps a side) plus 5 bps of basis slippage each way.
ENTER, LEAVE = 0.10, 0.03
ROUND_TRIP = 2 * (0.0010 + 0.0005) + 2 * 0.0005


def carry(symbol: str, start: str, end: str) -> pd.Series:
    """Daily returns (on the capital of the hedged position) of C1 on one pair, funding paid every 8 hours."""
    rates = load_funding(symbol)
    rates = rates[(rates.index >= pd.Timestamp(start, tz='UTC') - pd.Timedelta(days=14)) & (rates.index < pd.Timestamp(end, tz='UTC'))]
    trailing = rates.rolling(21).sum() * 365 / 7             # 21 payments = 7 days, annualized
    held, pnl = False, []

    for when, rate in rates.items():
        income = rate if held else 0.0                      # the short perpetual receives positive funding
        level = trailing.get(when)
        cost = 0.0

        if level == level:                                   # decided after this payment, for the next ones
            if not held and level > ENTER:
                held, cost = True, ROUND_TRIP / 2
            elif held and level < LEAVE:
                held, cost = False, ROUND_TRIP / 2

        pnl.append((when, income - cost))

    series = pd.Series(dict(pnl))
    series = series[series.index >= pd.Timestamp(start, tz='UTC')]
    return series.groupby(series.index.floor('1D')).sum()


if __name__ == '__main__':
    period = sys.argv[1] if len(sys.argv) > 1 else 'discovery'
    start, end = PERIODS[period]
    daily = {s: carry(s, start, end) for s in PAIRS}
    portfolio = pd.concat(daily, axis=1).fillna(0.0).mean(axis=1)
    s = summary(portfolio)
    print(f'C1 funding carry, {period}: sharpe {s["sharpe"]:.2f}, return {s["annual return"]:.1%}/y, vol {s["annual volatility"]:.1%}, '
          f'max drawdown {s["max drawdown"]:.1%}, positive months {s["positive months"]:.0%}')
    print('  by pair: ' + ', '.join(f'{k[:4]} {summary(v)["annual return"]:.1%}' for k, v in daily.items()) + '   by year: ' +
          ', '.join(f'{y} {portfolio[portfolio.index.year == y].sum():.1%}' for y in sorted(set(portfolio.index.year))))
