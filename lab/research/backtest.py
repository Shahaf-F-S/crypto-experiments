# backtest.py

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from lab.research.scan import bars


__all__ = [
    'COST_BPS',
    'Rule',
    'composite',
    'positions',
    'run'
]


# Round-trip cost: futures taker fees (5 bps a side) plus slippage (1 bp a side on BTC and ETH, 2 on the others).
COST_BPS = {'BTCUSDT': 12.0, 'ETHUSDT': 12.0, 'SOLUSDT': 14.0, 'BNBUSDT': 14.0, 'XRPUSDT': 14.0}


@dataclass(frozen=True)
class Rule:
    """A reversal rule on hourly bars: enter against the composite z beyond `enter`, leave inside `leave` or after `hold`."""

    name: str
    lookbacks: tuple[int, ...] = (4, 12, 24)    # hours
    enter: float = 1.0
    leave: float = 0.25
    hold: int = 24                               # hours
    continuous: bool = False                     # target -z / 2 (clipped to one) instead of all-or-nothing
    band: float = 0.25                           # continuous: rebalance only when the target moves this much
    target_volatility: float = 0.0               # per day, 0: no scaling


def composite(b: pd.DataFrame, lookbacks: tuple[int, ...]) -> pd.Series:
    """Mean over the lookbacks of the log return in units of its typical size (bar volatility over the last week)."""
    x = np.log(b['close'])
    sigma = x.diff().rolling(168, min_periods=72).std()
    return sum((x - x.shift(n)) / (sigma * math.sqrt(n)) for n in lookbacks) / len(lookbacks)


def positions(z: np.ndarray, rule: Rule) -> np.ndarray:
    """The position held over the next bar, decided at each bar's close (fading the composite z)."""
    out = np.zeros(len(z))
    position, age = 0.0, 0

    for t, value in enumerate(z):
        if not math.isfinite(value):
            out[t] = position = 0.0
            continue

        if rule.continuous:
            target = max(-1.0, min(1.0, -value / 2.0))

            if abs(target - position) >= rule.band or (target == 0.0 and position != 0.0 and abs(value) < rule.leave):
                position = target
        else:
            if position != 0.0:
                age += 1

                if abs(value) < rule.leave or age >= rule.hold or value * position > 0 and abs(value) > rule.enter:
                    position, age = 0.0, 0

            if position == 0.0 and abs(value) > rule.enter:
                position, age = -math.copysign(1.0, value), 0

        out[t] = position

    return out


def run(symbol: str, rule: Rule, start: str, end: str) -> pd.DataFrame:
    """Hourly P&L of `rule` on `symbol`: gross, costs, net (fractions of capital), and the position."""
    b = bars(symbol, start, end, '1h')
    r = np.log(b['close']).diff().fillna(0.0).to_numpy()
    z = composite(b, rule.lookbacks).to_numpy()
    held = positions(z, rule)

    if rule.target_volatility > 0:
        daily = pd.Series(r, index=b.index).rolling(168, min_periods=72).std().to_numpy() * math.sqrt(24)
        held = held * np.clip(rule.target_volatility / np.where(daily > 0, daily, np.nan), 0.0, 2.0)
        held = np.nan_to_num(held)

    previous = np.concatenate([[0.0], held[:-1]])
    gross = previous * r                                   # held over bar t, decided at the close of bar t-1
    costs = np.abs(held - previous) * COST_BPS[symbol] / 2e4
    return pd.DataFrame({'gross': gross, 'costs': costs, 'net': gross - costs, 'position': held}, index=b.index)
