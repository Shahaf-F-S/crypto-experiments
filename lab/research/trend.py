# trend.py

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from lab.research.backtest import COST_BPS
from system.history import load_funding
from lab.research.scan import bars


__all__ = [
    'Trend',
    'score',
    'run'
]


@dataclass(frozen=True)
class Trend:
    """
    Time-series momentum on a pair (Moskowitz, Ooi and Pedersen 2012): the trend score is the mean over the
    lookbacks of the volatility-normalized past return, clipped to +-2 and halved (in [-1, 1]); the position is the
    score times target over realized daily volatility, at most `cap`; decided at 00:00 UTC (or every hour with
    `timing`, moving toward the target only on a pullback, or when it is more than `force` away).
    """

    name: str
    lookbacks: tuple[int, ...] = (7, 14, 28)        # days
    target_volatility: float = 0.02                 # per day
    cap: float = 1.0
    band: float = 0.1
    long_only: bool = False
    timing: bool = False
    pullback: float = 0.5                           # timing: 24-hour z against the trend beyond this
    force: float = 0.5


def score(b: pd.DataFrame, lookbacks: tuple[int, ...]) -> tuple[pd.Series, pd.Series, pd.Series]:
    """The trend score, the realized daily volatility (from hourly returns over 30 days), and the 24-hour z."""
    x = np.log(b['close'])
    hourly = x.diff()
    daily = hourly.rolling(24 * 30, min_periods=24 * 10).std() * math.sqrt(24)
    trend = sum(((x - x.shift(24 * d)) / (daily * math.sqrt(d))).clip(-2, 2) / 2 for d in lookbacks) / len(lookbacks)
    short = (x - x.shift(24)) / daily
    return trend, daily, short


def run(symbol: str, rule: Trend, start: str, end: str, warmup_days: int = 60) -> pd.DataFrame:
    """Hourly P&L of `rule` on `symbol` (fractions of capital): gross, costs, funding, net, and the position."""
    from_date = (pd.Timestamp(start) - pd.Timedelta(days=warmup_days)).strftime('%Y-%m-%d')
    b = bars(symbol, from_date, end, '1h')
    trend, daily, short = score(b, rule.lookbacks)
    target = (trend * (rule.target_volatility / daily)).clip(-rule.cap, rule.cap)

    if rule.long_only:
        target = target.clip(lower=0.0)

    target, short = target.to_numpy(), short.to_numpy()
    hours = b.index.hour.to_numpy()
    held = np.zeros(len(b))
    position = 0.0

    for t in range(len(b)):
        wanted = target[t]

        if not math.isfinite(wanted):
            wanted = 0.0

        if rule.timing:
            gap = wanted - position
            against = math.isfinite(short[t]) and short[t] * math.copysign(1.0, gap) < -rule.pullback
            move = abs(gap) > rule.band and (against or abs(gap) > rule.force)
        else:
            move = hours[t] == 0 and abs(wanted - position) > rule.band

        if move:
            position = wanted

        held[t] = position

    r = np.log(b['close']).diff().fillna(0.0).to_numpy()
    previous = np.concatenate([[0.0], held[:-1]])
    gross = previous * r
    costs = np.abs(held - previous) * COST_BPS[symbol] / 2e4

    # Funding: at each funding time the position held pays (long) or receives (short) the rate.
    funding = np.zeros(len(b))

    try:
        rates = load_funding(symbol)
        hourly = rates.groupby(rates.index.floor('1h')).sum().reindex(b.index, fill_value=0.0).to_numpy()
        funding = -previous * hourly
    except FileNotFoundError:
        pass

    frame = pd.DataFrame({'gross': gross, 'costs': costs, 'funding': funding, 'net': gross - costs + funding,
                          'position': held}, index=b.index)
    return frame[frame.index >= pd.Timestamp(start, tz='UTC')]
