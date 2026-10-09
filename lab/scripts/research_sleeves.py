# research_sleeves.py

import multiprocessing
from pathlib import Path

import numpy as np
import pandas as pd

from lab.scripts.fetch_wide import WANTED
from lab.scripts.research_learner import formulas
from lab.scripts.research_miner import trend_score
from lab.scripts.research_reselect import reselect
from lab.scripts.research_validation import CACHE
from miner import fitness
from miner.fitness import Market, track_score
from miner.formula import parse, score
from miner.panel import UNIVERSE, Panel
from miner.stats import sharpe


# The three sleeves on the 78 pairs, each traded on equal capital: F2 (trend), the crowd (the mean score of 800 random
# formulas, seed 11, no selection), the selected (every month, the 20 formulas of the 3000-formula pool with the best
# Sharpe ratio over the last 730 days). Settings fixed before this run. Run from the root:
# python -m lab.scripts.research_sleeves

WORK = Path('data/miner/ensemble')
CROWD = 800


def crowd_sum(batch: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """In a worker: the sum of the batch's scores and how many were defined, per row and pair."""
    panel = fitness._panel
    total, count = np.zeros(panel.close.shape), np.zeros(panel.close.shape)

    for f in batch:
        s = score(parse(f), panel.fields)
        total += np.nan_to_num(s)
        count += np.isfinite(s)

    return total, count


if __name__ == '__main__':
    symbols = tuple(UNIVERSE) + tuple(f'{w}USDT' for w in WANTED)
    panel = Panel.load(symbols, '2022-01-01', None)
    panel = panel.columns(tuple(s for k, s in enumerate(panel.symbols) if np.isfinite(panel.close[:, k]).any()))
    panel = Panel(panel.symbols, panel.times, panel.close, panel.volume, panel.buy, panel.funding,
                  np.array([1e-4 if s in ('BTCUSDT', 'ETHUSDT') else 3e-4 for s in panel.symbols]))
    panel.save(WORK)
    pool = formulas(CROWD, seed=11)

    with multiprocessing.get_context('spawn').Pool(max(multiprocessing.cpu_count() - 2, 1), initializer=fitness.start_worker,
                                                   initargs=(str(WORK),)) as workers:
        parts = workers.map(crowd_sum, [pool[k:k + 20] for k in range(0, len(pool), 20)])

    total, count = sum(p[0] for p in parts), sum(p[1] for p in parts)
    crowd = np.where(count > 0.9 * CROWD, total / np.maximum(count, 1), np.nan)
    market = Market.of(panel)
    data = dict(np.load(CACHE))
    x = data['per_pair'].astype(np.float32)
    counts = np.isfinite(x).sum(axis=2)
    pool_daily = np.where(counts > 0, np.nansum(x, axis=2) / np.maximum(counts, 1), np.nan)
    selected_days, selected = reselect(pool_daily, data['days'], 730, 20, False)
    d0, d1 = int(selected_days[0]), int(selected_days[-1]) + 1
    sleeves = {
        'F2 trend': track_score(trend_score(panel.close), True, panel).daily(market, d0, d1, False),
        'crowd (800 random)': track_score(crowd, False, panel).daily(market, d0, d1, False),
        'selected (730 d, 20)': selected[np.searchsorted(selected_days, np.arange(d0, d1)).clip(0, len(selected) - 1)],
    }
    sleeves = {k: np.nan_to_num(v) for k, v in sleeves.items()}
    sleeves['all three, equal capital'] = np.mean(list(sleeves.values()), axis=0)
    sleeves['F2 and crowd'] = 0.5 * (sleeves['F2 trend'] + sleeves['crowd (800 random)'])
    years = pd.to_datetime(np.arange(d0, d1) * 86400, unit='s').year
    print(f'78 pairs, {pd.Timestamp(d0 * 86400, unit="s").date()} to {pd.Timestamp(d1 * 86400, unit="s").date()}, futures costs and funding\n')

    for name, r in sleeves.items():
        equity = np.cumprod(1.0 + r)
        drawdown = (equity / np.maximum.accumulate(equity) - 1.0).min()
        print(f'{name:26s} sharpe {sharpe(r):5.2f}  return {r.mean() * 365:6.1%}  vol {r.std() * np.sqrt(365):5.1%}  max dd {drawdown:6.1%}   '
              + ' '.join(f'{y} {sharpe(r[years == y]):5.2f}' for y in sorted(set(years))))

    names = list(sleeves)[:3]
    print('\ncorrelations: ' + ', '.join(f'{a} / {b} {np.corrcoef(sleeves[a], sleeves[b])[0, 1]:.2f}' for i, a in enumerate(names) for b in names[i + 1:]))
