# research_plateau.py

import asyncio
import itertools
import multiprocessing

import pandas as pd

from system.trend import FUTURES, SLIPPAGE_BPS, funding_of
from pipeline.combination import Combination
from pipeline.generators import TimeReturn, TimeVolatility
from pipeline.indicators import TrendScore
from pipeline.management import Target
from pipeline.runner import run
from pipeline.strategy import Follow
from system.bars import segments, stream
from system.history import load
from lab.research.stats import summary

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
DISCOVERY = ('2021-01-01', '2024-01-01')
DAY = 86400.0
GRID = list(itertools.product((0.25, 0.5, 0.75), (0.25, 0.5, 0.75)))     # pullback, force


def one(symbol: str) -> dict[tuple[float, float], pd.Series]:
    frame = load(symbol, (pd.Timestamp(DISCOVERY[0]) - pd.Timedelta(days=60)).strftime('%Y-%m-%d'), DISCOVERY[1], interval='1h')
    funding = funding_of(symbol)
    combinations = []

    for pullback, force in GRID:
        vol = TimeVolatility('mid', window=30 * DAY, resolution=3600.0)
        strategy = Follow(indicators=[TrendScore(returns=[TimeReturn('mid', window=d * DAY, resolution=3600.0) for d in (7, 14, 28)],
                                                 vol=TimeVolatility('mid', window=30 * DAY, resolution=3600.0))])
        manager = Target(strategy=strategy, fee=FUTURES, vol=vol, funding=funding, timing=TimeReturn('mid', window=DAY, resolution=3600.0),
                         pullback=pullback, force=force)
        combinations.append(Combination(name=f'{pullback}/{force}', manager=manager))

    sources = [stream(piece, symbol, slippage_bps=SLIPPAGE_BPS.get(symbol, 2.0), bar=pd.Timedelta(hours=1).to_pytimedelta())
               for piece in segments(frame, gap=pd.Timedelta(hours=3).to_pytimedelta())]
    result = asyncio.run(run(sources, combinations, sample_every=3600.0, keep_equity=True))
    out = {}

    for (pullback, force), c in zip(GRID, combinations):
        times, values = result['equity'][c.name]
        e = pd.Series(values, index=pd.to_datetime(times, unit='s', utc=True))
        out[(pullback, force)] = e[e.index >= pd.Timestamp(DISCOVERY[0], tz='UTC')].resample('1D').last().ffill().pct_change().dropna()

    return out


if __name__ == '__main__':
    with multiprocessing.get_context('spawn').Pool(len(SYMBOLS)) as pool:
        results = pool.map(one, SYMBOLS)

    print('F2 timing parameters on discovery (Sharpe of the 5-pair portfolio); rows pullback, columns force:')
    print(f'{"":>10}' + ''.join(f'{f:>8}' for f in (0.25, 0.5, 0.75)))

    for pullback in (0.25, 0.5, 0.75):
        row = []

        for force in (0.25, 0.5, 0.75):
            portfolio = pd.concat([r[(pullback, force)] for r in results], axis=1).fillna(0.0).mean(axis=1)
            row.append(summary(portfolio)['sharpe'])

        print(f'{pullback:>10}' + ''.join(f'{v:>8.2f}' for v in row))
