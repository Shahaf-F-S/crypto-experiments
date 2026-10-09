# research_validation.py

import multiprocessing
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from lab.scripts.fetch_wide import WANTED
from lab.scripts.research_rotation import formulas, series
from miner import fitness
from miner.panel import UNIVERSE, Panel
from miner.simulate import by_day
from miner.stats import sharpe


# Does agreement across assets predict which formulas keep working? 3000 random formulas (no data involved), each
# simulated on all 78 pairs since 2022 (time-series positions, daily rebalancing, futures costs, funding). The pairs
# are split at random in two halves (20 splits); formulas are chosen on 2022-04 to 2024 by their Sharpe ratio on one
# half, on the worse of the two halves, or on all pairs; the chosen are followed on all pairs in 2024 to 2026-10.
# Run from the root, after fetch_wide: python -m lab.scripts.research_validation

POOL = 3000
CACHE = Path('lab/results/pool_wide.npz')
WORK = Path('data/miner/wide')
FIRST, SPLIT, LAST = '2022-04-01', '2024-01-01', '2026-10-01'
CHOSEN = 20


def build() -> dict:
    symbols = tuple(UNIVERSE) + tuple(f'{w}USDT' for w in WANTED)
    panel = Panel.load(symbols, '2022-01-01', None)
    panel = panel.columns(tuple(s for k, s in enumerate(panel.symbols) if np.isfinite(panel.close[:, k]).any()))
    panel = Panel(panel.symbols, panel.times, panel.close, panel.volume, panel.buy, panel.funding,
                  np.array([1e-4 if s in ('BTCUSDT', 'ETHUSDT') else 3e-4 for s in panel.symbols]))
    panel.save(WORK)
    pool = formulas(POOL, seed=23)
    days, _ = by_day(np.zeros((len(panel), 1)), panel.times)
    began = time.time()

    with multiprocessing.get_context('spawn').Pool(max(multiprocessing.cpu_count() - 2, 1), initializer=fitness.start_worker,
                                                   initargs=(str(WORK),)) as workers:
        results = [r for batch in workers.map(series, [pool[k:k + 10] for k in range(0, len(pool), 10)], chunksize=1) for r in batch]

    print(f'{len(pool)} formulas on {len(panel.symbols)} pairs in {time.time() - began:.0f}s', flush=True)
    np.savez(CACHE, formulas=np.array(pool), days=days, per_pair=np.stack([r[0] for r in results]).astype(np.float16),
             symbols=np.array(panel.symbols))
    return dict(np.load(CACHE))


def sharpes(per_pair: np.ndarray, pairs: np.ndarray, rows: np.ndarray) -> np.ndarray:
    """Each formula's Sharpe ratio, equal weight over `pairs`, on day `rows`."""
    x = per_pair[:, rows][:, :, pairs].astype(np.float32)
    counts = np.isfinite(x).sum(axis=2)
    daily = np.where(counts > 0, np.nansum(x, axis=2) / np.maximum(counts, 1), np.nan)
    mean, sd = np.nanmean(daily, axis=1), np.nanstd(daily, axis=1)
    return np.where(sd > 0, mean / np.where(sd > 0, sd, 1.0) * np.sqrt(365), np.nan)


def portfolio(per_pair: np.ndarray, chosen: np.ndarray, rows: np.ndarray) -> np.ndarray:
    x = per_pair[chosen][:, rows].astype(np.float32)
    counts = np.isfinite(x).sum(axis=2)
    daily = np.where(counts > 0, np.nansum(x, axis=2) / np.maximum(counts, 1), np.nan)
    return np.nanmean(daily, axis=0)


if __name__ == '__main__':
    data = dict(np.load(CACHE)) if CACHE.exists() and 'rebuild' not in sys.argv else build()
    per_pair, days = data['per_pair'], data['days']
    before = np.flatnonzero((days >= pd.Timestamp(FIRST).timestamp() // 86400) & (days < pd.Timestamp(SPLIT).timestamp() // 86400))
    after = np.flatnonzero((days >= pd.Timestamp(SPLIT).timestamp() // 86400) & (days < pd.Timestamp(LAST).timestamp() // 86400))
    pairs = per_pair.shape[2]
    every = np.arange(pairs)
    pooled_before, pooled_after = sharpes(per_pair, every, before), sharpes(per_pair, every, after)
    ok = np.isfinite(pooled_before) & np.isfinite(pooled_after)
    print(f'{per_pair.shape[0]} formulas, {pairs} pairs; correlation of the 2022-23 and 2024-26 Sharpe ratios across formulas: '
          f'{np.corrcoef(pooled_before[ok], pooled_after[ok])[0, 1]:.2f}\n')
    rng = np.random.default_rng(0)
    rules = {'one half': [], 'both halves (worse of two)': [], 'all pairs': [], 'random': []}

    for split in range(20):
        order = rng.permutation(pairs)
        a, b = order[:pairs // 2], order[pairs // 2:]
        on_a, on_b = sharpes(per_pair, a, before), sharpes(per_pair, b, before)
        picks = {
            'one half': np.argsort(-np.nan_to_num(on_a, nan=-9))[:CHOSEN],
            'both halves (worse of two)': np.argsort(-np.nan_to_num(np.minimum(on_a, on_b), nan=-9))[:CHOSEN],
            'all pairs': np.argsort(-np.nan_to_num(pooled_before, nan=-9))[:CHOSEN],
            'random': rng.choice(per_pair.shape[0], CHOSEN, replace=False),
        }

        for rule, chosen in picks.items():
            rules[rule].append((sharpe(portfolio(per_pair, chosen, before)), sharpe(portfolio(per_pair, chosen, after))))

    print(f'{CHOSEN} formulas chosen on 2022-04 to 2024, followed on all pairs 2024 to 2026-10 (mean over 20 splits of the pairs)')
    print(f'{"rule":30s} {"chosen on":>9} {"after":>7}')

    for rule, values in rules.items():
        v = np.array(values)
        print(f'{rule:30s} {np.nanmean(v[:, 0]):9.2f} {np.nanmean(v[:, 1]):7.2f}')
