# The alpha miner

An independent, always-running system that generates formulaic alphas,
follows them on the whole universe, and keeps what it trades up to date as
alphas come and fade. Everything it trades is an ordinary `Combination` of the
trading system (a formula signal followed under the `Target` manager), so it
runs in sessions, portfolios, the collaborator and the dashboard like the
hand-built trend family.

Two versions exist. **Version 2, the breadth miner** (`miner/breadth.py`, the
live service) is the one that runs; it was designed from what version 1 and
the studies after it showed (docs/RESULTS.md, "The alpha miner and the search
for other alphas"). **Version 1** (`miner/miner.py`: genetic search,
incubation, a learned haircut) is kept with its pre-registered replay, below.

## Version 2: the breadth miner

What the evidence says, and what the design takes from it:

| Finding (docs/RESULTS.md) | Design |
|---|---|
| Mining 21 pairs with an evolving search (150,000 trials) picks lucky formulas; their in-sample Sharpe ratio of 3-4 was 0 forward | breadth (78 pairs) and plain random generation: far fewer, simpler trials, each judged on many pairs |
| Formulas chosen on 21 months of 78 pairs (top 20 of 3000) earned 0.69 the next 2.75 years; one family found that way (trading-volume trends, the "high-volume premium") earned 1.27 on 2021 data the search never read | the selected sleeve: the 20 formulas with the best record over the last two years, on all pairs |
| Alphas live for a while: that family was strong in 2022-24 and faded in 2025-26 | the selected sleeve is chosen again every month, so fading formulas drop out |
| Chasing recent winners (any lookback from a week to a year, per pair, exponential weights, an online learner) loses | no short-term selection |
| The plain mean score of hundreds of random formulas, chosen by nothing, earns 0.7-1.0 across seeds and universes: noise averages out, the market's persistent structure (trend, volume) stays; sized by how much the formulas agree it is better (1.21, 2024-26) than normalized (0.47) | the crowd sleeve: 400 random formulas, never chosen by results, refreshed slowly with fresh random ones |
| Trend held on 57 pairs never used (0.87) | the trend sleeve (F2) |

**Pool** (`Breadth.pool`, `daily`): random formulas from the grammar, each
simulated on all pairs (daily-rebalanced target positions, futures costs,
funding); its daily record is extended every day and only read up to the time
of a decision. A search round adds 200 fresh formulas a week.

**Sleeves**, each published as a catalog with its history
(`data/miner/<run>/crowd.json`, `selected.json`), which the trading system
follows by itself (`CatalogSignal`: no warm-up and no flattening when the
catalog changes; a replay trades what the miner traded at each time):

- **crowd**: the mean score of 400 random formulas (sized by their agreement);
  8 replaced by fresh random formulas each month;
- **selected**: the 20 formulas with the best Sharpe ratio over the last 730
  days (with records covering at least nine tenths of them), chosen on the
  first day of each month, traded as a blend normalized to the size of one
  formula;
- **trend**: F2 (system/trend.py).

