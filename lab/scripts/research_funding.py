# research_funding.py

import math

import numpy as np
import pandas as pd

from system.history import load_funding
from lab.research.scan import bars

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
DISCOVERY = ('2021-01-01', '2024-01-01')
HORIZONS = {'24h': 24, '72h': 72, '168h': 168}


def signals(b: pd.DataFrame, rates: pd.Series) -> pd.DataFrame:
    """Funding signals known at each hour (funding paid up to that hour only)."""
    hourly = rates.groupby(rates.index.floor('1h')).sum().reindex(b.index, fill_value=0.0)
    out = {}

    for name, days in {'funding 1d': 1, 'funding 3d': 3, 'funding 7d': 7}.items():
        level = hourly.rolling(24 * days).sum() * 365 / days          # annualized
        history = level.rolling(24 * 90, min_periods=24 * 30)
        out[name] = (level - history.mean()) / history.std()

    out['funding level 3d'] = hourly.rolling(72).sum() * 365 / 3
    return pd.DataFrame(out)


if __name__ == '__main__':
    rows = []

    for symbol in SYMBOLS:
        b = bars(symbol, *DISCOVERY, '1h')
        s = signals(b, load_funding(symbol))
        x = np.log(b['close'])

        for horizon, n in HORIZONS.items():
            forward = (x.shift(-n) - x) * 1e4

            for name in s.columns:
                raw = s[name].replace([np.inf, -np.inf], np.nan)
                scale = raw.expanding(500).std().shift(1)
                frame = pd.DataFrame({'p': (raw / scale).clip(-2, 2), 't': forward}).iloc[::n].dropna()

                for year, g in frame.groupby(frame.index.year):
                    # Returns demeaned within the pair-year: the drift of a bull or bear year is not an edge.
                    t = g['t'] - g['t'].mean()
                    pnl = g['p'] * t
                    rows.append({'symbol': symbol, 'signal': name, 'horizon': horizon, 'year': year,
                                 'edge': pnl.mean() / g['p'].abs().mean()})

    rows = pd.DataFrame(rows)
    print('Funding signals, discovery, mean-based edge per unit position (bps), returns demeaned per pair-year:')

    for (signal, horizon), g in rows.groupby(['signal', 'horizon']):
        mean = g['edge'].mean()
        t = mean / (g['edge'].std(ddof=1) / math.sqrt(len(g)))
        print(f'  {signal:<18}{horizon:>6}{mean:>9.1f} bps   t {t:>6.2f}   same sign {int((g["edge"] * mean > 0).sum())}/{len(g)}')
