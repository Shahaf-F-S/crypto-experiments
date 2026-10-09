# research_reselect.py

import numpy as np
import pandas as pd

from lab.scripts.research_validation import CACHE
from miner.stats import sharpe


# The selected sleeve as the system would run it: every month (first day), the K formulas of the 78-pair pool with the
# best Sharpe ratio over the trailing window (at least that much history), optionally no two correlated above 0.7,
# held equal weight for the month. Walk-forward from the first month with a full window to 2026-10.
# Run from the root, after research_validation: python -m lab.scripts.research_reselect

LOOKBACKS = (365, 548, 730)
SIZES = (10, 20)


def reselect(daily: np.ndarray, days: np.ndarray, lookback: int, size: int, diverse: bool) -> tuple[np.ndarray, np.ndarray]:
    months = pd.to_datetime(days * 86400, unit='s').to_period('M')
    starts = np.flatnonzero(np.r_[True, months[1:] != months[:-1]])
    out = np.full(len(days), np.nan)

    for k, t in enumerate(starts):
        if t < lookback:
            continue

        window = daily[:, t - lookback:t]
        mean, sd = np.nanmean(window, axis=1), np.nanstd(window, axis=1)
        rank = np.where((sd > 0) & (np.isfinite(window).sum(axis=1) > 0.9 * lookback), mean / np.where(sd > 0, sd, 1.0), -np.inf)
        chosen = []

        for f in np.argsort(-rank):
            if len(chosen) == size or not np.isfinite(rank[f]):
                break

            if diverse and chosen:
                c = np.corrcoef(np.nan_to_num(window[[f] + chosen]))[0, 1:]

                if np.max(np.abs(c)) > 0.7:
                    continue

            chosen.append(f)

        end = starts[k + 1] if k + 1 < len(starts) else len(days)
        out[t:end] = np.nanmean(daily[chosen, t:end], axis=0)

    live = np.isfinite(out)
    return days[live], out[live]


if __name__ == '__main__':
    data = dict(np.load(CACHE))
    x = data['per_pair'].astype(np.float32)
    counts = np.isfinite(x).sum(axis=2)
    daily = np.where(counts > 0, np.nansum(x, axis=2) / np.maximum(counts, 1), np.nan)
    days = data['days']
    print(f'{daily.shape[0]} random formulas on 78 pairs; monthly re-selection, walk-forward\n')

    for lookback in LOOKBACKS:
        for size in SIZES:
            for diverse in (False, True):
                d, r = reselect(daily, days, lookback, size, diverse)
                years = pd.to_datetime(d * 86400, unit='s').year
                print(f'window {lookback:>3} days, {size:>2} formulas{", diverse" if diverse else "         "}: sharpe {sharpe(r):5.2f} '
                      f'from {pd.Timestamp(d[0] * 86400, unit="s").date()}   ' + ' '.join(f'{y} {sharpe(r[years == y]):5.2f}' for y in sorted(set(years))))
