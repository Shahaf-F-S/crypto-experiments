# research_wide.py

import numpy as np
import pandas as pd

from lab.scripts.fetch_wide import WANTED
from lab.scripts.research_miner import trend_score
from miner.fitness import Market, track_score
from miner.panel import Panel
from miner.stats import sharpe


# F2 on the wider universe: 57 pairs never used in any design (hourly bars since 2022), at the usual 2 bps of
# slippage a side and at a stricter 4 bps for smaller coins; by year and by pair. Run from the root, after
# fetch_wide: python -m lab.scripts.research_wide

START = '2022-04-01'          # after the first 60 days of warm-up
END = '2026-10-01'

if __name__ == '__main__':
    panel = Panel.load(tuple(f'{w}USDT' for w in WANTED), '2022-01-01', None)
    panel = panel.columns(tuple(s for k, s in enumerate(panel.symbols) if np.isfinite(panel.close[:, k]).any()))
    market = Market.of(panel)
    d0, d1 = int(pd.Timestamp(START).timestamp() // 86400), int(pd.Timestamp(END).timestamp() // 86400)
    print(f'F2 (trend, pullback timing) on {len(panel.symbols)} pairs never used in design, {START} to {END}, futures costs and funding\n')

    for slippage in (2.0, 4.0):
        p = Panel(panel.symbols, panel.times, panel.close, panel.volume, panel.buy, panel.funding, np.full(len(panel.symbols), slippage * 1e-4))
        t = track_score(trend_score(p.close), True, p)
        daily = t.daily(market, d0, d1, False)
        years = pd.to_datetime(np.arange(d0, d1) * 86400, unit='s').year
        equity = np.cumprod(1.0 + np.nan_to_num(daily))
        drawdown = (equity / np.maximum.accumulate(equity) - 1.0).min()
        by_year = '  '.join(f'{y} {sharpe(daily[years == y]):5.2f}' for y in sorted(set(years)))
        print(f'slippage {slippage:.0f} bps: sharpe {sharpe(daily):.2f}, return {np.nanmean(daily) * 365:.1%}/y, '
              f'max drawdown {drawdown:.1%}   {by_year}')

        if slippage == 2.0:
            k0, k1 = np.searchsorted(t.days, d0), np.searchsorted(t.days, d1)
            per_pair = [sharpe(np.where(t.active[k0:k1, k], t.pnl[k0:k1, k], np.nan)) for k in range(len(p.symbols))]
            positive = int(np.sum(np.array(per_pair) > 0))
            print(f'  positive on {positive} of {len(per_pair)} pairs; by pair: ' +
                  ', '.join(f'{s[:-4]} {v:.2f}' for s, v in sorted(zip(p.symbols, per_pair), key=lambda x: -np.nan_to_num(x[1]))))