The full system (`system/mined.py`, the dashboard's "full system") trades the
three on equal capital per pair.

**Walk-forward** (78 pairs, 2024-01 to 2026-10, exact `Target`, futures costs,
funding; `lab/scripts/research_sleeves_exact.py`):

| | Sharpe | Return / y | Volatility | Max drawdown | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| F2 (trend) | 0.60 | 6.1% | 10.2% | -12.7% | 0.99 | -0.07 | 0.82 |
| selected (730 d, 20) | 0.82 | 10.3% | 12.6% | -12.9% | 2.27 | 0.08 | -0.15 |
| crowd (400, by agreement) | 1.21 | 3.6% | 3.0% | -3.3% | 2.23 | -0.44 | 1.27 |
| **all three, equal capital** | **1.02** | **6.7%** | **6.5%** | **-6.4%** | 2.08 | -0.03 | 0.58 |

Correlations: trend / crowd 0.44, trend / selected 0.19, crowd / selected 0.45.
How clean this is: the trend sleeve is a frozen design confirmed on untouched
pairs; the crowd uses no data at all, but its sizing (by agreement rather than
normalized) and size (400 rather than 800, which gave 0.87) were chosen after
seeing both; the selected sleeve's rule (two years, 20 formulas) was fixed
before its walk-forward, but the decision to build on breadth and long windows
came from studies over the same years. Paper trading is the test that remains.

**Running it**: `python -m miner` (or **Start live miner** on the dashboard) runs
the breadth miner live: hourly data for the 78 pairs, daily record extension,
weekly search rounds, monthly reviews; it starts from the replay's record
(`python -m lab.scripts.research_breadth`, `data/miner/breadth`). Trade it with
the dashboard's **full system** (a portfolio of pairs, history or live).

## What the literature says (2026-10)

| Approach | Representative work | What it contributes | Why (not) here |
|---|---|---|---|
| Formulaic alphas | Kakushadze, *101 Formulaic Alphas* (2016) | alphas as short expressions of operators over price/volume | the representation used here |
| Genetic programming | Allen and Karjalainen (JFE 1999); Neely, Weller and Dittmar (1997) | evolves trading rules; on stocks, no excess return after costs out of sample; on FX (1980s-90s) it found some | the search engine, with that warning built in: costs and out-of-sample judgment are part of fitness and selection |
| Pool-aware RL | AlphaGen (Yu et al., KDD 2023) | a policy writes formulas token by token; reward = gain of the *combined pool* | the idea kept: alphas are judged against what is already tracked (correlation gate), not alone |
| Generative + dynamic combination | AlphaForge (Shi et al., AAAI 2025) | a generator for diverse factors, then time-varying weights from recent performance | the dynamic part kept as incubation/promotion/retirement on forward performance |
| GFlowNets, MCTS | AlphaSAGE (ICLR 2026); LLM-guided MCTS (AAAI 2026) | better exploration and diversity of the formula space | QD archive serves the same purpose at a fraction of the machinery |
| LLM agents | Alpha-GPT (2023), AlphaAgent (2025), QuantaAlpha, FactorMiner (2026), RD-Agent | hypothesis-driven generation; AlphaAgent regularizes originality and complexity against decay | not used for generation: an LLM has read the history it would be tested on (look-ahead bias through memorization, Look-Ahead-Bench 2026), and needs credentials. The complexity and originality regularizers are kept |
| Quality diversity | MAP-Elites (Mouret and Clune 2015); QuantEvolve (2025) | keep the best of each *kind* of solution, not one champion | the archive (niches: data family x horizon x turnover) |
| Multiple testing | White (2000), Hansen (2005), Harvey, Liu and Zhu (2016), Bailey and Lopez de Prado (2014) | a mined Sharpe ratio is inflated by the number of trials; walk-forward alone does not fix it | every distinct behavior is a counted trial; deflated Sharpe is recorded; trading needs data the search never saw |
| Alpha decay | McLean and Pontiff (2016) | published anomalies lose about a third to a half out of sample | the haircut is not assumed, it is measured on the miner's own alphas |

The lesson that shapes everything below: a miner is a machine for multiple
testing. An in-sample number from a search over thousands of formulas cannot
be trusted on its own, at any level of deflation that still lets anything
through; only performance on data that did not exist when the alpha was found
is evidence. So the miner is built as a pipeline in time: search, incubate on
new data, trade, retire - and it learns from its own record how much of an
in-sample result survives.

## Version 1: search, incubation, haircut

**Formulas** (`miner/formula.py`, shared by both versions). A typed expression language over hourly
bars, restricted to what the event stream carries: `price` (log close) and
`volume` (log volume) are levels, `ret` (log return) and `flow` (taker-flow
share, 2 x buy / volume - 1) are series. Levels enter only through operators
that make them stationary (`delta`, `zscore`, `dev`, `stoch`); series operators
are windowed (`mean`, `std`, `delay`, `wma`, `max`, `min`, `corr`, plus the
level ones), unary (`neg`, `abs`, `sign`, `slog`, `tanh`) and binary (`add`,
`sub`, `mul`, `div`, `gate`). Windows run from 3 hours to 30 days. Every
operator is causal with a finite window and strict warm-up, so a formula's
value never depends on rows after it and is the same computed over all history
or over the minimal buffer a live indicator keeps (tested to 1e-11). A raw
value becomes a score in [-1, 1] by its root mean square over the last 30
days (clipped at 2 and halved, as `TrendScore`), keeping its sign.

**Search** (`miner/search.py`, `miner/fitness.py`). A round evolves a
population (240) for 10 generations: tournament selection, typed subtree
crossover, mutation (regrow, operator or terminal swap, window step, wrap,
hoist) and fresh random formulas; formulas are simplified and limited to 12
nodes, depth 5 and 45 days of warm-up. Fitness is computed on the training
window (up to the last three years) by a fast, vectorized daily-rebalanced
`Target` at futures costs (taker 5 bps + slippage per side) and actual
funding, on returns **net of their mean over the window** (no credit for
holding the sample's drift). It is the mean Sharpe ratio over four consecutive
folds minus half their spread (consistency) minus 0.02 per node (parsimony).
Formulas whose positions coincide are one behavior: every distinct behavior
counts as a trial. A MAP-Elites archive keeps the fittest formula of each
niche (data family x longest window x turnover) and seeds the next round.

**Incubation**. The best formulas of a round (fitness order) are re-run in the
exact `Target` simulation (`miner/simulate.py`, equal to the framework's
equity to 1e-12), with both rebalancing rules (daily; F2's pullback timing).
A formula starts incubating when its exact in-sample Sharpe ratio is at least
0.8, its P&L is positive on at least 55% of pairs, and its daily P&L
correlates below 0.6 with every alpha already incubating or trading; at most
three a round.

**Judgment** (`miner/stats.py`). From birth on, every alpha is simulated on
bars that came after it. The **haircut** is fitted on the miner's own record:
forward Sharpe = kappa x in-sample Sharpe, through the origin, shrunk to a
prior kappa of 0.25. An alpha's expected Sharpe ratio combines kappa x its
in-sample Sharpe (prior, with the scatter of the fit) and its forward Sharpe
(with its sampling error), each by precision. After 90 forward days an alpha
with expected Sharpe >= 0.5 that correlates below 0.6 with the traded ones
trades (at most 8; a better one replaces the weakest by a margin of 0.25).
A traded alpha whose expectation falls below 0 retires; an incubating one not
promoted within a year is rejected. Retired and rejected alphas are still
followed for two years, so the haircut learns from failures as well.

**Output**. The traded alphas are published in `data/miner/catalog.json`;
`system/mined.py` builds them as combinations (`miner/components.py`: the
`FormulaValue` generator builds hourly bars from the events and evaluates the
formula; `Formula` is the indicator).

## Running version 1

Version 1 is no longer the live service (version 2 is); its runs remain as
experiments: `python -m lab.scripts.research_miner replay|null|planted` (state
in `data/miner/<run>/`, viewable on the dashboard's Miner page). Its catalog
format (`catalog.json`: the traded alphas with their history) is the one
`CatalogSignal` follows, as the breadth miner's sleeves are.

Tests (`tests/test_miner.py`): formula causality and live-buffer parity;
framework parity of single, blended and catalog-following combinations
(normalized or not, over a catalog that changes); search operators; the
haircut; the breadth miner's cycle (search, review, save, load).

## Generating components: the levels

A combination is generators -> indicators -> strategy -> manager, with dynamic
parameters and a collaborator around them. Each level can be generated
automatically; each level added multiplies the search space, and so the
number of trials and the overfitting risk, so they are added in order of how
much new information they bring per trial.

| Level | Generated how | State |
|---|---|---|
| Indicators | formulas over bar fields (`Formula` + `FormulaValue`): the space above; conditional logic inside formulas (`gate`) covers regime filters | built |
| Manager rules | the rebalancing rule (daily, or F2's pullback timing) chosen per alpha in the exact simulation; sizing stays `Target`'s volatility target, a risk budget rather than an alpha | built (two rules) |
| Strategies | combining traded alphas per pair into one position (a blended score, as AlphaForge's "mega-alpha"): positions net out, so opposite calls stop paying costs twice; weights equal, or learned online by the existing `Predictor` (RLS) from forward returns | next: needs its own test (netting changes the traded result) |
| Dynamic parameters | `Target`'s band or scale as `SPSA`/`Bandit` parameters tuned by the feedback bus while trading | possible; on the trend family this did not help (RESULTS.md), so not a priority |
| Generators (data) | new terminals: high-low range, trade counts, funding, open interest, other pairs (cross-asset) | each new terminal needs the event stream to carry it live (the bar stream carries close, volume, taker volume) |
| Code | an LLM writing indicators as code, run in a sandbox and judged like any formula | not used: look-ahead through memorization, credentials; possible later for live-only generation, where every evaluation is forward |

The search itself adapts through its archive (the elites of the last round
seed the next) and its haircut (how much the miner trusts in-sample results is
learned from its own record). Selection is never by in-sample numbers alone.

## Pre-registered replay (written before it was run)

The miner run as if live from 2022-01-03 to 2026-10-05 on the 21 pairs, a step
each Monday 00:00 UTC (review), a search round every fourth step, default
settings above, seed 0, reading only bars closed by each step
(`python -m lab.scripts.research_miner replay`). Reported, whatever they are:
the daily return of the traded alphas (equal weight, real P&L at futures costs
and funding), of every tracked alpha (a diagnostic), F2 on the same 21 pairs,
and equal-weight holding; by year; trials, rounds and the haircut. Added while
the replay was running, before any result was seen: the same traded alphas
blended into one position per pair (`Blend`), which is how the trading system
runs them - chosen because netting cannot cost more than separate positions,
not because of its result; both are reported.

Control: the identical run on a null market, each pair's days shuffled
(`python -m lab.scripts.research_miner null`): the traded alphas must not earn
there; if they do, the pipeline leaks.

Power: the null market with a planted edge, each hour's log return tilted by
0.015 hourly volatilities x the score of `mean(flow, 72)` at the previous close
(`python -m lab.scripts.research_miner planted`; the planted formula itself
earns a Sharpe ratio of 1.31 net over the replay's period, about F2's
strength). The miner should incubate and trade formulas that capture it, and
earn a clearly positive Sharpe ratio; if it does not, the search or the
judgment lacks power at realistic strengths.

Amendment (made while the replay ran, before either control had started):
the two controls run from 2022-01-03 to 2024-07-01 instead of 2026-10, to save
about three hours of computation; their markets are stationary by construction
(shuffled days, a constant planted edge), so the shorter span answers the same
questions with about 30 search rounds each.

The miner's design was fixed before this replay; its settings will not be
tuned on the replay's result. I have seen all of this history (the trend
research), and the formula language can express trend - that prior knowledge
is in the design and is stated here rather than hidden.

### Outcome (2026-10-08)

| 21 pairs, 2022-01 to 2026-10 | Sharpe | Return / y | Max drawdown |
|---|---|---|---|
| Version 1, traded alphas | 0.35 | 2.6% | -11.9% |
| every alpha it tracked | -0.27 | -2.0% | -13.2% |
| F2 trend | 0.69 | 7.9% | -12.9% |

58 rounds, 147,533 distinct behaviors, 24 alphas incubated, 9 traded. In-sample
Sharpe ratios of 3 to 4 were near 0 forward; the learned haircut went from 0.25
to 0.00. The pipeline did what it was built to do - it measured, honestly, that
its own in-sample numbers were worthless and stopped trusting them - but it
found almost nothing: with that many trials on 21 correlated pairs, luck sets
the top of the ranking. Version 2 was built from this (above).

**Controls** (2022-01 to 2024-07). *Planted* (a known edge of Sharpe 1.97 in that span, the null market's returns
tilted by `mean(flow, 72)`): the miner traded 9 alphas, all built on the planted ingredient (`mean(flow, 120)`,
`mean(flow, 48)`...), blended Sharpe **2.63**, its haircut rising to 0.45 - it has power at realistic strengths, and
its haircut of 0 on real data was a reading of the data, not a broken search. *Null*, first run: the traded alphas
earned 1.19 blended, with positive drift-free forward Sharpe ratios - which fails the pre-registered criterion as
written. The cause is the null's construction, not the pipeline: its shuffled days were blocks of the bars closing
00:00 to 23:00, and the daily decision is made at the close of the 23:00-00:00 bar, the first bar of its block, so
each decision saw the first hour of the very day it traded (the intraday relation of that hour to the rest of the
day, and which era the day came from, survive a shuffle of whole days). Corrected (blocks of the bars opening 00:00
to 23:00: a decision sees nothing of the day it trades) and run again: the traded alphas **-0.60** (each alone -0.48,
every tracked alpha -0.69; haircut learned 0.00): nothing earns beyond its costs - no leak. The first run's record is
kept as `data/miner/null_closeblocks`.

## Final pre-registered test of version 2 (written before its data was downloaded)

A third universe never used in any design: the next tier of Binance USDT pairs
listed before 2023 (`lab/scripts/fetch_fresh_wide.py`, about 60 pairs, smaller
and less liquid than the 78), at 5 bps of slippage a side. The frozen design:
F2; the crowd (the first 400 random formulas of seed 11, sized by agreement);
the selected sleeve (each month the 20 best over the last 730 days among the
same 3000 random formulas, simulated on these pairs); equal capital, 2024-01 to
2026-10 (`python -m lab.scripts.research_fresh_system`). Criterion: the
combination's Sharpe ratio is at least 0.5. Reported whatever it is.

**Result: not met.** 57 pairs (ACH, ALICE, API3, ... ZRX), 2024-01 to 2026-10, 5 bps:

| | Sharpe | Return / y | Max drawdown | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| F2 | 0.04 | 0.3% | -15.9% | 0.13 | -0.45 | 0.57 |
| crowd | 0.24 | 0.6% | -5.9% | 1.23 | -1.79 | 0.50 |
| selected | -0.15 | -1.5% | -20.9% | 0.88 | -0.02 | -2.31 |
| **all three** | **-0.04** | -0.2% | -10.7% | 0.80 | -0.52 | -1.24 |

Diagnosis (it does not change the verdict): not costs (F2 0.06 at 2 bps against 0.04 at 5); trend worked on these
same pairs in 2022-23 (0.54) and stopped in 2024-26, while on the 78 it kept working in 2024-26 in every liquidity
third (0.55, 0.54, 0.66, the least liquid third trading a median $0.14M an hour). These pairs trade a median $52k an
hour (52 of 57 under $100k) and are mostly 2021-era tokens in long decline. **The design holds on liquid and mid-sized
coins and does not reach the long tail of thin legacy tokens**: trade the 78 (or pairs like them), not the tail.
