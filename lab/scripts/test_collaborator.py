# test_collaborator.py

import datetime as dt
import functools
import math
import statistics

from system.microstructure import build
from pipeline.runner import run_seeds
from simulation import Market, MarketModel

MODEL = 'simulation/btc_usdt.model'
SEEDS, HOURS = range(16), 48.0
FEES = (20.0, 4.0)      # round trip, bps
SCENARIOS = {
    'no edge': {},
    'planted trend': dict(edge_bps=20.0, edge_halflife=dt.timedelta(hours=2), edge_kind='trend'),
    'planted reversion': dict(edge_bps=20.0, edge_halflife=dt.timedelta(hours=1), edge_kind='reversion'),
    'regime switching': dict(edge_bps=20.0, edge_halflife=dt.timedelta(hours=1.5), edge_switch=dt.timedelta(hours=12)),
}


def line(label: str, pnl: list[float], extra: str = '') -> None:
    spread = statistics.stdev(pnl)
    sharpe = statistics.fmean(pnl) / spread * math.sqrt(365) if spread > 0 else math.nan
    print(f'  {label:<24}{statistics.fmean(pnl):>9.1f}b{spread:>8.1f}b{sum(p > 0 for p in pnl) / len(pnl):>10.0%}{sharpe:>8.2f}  {extra}')


def table(results: list[dict]) -> None:
    days = [r['hours'] / 24.0 for r in results]
    names = list(results[0]['combinations'])
    collective = [(r['collaborator']['capital'] - 1.0) / day * 1e4 for r, day in zip(results, days)]
    own = {n: [(r['combinations'][n]['capital'] - 1.0) / day * 1e4 for r, day in zip(results, days)] for n in names}
    equal = [statistics.fmean(own[n][i] for n in names) for i in range(len(results))]
    best = max(names, key=lambda n: statistics.fmean(own[n]))

    print(f'  {"(P&L per day)":<24}{"mean":>10}{"sd":>9}{"positive":>10}{"sharpe":>8}')
    changes = statistics.fmean(r['collaborator']['changes'] for r in results)
    line('collaborator', collective, f'{changes:.0f} mode changes a run')
    line('all members, equal weight', equal)
    line(f'best member ({best})', own[best], 'chosen in hindsight')

    print(f'  {"member":<24}{"own P&L":>10}{"active":>9}{"copied":>10}{"promoted":>10}')

    for n in names:
        members = [r['collaborator']['members'][n] for r in results]
        active = statistics.fmean(m['seconds']['active'] / max(sum(m['seconds'].values()), 1.0) for m in members)
        copied = statistics.fmean(m['realized'] / day * 1e4 for m, day in zip(members, days))
        print(f'  {n:<24}{statistics.fmean(own[n]):>9.1f}b{active:>9.0%}{copied:>9.1f}b{statistics.fmean(m["promotions"] for m in members):>10.1f}')


if __name__ == '__main__':
    model = MarketModel.load(MODEL)

    for scenario, edge in SCENARIOS.items():
        for fee in FEES:
            results = run_seeds(functools.partial(build, fee), Market(model=model, **edge), SEEDS, HOURS, collaborate={})
            print(f'\n{scenario}, {fee:.0f} bps round trip, {len(results)} runs of {HOURS:.0f} h:')
            table(results)
