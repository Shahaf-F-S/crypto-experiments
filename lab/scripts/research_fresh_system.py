# research_fresh_system.py

import multiprocessing
from pathlib import Path

import numpy as np
import pandas as pd

from lab.scripts.fetch_fresh_wide import WANTED
from lab.scripts.research_learner import formulas
from lab.scripts.research_miner import trend_score
from lab.scripts.research_sleeves import crowd_sum
from lab.scripts.research_sleeves_exact import monthly_plan
from lab.scripts.research_validation import CACHE as POOL_CACHE
from miner import fitness
from miner.breadth import _record
from miner.components import NORMALIZED, SIZE
from miner.fitness import Market, schedule_score, track_score
from miner.panel import Panel
from miner.stats import sharpe


# The final, pre-registered test of the breadth miner's frozen design (docs/MINER.md): a third universe never used in
# any design (lab/scripts/fetch_fresh_wide.py), 5 bps of slippage a side. F2; the crowd (the first 400 random
# formulas of seed 11, sized by agreement); the selected sleeve (monthly, the 20 best over 730 days among the same 3000
# random formulas as the replay, simulated on these pairs); equal capital, 2024-01 to 2026-10. It works out of sample
# if the combination's Sharpe ratio is at least 0.5. Run from the root: python -m lab.scripts.research_fresh_system

WORK = Path('data/miner/fresh')
START, END = '2024-01-01', '2026-10-01'

if __name__ == '__main__':
    from system.history import DATA
    available = tuple(f'{w}USDT' for w in WANTED if any((DATA / '1h' / f'{w}USDT').glob('*.parquet')))
    panel = Panel.load(available, '2022-01-01', None)
    panel = panel.columns(tuple(s for k, s in enumerate(panel.symbols) if np.isfinite(panel.close[:, k]).any()))
    panel = Panel(panel.symbols, panel.times, panel.close, panel.volume, panel.buy, panel.funding, np.full(len(panel.symbols), 5e-4))
    panel.save(WORK)
    pool = [str(f) for f in np.load(POOL_CACHE)['formulas']]
    crowd = formulas(800, seed=11)[:400]

    with multiprocessing.get_context('spawn').Pool(max(multiprocessing.cpu_count() - 2, 1), initializer=fitness.start_worker,
                                                   initargs=(str(WORK),)) as workers:
        records = np.stack([r for batch in workers.map(_record, [pool[k:k + 10] for k in range(0, len(pool), 10)], chunksize=1) for r in batch])
        total = sum(part[0] for part in workers.map(crowd_sum, [crowd[k:k + 20] for k in range(0, len(crowd), 20)]))

    from miner.simulate import by_day
    days, _ = by_day(np.zeros((len(panel), 1)), panel.times)
    plan = [(t, f) for t, f in monthly_plan(records, days, np.array(pool)) if t >= pd.Timestamp(START).timestamp()]
    market = Market.of(panel)
    d0, d1 = int(pd.Timestamp(START).timestamp() // 86400), int(pd.Timestamp(END).timestamp() // 86400)
    mean = total / len(crowd)
    first = np.argmax(np.isfinite(panel.close), axis=0)
    mean[(np.arange(len(panel))[:, None] < first + SIZE - 1) | np.isnan(panel.close)] = np.nan
    sleeves = {
        'F2 (trend)': track_score(trend_score(panel.close), True, panel).daily(market, d0, d1, False),
        'crowd (400, by agreement)': track_score(mean, False, panel).daily(market, d0, d1, False),
        'selected (730 d, 20)': track_score(schedule_score(plan, panel, NORMALIZED, True), False, panel).daily(market, d0, d1, False),
    }
    sleeves = {k: np.nan_to_num(v) for k, v in sleeves.items()}
    sleeves['all three, equal capital'] = np.mean(list(sleeves.values()), axis=0)
    years = pd.to_datetime(np.arange(d0, d1) * 86400, unit='s').year
    print(f'{len(panel.symbols)} pairs never used ({" ".join(s[:-4] for s in panel.symbols)}), {START} to {END}, 5 bps slippage\n')

    for name, r in sleeves.items():
        equity = np.cumprod(1.0 + r)
        drawdown = (equity / np.maximum.accumulate(equity) - 1.0).min()
        print(f'{name:26s} sharpe {sharpe(r):5.2f}  return {r.mean() * 365:6.1%}  vol {r.std() * np.sqrt(365):5.1%}  max dd {drawdown:6.1%}   '
              + ' '.join(f'{y} {sharpe(r[years == y]):5.2f}' for y in sorted(set(years))))

    verdict = sharpe(sleeves['all three, equal capital'])
    print(f'\npre-registered criterion (Sharpe >= 0.5): {"met" if verdict >= 0.5 else "not met"} ({verdict:.2f})')
