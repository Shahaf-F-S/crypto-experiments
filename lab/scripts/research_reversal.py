# research_reversal.py

import pandas as pd

from lab.research.backtest import Rule, run
from lab.research.stats import deflated_sharpe, summary

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
DISCOVERY = ('2021-01-01', '2024-01-01')

# The whole pre-registered family (docs/RESULTS.md): every variant is reported.
RULES = [
    Rule('enter 1.0, hold 24h'),
    Rule('enter 1.5, hold 24h', enter=1.5),
    Rule('enter 1.0, hold 12h', hold=12),
    Rule('continuous', continuous=True),
    Rule('enter 1.0, hold 24h, vol target', target_volatility=0.02),
    Rule('continuous, vol target', continuous=True, target_volatility=0.02),
]


def daily(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].resample('1D').sum()


if __name__ == '__main__':
    results, sharpes = {}, []
    pd.set_option('display.width', 220)

    for rule in RULES:
        per_symbol = {symbol: run(symbol, rule, *DISCOVERY) for symbol in SYMBOLS}
        portfolio = sum(daily(f, 'net') for f in per_symbol.values()) / len(SYMBOLS)
        gross = sum(daily(f, 'gross') for f in per_symbol.values()) / len(SYMBOLS)
        s = summary(portfolio)
        sharpes.append(s['sharpe'])
        turnover = sum(f['position'].diff().abs().sum() for f in per_symbol.values()) / len(SYMBOLS) / (s['days'] / 365)
        results[rule.name] = (portfolio, s, summary(gross)['sharpe'], turnover, {
            symbol: summary(daily(f, 'net'))['sharpe'] for symbol, f in per_symbol.items()
        }, {year: summary(portfolio[portfolio.index.year == year])['sharpe'] for year in (2021, 2022, 2023)})

    print(f'Discovery {DISCOVERY[0]} to {DISCOVERY[1]}, equal weight over {len(SYMBOLS)} pairs, net of costs:')

    for name, (portfolio, s, gross_sharpe, turnover, by_symbol, by_year) in results.items():
        print(f'\n{name}: sharpe {s["sharpe"]:.2f} (gross {gross_sharpe:.2f}), return {s["annual return"]:.1%}/y, '
              f'vol {s["annual volatility"]:.1%}, max drawdown {s["max drawdown"]:.1%}, positive months {s["positive months"]:.0%}, '
              f'turnover {turnover:.0f}x/y, deflated sharpe {deflated_sharpe(portfolio, len(RULES), sharpes):.2f}')
        print('  by pair: ' + ', '.join(f'{k[:3]} {v:.2f}' for k, v in by_symbol.items()) + '   by year: ' + ', '.join(f'{k} {v:.2f}' for k, v in by_year.items()))
