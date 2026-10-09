# research_factors.py

import numpy as np
import pandas as pd

from lab.scripts.fetch_wide import WANTED
from miner.panel import UNIVERSE, Panel
from miner.simulate import TAKER
from miner.stats import sharpe


# Cross-sectional crypto factors (Liu, Tsyvinski and Wu 2022: size and momentum price the cross-section of coins) on
# the 21 + 57 pairs: every Monday 00:00 UTC, the pairs ranked on each pre-specified characteristic, held long the
# top fifth and short the bottom fifth (each leg equal-risk: weights inverse to 30-day volatility), for a week, at
# futures costs with 2 bps of slippage on BTC and ETH and 4 elsewhere, and funding. Market-neutral by construction.
# All factors are reported. Run from the root, after fetch_wide: python -m lab.scripts.research_factors

PERIODS = (('2022-04-01', '2024-01-01'), ('2024-01-01', '2026-10-01'))


def weekly(panel: Panel) -> tuple[np.ndarray, dict[str, np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
    """Monday rows, the characteristics at each, the next week's returns and funding, the volatility."""
    opened = pd.to_datetime(panel.times, unit='s', utc=True)
    rows = np.flatnonzero((opened.weekday == 6) & (opened.hour == 23))                 # the bar closing Monday 00:00
    close = panel.close
    log = np.log(close)
    hourly = np.diff(log, axis=0, prepend=np.nan)
    vol = pd.DataFrame(hourly).rolling(720, min_periods=480).std().to_numpy() * np.sqrt(24)
    dollars = pd.DataFrame(panel.volume * close).rolling(720, min_periods=480).sum().to_numpy()
    week = pd.DataFrame(panel.volume * close).rolling(168, min_periods=120).sum().to_numpy()
    quarter = pd.DataFrame(panel.volume * close).rolling(2160, min_periods=1440).sum().to_numpy() / (2160 / 168)

    def back(hours: int, skip: int = 24) -> np.ndarray:
        return log[rows - skip] - log[rows - hours]

    traits = {
        'momentum 1w': back(168), 'momentum 2w': back(336), 'momentum 4w': back(672),
        'reversal 1w': -(log[rows] - log[rows - 168]),
        'size (small)': -np.log(dollars[rows]),
        'low volatility': -vol[rows],
        'volume shock (quiet)': -(week[rows] / quarter[rows]),
    }
    nxt = np.r_[rows[1:], len(close) - 1]
    ret = close[nxt] / close[rows] - 1.0
    cumulative = np.nancumsum(np.nan_to_num(panel.funding), axis=0)
    funding = cumulative[nxt] - cumulative[rows]
    return rows, traits, ret, funding, vol[rows]


def long_short(trait: np.ndarray, ret: np.ndarray, funding: np.ndarray, vol: np.ndarray, cost: np.ndarray) -> np.ndarray:
    """Weekly return of long the top fifth, short the bottom fifth, risk-weighted, gross 1, net of costs and funding."""
    out = np.zeros(len(trait))
    previous = np.zeros(trait.shape[1])

    for k in range(len(trait)):
        ok = np.isfinite(trait[k]) & np.isfinite(ret[k]) & (vol[k] > 0)

        if ok.sum() < 10:
            previous = np.zeros_like(previous)
            continue

        ranks = pd.Series(trait[k][ok]).rank(pct=True).to_numpy()
        side = np.where(ranks > 0.8, 1.0, np.where(ranks <= 0.2, -1.0, 0.0))
        w = np.zeros(trait.shape[1])
        w[ok] = side / vol[k][ok]

        for sign in (1.0, -1.0):
            leg = np.sign(w) == sign
            w[leg] = sign * 0.5 * np.abs(w[leg]) / np.abs(w[leg]).sum() if leg.any() else 0.0

        out[k] = np.nansum(w * np.nan_to_num(ret[k]) - w * np.nan_to_num(funding[k])) - np.sum(np.abs(w - previous) * cost)
        previous = w

    return out


if __name__ == '__main__':
    symbols = tuple(UNIVERSE) + tuple(f'{w}USDT' for w in WANTED)
    panel = Panel.load(symbols, '2021-06-01', None)
    panel = panel.columns(tuple(s for k, s in enumerate(panel.symbols) if np.isfinite(panel.close[:, k]).any()))
    cost = TAKER + np.array([2e-4 if s in ('BTCUSDT', 'ETHUSDT') else 4e-4 for s in panel.symbols])
    rows, traits, ret, funding, vol = weekly(panel)
    when = panel.times[rows]
    print(f'{len(panel.symbols)} pairs, weekly long-short fifths, market-neutral, futures costs and funding\n')
    print(f'{"factor":22s} ' + ' '.join(f'{a[:7]}..{b[:4]}' for a, b in PERIODS) + '   return / y (second period)')

    for name, trait in traits.items():
        weekly_returns = long_short(trait, ret, funding, vol, cost)
        cells = []

        for a, b in PERIODS:
            mask = (when >= pd.Timestamp(a).timestamp()) & (when < pd.Timestamp(b).timestamp())
            x = weekly_returns[mask]
            cells.append(x.mean() / x.std() * np.sqrt(52) if x.std() > 0 else np.nan)

        last = weekly_returns[when >= pd.Timestamp(PERIODS[1][0]).timestamp()]
        print(f'{name:22s} ' + ' '.join(f'{c:15.2f}' for c in cells) + f'   {last.mean() * 52:6.1%}')
