# research_sleeves_exact.py

import multiprocessing
from pathlib import Path

import numpy as np
import pandas as pd

from lab.scripts.fetch_wide import WANTED
from lab.scripts.research_learner import formulas
from lab.scripts.research_miner import trend_score
from lab.scripts.research_sleeves import crowd_sum
from lab.scripts.research_validation import CACHE
from miner import fitness
from miner.components import NORMALIZED, normalized
from miner.fitness import Market, schedule_score, track_score
from miner.panel import UNIVERSE, Panel
from miner.stats import sharpe


# The three sleeves exactly as the trading system runs them (miner.components.following: a normalized blend, daily
# Target, futures costs, funding), walk-forward on the 78 pairs: the crowd (400 or 800 random formulas, seed 11, no
# selection), the selected (every month the 20 formulas of the 3000-formula pool with the best Sharpe ratio over the
# last 730 days, from the pool's daily record before that month), and F2. Equal capital.
# Run from the root, after research_validation: python -m lab.scripts.research_sleeves_exact

WORK = Path('data/miner/ensemble')


def monthly_plan(daily: np.ndarray, days: np.ndarray, names: np.ndarray, window: int = 730, size: int = 20) -> list:
    months = pd.to_datetime(days * 86400, unit='s').to_period('M')
    starts = np.flatnonzero(np.r_[True, months[1:] != months[:-1]])
    plan = []

    for t in starts:
        if t < window:
            continue

        past = daily[:, t - window:t]
        mean, sd = np.nanmean(past, axis=1), np.nanstd(past, axis=1)
        rank = np.where((sd > 0) & (np.isfinite(past).sum(axis=1) > 0.9 * window), mean / np.where(sd > 0, sd, 1.0), -np.inf)
        chosen = tuple(str(names[f]) for f in np.argsort(-rank)[:size])
        plan.append((float(days[t] * 86400), chosen))

    return plan


if __name__ == '__main__':
    symbols = tuple(UNIVERSE) + tuple(f'{w}USDT' for w in WANTED)
    panel = Panel.load(symbols, '2022-01-01', None)
    panel = panel.columns(tuple(s for k, s in enumerate(panel.symbols) if np.isfinite(panel.close[:, k]).any()))
    panel = Panel(panel.symbols, panel.times, panel.close, panel.volume, panel.buy, panel.funding,
                  np.array([1e-4 if s in ('BTCUSDT', 'ETHUSDT') else 3e-4 for s in panel.symbols]))
    panel.save(WORK)
    market = Market.of(panel)
    data = dict(np.load(CACHE))
    x = data['per_pair'].astype(np.float32)
    counts = np.isfinite(x).sum(axis=2)
    pool_daily = np.where(counts > 0, np.nansum(x, axis=2) / np.maximum(counts, 1), np.nan)
    plan = monthly_plan(pool_daily, data['days'], data['formulas'])
    d0, d1 = int(plan[0][0] // 86400), int(pd.Timestamp('2026-10-01').timestamp() // 86400)
    sleeves = {'F2 trend': track_score(trend_score(panel.close), True, panel).daily(market, d0, d1, False),
               'selected (730 d, 20)': track_score(schedule_score(plan, panel, NORMALIZED, True), False, panel).daily(market, d0, d1, False)}
    crowd = formulas(800, seed=11)

    with multiprocessing.get_context('spawn').Pool(max(multiprocessing.cpu_count() - 2, 1), initializer=fitness.start_worker,
                                                   initargs=(str(WORK),)) as workers:
        parts = workers.map(crowd_sum, [crowd[k:k + 20] for k in range(0, len(crowd), 20)])

    first = np.argmax(np.isfinite(panel.close), axis=0)
    young = np.arange(len(panel))[:, None] < first + NORMALIZED - 1

    for size in (400, 800):
        total = sum(p[0] for p in parts[:size // 20])
        mean = total / size

        for name, s in ((f'crowd ({size} random)', normalized(mean)), (f'crowd ({size}, by agreement)', mean.copy())):
            s[young | np.isnan(panel.close)] = np.nan
            sleeves[name] = track_score(s, False, panel).daily(market, d0, d1, False)

    sleeves = {k: np.nan_to_num(v) for k, v in sleeves.items()}
    sleeves['F2 + crowd 400 + selected'] = np.mean([sleeves['F2 trend'], sleeves['crowd (400 random)'], sleeves['selected (730 d, 20)']], axis=0)
    sleeves['F2 + crowd 800 + selected'] = np.mean([sleeves['F2 trend'], sleeves['crowd (800 random)'], sleeves['selected (730 d, 20)']], axis=0)
    sleeves['F2 + crowd 400 by agreement + selected'] = np.mean([sleeves['F2 trend'], sleeves['crowd (400, by agreement)'], sleeves['selected (730 d, 20)']], axis=0)
    years = pd.to_datetime(np.arange(d0, d1) * 86400, unit='s').year
    print(f'78 pairs, {pd.Timestamp(d0 * 86400, unit="s").date()} to 2026-10-01, exact Target, futures costs and funding, equal capital\n')

    for name, r in sleeves.items():
        equity = np.cumprod(1.0 + r)
        drawdown = (equity / np.maximum.accumulate(equity) - 1.0).min()
        print(f'{name:40s} sharpe {sharpe(r):5.2f}  return {r.mean() * 365:6.1%}  vol {r.std() * np.sqrt(365):5.1%}  max dd {drawdown:6.1%}   '
              + ' '.join(f'{y} {sharpe(r[years == y]):5.2f}' for y in sorted(set(years))))

    names = ['F2 trend', 'crowd (400, by agreement)', 'selected (730 d, 20)']
    print('\ncorrelations: ' + ', '.join(f'{a} / {b} {np.corrcoef(sleeves[a], sleeves[b])[0, 1]:.2f}' for i, a in enumerate(names) for b in names[i + 1:]))
    print('distinct formulas ever selected:', len({f for _, fs in plan for f in fs}), '; first and last selection:', plan[0][1][:3], plan[-1][1][:3])
