# stats.py

import math

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew


__all__ = [
    'summary',
    'probabilistic_sharpe',
    'deflated_sharpe'
]


EULER = 0.5772156649


def summary(daily: pd.Series) -> dict[str, float]:
    """Performance of a series of daily returns (fractions): annualized return, volatility and Sharpe ratio, worst
    drawdown, share of positive months, and the deflation inputs (days, skewness, kurtosis)."""
    daily = daily.dropna()
    equity = (1.0 + daily).cumprod()
    drawdown = (equity / equity.cummax() - 1.0).min() if len(equity) else math.nan
    monthly = (1.0 + daily).groupby([daily.index.year, daily.index.month]).prod() - 1.0
    sd = daily.std()
    return {
        'days': len(daily),
        'annual return': daily.mean() * 365,
        'annual volatility': sd * math.sqrt(365),
        'sharpe': daily.mean() / sd * math.sqrt(365) if sd > 0 else math.nan,
        'max drawdown': drawdown,
        'positive months': float((monthly > 0).mean()) if len(monthly) else math.nan,
        'skew': float(skew(daily)) if len(daily) > 3 else math.nan,
        'kurtosis': float(kurtosis(daily, fisher=False)) if len(daily) > 3 else math.nan,
    }


def probabilistic_sharpe(sharpe: float, benchmark: float, days: int, skewness: float, kurt: float) -> float:
    """
    The probability that the true Sharpe ratio exceeds `benchmark`, given an observed one over `days` daily returns
    with their skewness and (non-excess) kurtosis (Bailey and Lopez de Prado 2012). Sharpe ratios per day here.
    """
    variance = (1.0 - skewness * sharpe + (kurt - 1.0) / 4.0 * sharpe ** 2) / max(days - 1, 1)
    return float(norm.cdf((sharpe - benchmark) / math.sqrt(max(variance, 1e-12))))


def deflated_sharpe(daily: pd.Series, trials: int, trial_sharpes: list[float] | None = None) -> float:
    """
    The deflated Sharpe ratio (Bailey and Lopez de Prado 2014): the probabilistic Sharpe ratio against the best
    Sharpe ratio expected by chance among `trials` independent variants (their spread from `trial_sharpes`, daily,
    when given; otherwise from the sampling error of one). Above 0.95: unlikely to be a selection artifact.
    """
    s = summary(daily)
    days = s['days']
    observed = s['sharpe'] / math.sqrt(365)

    if trial_sharpes and len(trial_sharpes) > 1:
        spread = float(np.std(np.array(trial_sharpes) / math.sqrt(365), ddof=1))
    else:
        spread = 1.0 / math.sqrt(days)

    trials = max(trials, 1)
    expected = spread * ((1.0 - EULER) * norm.ppf(1.0 - 1.0 / trials) + EULER * norm.ppf(1.0 - 1.0 / (trials * math.e))) if trials > 1 else 0.0
    return probabilistic_sharpe(observed, expected, days, s['skew'], s['kurtosis'])
