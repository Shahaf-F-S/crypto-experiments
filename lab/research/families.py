# families.py

import math

import numpy as np
import pandas as pd

from lab.research.backtest import COST_BPS
from system.history import load_funding
from lab.research.scan import bars


__all__ = [
    'target_reversal',
    'target_spike',
    'simulate'
]


def _daily_volatility(x: pd.Series) -> pd.Series:
    return x.diff().rolling(24 * 30, min_periods=24 * 10).std() * math.sqrt(24)


def target_reversal(b: pd.DataFrame, hold: int = 24) -> pd.Series:
    """R1: fade each hour's move (its z, clipped to +-2, halved) for `hold` hours, overlapping (mean of the last `hold`)."""
    x = np.log(b['close'])
    hourly = x.diff()
    sigma = hourly.rolling(24 * 7, min_periods=24 * 3).std()
    z = (hourly / sigma).clip(-2, 2) / 2
    return -z.rolling(hold).mean() * math.sqrt(hold)     # a sum of `hold` such calls scaled to unit size


def target_spike(b: pd.DataFrame) -> pd.Series:
    """V1: the volatility spike (log of 1-day over 30-day volatility, clipped to +-2, halved), held as a slow position."""
    x = np.log(b['close'])
    hourly = x.diff()
    spike = np.log(hourly.rolling(24).std() / hourly.rolling(24 * 30, min_periods=24 * 10).std())
    return (spike / 0.5).clip(-2, 2).rolling(24 * 7).mean() / 2


def simulate(symbol: str, score: pd.Series, b: pd.DataFrame, target_volatility: float = 0.02, cap: float = 1.0,
             band: float = 0.1) -> pd.DataFrame:
    """
    Hourly decisions, exact linear-futures accounting (fixed quantity between changes): the position moves to
    score x target / daily volatility (at most `cap`) when more than `band` away; taker fee and slippage on the
    change, funding on the notional.
    """
    x = np.log(b['close'])
    daily = _daily_volatility(x)
    target = (score * target_volatility / daily).clip(-cap, cap).to_numpy()
    price = b['close'].to_numpy()
    cost = COST_BPS[symbol] / 2e4 if symbol in COST_BPS else 7e-4

    try:
        rates = load_funding(symbol)
        funding = rates.groupby(rates.index.floor('1h')).sum().reindex(b.index, fill_value=0.0).to_numpy()
    except FileNotFoundError:
        funding = np.zeros(len(b))

    cash, quantity, equity = 1.0, 0.0, np.empty(len(b))

    for t in range(len(b)):
        p = price[t]
        cash -= quantity * p * funding[t]
        value = cash + quantity * p
        wanted = target[t]

        if math.isfinite(wanted) and value > 0:
            held = quantity * p / value

            if abs(wanted - held) > band:
                new = wanted * value / p
                cash -= (new - quantity) * p + abs(new - quantity) * p * cost
                quantity = new
                value = cash + quantity * p

        equity[t] = value

    return pd.DataFrame({'equity': equity}, index=b.index)
