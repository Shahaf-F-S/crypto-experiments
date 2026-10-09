# research_breadth.py

import time
from pathlib import Path

import numpy as np
import pandas as pd

from lab.scripts.research_miner import trend_score
from lab.scripts.research_validation import CACHE
from miner.breadth import WIDE, Breadth, Plan
from miner.fitness import Market, track_score
from miner.panel import Panel
from miner.simulate import by_day
from miner.stats import sharpe


# The breadth miner (version 2) as if live since 2024: its pool is the 3000 random formulas of research_validation
# (drawn from the grammar, no data involved; their records are only read up to each decision), a review on the
# first day of each month (crowd refresh, selected sleeve chosen again). Writes data/miner/breadth, the record the
# live miner starts from and the dashboard shows. Run from the root: python -m lab.scripts.research_breadth

FOLDER = Path('data/miner/breadth')
START, END = '2024-01-01', '2026-10-01'


if __name__ == '__main__':
    panel = Panel.load(WIDE, '2022-01-01', None)
    data = dict(np.load(CACHE))
    x = data['per_pair'].astype(np.float32)
    counts = np.isfinite(x).sum(axis=2)
    daily = np.where(counts > 0, np.nansum(x, axis=2) / np.maximum(counts, 1), np.nan).astype(np.float32)
    days, _ = by_day(np.zeros((len(panel), 1)), panel.times)
    grown = np.full((daily.shape[0], len(days)), np.nan, dtype=np.float32)
    grown[:, np.searchsorted(days, data['days'])] = daily
    began = time.time()

    with Breadth(panel, Plan(), FOLDER, pool=[str(f) for f in data['formulas']]) as miner:
        miner.daily, miner.days = grown, days
        miner.extend()

        for month in pd.date_range(START, END, freq='MS', tz='UTC', inclusive='left'):
            miner.step(month.timestamp(), search=False, review=True)

        miner.save()
        performance = miner.performance()
        d = np.array(performance['days'])
        sleeves = {'crowd': np.array(performance['crowd']), 'selected': np.array(performance['selected']),
                   'F2': np.nan_to_num(track_score(trend_score(panel.close), True, panel).daily(Market.of(panel), int(d[0]), int(d[-1]) + 1, False))}
        sleeves['all three, equal capital'] = np.mean(list(sleeves.values()), axis=0)
        years = pd.to_datetime(d * 86400, unit='s').year
        print(f'breadth miner, {len(panel.symbols)} pairs, {START} to {END} ({time.time() - began:.0f}s)\n')

        for name, r in sleeves.items():
            print(f'{name:26s} sharpe {sharpe(r):5.2f}  return {r.mean() * 365:6.1%}  vol {r.std() * np.sqrt(365):5.1%}   '
                  + ' '.join(f'{y} {sharpe(r[years == y]):5.2f}' for y in sorted(set(years))))
