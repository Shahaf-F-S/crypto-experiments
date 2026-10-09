# research_cross_formulas.py

import numpy as np
import pandas as pd

from lab.scripts.research_learner import CACHE, DISCOVERY, HOLDOUT, learn, period
from miner.simulate import TAKER
from miner.stats import deflated, sharpe


# Relative (cross-sectional) alphas: each day, the pairs ranked on a formula's score, held long the high and short
# the low in proportion to the cross-sectional z-score, each pair volatility-scaled; market-neutral by construction.
# For each of the learner's 200 random formulas (no data involved), and for an online learner predicting each
# pair's return relative to the others. Discovery to choose, holdout to check. Run from the root, after
# research_learner: python -m lab.scripts.research_cross_formulas


def neutral_weights(signal: np.ndarray, volatility: np.ndarray) -> np.ndarray:
    """Cross-sectional z-scores of the signal (pairs with a value), volatility-scaled and normalized to a gross
    exposure of 1 a day."""
    s = np.where(np.isfinite(signal) & (volatility > 0), signal, np.nan)
    z = (s - np.nanmean(s, axis=1, keepdims=True)) / np.nanstd(s, axis=1, keepdims=True)
    w = np.nan_to_num(z) * 0.02 / np.where(volatility > 0, volatility, np.inf)
    gross = np.abs(w).sum(axis=1, keepdims=True)
    return np.where(gross > 0, w / np.where(gross > 0, gross, 1.0), 0.0)


def run(weights: np.ndarray, data: dict) -> np.ndarray:
    """Daily P&L of the weights held from each day's first close to the next, at futures costs and funding."""
    close = data['close']
    ret = np.vstack([close[1:] / close[:-1] - 1.0, np.full((1, close.shape[1]), np.nan)])
    change = np.abs(np.diff(np.vstack([np.zeros((1, weights.shape[1])), weights]), axis=0))
    return np.nansum(weights * np.nan_to_num(ret) - weights * data['funding'] - change * (TAKER + data['slippage']), axis=1)


if __name__ == '__main__':
    data = dict(np.load(CACHE))
    days, scores, vol = data['days'], data['scores'].astype(np.float64), data['volatility']
    first = int(np.searchsorted(days, pd.Timestamp(DISCOVERY[0]).timestamp() // 86400))
    results = []

    for k, formula in enumerate(data['formulas']):
        pnl = run(neutral_weights(scores[k], vol), data)
        pnl[:first] = 0.0
        results.append((sharpe(period(days, pnl, DISCOVERY)), sharpe(period(days, pnl, HOLDOUT)), str(formula), pnl))

    results.sort(key=lambda r: -r[0] if np.isfinite(r[0]) else np.inf)
    discovery = np.array([r[0] for r in results])
    holdout = np.array([r[1] for r in results])
    print(f'{len(results)} random formulas, cross-sectional (market-neutral), daily, futures costs and funding')
    print(f'discovery Sharpe quantiles (5/50/95%): {np.round(np.nanpercentile(discovery, [5, 50, 95]), 2)}; '
          f'correlation of discovery and holdout Sharpe across formulas: {np.corrcoef(np.nan_to_num(discovery), np.nan_to_num(holdout))[0, 1]:.2f}\n')
    print(f'{"formula":60s} {"discovery":>9} {"holdout":>8} {"deflated":>8}')

    for d, h, formula, pnl in results[:10]:
        print(f'{formula[:60]:60s} {d:9.2f} {h:8.2f} {deflated(period(days, pnl, DISCOVERY), len(results), float(np.nanstd(discovery))):8.2f}')

    top = np.mean([r[3] for r in results[:10]], axis=0)
    print(f'\nthe 10 best on discovery, equal weight: discovery {sharpe(period(days, top, DISCOVERY)):.2f}, holdout {sharpe(period(days, top, HOLDOUT)):.2f}')

    # The learner on relative returns: each pair's next-day return minus the day's cross-sectional mean.
    x = np.transpose(scores, (1, 2, 0))
    x = x - np.nanmean(x, axis=1, keepdims=True)
    y = np.vstack([np.log(data['close'][1:] / data['close'][:-1]), np.full((1, vol.shape[1]), np.nan)])
    y = (y - np.nanmean(y, axis=1, keepdims=True)) / np.where(vol > 0, vol, np.nan)

    for halflife in (90, 365):
        for ridge in (10.0, 100.0):
            prediction = learn(x, y, halflife, ridge, first)
            pnl = run(neutral_weights(prediction, vol), data)
            pnl[:first] = 0.0
            print(f'learner on relative returns, half-life {halflife}d, ridge {ridge:g}: '
                  f'discovery {sharpe(period(days, pnl, DISCOVERY)):.2f}, holdout {sharpe(period(days, pnl, HOLDOUT)):.2f}')
