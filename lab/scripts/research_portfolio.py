# research_portfolio.py

import multiprocessing
import sys

import pandas as pd

from lab.research.stats import deflated_sharpe, summary
from lab.scripts.research_cross import UNIVERSE, backtest, panel, weights
from lab.scripts.research_framework import one

PERIODS = {'discovery': ('2021-01-01', '2024-01-01'), 'holdout': ('2024-01-01', '2026-10-08')}
PRIMARY = 'F2 trend, pullback timing'


def trend(start: str, end: str) -> pd.Series:
    with multiprocessing.get_context('spawn').Pool(len(UNIVERSE)) as pool:
        results = pool.starmap(one, [(s, start, end, False) for s in UNIVERSE])

    return pd.concat([r[PRIMARY] for r in results], axis=1).fillna(0.0).mean(axis=1)


def cross(start: str, end: str) -> pd.Series:
    closes, funding = panel(UNIVERSE, (pd.Timestamp(start) - pd.Timedelta(days=60)).strftime('%Y-%m-%d'), end)
    hourly = backtest(closes, funding, weights(closes))
    hourly = hourly[hourly.index >= pd.Timestamp(start, tz='UTC')]
    return (1.0 + hourly).resample('1D').prod() - 1.0


if __name__ == '__main__':
    period = sys.argv[1] if len(sys.argv) > 1 else 'discovery'
    start, end = PERIODS[period]
    t, x = trend(start, end), cross(start, end)
    both = pd.concat([t, x], axis=1, keys=['trend', 'cross']).dropna()

    # Equal risk, from the discovery period's volatilities only (fixed before the holdout).
    vt, vx = (0.0, 0.0)
    d0, d1 = PERIODS['discovery']

    if period == 'discovery':
        vt, vx = both['trend'].std(), both['cross'].std()
        print(f'discovery daily volatilities: trend {vt:.5f}, cross {vx:.5f}')
    else:
        vt, vx = float(sys.argv[2]), float(sys.argv[3])

    combined = 0.5 * both['trend'] / vt * vt + 0.5 * both['cross'] * (vt / vx)
    print(f'{period} {start} to {end}: correlation of daily returns {both.corr().iloc[0, 1]:.2f}')

    for name, series in (('trend F2, 13 pairs', both['trend']), ('cross-sectional XS1', both['cross']), ('combined, equal risk', combined)):
        s = summary(series)
        years = ', '.join(f'{y} {summary(series[series.index.year == y])["sharpe"]:.2f}' for y in sorted(set(series.index.year)))
        print(f'  {name:<24} sharpe {s["sharpe"]:.2f}, return {s["annual return"]:.1%}/y, vol {s["annual volatility"]:.1%}, '
              f'max drawdown {s["max drawdown"]:.1%}, positive months {s["positive months"]:.0%}   {years}')
