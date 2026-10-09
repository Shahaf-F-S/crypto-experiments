# research_rotation.py

import math
import multiprocessing
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from miner import fitness
from miner.formula import parse, score
from miner.panel import Panel
from miner.search import admissible, grow, simplify
from miner.simulate import by_day, screen
from miner.stats import sharpe


# Alpha persistence: do formulas that earned recently keep earning for a while ("factor momentum", Gupta and Kelly
# 2019; Arnott, Clements, Kalesnik and Linnainmaa 2021), and for how long? A pool of formulas drawn at random from
# the grammar (no data involved), each simulated at futures costs on the 21 pairs; each week, the K best of the last
# L days are held for the next week. Everything a week's choice reads is before that week.
# Run from the root: python -m lab.scripts.research_rotation

POOL = 4000
CACHE = Path('lab/results/pool.npz')
WORK = Path('data/miner/rotation')
DISCOVERY, HOLDOUT = ('2021-06-01', '2024-01-01'), ('2024-01-01', '2026-10-01')
LOOKBACKS = (7, 14, 30, 60, 90, 180, 365)
SIZES = (5, 20, 100)


def formulas(count: int, seed: int = 7) -> list[str]:
    rng, out = random.Random(seed), {}

    while len(out) < count:
        node = simplify(grow(rng, rng.randint(1, 3)))

        if admissible(node):
            out[str(node)] = None

    return list(out)


def series(batch: list[str]) -> list[tuple[np.ndarray, float, float]]:
    """In a worker: each formula's daily P&L per pair over the whole panel (real returns, net of costs and funding),
    its mean absolute position and daily turnover."""
    panel = fitness._panel
    out = []

    for f in batch:
        s = score(parse(f), panel.fields)
        pnl, held = screen(s, panel.close, panel.funding, panel.slippage, panel.times, 0, neutral=False)
        _, per_pair = by_day(pnl, panel.times)
        live = np.isfinite(panel.close)
        out.append((per_pair.astype(np.float32), float(np.abs(held[live]).mean()), float(np.nanmean(np.abs(np.diff(held, axis=0))) * 24)))

    return out


def build() -> dict:
    panel = Panel.load()
    panel.save(WORK)
    pool = formulas(POOL)
    days, _ = by_day(np.zeros((len(panel), 1)), panel.times)
    batches = [pool[k:k + 20] for k in range(0, len(pool), 20)]
    began = time.time()

    with multiprocessing.get_context('spawn').Pool(max(multiprocessing.cpu_count() - 2, 1), initializer=fitness.start_worker,
                                                   initargs=(str(WORK),)) as workers:
        results = [r for batch in workers.map(series, batches, chunksize=1) for r in batch]

    print(f'{len(pool)} formulas simulated in {time.time() - began:.0f}s', flush=True)
    per_pair = np.stack([r[0] for r in results], axis=0).astype(np.float16)         # formulas x days x pairs
    exposure = np.array([r[1] for r in results])
    turnover = np.array([r[2] for r in results])
    np.savez(CACHE, formulas=np.array(pool), days=days, per_pair=per_pair, exposure=exposure, turnover=turnover,
             symbols=np.array(panel.symbols))
    return dict(np.load(CACHE))


def daily_of(per_pair: np.ndarray) -> np.ndarray:
    """Equal weight over the pairs trading each day: formulas x days."""
    x = per_pair.astype(np.float32)
    counts = np.isfinite(x).sum(axis=2)
    return np.where(counts > 0, np.nansum(x, axis=2) / np.maximum(counts, 1), np.nan)


def rolling_sharpe(daily: np.ndarray, end: int, lookback: int) -> np.ndarray:
    window = daily[:, max(end - lookback, 0):end]
    mean, sd = np.nanmean(window, axis=1), np.nanstd(window, axis=1)
    return np.where(sd > 0, mean / np.where(sd > 0, sd, 1.0), -np.inf)


def rotate(daily: np.ndarray, days: np.ndarray, lookback: int, size: int, first: int, hold: int = 7) -> np.ndarray:
    """The daily return of holding, each `hold` days, the `size` formulas with the best Sharpe ratio over the last
    `lookback` days (equal weight); zero before `first`."""
    out = np.zeros(daily.shape[1])

    for t in range(first, daily.shape[1], hold):
        rank = rolling_sharpe(daily, t, lookback)
        chosen = np.argsort(-rank)[:size]
        out[t:t + hold] = np.nan_to_num(np.nanmean(daily[chosen, t:t + hold], axis=0))

    return out


def rotate_pairs(per_pair: np.ndarray, lookback: int, size: int, first: int, hold: int = 7) -> np.ndarray:
    """As `rotate`, but each pair holds its own `size` best formulas (by their record on that pair); equal weight over
    the pairs."""
    formulas, days, pairs = per_pair.shape
    out = np.zeros(days)

    for t in range(first, days, hold):
        window = per_pair[:, max(t - lookback, 0):t, :].astype(np.float32)
        mean, sd = np.nanmean(window, axis=1), np.nanstd(window, axis=1)
        rank = np.where(sd > 0, mean / np.where(sd > 0, sd, 1.0), -np.inf)               # formulas x pairs
        chosen = np.argsort(-rank, axis=0)[:size]                                          # size x pairs
        ahead = per_pair[:, t:t + hold, :].astype(np.float32)
        picked = np.stack([ahead[chosen[:, k], :, k] for k in range(pairs)], axis=2)      # size x hold x pairs
        out[t:t + hold] = np.nan_to_num(np.nanmean(np.nanmean(picked, axis=0), axis=1))

    return out


