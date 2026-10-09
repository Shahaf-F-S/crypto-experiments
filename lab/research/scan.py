# scan.py

import math

import numpy as np
import pandas as pd

from system.history import load


__all__ = [
    'bars',
    'signals',
    'scan'
]


def bars(symbol: str, start: str | None, end: str | None, interval: str = '1h') -> pd.DataFrame:
    """Klines on a regular grid: missing bars (exchange outages) carry the last price and no volume."""
    k = load(symbol, start, end, interval=interval)
    out = pd.DataFrame({'close': k['close'], 'high': k['high'], 'low': k['low'], 'volume': k['volume'],
                        'buy': k['taker_buy'], 'trades': k['trades']})
    grid = pd.date_range(out.index[0], out.index[-1], freq=pd.Timedelta(interval.replace('m', 'min')), tz='UTC')
    out = out.reindex(grid)
    out['close'] = out['close'].ffill()
    out[['high', 'low']] = out[['high', 'low']].ffill()
    out[['volume', 'buy', 'trades']] = out[['volume', 'buy', 'trades']].fillna(0.0)
    return out


def signals(b: pd.DataFrame, hours: float) -> pd.DataFrame:
    """Candidate signals at each bar close (bars of `hours`), from completed bars only (no look-ahead)."""
    per_day = int(round(24 / hours))
    x = np.log(b['close'])
    r = x.diff()
    sigma = r.rolling(7 * per_day, min_periods=3 * per_day).std()      # bar volatility over the last week
    out = {}

    for name, h in {'1h': 1, '4h': 4, '12h': 12, '24h': 24, '72h': 72, '168h': 168}.items():
        n = int(round(h / hours))

        if n >= 1:
            out[f'momentum {name}'] = (x - x.shift(n)) / (sigma * math.sqrt(n))

    for name, h in {'1h': 1, '4h': 4, '24h': 24}.items():
        n = int(round(h / hours))

        if n >= 1:
            out[f'flow {name}'] = b['buy'].rolling(n).sum() / b['volume'].rolling(n).sum() - 0.5

    day = b.index.floor('1D')
    elapsed = np.maximum((b.index.hour + b.index.minute / 60) / hours, 1)
    out['since midnight'] = (x - x.groupby(day).transform('first')) / (sigma * np.sqrt(elapsed))
    out['24h range position'] = (b['close'] - b['low'].rolling(per_day).min()) / (b['high'].rolling(per_day).max() - b['low'].rolling(per_day).min()) - 0.5
    out['volatility regime'] = np.log(r.rolling(per_day).std() / r.rolling(30 * per_day, min_periods=10 * per_day).std())
    out['activity regime'] = np.log(b['trades'].rolling(per_day).mean() / b['trades'].rolling(30 * per_day, min_periods=10 * per_day).mean())
    out['distance from 7d mean'] = (x - x.rolling(7 * per_day).mean()) / (sigma * math.sqrt(7 * per_day))
    return pd.DataFrame(out)


def scan(symbols: list[str], start: str, end: str, interval: str = '1h', horizons: dict[str, float] | None = None) -> pd.DataFrame:
    """
    Information coefficients (Spearman) of every signal against the log return over each horizon, from
    non-overlapping samples (one every horizon), per symbol and year; and the mean forward return (bps) when the
    signal is beyond its top and bottom deciles (decile edges from earlier samples only).
    """
    hours = pd.Timedelta(interval.replace('m', 'min')).total_seconds() / 3600
    horizons = horizons or {'1h': 1, '4h': 4, '8h': 8, '24h': 24, '72h': 72}
    rows = []

    for symbol in symbols:
        b = bars(symbol, start, end, interval)
        s = signals(b, hours)
        x = np.log(b['close'])

        for horizon, h in horizons.items():
            n = int(round(h / hours))

            if n < 1:
                continue

            forward = (x.shift(-n) - x) * 1e4
            sampled, target = s.iloc[::n], forward.iloc[::n]

            for name in s.columns:
                frame = pd.DataFrame({'s': sampled[name], 't': target}).replace([np.inf, -np.inf], np.nan).dropna()

                for year, group in frame.groupby(frame.index.year):
                    if len(group) < 30:
                        continue

                    high = group['s'].expanding(30).quantile(0.9).shift(1)
                    low = group['s'].expanding(30).quantile(0.1).shift(1)
                    rows.append({
                        'symbol': symbol, 'horizon': horizon, 'signal': name, 'year': year, 'n': len(group),
                        'ic': group['s'].corr(group['t'], method='spearman'),
                        'top': group['t'][group['s'] > high].mean(), 'bottom': group['t'][group['s'] < low].mean(),
                        'sd': group['t'].std()
                    })

    return pd.DataFrame(rows)


def tradable(symbols: list[str], start: str, end: str, interval: str = '1h', horizons: dict[str, float] | None = None) -> pd.DataFrame:
    """
    Mean-based edge, the one a position earns: for each signal, standardized by its own past spread (expanding,
    no look-ahead) and clipped to +-2, the average of signal x forward log return (bps), from non-overlapping
    samples, per symbol and year. Positive: follow the signal; negative: fade it.
    """
    hours = pd.Timedelta(interval.replace('m', 'min')).total_seconds() / 3600
    horizons = horizons or {'4h': 4, '24h': 24, '72h': 72, '168h': 168}
    rows = []

    for symbol in symbols:
        b = bars(symbol, start, end, interval)
        s = signals(b, hours)
        x = np.log(b['close'])

        for horizon, h in horizons.items():
            n = int(round(h / hours))
            forward = (x.shift(-n) - x) * 1e4

            for name in s.columns:
                raw = s[name].replace([np.inf, -np.inf], np.nan)
                scale = raw.expanding(500).std().shift(1)
                position = (raw / scale).clip(-2, 2)
                frame = pd.DataFrame({'p': position, 't': forward}).iloc[::n].dropna()

                for year, group in frame.groupby(frame.index.year):
                    if len(group) < 20:
                        continue

                    pnl = group['p'] * group['t']
                    rows.append({'symbol': symbol, 'horizon': horizon, 'signal': name, 'year': year, 'n': len(group),
                                 'edge': pnl.mean(), 'sd': pnl.std(), 'exposure': group['p'].abs().mean()})

    return pd.DataFrame(rows)
