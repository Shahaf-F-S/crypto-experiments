# research_miner.py

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from miner.fitness import Market, track, track_score
from miner.formula import _shift, parse, score
from miner.miner import Miner, Settings
from miner.panel import Panel
from miner.simulate import daily_volatility, trend_score
from miner.stats import sharpe


# The pre-registered replay (docs/MINER.md): the miner as if it had run live since 2022, a step a week, a search
# round every four. `null`: the same on a panel whose days are shuffled within each pair (no multi-day structure
# left), where nothing it trades should earn. `planted`: the null market with a known edge planted (each hour's
# return tilted by PLANTED's score at the previous close), which it should find and trade.
# Run from the root: python -m lab.scripts.research_miner [replay|null|planted]

MODE = sys.argv[1] if len(sys.argv) > 1 else 'replay'
START = '2022-01-03'
END = '2026-10-05' if MODE == 'replay' else '2024-07-01'      # the controls' markets are stationary by construction
WEEK = 7 * 86400
PLANTED, STRENGTH = 'mean(flow, 72)', 0.015       # the planted edge: its score x STRENGTH hourly volatilities


def shuffled(panel: Panel, seed: int, decisions: bool = False) -> Panel:
    """
    Each pair's whole days (hourly returns with their volumes) in a random order: the null market. A day runs from
    the bar after a daily decision to the bar it is made on (bars opening 00:00 to 23:00 UTC), so nothing a
    decision sees belongs to the day it trades. With `decisions`, the first version (days of bars closing 00:00 to
    23:00): the decision bar opened each day, which left its first hour visible to the decision (the first null run).
    """
    rng = np.random.default_rng(seed)
    close, volume, buy = panel.close.copy(), panel.volume.copy(), panel.buy.copy()
    day = (panel.times + 3600) // 86400 if decisions else panel.times // 86400

    for k in range(close.shape[1]):
        rows = np.flatnonzero(np.isfinite(close[:, k]))
        rows = rows[np.isin(day[rows], [d for d in np.unique(day[rows]) if (day[rows] == d).sum() == 24])]
        blocks = rows.reshape(-1, 24)
        order = rng.permutation(len(blocks))
        log_returns = np.diff(np.log(close[rows, k]), prepend=np.log(close[rows[0], k]))
        log_returns[0] = 0.0
        moved = log_returns.reshape(-1, 24)[order].ravel()
        close[rows, k] = close[rows[0], k] * np.exp(np.cumsum(moved))
        volume[rows, k] = volume[blocks[order].ravel(), k]
        buy[rows, k] = buy[blocks[order].ravel(), k]

    return Panel(panel.symbols, panel.times, close, volume, buy, panel.funding, panel.slippage)


def planted(panel: Panel, formula: str = PLANTED, strength: float = STRENGTH) -> Panel:
    """`panel` with each hour's log return tilted by `formula`'s score at the previous close, in units of the pair's
    hourly volatility: a known, persistent edge."""
    s = score(parse(formula), panel.fields)
    log = np.log(panel.close)
    ret = np.diff(log, axis=0, prepend=np.nan)
    tilt = np.vstack([np.zeros((1, ret.shape[1])), np.nan_to_num(s[:-1])]) * strength * np.nanstd(ret, axis=0)
    first = np.argmax(np.isfinite(log), axis=0)
    close = np.exp(np.cumsum(np.where(np.isfinite(ret), ret + tilt, 0.0), axis=0) + log[first, np.arange(log.shape[1])])
    close[np.isnan(panel.close)] = np.nan
    return Panel(panel.symbols, panel.times, close, panel.volume, panel.buy, panel.funding, panel.slippage)


def row(name: str, days: np.ndarray, daily: np.ndarray) -> str:
    years = pd.to_datetime(days * 86400, unit='s').year
    equity = np.cumprod(1.0 + daily)
    drawdown = float((equity / np.maximum.accumulate(equity) - 1.0).min())
    by_year = '  '.join(f'{y} {sharpe(daily[years == y]):5.2f}' for y in sorted(set(years)))
    return f'{name:28s} {sharpe(daily):5.2f}  {daily.mean() * 365:6.1%}  {drawdown:6.1%}   {by_year}'


if __name__ == '__main__':
    panel = Panel.load()
    panel = shuffled(panel, 0, decisions=MODE == 'planted') if MODE in ('null', 'planted') else panel
    panel = planted(panel) if MODE == 'planted' else panel
    t, end = pd.Timestamp(START, tz='UTC').timestamp(), pd.Timestamp(END, tz='UTC').timestamp()
    began, k = time.time(), 0

    with Miner(panel, Settings(), folder=Path(f'data/miner/{MODE}')) as miner:
        while t < end:
            miner.step(t, mine=k % 4 == 0)

            if k % 13 == 0:
                print(pd.Timestamp(t, unit='s').date(), miner.summary(), f'{time.time() - began:.0f}s', flush=True)

            k, t = k + 1, t + WEEK

        miner.save()
        days, active = miner.portfolio()
        _, blended = miner.portfolio(members='blended')
        _, tracked = miner.portfolio(members='tracked')

        market = Market.of(panel)
        benchmark = track_score(trend_score(panel.close), True, panel).daily(market, int(days[0]), int(days[-1]) + 1, False)
        holding = np.nanmean(np.where(market.rows > 0, market.returns, np.nan), axis=1)
        held = (market.days >= days[0]) & (market.days <= days[-1])

        print(f'\n{MODE}: {START} to {END}, {miner.rounds} rounds, {miner.trials} trials, haircut {miner.haircut.kappa:.2f} '
              f'({miner.haircut.samples} alphas), {len(miner.alphas)} alphas incubated, '
              f'{sum(a.promoted is not None for a in miner.alphas.values())} traded\n')
        print(f'{"":28s} sharpe  return  max dd   by year')
        print(row('mined, blended (traded)', days, blended))
        print(row('mined, each alone', days, active))
        print(row('every tracked alpha', days, tracked))
        print(row('F2 trend (benchmark)', days, np.nan_to_num(benchmark)))
        print(row('equal-weight holding', market.days[held], np.nan_to_num(holding[held])))

        if MODE == 'planted':
            truth = track(PLANTED, False, panel).daily(market, int(days[0]), int(days[-1]) + 1, False)
            print(row(f'the planted {PLANTED}', days, np.nan_to_num(truth)))
        print('\nalphas traded:')

        for a in sorted(miner.alphas.values(), key=lambda a: a.promoted or 0):
            if a.promoted is not None:
                end_text = pd.Timestamp(a.ended, unit='s').date() if a.ended else 'still'
                print(f'  {a.name}: {pd.Timestamp(a.promoted, unit="s").date()} to {end_text}, in-sample {a.insample["sharpe"]:.2f}, '
                      f'forward {a.forward.get("sharpe", float("nan")):.2f} ({a.forward.get("days", 0)} days)')
