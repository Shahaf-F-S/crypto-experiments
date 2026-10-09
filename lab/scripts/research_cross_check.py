# research_cross_check.py

import numpy as np
import pandas as pd

from lab.scripts.fetch_wide import WANTED
from lab.scripts.research_cross_formulas import neutral_weights, run
from lab.scripts.research_miner import trend_score
from miner.fitness import Market, track_score
from miner.formula import parse, score
from miner.panel import UNIVERSE, Panel
from miner.simulate import daily_volatility
from miner.stats import sharpe


# The cross-sectional formulas chosen on the 21 pairs' discovery period (research_cross_formulas: the 10 best of 200
# random formulas, equal weight), applied unchanged to the 57 pairs never used in any design, and to all 78; their
# correlation with the trend system F2 on the same pairs. Run from the root: python -m lab.scripts.research_cross_check

CHOSEN = (
    'stoch(price, 168)', 'stoch(price, 336)', 'min(mean(stoch(price, 168), 504), 3)', 'zscore(price, 336)',
    'wma(stoch(price, 336), 72)', 'stoch(price, 720)', 'gate(min(stoch(volume, 168), 72), zscore(price, 72))',
    'delta(price, 504)', 'zscore(price, 504)', 'delay(zscore(price, 720), 3)',
)
START, END = '2022-04-01', '2026-10-01'


def daily_inputs(panel: Panel) -> dict:
    rows = np.flatnonzero(((panel.times + 3600) % 86400) == 0)
    cumulative = np.nancumsum(np.nan_to_num(panel.funding), axis=0)
    nxt = np.r_[rows[1:], len(panel) - 1]
    return {'rows': rows, 'close': panel.close[rows], 'volatility': daily_volatility(panel.close)[rows],
            'funding': cumulative[nxt] - cumulative[rows], 'slippage': panel.slippage,
            'days': (panel.times[rows] + 3600) // 86400}


if __name__ == '__main__':
    for name, symbols in (('57 new pairs', tuple(f'{w}USDT' for w in WANTED)), ('all 78 pairs', tuple(UNIVERSE) + tuple(f'{w}USDT' for w in WANTED))):
        panel = Panel.load(symbols, '2022-01-01', None)
        panel = panel.columns(tuple(s for k, s in enumerate(panel.symbols) if np.isfinite(panel.close[:, k]).any()))
        panel = Panel(panel.symbols, panel.times, panel.close, panel.volume, panel.buy, panel.funding,
                      np.array([2e-4 if s in ('BTCUSDT', 'ETHUSDT') else 4e-4 for s in panel.symbols]))
        data = daily_inputs(panel)
        days = data['days']
        span = (days >= pd.Timestamp(START).timestamp() // 86400) & (days < pd.Timestamp(END).timestamp() // 86400)
        each = []

        for formula in CHOSEN:
            s = score(parse(formula), panel.fields)[data['rows']]
            each.append(run(neutral_weights(s, data['volatility']), data))

        blend = np.mean(each, axis=0)
        trend = track_score(trend_score(panel.close), True, panel).daily(Market.of(panel), int(days[span][0]), int(days[span][-1]) + 1, False)
        years = pd.to_datetime(days[span] * 86400, unit='s').year
        x = blend[span]
        both = 0.5 * x / np.std(x) + 0.5 * np.nan_to_num(trend) / np.nanstd(trend)
        print(f'{name} ({len(panel.symbols)}), {START} to {END}, daily, market-neutral, futures costs (4 bps slippage) and funding')
        print(f'  the 10 chosen formulas, equal weight: sharpe {sharpe(x):.2f}, return {x.mean() * 365:.1%}/y at {x.std() * np.sqrt(365):.1%} volatility   '
              + ' '.join(f'{y} {sharpe(x[years == y]):.2f}' for y in sorted(set(years))))
        print(f'  each: ' + ', '.join(f'{sharpe(e[span]):.2f}' for e in each))
        print(f'  correlation with F2 {np.corrcoef(x, np.nan_to_num(trend))[0, 1]:.2f}; F2 alone {sharpe(trend):.2f}; '
              f'equal-risk mix {sharpe(both):.2f}   ' + ' '.join(f'{y} {sharpe(both[years == y]):.2f}' for y in sorted(set(years))) + '\n')
