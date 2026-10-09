# research_calendar.py

import numpy as np
import pandas as pd

from miner.panel import Panel
from miner.stats import sharpe


# Two kinds of information the formulas cannot see. Time: the mean return of each hour of the day and day of the
# week (pairs pooled, each return in units of its pair's volatility), on discovery and holdout. Cross-asset: does
# BTC's last hour (or day) predict the other pairs' next hour (or day)? Run from the root:
# python -m lab.scripts.research_calendar

SPLIT = '2024-01-01'


def tstat(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    return float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else np.nan


if __name__ == '__main__':
    panel = Panel.load()
    ret = np.diff(np.log(panel.close), axis=0, prepend=np.nan)
    vol = pd.DataFrame(ret).rolling(720, min_periods=240).std().shift(1).to_numpy()
    z = ret / vol
    opened = pd.to_datetime(panel.times, unit='s', utc=True)
    hour, weekday = opened.hour.to_numpy(), opened.weekday.to_numpy()
    discovery = (panel.times < pd.Timestamp(SPLIT).timestamp())[:, None] & np.isfinite(z)
    holdout = (panel.times >= pd.Timestamp(SPLIT).timestamp())[:, None] & np.isfinite(z)

    print('hour of the bar (UTC open): mean vol-normalized return x 100 and t-statistic, discovery | holdout')

    for h in range(24):
        rows = (hour == h)[:, None]
        d, o = z[rows & discovery], z[rows & holdout]
        print(f'  {h:02d}h  {d.mean() * 100:6.2f} ({tstat(d):5.1f}) | {o.mean() * 100:6.2f} ({tstat(o):5.1f})')

    print('\nday of the week: discovery | holdout')

    for k, name in enumerate(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']):
        rows = (weekday == k)[:, None]
        d, o = z[rows & discovery], z[rows & holdout]
        print(f'  {name}  {d.mean() * 100:6.2f} ({tstat(d):5.1f}) | {o.mean() * 100:6.2f} ({tstat(o):5.1f})')

    # Agreement of the hour-of-day pattern between the two periods: the correlation of the 24 hourly means.
    means = [[np.nanmean(z[(hour == h)[:, None] & m]) for h in range(24)] for m in (discovery, holdout)]
    print(f'\ncorrelation of the hourly pattern, discovery vs holdout: {np.corrcoef(means[0], means[1])[0, 1]:.2f}')

    # Lead-lag: BTC's return over the last hour / day against each other pair's return over the next.
    btc = panel.symbols.index('BTCUSDT')
    print('\nBTC leads? correlation of its last return with the other pairs\' next return (pooled), discovery | holdout')

    for span in (1, 4, 24):
        log = np.log(panel.close)
        past = log - np.vstack([np.full((span, log.shape[1]), np.nan), log[:-span]])
        future = np.vstack([log[span:], np.full((span, log.shape[1]), np.nan)]) - log
        rows = np.arange(0, len(log), span)
        for name, mask in (('discovery', panel.times < pd.Timestamp(SPLIT).timestamp()), ('holdout', panel.times >= pd.Timestamp(SPLIT).timestamp())):
            r = rows[mask[rows]]
            x = np.repeat(past[r, btc][:, None], log.shape[1] - 1, axis=1).ravel()
            y = np.delete(future[r], btc, axis=1).ravel()
            ok = np.isfinite(x) & np.isfinite(y)
            own = np.delete(past[r], btc, axis=1).ravel()
            ok2 = ok & np.isfinite(own)
            print(f'  {span:>2}h {name:9s}: BTC-led {np.corrcoef(x[ok], y[ok])[0, 1]:+.4f}, own past {np.corrcoef(own[ok2], y[ok2])[0, 1]:+.4f}  (n={ok.sum()})')
