# research_ensemble.py

import multiprocessing
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lab.scripts.fetch_wide import WANTED
from lab.scripts.research_learner import daily_scores, formulas, trade
from lab.scripts.research_miner import trend_score
from miner import fitness
from miner.fitness import Market, track_score
from miner.panel import UNIVERSE, Panel
from miner.simulate import daily_volatility
from miner.stats import sharpe


# The crowd of random formulas: the plain mean of the scores of N formulas drawn at random from the grammar (no data,
# no selection), traded daily per pair (volatility-targeted, futures costs, funding). Robustness: other seeds, other
# sizes, the 57 pairs never used, the crowd without its members that lean with the trend, and with F2.
# Run from the root, after fetch_wide: python -m lab.scripts.research_ensemble

WORK = Path('data/miner/ensemble')
SEEDS = (11, 12, 13)
SIZES = (50, 200, 800)
PERIODS = (('2022-04-01', '2024-01-01'), ('2024-01-01', '2026-10-01'))


def inputs(panel: Panel) -> dict:
    rows = np.flatnonzero(((panel.times + 3600) % 86400) == 0)
    cumulative = np.nancumsum(np.nan_to_num(panel.funding), axis=0)
    nxt = np.r_[rows[1:], len(panel) - 1]
    return {'close': panel.close[rows], 'volatility': daily_volatility(panel.close)[rows], 'slippage': panel.slippage,
            'funding': cumulative[nxt] - cumulative[rows], 'days': (panel.times[rows] + 3600) // 86400}


def periods(days: np.ndarray, pnl: np.ndarray) -> str:
    out = []

    for a, b in PERIODS:
        mask = (days >= pd.Timestamp(a).timestamp() // 86400) & (days < pd.Timestamp(b).timestamp() // 86400)
        out.append(f'{sharpe(pnl[mask]):5.2f}')

    return ' / '.join(out)


if __name__ == '__main__':
    universes = {'21 pairs': tuple(UNIVERSE), '57 new pairs': tuple(f'{w}USDT' for w in WANTED)}
    pool = {seed: formulas(max(SIZES), seed=seed) for seed in SEEDS}

    for name, symbols in universes.items():
        panel = Panel.load(symbols, '2022-01-01', None)
        panel = panel.columns(tuple(s for k, s in enumerate(panel.symbols) if np.isfinite(panel.close[:, k]).any()))
        panel = Panel(panel.symbols, panel.times, panel.close, panel.volume, panel.buy, panel.funding,
                      np.array([1e-4 if s in ('BTCUSDT', 'ETHUSDT') else 3e-4 for s in panel.symbols]))
        panel.save(WORK)
        data = inputs(panel)
        days = data['days']
        close = data['close']
        past = np.log(close / np.vstack([np.full((14, close.shape[1]), np.nan), close[:-14]]))

        with multiprocessing.get_context('spawn').Pool(max(multiprocessing.cpu_count() - 2, 1), initializer=fitness.start_worker,
                                                       initargs=(str(WORK),)) as workers:
            scores = {seed: np.stack([s for batch in workers.map(daily_scores, [f[k:k + 10] for k in range(0, len(f), 10)])
                                      for s in batch]) for seed, f in pool.items()}

        trend = track_score(trend_score(panel.close), True, panel).daily(Market.of(panel), int(days[0]), int(days[-1]) + 1, False)
        trend = trend[np.isin(np.arange(int(days[0]), int(days[-1]) + 1), days)]
        print(f'\n{name} ({len(panel.symbols)}): Sharpe 2022-04..2023 / 2024..2026-10; F2 alone {periods(days, np.nan_to_num(trend))}')

        for seed in SEEDS:
            for size in SIZES:
                s = scores[seed][:size]
                pnl = trade(np.nanmean(s, axis=0), data, 0.25)
                corr = np.corrcoef(np.nan_to_num(pnl[400:]), np.nan_to_num(trend[400:]))[0, 1]
                print(f'  seed {seed}, {size:>3} formulas: {periods(days, pnl)}   correlation with F2 {corr:.2f}')

        s = scores[SEEDS[0]]
        tilt = np.array([np.corrcoef(np.nan_to_num(x).ravel(), np.nan_to_num(past).ravel())[0, 1] for x in s])
        neutral = s[np.abs(tilt) <= 0.1]
        pnl = trade(np.nanmean(neutral, axis=0), data, 0.25)
        print(f'  without the {int((np.abs(tilt) > 0.1).sum())} members leaning with or against the trend ({len(neutral)} left): {periods(days, pnl)}')
        crowd = trade(np.nanmean(s, axis=0), data, 0.25)
        both = 0.5 * crowd / np.nanstd(crowd) + 0.5 * np.nan_to_num(trend) / np.nanstd(trend)
        print(f'  crowd ({len(s)}) and F2, equal risk: {periods(days, both)}')
