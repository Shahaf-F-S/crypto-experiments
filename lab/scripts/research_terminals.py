# research_terminals.py

import multiprocessing
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lab.scripts.research_validation import CACHE as BASE_CACHE, portfolio, sharpes
from miner import fitness, formula, search
from miner.breadth import WIDE
from miner.formula import bar_fields, parse, score, terminals
from miner.panel import Panel
from miner.search import admissible, grow, simplify
from miner.simulate import by_day, screen
from miner.stats import sharpe


# Does new information help? Two fields the grammar lacks, registered here only: `turnover` (the log of price x
# volume, a level: trading in dollars) and `idio` (a series: the pair's hourly log return minus the mean of all
# pairs', its own move net of the market's). 3000 random formulas from the extended grammar on the 78 pairs since
# 2022, against the 3000 of the base grammar (research_validation): the formulas using the new fields, their crowd,
# and how their selection carries forward. Run from the root: python -m lab.scripts.research_terminals

CACHE = Path('lab/results/pool_terminals.npz')
WORK = Path('data/miner/wide')
FIRST, SPLIT, LAST = '2022-04-01', '2024-01-01', '2026-10-01'

formula.TERMINALS.update({'turnover': 'level', 'idio': 'series'})
search.SERIES.append('idio')
search.LEVELS.append('turnover')
_fields: dict | None = None


def extended(panel: Panel) -> dict:
    fields = bar_fields(panel.close, panel.volume, panel.buy)
    fields['turnover'] = np.log1p(panel.close * panel.volume)
    ret = fields['ret']
    with np.errstate(invalid='ignore'):
        fields['idio'] = ret - np.nanmean(ret, axis=1, keepdims=True)

    fields['idio'][np.isnan(ret)] = np.nan
    return fields


def _worker_fields() -> dict:
    global _fields

    if _fields is None:
        _fields = extended(fitness._panel)

    return _fields


def record(batch: list[str]) -> list[np.ndarray]:
    """In a worker: each formula's daily P&L per pair."""
    panel, fields = fitness._panel, _worker_fields()
    out = []

    for f in batch:
        pnl, _ = screen(score(parse(f), fields), panel.close, panel.funding, panel.slippage, panel.times, 0, neutral=False)
        _, per_pair = by_day(pnl, panel.times)
        out.append(per_pair.astype(np.float16))

    return out


def crowd_sum(batch: list[str]) -> np.ndarray:
    panel, fields = fitness._panel, _worker_fields()
    return sum(np.nan_to_num(score(parse(f), fields)) for f in batch)


def draw(count: int, seed: int) -> list[str]:
    rng, out = random.Random(seed), {}

    while len(out) < count:
        node = simplify(grow(rng, rng.randint(1, 3)))

        if admissible(node):
            out[str(node)] = None

    return list(out)


if __name__ == '__main__':
    if CACHE.exists() and 'rebuild' not in sys.argv:
        data = dict(np.load(CACHE))
    else:
        panel = Panel.load(WIDE, '2022-01-01', None)
        panel = Panel(panel.symbols, panel.times, panel.close, panel.volume, panel.buy, panel.funding,
                      np.array([1e-4 if s in ('BTCUSDT', 'ETHUSDT') else 3e-4 for s in panel.symbols]))
        panel.save(WORK)
        pool = draw(3000, seed=29)

        with multiprocessing.get_context('spawn').Pool(max(multiprocessing.cpu_count() - 2, 1), initializer=fitness.start_worker,
                                                       initargs=(str(WORK),)) as workers:
            results = [r for batch in workers.map(record, [pool[k:k + 10] for k in range(0, len(pool), 10)], chunksize=1) for r in batch]
            uses = [bool({'turnover', 'idio'} & terminals(parse(f))) for f in pool]
            crowd_new = sum(workers.map(crowd_sum, [[f for f, u in zip(pool, uses) if u][:400][k:k + 20] for k in range(0, 400, 20)]))
            crowd_old = sum(workers.map(crowd_sum, [[f for f, u in zip(pool, uses) if not u][:400][k:k + 20] for k in range(0, 400, 20)]))

        days, _ = by_day(np.zeros((len(panel), 1)), panel.times)
        np.savez(CACHE, formulas=np.array(pool), days=days, per_pair=np.stack(results),
                 crowd_new=crowd_new / 400, crowd_old=crowd_old / 400, close=panel.close, times=panel.times)
        data = dict(np.load(CACHE))

    pool = [str(f) for f in data['formulas']]
    per_pair, days = data['per_pair'], data['days']
    uses = np.array([bool({'turnover', 'idio'} & terminals(parse(f))) for f in pool])
    before = np.flatnonzero((days >= pd.Timestamp(FIRST).timestamp() // 86400) & (days < pd.Timestamp(SPLIT).timestamp() // 86400))
    after = np.flatnonzero((days >= pd.Timestamp(SPLIT).timestamp() // 86400) & (days < pd.Timestamp(LAST).timestamp() // 86400))
    every = np.arange(per_pair.shape[2])
    b, a = sharpes(per_pair, every, before), sharpes(per_pair, every, after)
    print(f'{len(pool)} formulas from the extended grammar, {uses.sum()} using turnover or idio, 78 pairs\n')

    for name, mask in (('using the new fields', uses), ('not using them', ~uses), ('using idio', np.array(['idio' in f for f in pool])),
                       ('using turnover', np.array(['turnover' in f for f in pool]))):
        ok = mask & np.isfinite(a) & np.isfinite(b)
        top = np.flatnonzero(mask)[np.argsort(-np.nan_to_num(b[mask], nan=-9))[:20]]
        print(f'{name:22s} {ok.sum():5d} formulas: median Sharpe {np.median(b[ok]):5.2f} / {np.median(a[ok]):5.2f}, '
              f'before-after correlation {np.corrcoef(b[ok], a[ok])[0, 1]:.2f}; 20 best before: {sharpe(portfolio(per_pair, top, before)):.2f} -> '
              f'{sharpe(portfolio(per_pair, top, after)):.2f}')

    base = dict(np.load(BASE_CACHE))
    bb = sharpes(base['per_pair'], every, before)
    ba = sharpes(base['per_pair'], every, after)
    top = np.argsort(-np.nan_to_num(bb, nan=-9))[:20]
    print(f'{"base grammar (3000)":22s}       20 best before: {sharpe(portfolio(base["per_pair"], top, before)):.2f} -> {sharpe(portfolio(base["per_pair"], top, after)):.2f}')

    # The two crowds (400 formulas each), traded through the exact simulation.
    from miner.fitness import Market, track_score
    panel = Panel.load(WIDE, '2022-01-01', None)
    panel = Panel(panel.symbols, panel.times[:len(data['times'])], panel.close[:len(data['times'])], panel.volume[:len(data['times'])],
                  panel.buy[:len(data['times'])], panel.funding[:len(data['times'])],
                  np.array([1e-4 if s in ('BTCUSDT', 'ETHUSDT') else 3e-4 for s in panel.symbols]))
    market = Market.of(panel)

    for name in ('crowd_old', 'crowd_new'):
        s = data[name].copy()
        s[np.isnan(panel.close)] = np.nan
        t = track_score(s, False, panel)
        d0, d1 = int(days[before[0]]), int(days[before[-1]]) + 1
        d2, d3 = int(days[after[0]]), int(days[after[-1]]) + 1
        print(f'{name} (400): {sharpe(t.daily(market, d0, d1, False)):.2f} / {sharpe(t.daily(market, d2, d3, False)):.2f}')
