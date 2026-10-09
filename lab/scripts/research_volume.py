# research_volume.py

import numpy as np
import pandas as pd

from lab.scripts.research_miner import trend_score
from miner.fitness import Market, track_score
from miner.formula import parse, score
from miner.panel import UNIVERSE, Panel
from miner.stats import sharpe


# The volume-trend family, named after research_validation pointed at it (2022-04 to 2023 on 78 pairs): fixed here,
# before this test, as the four simplest volume formulas among that study's 20 best. Tested on data the study never
# read: the 21 pairs from 2021-04 to 2022-03 (exact Target simulation, daily rebalancing, futures costs, funding);
# then for reference over 2022-04 to 2026-10. Correlation with F2. Run from the root: python -m lab.scripts.research_volume

FAMILY = ('delta(volume, 720)', 'mean(delta(volume, 336), 504)', 'mean(delta(volume, 120), 720)', 'wma(zscore(volume, 720), 336)')
UNSEEN, LATER = ('2021-04-01', '2022-04-01'), ('2022-04-01', '2026-10-01')


def span(days: np.ndarray, a: str, b: str) -> tuple[int, int]:
    return int(pd.Timestamp(a).timestamp() // 86400), int(pd.Timestamp(b).timestamp() // 86400)


if __name__ == '__main__':
    panel = Panel.load(tuple(UNIVERSE), None, None)
    market = Market.of(panel)
    crowd = sum(np.nan_to_num(score(parse(f), panel.fields)) for f in FAMILY) / len(FAMILY)
    crowd[np.isnan(score(parse(FAMILY[0]), panel.fields)) & np.isnan(score(parse(FAMILY[1]), panel.fields))] = np.nan
    tracks = {f: track_score(score(parse(f), panel.fields), False, panel) for f in FAMILY}
    tracks['the family (mean score)'] = track_score(crowd, False, panel)
    trend = track_score(trend_score(panel.close), True, panel)

    for name, (a, b) in (('never read: 2021-04 to 2022-03', UNSEEN), ('2022-04 to 2026-10', LATER)):
        d0, d1 = span(None, a, b)
        f2 = trend.daily(market, d0, d1, False)
        print(f'\n21 pairs, {name}; F2 {sharpe(f2):.2f}')

        for f, t in tracks.items():
            daily = t.daily(market, d0, d1, False)
            neutral = t.daily(market, d0, d1, True)
            ok = np.isfinite(daily) & np.isfinite(f2)
            print(f'  {f:34s} sharpe {sharpe(daily):5.2f} (drift-free {sharpe(neutral):5.2f}), return {np.nanmean(daily) * 365:6.1%}, '
                  f'correlation with F2 {np.corrcoef(daily[ok], f2[ok])[0, 1]:5.2f}')

        family = tracks['the family (mean score)'].daily(market, d0, d1, False)
        both = 0.5 * np.nan_to_num(family) / np.nanstd(family) + 0.5 * np.nan_to_num(f2) / np.nanstd(f2)
        print(f'  family and F2, equal risk: sharpe {sharpe(both):.2f}')
