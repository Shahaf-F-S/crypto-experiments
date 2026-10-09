# research_framework.py

import asyncio
import multiprocessing
import sys

import pandas as pd

from system.trend import SLIPPAGE_BPS, build
from pipeline.collaborator import Collaborator
from pipeline.runner import run
from system.bars import segments, stream
from system.history import load
from lab.research.stats import summary

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
UNSEEN = ['DOGEUSDT', 'ADAUSDT', 'LTCUSDT', 'LINKUSDT', 'AVAXUSDT', 'DOTUSDT', 'TRXUSDT', 'BCHUSDT']   # never used in design
FRESH = ['ATOMUSDT', 'NEARUSDT', 'FILUSDT', 'ETCUSDT', 'UNIUSDT', 'AAVEUSDT', 'XLMUSDT', 'ALGOUSDT']   # final validation only
PERIODS = {'discovery': ('2021-01-01', '2024-01-01'), 'holdout': ('2024-01-01', '2026-10-08'), 'full': ('2021-01-01', '2026-10-08')}
WARMUP = pd.Timedelta(days=60)


def one(symbol: str, start: str, end: str, collaborate: bool) -> dict[str, pd.Series]:
    """Daily returns of every combination (and the collaborator) on one pair, run through the framework."""
    frame = load(symbol, (pd.Timestamp(start) - WARMUP).strftime('%Y-%m-%d'), end, interval='1h')
    combinations = build(symbol)
    collaborator = Collaborator(combinations, warmup=14 * 86400.0, select=False) if collaborate else None
    sources = [stream(piece, symbol, slippage_bps=SLIPPAGE_BPS.get(symbol, 2.0), bar=pd.Timedelta(hours=1).to_pytimedelta())
               for piece in segments(frame, gap=pd.Timedelta(hours=3).to_pytimedelta())]
    result = asyncio.run(run(sources, combinations, sample_every=3600.0, collaborator=collaborator, keep_equity=True))
    out = {}

    for name, (times, values) in result['equity'].items():
        equity = pd.Series(values, index=pd.to_datetime(times, unit='s', utc=True))
        equity = equity[equity.index >= pd.Timestamp(start, tz='UTC')].resample('1D').last().ffill()
        out[name] = equity.pct_change().dropna()

    return out


if __name__ == '__main__':
    period = sys.argv[1] if len(sys.argv) > 1 else 'discovery'
    collaborate = 'collaborate' in sys.argv
    symbols = UNSEEN if 'unseen' in sys.argv else FRESH if 'fresh' in sys.argv else SYMBOLS
    start, end = PERIODS[period]

    with multiprocessing.get_context('spawn').Pool(len(symbols)) as pool:
        results = dict(zip(symbols, pool.starmap(one, [(s, start, end, collaborate) for s in symbols])))

    print(f'{period} {start} to {end}, through the framework (hourly bar events), equal weight over {len(symbols)} pairs:')

    for name in results[symbols[0]]:
        portfolio = pd.concat([results[s][name] for s in symbols], axis=1).fillna(0.0).mean(axis=1)
        s = summary(portfolio)
        by_pair = ', '.join(f'{p[:4]} {summary(results[p][name])["sharpe"]:.2f}' for p in symbols)
        by_year = ', '.join(f'{y} {summary(portfolio[portfolio.index.year == y])["sharpe"]:.2f}' for y in sorted(set(portfolio.index.year)))
        print(f'\n{name}: sharpe {s["sharpe"]:.2f}, return {s["annual return"]:.1%}/y, vol {s["annual volatility"]:.1%}, '
              f'max drawdown {s["max drawdown"]:.1%}, positive months {s["positive months"]:.0%}')
        print(f'  by pair: {by_pair}   by year: {by_year}')