def hedge(daily: np.ndarray, halflife: float, rate: float, first: int, hold: int = 7) -> np.ndarray:
    """Exponential weights over the formulas on their discounted record (discounted mean over discounted deviation,
    a Sharpe-like t-statistic, x `rate`), re-weighted every `hold` days."""
    factor = 0.5 ** (1.0 / halflife)
    x = np.nan_to_num(daily)
    out = np.zeros(daily.shape[1])
    s1, s2, w = np.zeros(daily.shape[0]), np.zeros(daily.shape[0]), 0.0
    weights = np.full(daily.shape[0], 1.0 / daily.shape[0])

    for t in range(daily.shape[1]):
        if t >= first and (t - first) % hold == 0 and w > 0:
            z = s1 / np.sqrt(np.maximum(s2 * w - s1 * s1, 1e-18)) * np.sqrt(w)
            logits = rate * z
            weights = np.exp(logits - logits.max())
            weights /= weights.sum()

        if t >= first:
            out[t] = float(weights @ x[:, t])

        s1, s2, w = factor * s1 + x[:, t], factor * s2 + x[:, t] ** 2, factor * w + 1.0

    return out


def decay(daily: np.ndarray, lookback: int, size: int, first: int, weeks: int = 26) -> tuple[np.ndarray, np.ndarray]:
    """For formulas chosen as in `rotate`: their mean daily return in each week after the choice, and the pool's, over
    every weekly choice from `first` on (annualized, in %)."""
    chosen_returns, pool_returns = [[] for _ in range(weeks)], [[] for _ in range(weeks)]

    for t in range(first, daily.shape[1] - 7 * weeks, 7):
        chosen = np.argsort(-rolling_sharpe(daily, t, lookback))[:size]

        for h in range(weeks):
            span = slice(t + 7 * h, t + 7 * h + 7)
            chosen_returns[h].append(np.nanmean(daily[chosen, span]))
            pool_returns[h].append(np.nanmean(daily[:, span]))

    return np.array([np.mean(r) for r in chosen_returns]) * 36500, np.array([np.mean(r) for r in pool_returns]) * 36500


def period(days: np.ndarray, values: np.ndarray, start: str, end: str) -> np.ndarray:
    d0, d1 = int(pd.Timestamp(start).timestamp() // 86400), int(pd.Timestamp(end).timestamp() // 86400)
    return values[(days >= d0) & (days < d1)]


if __name__ == '__main__':
    data = dict(np.load(CACHE)) if CACHE.exists() and 'rebuild' not in sys.argv else build()
    days, daily = data['days'], daily_of(data['per_pair'])
    first = int(np.searchsorted(days, pd.Timestamp(DISCOVERY[0]).timestamp() // 86400))
    pool_mean = np.nan_to_num(np.nanmean(daily, axis=0))

    print(f'\npool: {daily.shape[0]} random formulas; the pool itself (equal weight): '
          f'discovery {sharpe(period(days, pool_mean, *DISCOVERY)):.2f}, holdout {sharpe(period(days, pool_mean, *HOLDOUT)):.2f}')
    print(f'single formulas, discovery Sharpe ratio quantiles (5/50/95%): '
          f'{np.round(np.nanpercentile([sharpe(period(days, d, *DISCOVERY)) for d in daily], [5, 50, 95]), 2)}\n')
    print(f'{"lookback":>8} {"size":>5}   {"discovery":>9} {"holdout":>8}   by year')

    for lookback in LOOKBACKS:
        for size in SIZES:
            r = rotate(daily, days, lookback, size, first)
            years = pd.to_datetime(days * 86400, unit='s').year
            by_year = '  '.join(f'{y} {sharpe(r[(years == y) & (days >= days[first])]):5.2f}' for y in sorted(set(years)) if y >= 2021)
            print(f'{lookback:>8} {size:>5}   {sharpe(period(days, r, *DISCOVERY)):9.2f} {sharpe(period(days, r, *HOLDOUT)):8.2f}   {by_year}')

    print('\nper pair (each pair its own best formulas):')

    for lookback in (30, 90, 180):
        for size in (5, 20):
            r = rotate_pairs(data['per_pair'], lookback, size, first)
            print(f'{lookback:>8} {size:>5}   {sharpe(period(days, r, *DISCOVERY)):9.2f} {sharpe(period(days, r, *HOLDOUT)):8.2f}', flush=True)

    print('\nexponential weights (half-life in days, rate):')

    for halflife in (30, 90, 180):
        for rate in (2.0, 5.0):
            r = hedge(daily, halflife, rate, first)
            print(f'{halflife:>8} {rate:>5}   {sharpe(period(days, r, *DISCOVERY)):9.2f} {sharpe(period(days, r, *HOLDOUT)):8.2f}', flush=True)

    print('\npersistence: mean return (%/y) of the 20 best of the last 60 days, week by week after the choice, against the pool')
    chosen, pool = decay(daily, 60, 20, first)
    print('  week   ' + ' '.join(f'{h + 1:>5}' for h in range(len(chosen))))
    print('  chosen ' + ' '.join(f'{v:5.1f}' for v in chosen))
    print('  pool   ' + ' '.join(f'{v:5.1f}' for v in pool))
