# research_cross.py

import math
import sys

import numpy as np
import pandas as pd

from lab.research.backtest import COST_BPS
from system.history import load_funding
from lab.research.scan import bars
from lab.research.stats import summary

UNIVERSE = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'LTCUSDT', 'LINKUSDT',
            'AVAXUSDT', 'DOTUSDT', 'TRXUSDT', 'BCHUSDT']
PERIODS = {'discovery': ('2021-01-01', '2024-01-01'), 'holdout': ('2024-01-01', '2026-10-08')}


def panel(symbols: list[str], start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    closes, funding = {}, {}

    for symbol in symbols:
        b = bars(symbol, start, end, '1h')
        closes[symbol] = b['close']

        try:
            rates = load_funding(symbol)
            funding[symbol] = rates.groupby(rates.index.floor('1h')).sum().reindex(b.index, fill_value=0.0)
        except FileNotFoundError:
            funding[symbol] = pd.Series(0.0, index=b.index)

    return pd.DataFrame(closes), pd.DataFrame(funding).fillna(0.0)


def weights(closes: pd.DataFrame, lookback_days: int = 7) -> pd.DataFrame:
    """
    XS1: at 00:00 UTC, rank the pairs by their volatility-normalized return over `lookback_days`; long the top third,
    short the bottom third, each leg weighted by inverse volatility to 1% daily volatility per pair, total gross at
    most one; zero for pairs without enough history.
    """
    x = np.log(closes)
    daily = x.diff().rolling(24 * 30, min_periods=24 * 10).std() * math.sqrt(24)
    score = (x - x.shift(24 * lookback_days)) / (daily * math.sqrt(lookback_days))
    out = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)

    for t in np.nonzero(closes.index.hour == 0)[0]:
        s = score.iloc[t].dropna()

        if len(s) < 6:
            continue

        third = len(s) // 3
        ranked = s.sort_values()
        w = pd.Series(0.0, index=closes.columns)
        w[ranked.index[-third:]] = 1.0
        w[ranked.index[:third]] = -1.0
        w = w * (0.01 / daily.iloc[t]).fillna(0.0)
        gross = w.abs().sum()
        out.iloc[t] = w / gross if gross > 1 else w

    held = out.copy()
    held[out.index.hour != 0] = np.nan
    return held.ffill().fillna(0.0)


def backtest(closes: pd.DataFrame, funding: pd.DataFrame, held: pd.DataFrame) -> pd.Series:
    """Hourly net returns: weights decided at a close earn the next hour's simple return; costs on changes; funding."""
    r = closes.pct_change().fillna(0.0)
    previous = held.shift(1).fillna(0.0)
    costs = sum((held[s] - previous[s]).abs() * COST_BPS.get(s, 14.0) / 2e4 for s in held.columns)
    return (previous * r).sum(axis=1) - costs - (previous * funding).sum(axis=1)


if __name__ == '__main__':
    period = sys.argv[1] if len(sys.argv) > 1 else 'discovery'
    start, end = PERIODS[period]
    closes, funding = panel(UNIVERSE, (pd.Timestamp(start) - pd.Timedelta(days=60)).strftime('%Y-%m-%d'), end)
    hourly = backtest(closes, funding, weights(closes))
    hourly = hourly[hourly.index >= pd.Timestamp(start, tz='UTC')]
    daily = (1.0 + hourly).resample('1D').prod() - 1.0
    s = summary(daily)
    print(f'XS1 cross-sectional momentum, {period}, {closes.shape[1]} pairs: sharpe {s["sharpe"]:.2f}, return '
          f'{s["annual return"]:.1%}/y, vol {s["annual volatility"]:.1%}, max drawdown {s["max drawdown"]:.1%}, positive months '
          f'{s["positive months"]:.0%}   by year: ' + ', '.join(f'{y} {summary(daily[daily.index.year == y])["sharpe"]:.2f}' for y in sorted(set(daily.index.year))))
