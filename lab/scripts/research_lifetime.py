# research_lifetime.py

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from miner.fitness import Market
from miner.miner import Miner
from miner.panel import Panel
from miner.stats import sharpe


# How long do the miner's discoveries last? Every alpha the replay incubated (docs/MINER.md), followed from the day
# it was born: its mean return by age (weeks since birth), then the policy of trading every new alpha from birth for
# H weeks (equal weight over the live ones). H is chosen on the first half of the replay and tested on the second.
# Run from the root, after the replay: python -m lab.scripts.research_lifetime [replay]

RUN = sys.argv[1] if len(sys.argv) > 1 else 'replay'
WEEKS = 52
HORIZONS = (2, 4, 8, 13, 26, 52)
SPLIT = '2024-04-01'


def by_age(miner: Miner, neutral: bool) -> np.ndarray:
    """alphas x weeks since birth: each alpha's mean daily return in each week of its life (missing past the data)."""
    last = int(miner.history[-1]['time'] // 86400)
    out = np.full((len(miner.alphas), WEEKS), np.nan)

    for k, a in enumerate(miner.alphas.values()):
        born = int(a.born // 86400)
        daily = miner._track(a).daily(miner.market, born, min(born + 7 * WEEKS, last), neutral)

        for w in range(len(daily) // 7):
            out[k, w] = np.nanmean(daily[7 * w:7 * w + 7])

    return out


def policy(miner: Miner, weeks: int) -> tuple[np.ndarray, np.ndarray]:
    """Every alpha traded from the day it was born for `weeks`, equal weight over those live each day (real P&L)."""
    first, last = int(miner.history[0]['time'] // 86400), int(miner.history[-1]['time'] // 86400)
    days = np.arange(first, last)
    total, count = np.zeros(len(days)), np.zeros(len(days))

    for a in miner.alphas.values():
        born = int(a.born // 86400)
        end = min(born + 7 * weeks, last)

        if end <= born:
            continue

        daily = np.nan_to_num(miner._track(a).daily(miner.market, born, end, False))
        total[born - first:end - first] += daily
        count[born - first:end - first] += 1

    return days, np.where(count > 0, total / np.maximum(count, 1), 0.0)


if __name__ == '__main__':
    panel = Panel.load()

    if RUN in ('null', 'planted'):
        from lab.scripts.research_miner import planted, shuffled
        panel = shuffled(panel, 0)
        panel = planted(panel) if RUN == 'planted' else panel

    with Miner.load(panel, Path(f'data/miner/{RUN}')) as miner:
        miner._prepare(list(miner.alphas.values()))
        real, neutral = by_age(miner, False), by_age(miner, True)
        print(f'{RUN}: {len(miner.alphas)} alphas incubated; mean return by age (%/y, all alphas alive at that age)\n')
        print('  week         ' + ' '.join(f'{w + 1:>5}' for w in range(0, WEEKS, 4)))
        print('  real         ' + ' '.join(f'{np.nanmean(real[:, w:w + 4]) * 36500:5.1f}' for w in range(0, WEEKS, 4)))
        print('  drift-free   ' + ' '.join(f'{np.nanmean(neutral[:, w:w + 4]) * 36500:5.1f}' for w in range(0, WEEKS, 4)))
        print('  alphas       ' + ' '.join(f'{int(np.isfinite(real[:, w]).sum()):5d}' for w in range(0, WEEKS, 4)))

        split = int(pd.Timestamp(SPLIT).timestamp() // 86400)
        print(f'\ntrade every alpha from birth for H weeks (first half to {SPLIT} / second half):')

        for weeks in HORIZONS:
            days, daily = policy(miner, weeks)
            print(f'  H {weeks:>2}: sharpe {sharpe(daily[days < split]):5.2f} / {sharpe(daily[days >= split]):5.2f}, '
                  f'return {daily[days < split].mean() * 365:6.1%} / {daily[days >= split].mean() * 365:6.1%}')

        days, active = miner.portfolio()
        print(f'\nfor comparison, the replay as run (90-day incubation): sharpe {sharpe(active[days < split]):5.2f} / '
              f'{sharpe(active[days >= split]):5.2f}')
