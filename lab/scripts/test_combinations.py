# test_combinations.py

import datetime as dt
import functools
import math
import statistics

from system.microstructure import build
from pipeline.runner import run_seeds
from simulation import Market, MarketModel

MODEL = 'simulation/btc_usdt.model'
SEEDS, HOURS = range(16), 24.0
FEES = (20.0, 4.0)      # round trip, bps
SCENARIOS = {
    'no edge': {},
    'planted trend': dict(edge_bps=20.0, edge_halflife=dt.timedelta(hours=2), edge_kind='trend'),
    'planted reversion': dict(edge_bps=20.0, edge_halflife=dt.timedelta(hours=1), edge_kind='reversion'),
}


def table(results: list[dict]) -> None:
    """Per combination: trades a day, net per trade, daily P&L (mean, sd, share of runs positive), the Sharpe ratio of
    the daily P&L across runs (annualized), and the mean of the runs' worst drawdowns."""
    print(f'{"":<22}{"trades":>8}{"net/trade":>11}{"P&L/day":>10}{"sd":>8}{"positive":>10}{"sharpe":>8}{"drawdown":>10}')

    for name in results[0]['combinations']:
        runs = [r['combinations'][name] for r in results]
        days = [r['hours'] / 24.0 for r in results]
        trades = statistics.fmean(run['exits'] / day for run, day in zip(runs, days))
        pnl = [(run['capital'] - 1.0) / day * 1e4 for run, day in zip(runs, days)]
        per_trade = sum(run['capital'] - 1.0 for run in runs) / max(sum(run['exits'] for run in runs), 1) * 1e4
        spread = statistics.stdev(pnl)
        sharpe = statistics.fmean(pnl) / spread * math.sqrt(365) if spread > 0 else math.nan
        print(
            f'{name:<22}{trades:>8.1f}{per_trade:>10.1f}b{statistics.fmean(pnl):>9.1f}b{spread:>7.1f}b'
            f'{sum(p > 0 for p in pnl) / len(pnl):>10.0%}{sharpe:>8.2f}{statistics.fmean(run["max_drawdown"] for run in runs):>10.2%}'
        )


if __name__ == '__main__':
    model = MarketModel.load(MODEL)

    for scenario, edge in SCENARIOS.items():
        for fee in FEES:
            results = run_seeds(functools.partial(build, fee), Market(model=model, **edge), SEEDS, HOURS)
            print(f'\n{scenario}, {fee:.0f} bps round trip, {len(results)} runs of {HOURS:.0f} h:')
            table(results)
