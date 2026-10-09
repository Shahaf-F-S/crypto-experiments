# research_synthetic_bars.py

import asyncio
import datetime as dt
import math
import multiprocessing

import numpy as np
import pandas as pd

from rapid_markets.source import Book
from lab.research.scan import bars
from simulation import Market, MarketModel

MODEL = 'simulation/btc_usdt.model'
DAYS, SEEDS = 21, 16


def synthetic(seed: int) -> pd.DataFrame:
    """Hourly bars (close, volume, taker-buy volume) of one synthetic replica."""
    async def go() -> pd.DataFrame:
        market = Market(model=MarketModel.load(MODEL), duration=dt.timedelta(days=DAYS), seed=seed)
        rows, hour, close, volume, buy = [], None, None, 0.0, 0.0

        async for event in market.stream():
            h = int(event.timestamp.timestamp() // 3600)

            if hour is not None and h != hour:
                rows.append((hour * 3600, close, volume, buy))
                volume = buy = 0.0

            hour = h

            if isinstance(event, Book):
                close = event.mid
            else:
                volume += event.quantity
                buy += event.quantity if event.side[0] in 'Bb' else 0.0

        frame = pd.DataFrame(rows, columns=['time', 'close', 'volume', 'buy'])
        frame.index = pd.to_datetime(frame['time'], unit='s', utc=True)
        return frame

    return asyncio.run(go())


def statistics(b: pd.DataFrame) -> dict[str, float]:
    """Hourly-scale statistics of one window of hourly bars."""
    r = np.log(b['close']).diff().dropna() * 1e4
    a = r.abs()
    daily = np.log(b['close']).iloc[::24].diff().dropna() * 1e4
    flow = (b['buy'] / b['volume'] - 0.5).dropna()
    centered = r - r.mean()

    def ac(x: pd.Series, k: int) -> float:
        return float(x.autocorr(k)) if len(x) > k + 10 else math.nan

    return {
        'hourly volatility (bps)': r.std(),
        'hourly kurtosis': float((centered ** 4).mean() / (centered ** 2).mean() ** 2),
        'largest hourly move (bps)': a.max(),
        'hourly return autocorrelation': ac(r, 1),
        'volatility clustering, 1 h': ac(a, 1),
        'volatility clustering, 24 h': ac(a, 24),
        'variance ratio, day / hour': daily.var() / (24 * r.var()),
        'net move over the window (bps)': abs(np.log(b['close'].iloc[-1] / b['close'].iloc[0])) * 1e4,
        'flow share autocorrelation, 1 h': ac(flow, 1),
        'daily volatility of volatility': float(np.log(r.groupby(r.index.floor('1D')).std()).std()),
    }


if __name__ == '__main__':
    with multiprocessing.get_context('spawn').Pool(SEEDS) as pool:
        replicas = pool.map(synthetic, range(SEEDS))

    real = bars('BTCUSDT', '2021-01-01', '2026-10-01', '1h').rename(columns={'buy': 'buy'})
    windows = [real.iloc[i:i + DAYS * 24] for i in range(0, len(real) - DAYS * 24, DAYS * 24)]
    real_stats = pd.DataFrame([statistics(w) for w in windows])
    syn_stats = pd.DataFrame([statistics(r) for r in replicas])

    print(f'{len(windows)} real BTC windows of {DAYS} days (2021-2026) against {SEEDS} synthetic replicas of {DAYS} days:')
    print(f'{"":<34}{"real 5%":>10}{"median":>10}{"95%":>10}   {"synthetic 5%":>13}{"median":>10}{"95%":>10}')

    for name in real_stats.columns:
        q = real_stats[name].quantile([0.05, 0.5, 0.95]).to_numpy()
        p = syn_stats[name].quantile([0.05, 0.5, 0.95]).to_numpy()
        print(f'{name:<34}' + ''.join(f'{v:>10.3g}' for v in q) + '   ' + f'{p[0]:>13.3g}' + ''.join(f'{v:>10.3g}' for v in p[1:]))
