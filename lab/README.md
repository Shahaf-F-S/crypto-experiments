# lab

Research and experimentation: everything that produced the findings in
`docs/` but is not needed to run the system. Nothing outside `lab/` imports
from it. Run scripts as modules from the repository root, so that relative
paths (`data/`, `database/`, `simulation/`) resolve:

```bash
python -m lab.scripts.research_framework holdout
```

## scripts/

| Script | What it does | Results |
|---|---|---|
| `fetch_klines.py`, `fetch_funding.py`, `fetch_more.py`, `fetch_fresh.py` | download Binance hourly klines and funding history for the pair groups into `data/` | |
| `research_scan.py` | rank-correlation scan of 14 signals x 5 horizons (discovery) | RESULTS.md, real history |
| `research_tradable.py` | mean-based (tradable) scan | RESULTS.md |
| `research_reversal.py` | reversal family (6 rules) | RESULTS.md |
| `research_trend.py` | trend family, vectorized (first version, log-return accounting) | superseded by `research_framework.py` |
| `research_framework.py` | the trend family through the framework (`discovery`, `holdout`, `full`; `unseen`, `fresh` pairs; `collaborate`) | RESULTS.md, SYSTEM.md |
| `research_funding.py` | funding as a crowding signal | RESULTS.md |
| `research_families.py` | R1 (fading the last hour) and V1 (volatility spike) | RESULTS.md |
| `research_cross.py`, `research_portfolio.py` | cross-sectional momentum, and its combination with the trend | RESULTS.md |
| `research_carry.py` | funding carry (long spot, short perpetual) | RESULTS.md |
| `research_plateau.py` | robustness of F2's timing parameters | RESULTS.md |
| `research_synthetic_bars.py` | synthetic against real hourly bars | PROGRESS.md |
| `test_synthetic.py` | calibrate, fit and validate synthetic generator v2 on the tick database | SYNTHETIC.md |
| `test_combinations.py` | tick-level combinations on synthetic seeds (no edge, planted trend, planted reversion) | RESULTS.md, run 1 |
| `test_collaborator.py` | the collaborator on synthetic seeds | RESULTS.md |

## research/

Analysis modules used by the scripts: `scan` (signals, scans), `stats`
(performance summaries, probabilistic and deflated Sharpe ratios),
`backtest` (reversal rules, costs), `trend` (vectorized trend backtest),
`families` (R1, V1, a fixed-quantity simulator).

## experiment/

The earlier experiment helpers (`pair`, `select`, `report`, `Performance`,
`Activity`).

## results/, archive/

Saved scan tables; the pre-rebuild code snapshot
(`snapshot_2026-10-07_before_rebuild.zip`), the old v1 synthetic calibration,
and the old intraday report.
