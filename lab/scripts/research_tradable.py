# research_tradable.py

import math

import pandas as pd

from lab.research.scan import tradable

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
DISCOVERY = ('2021-01-01', '2024-01-01')

if __name__ == '__main__':
    rows = tradable(SYMBOLS, *DISCOVERY)
    rows.to_parquet('lab/results/tradable_discovery_1h.parquet')
    table = []

    for (signal, horizon), g in rows.groupby(['signal', 'horizon']):
        # Per pair-year edge in bps per unit of exposure, and its t across the 15 pair-years.
        per = g['edge'] / g['exposure']
        mean = per.mean()
        table.append({'signal': signal, 'horizon': horizon, 'edge/exposure (bps)': mean,
                      't': mean / (per.std(ddof=1) / math.sqrt(len(per))), 'same sign': f'{int((per * mean > 0).sum())}/{len(per)}',
                      'pooled t': g['edge'].sum() / math.sqrt((g['sd'] ** 2 * g['n']).sum())})

    table = pd.DataFrame(table).sort_values('t', key=abs, ascending=False)
    pd.set_option('display.width', 200)
    print(f'{len(table)} tests, mean-based (bps per unit position per trade; costs about 12 per unit of turnover):')
    print(table.to_string(index=False, float_format=lambda v: f'{v:.2f}'))
