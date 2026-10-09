# research_scan.py

import math

import pandas as pd

from lab.research.scan import scan

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
DISCOVERY = ('2021-01-01', '2024-01-01')

if __name__ == '__main__':
    rows = scan(SYMBOLS, *DISCOVERY, interval='1h')
    rows.to_parquet('lab/results/scan_discovery_1h.parquet')
    table = []

    for (signal, horizon), group in rows.groupby(['signal', 'horizon']):
        ic = group['ic']
        mean = ic.mean()
        t = mean / (ic.std(ddof=1) / math.sqrt(len(ic))) if ic.std() > 0 else math.nan
        spread = (group['top'] - group['bottom']).mean()
        table.append({
            'signal': signal, 'horizon': horizon, 'ic': mean, 't': t,
            'same sign': f'{int((ic * mean > 0).sum())}/{len(ic)}', 'top - bottom (bps)': spread,
            'sd (bps)': group['sd'].mean()
        })

    table = pd.DataFrame(table).sort_values('t', key=abs, ascending=False)
    pd.set_option('display.width', 200)
    print(f'{len(table)} signal x horizon tests on {len(SYMBOLS)} pairs x 3 years ({DISCOVERY[0]} to {DISCOVERY[1]}):')
    print(table.to_string(index=False, float_format=lambda v: f'{v:.3f}'))
