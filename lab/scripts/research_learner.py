# research_learner.py

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
from miner.simulate import TAKER, daily_volatility
from miner.stats import sharpe


# An online learner over many alphas: each day, each pair's next-day return (in units of its volatility) is predicted
# from the scores of FEATURES formulas drawn at random from the grammar (no data involved) by a ridge regression
# whose memory fades with a half-life (alphas that stop working lose their weight, new ones gain it). The position is
# the prediction, volatility-targeted and capped, held for the day at futures costs. Everything a day's prediction
# reads is before that day. Run from the root: python -m lab.scripts.research_learner

FEATURES = 200
WORK = Path('data/miner/rotation')
CACHE = Path('lab/results/learner_scores.npz')
DISCOVERY, HOLDOUT = ('2021-06-01', '2024-01-01'), ('2024-01-01', '2026-10-01')
HALFLIVES = (30, 90, 180, 365)
RIDGES = (1.0, 10.0, 100.0)


def formulas(count: int, seed: int = 11) -> list[str]:
    rng, out = random.Random(seed), {}

    while len(out) < count:
        node = simplify(grow(rng, rng.randint(1, 3)))

        if admissible(node):
            out[str(node)] = None

    return list(out)


def daily_scores(batch: list[str]) -> list[np.ndarray]:
    """In a worker: each formula's score at the first bar close of every UTC day (days x pairs)."""
    panel = fitness._panel
    rows = np.flatnonzero(((panel.times + 3600) % 86400) == 0)
    return [score(parse(f), panel.fields)[rows].astype(np.float32) for f in batch]


def build() -> dict:
    panel = Panel.load()
    panel.save(WORK)
    pool = formulas(FEATURES)

    with multiprocessing.get_context('spawn').Pool(max(multiprocessing.cpu_count() - 2, 1), initializer=fitness.start_worker,
                                                   initargs=(str(WORK),)) as workers:
        scores = [s for batch in workers.map(daily_scores, [pool[k:k + 5] for k in range(0, len(pool), 5)]) for s in batch]

    rows = np.flatnonzero(((panel.times + 3600) % 86400) == 0)
    close = panel.close[rows]
    volatility = daily_volatility(panel.close)[rows]
    funding = np.add.reduceat(np.nan_to_num(panel.funding), np.r_[0, rows[:-1] + 1], axis=0)[1:]
    funding = np.vstack([funding, np.zeros((1, funding.shape[1]))])          # funding paid over the day after each row
    np.savez(CACHE, formulas=np.array(pool), scores=np.stack(scores), close=close, volatility=volatility,
             funding=funding, slippage=panel.slippage, days=(panel.times[rows] + 3600) // 86400)
    return dict(np.load(CACHE))


def learn(x: np.ndarray, y: np.ndarray, halflife: float, ridge: float, first: int) -> np.ndarray:
    """Predictions for each day from `first` on (days x pairs), from a ridge regression of y on x over the days before,
    weighted by a memory with this half-life (pairs pooled)."""
    days, pairs, k = x.shape
    decay = 0.5 ** (1.0 / halflife)
    a, b = np.zeros((k, k)), np.zeros(k)
    out = np.full((days, pairs), np.nan)

    for d in range(days):
        if d >= first:
            beta = np.linalg.solve(a + ridge * np.eye(k), b)
            out[d] = np.nan_to_num(x[d]) @ beta

        ok = np.isfinite(y[d]) & np.isfinite(x[d]).all(axis=1)

        if ok.any():
            a = decay * a + x[d][ok].T @ x[d][ok]
            b = decay * b + x[d][ok].T @ y[d][ok]
        else:
            a, b = decay * a, decay * b

    return out


def trade(signal: np.ndarray, data: dict, scale: float) -> np.ndarray:
    """Daily P&L (equal weight over pairs) of holding, from each day's first close to the next, the position
    clip(signal / scale) x 2% / daily volatility (at most 1), paying taker fees and slippage on changes and funding."""
    close, vol = data['close'], data['volatility']
    position = np.clip(np.nan_to_num(signal / scale), -1.0, 1.0) * np.where(vol > 0, 0.02 / np.where(vol > 0, vol, 1.0), 0.0)
    position = np.clip(position, -1.0, 1.0)
    ret = np.vstack([close[1:] / close[:-1] - 1.0, np.full((1, close.shape[1]), np.nan)])
    change = np.abs(np.diff(np.vstack([np.zeros((1, position.shape[1])), position]), axis=0))
    pnl = position * np.nan_to_num(ret) - position * data['funding'] - change * (TAKER + data['slippage'])
    pnl[np.isnan(ret) | np.isnan(close)] = np.nan
    counts = np.isfinite(pnl).sum(axis=1)
    return np.where(counts > 0, np.nansum(pnl, axis=1) / np.maximum(counts, 1), 0.0)


def period(days: np.ndarray, values: np.ndarray, span: tuple[str, str]) -> np.ndarray:
    d0, d1 = (int(pd.Timestamp(s).timestamp() // 86400) for s in span)
    return values[(days >= d0) & (days < d1)]


if __name__ == '__main__':
    data = dict(np.load(CACHE)) if CACHE.exists() and 'rebuild' not in sys.argv else build()
    days = data['days']
    x = np.transpose(data['scores'], (1, 2, 0)).astype(np.float64)                    # days x pairs x formulas
    close, vol = data['close'], data['volatility']
    y = np.vstack([np.log(close[1:] / close[:-1]), np.full((1, close.shape[1]), np.nan)]) / np.where(vol > 0, vol, np.nan)
    first = int(np.searchsorted(days, pd.Timestamp(DISCOVERY[0]).timestamp() // 86400))
    began = time.time()

    print(f'{FEATURES} random formulas as features; daily decisions, futures costs and funding\n')
    print(f'{"":26s} {"discovery":>9} {"holdout":>8}')
    plain = np.nanmean(x, axis=2)
    plain[:first] = np.nan
    print(f'{"mean of the scores":26s} {sharpe(period(days, trade(plain, data, 0.25), DISCOVERY)):9.2f} '
          f'{sharpe(period(days, trade(plain, data, 0.25), HOLDOUT)):8.2f}')

    for halflife in HALFLIVES:
        for ridge in RIDGES:
            prediction = learn(x, y, halflife, ridge, first)
            scale = np.nanstd(prediction[first:first + 365]) if np.isfinite(prediction[first:first + 365]).any() else 1.0
            pnl = trade(prediction, data, 2.0 * scale)
            print(f'{f"half-life {halflife}d, ridge {ridge:g}":26s} {sharpe(period(days, pnl, DISCOVERY)):9.2f} '
                  f'{sharpe(period(days, pnl, HOLDOUT)):8.2f}', flush=True)

    print(f'\n({time.time() - began:.0f}s)')
