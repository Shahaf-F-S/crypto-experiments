# Results

Experiment results, newest first. Every number is on synthetic data from the
calibrated generator v2 (`simulation/btc_usdt.model`) unless stated
otherwise. Read them against [SYNTHETIC.md](SYNTHETIC.md): the generator
reproduces the real market's structure up to a few minutes, and has none
beyond that unless an edge is planted.

## The alpha miner and the search for other alphas (2026-10-08)

**Pre-registered miner replay** (docs/MINER.md; `python -m lab.scripts.research_miner replay`): the miner as if live
from 2022-01-03 to 2026-10-05 on the 21 pairs, 58 search rounds, 147,533 distinct behaviors screened, 24 alphas
incubated, 9 traded.

| 21 pairs, 2022-01 to 2026-10 | Sharpe | Return / y | Max drawdown | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| Mined, traded alphas | 0.35 | 2.6% | -11.9% | 0.04 | 0.63 | 0.91 | -0.04 | 0.13 |
| Every alpha it tracked | -0.27 | -2.0% | -13.2% | -0.83 | 0.23 | 0.99 | -0.96 | -0.62 |
| F2 trend (benchmark) | 0.69 | 7.9% | -12.9% | 0.40 | 1.24 | 1.26 | -0.58 | 0.97 |
| Equal-weight holding | 0.26 | 17.1% | -73.3% | | | | | |

In-sample Sharpe ratios of 3 to 4 became forward ratios between -0.96 and 0.88; the learned haircut fell from 0.25 to
0.00 (forward = 0 x in-sample): the miner learned, correctly, that its in-sample numbers carried no information.
Incubation filtered a little (tracked -0.27, traded 0.35), far short of plain trend. The reason: with 150,000 trials
the best in-sample Sharpe ratio is set by luck (3 to 4), real effects here are near 1, so ranking by fitness picks
the lucky formulas; F2-like formulas never ranked high enough to be chosen.

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

**Lifetime of the miner's discoveries** (`lab/scripts/research_lifetime.py`): their mean return by week since birth
is noise around zero from the first week (-9.6, 12.3, -4.6, -7.5, 11.2, -18.5 %/y in weeks 1, 5, 9, 13, 17, 21);
trading every alpha from birth for H weeks: Sharpe -0.4 to 0.3 for every H in 2 to 52, in both halves. No early
life to exploit.

**Persistence of formula performance** (`lab/scripts/research_rotation.py`: 4,000 random formulas, data-free, each
simulated on the 21 pairs; every week the K best of the last L days held for a week): negative for every L in 7 to
365 days and K in 5 to 100 (discovery -1.48 to 0.09), per pair (-1.1 to -1.6), and with exponential weights (-0.4
to -0.7). The 20 best of the last 60 days earn less than the pool in each of the next 26 weeks (week 1: -2.7%/y
against -0.6%). Recent formula performance is luck and short-term market direction, which reverse.

**Online learner** (`lab/scripts/research_learner.py`: each pair's next-day return predicted from the scores of 200
random formulas by a ridge regression with a fading memory, half-life 30 to 365 days): -0.9 to -1.8 on 2021-06 to 2023,
about 0 on 2024-26. The plain mean of the same 200 scores, learned from nothing: **0.68 and 0.88**. Weighting
formulas by their recent record re-introduces the noise the average removed.

**Calendar and lead-lag** (`lab/scripts/research_calendar.py`): the hour-of-day pattern of returns does not repeat
(correlation of the 24 hourly means between 2021-23 and 2024-26: -0.22), weekday signs flip between the periods;
BTC's last 4 hours predict the other pairs' next 4 hours slightly negatively (a reversal weaker than their own,
-0.056 falling to -0.019 in the second period). Nothing tradable at these costs.

**Cross-sectional factors on 78 pairs** (`lab/scripts/research_factors.py`; weekly long-short fifths, market
neutral, futures costs with 4 bps slippage off BTC and ETH, funding): momentum 1, 2, 4 weeks -0.94 / -0.27, -0.76 /
0.09, -0.01 / -0.21; reversal 1 week -0.60 / -0.23; size (small) -0.18 / -0.80; low volatility -0.56 / 0.23;
volume shock -0.03 / -0.52 (2022-04 to 2023 / 2024 to 2026-10). None.

**Cross-sectional formulas** (`lab/scripts/research_cross_formulas.py`: 200 random formulas, daily z-score weights,
21 pairs): the 10 best on 2021-06 to 2023 (all "where the price sits in its 1-4 week range", relative to the
others) earned 1.53, and **1.05 on the 2024-26 holdout**. Applied unchanged to the 57 pairs never used
(`lab/scripts/research_cross_check.py`): **-0.53** (2022-04 to 2026-10), 0.31 on all 78; mixed with F2 it lowers
F2. A false discovery that a time holdout passed and an asset holdout caught.

**The crowd of random formulas** (`lab/scripts/research_ensemble.py`: the plain mean score of N formulas drawn
from the grammar, no data, no selection, daily, futures costs and funding; 2022-04 to 2023 / 2024 to 2026-10):
800 formulas, three seeds: 0.43-0.55 / 0.91-1.01 on the 21 pairs, 0.87-1.02 / 0.66-0.79 on the 57 new pairs; larger
crowds are steadier (50 formulas: -0.07 to 0.90). Correlation with F2 0.4-0.5; with F2 at equal risk 0.81 / 0.89 (21
pairs) and 1.35 / 0.75 (57). 74 of 200 formulas lean with the trend; without every member that leans either way the
crowd keeps a weaker edge (-0.12 / 0.65, 0.20 / 0.29).

**Selection with breadth** (`lab/scripts/research_validation.py`: 3000 random formulas simulated on all 78 pairs
since 2022): their Sharpe ratios on 2022-04 to 2023 and on 2024 to 2026-10 correlate at 0.64 across formulas (0.63
net of market beta, which is near zero for all of them); the decile ranking holds forward (-1.28 for the worst
decile to 0.47 for the best). The 20 best of 2022-23 earned **0.69** in 2024-26 (20 random: -0.08). Requiring the
formula to work on both halves of the pairs adds nothing (0.69): the pairs move together. Simple formulas carry
over better (median forward Sharpe 0.12 for up to 3 nodes, -0.21 for 7 to 12).

**The volume family** (named from that list, then tested on data the selection never read,
`lab/scripts/research_volume.py`): the four simplest volume formulas among the 20 best (`delta(volume, 720)`,
`mean(delta(volume, 336), 504)`, `mean(delta(volume, 120), 720)`, `wma(zscore(volume, 720), 336)`: long when a pair's
trading volume has been rising over weeks, the "high-volume return premium" of Gervais, Kaniel and Mingelgrin
2001) on the 21 pairs, 2021-04 to 2022-03: each 0.50 to 1.52, their mean score **1.27** (drift-free 1.46),
correlation with F2 0.26, with F2 at equal risk 1.84 (F2 alone 1.65). On the 78 pairs it was strong in 2023 (2.97)
and 2024 (2.67) and faded: 2025 0.32, 2026 -1.28.

**Monthly re-selection** (`lab/scripts/research_reselect.py`: each month the K best of the 3000 over the last L
days, on 78 pairs): positive for every L in one to two years and K of 10 or 20 (0.05 to 1.01), nearly all of it from
2024 (1.5 to 2.7); 2025 about 0, 2026 negative. It caught the volume family while it lived and found no successor in
this formula space. Forcing diversity (no two above 0.7) hurts: the winners were one family.

**The three sleeves, as traded** (`lab/scripts/research_sleeves_exact.py`: exact `Target`, the selected sleeve a
normalized blend re-chosen monthly from the pool's record before each month, 78 pairs, 2024-01 to 2026-10): F2 0.60
(6.1%/y, -12.7%), selected 0.82 (10.3%/y, -12.9%), the crowd of 400 sized by agreement 1.21 (3.6%/y at 3.0%
volatility, -3.3%), normalized 0.47 (-20.4%: the average's size is information, normalizing it away scales the
disagreement up), the crowd of 800 by agreement 0.87; **the three on equal capital 1.02** (6.7%/y at 6.5%
volatility, max drawdown -6.4%; 2024 2.08, 2025 -0.03, 2026 0.58). This is the breadth miner's design (docs/MINER.md).

**New fields** (`lab/scripts/research_terminals.py`: 3000 random formulas from a grammar extended with dollar
turnover, the log of price x volume, and the idiosyncratic return, a pair's hourly return minus the mean of all
pairs', on the 78 pairs): the 20 best on 2022-23 earned forward 0.87 using turnover, 0.50 using the idiosyncratic
return, 0.80 using neither; a crowd of 400 formulas using the new fields 0.42 / 0.61 against 0.90 / 0.98 for one
without them. Turnover repeats price and volume; idiosyncratic formulas mostly lose. The grammar stays as it is. This
second random pool reproduces both effects the breadth miner is built on (selection carries forward, 0.80; the
crowd earns, 0.90 / 0.98).

**Final pre-registered test of the breadth miner** (docs/MINER.md; a third universe of 57 smaller pairs never used,
5 bps): the three sleeves on equal capital **-0.04** over 2024-01 to 2026-10 (F2 0.04, crowd 0.24, selected -0.15):
criterion (0.5) not met. F2 had worked on them in 2022-23 (0.54); they trade a median $52k an hour, mostly 2021-era
tokens in long decline, below the least liquid third of the 78, where trend kept working in 2024-26 (0.66). The
design is bounded to liquid and mid-sized coins.

**Trend on 57 pairs never used in any design** (`lab/scripts/research_wide.py`, liquid long-listed USDT pairs
chosen by listing, hourly bars since 2022): F2 Sharpe **0.87**, 8.9%/y, max drawdown -12.7%, positive every year
(2022 1.06, 2023 1.54, 2024 0.86, 2025 0.13, 2026 0.75) and on 52 of the 57 pairs; 0.86 at 4 bps of slippage. On all
78 pairs: 0.85, 8.7%/y at 10.3% volatility (the 21 alone over the same years: 0.72). Trend is a property of the
whole market, and breadth helps it.

## Correction: the framework runs charged no funding (2026-10-08)

`system/trend.py:funding_of` converted the funding history's times with
`index.asi8 / 1e9`, which assumes nanoseconds; pandas 3 loads them in
milliseconds, so every funding time fell in January 1970 and the lookup always
returned zero. Every framework result below was therefore without funding (the
vectorized research in `lab/research/trend.py` had it right). Re-run with
funding (`python -m lab.scripts.research_framework ...`), F2:

| Test | Reported | With funding |
|---|---|---|
| Discovery, 5 pairs, 2021-2023 | 1.53 | 1.39 |
| Holdout, same pairs, 2024 to 2026-10 | 1.02 | 0.96 |
| Unseen 8 pairs, 2021 to 2026-10 | 0.80 | 0.71 |
| 13 pairs, holdout years (miner's exact simulator) | 0.78 | 0.72 |
| Fresh 8 pairs, 2021 to 2026-10 | 0.50 | 0.43 |

Funding costs F2 about 1% a year. The long-only F3 leads F2 on every test of
this re-run (discovery 1.59, holdout 1.16, unseen 0.84, fresh 0.74): noted, not
acted on - F2 was chosen on discovery before any of this, and switching now
would be selection on the holdout (F3 is long a market that rose). A second fix in the same
pass: `compute_features` dropped the events before the first book, so a bar
stream's first bar never reached the generators (only trade-based generators
were affected, none of the trend family).

## Final validation on fresh pairs, and funding carry (2026-10-08)

**Fresh pairs** (ATOM, NEAR, FIL, ETC, UNI, AAVE, XLM, ALGO: fetched only for
this test, never explored; 2021 to 2026-10; run once): F2 Sharpe 0.50, 5.6%/y
at 11.4% volatility, max drawdown -16.3%, positive on 7 of 8 pairs (AAVE
-0.02); F1 0.40, F3 0.87, F4 0.40. The decay is consistent: 1.53 on the
discovery pairs, 1.02 on their unseen years, 0.80 on the next 8 liquid pairs,
0.50 on these smaller ones. Over the 21 pairs F2 was positive on 19.

**C1, funding carry** (long spot, short perpetual, delta neutral, while the
trailing 7-day funding is above 10% a year, out below 3%; both legs at taker
fees plus basis slippage; basis P&L and margin needs not modeled;
`lab/scripts/research_carry.py`, one pre-registered rule): discovery 11.8% a year at 1.6%
volatility (2021 31.5%, 2022 0.2%, 2023 3.6%); holdout 3.9% a year (2024
10.0%, 2025 1.2%, 2026 -0.2%). Real and nearly riskless in this model, but
funding yields have compressed: an optional overlay on idle collateral, not a
trading edge.

## Robustness: F2's timing parameters (2026-10-08)

`python -m lab.scripts.research_plateau`, discovery, 5 pairs, Sharpe ratio of the
portfolio as the pullback threshold (rows) and the force threshold (columns)
vary; F2 uses 0.5 and 0.5, unchanged by this check:

| pullback \ force | 0.25 | 0.5 | 0.75 |
|---|---|---|---|
| 0.25 | 1.49 | 1.57 | 1.56 |
| 0.5 | 1.59 | **1.53** | 1.50 |
| 0.75 | 1.57 | 1.45 | 1.46 |

A plateau (1.45 to 1.59): the result does not hang on a tuned value.

## Refinement tried: managed volatility (2026-10-08), dropped

F5 = F2 with its scale as a `Tracking` dynamic parameter: a slow PI loop
holding the strategy's own realized daily volatility (`RealizedVolatility`,
hourly equity returns over 30 days) at 1% (Barroso and Santa-Clara 2015;
Moreira and Muir 2017). Discovery, 5 pairs: Sharpe 1.20 (F2: 1.53), drawdown
-8.7% (F2: -10.3%), 2022 better (0.93 against 0.71), other years worse. The
per-pair volatility targeting already does most of the work; the book-level
loop lags. Dropped without touching the fresh pairs.

## Breadth and diversification of the trend system (2026-10-08)

**Unseen pairs** (DOGE, ADA, LTC, LINK, AVAX, DOT, TRX, BCH: never used in
design; 2021 to 2026-10, run once with the frozen family): F2 Sharpe 0.80,
9.0%/y at 11.3% volatility, max drawdown -12.6%, positive on all 8 pairs; F1
0.61, F3 0.95, F4 0.52. The edge generalizes to new assets, weaker than on
the pairs it was designed on.

**Equal-weight collaborator over F1 to F4** (`select=False`, unseen pairs):
Sharpe 0.75, about the average of its members (two accounting bugs in the
collective's mark-to-market with the `Target` manager were found by an
implausible first result, 1.23, and fixed: holding periods now include their
opening cost, and the collective marks open trades through
`Manager.open_return`).

**XS1, cross-sectional momentum** (13 pairs, daily: long the top third, short
the bottom third of the 7-day volatility-normalized return, inverse-volatility
weights; one pre-registered variant, `lab/scripts/research_cross.py`): discovery Sharpe
0.93 (2021 1.76, 2022 0.88, 2023 -0.47); **holdout 0.05**, max drawdown -30%.
Its correlation with the trend system is 0.22, and the equal-risk combination
was 1.45 on discovery but **0.62 on the holdout**, below the trend alone (0.78).
Dropped.

**Trend F2 on all 13 pairs:** discovery 1.34 (14.6%/y, volatility 10.9%,
drawdown -9.3%); holdout 0.78 (9.3%/y, volatility 11.9%, drawdown -11.7%;
2024 1.30, 2025 -0.41, 2026 to October 1.26).

**Where this leaves the search:** one robust edge, multi-day trend following
with pullback-timed entries, at an out-of-sample Sharpe ratio of about 0.8 to
1.0. Every year of history has now been seen by it, so its next true test is
the future: paper trading on the live feed (DASHBOARD.md), compared with the
backtest's expectations before any capital is risked.

## Other directions tried on discovery (2026-10-08), all dropped

Tests counted in the deflation: 12 funding signals, 8 demeaned re-tests, 2
families. Scripts: `lab/scripts/research_funding.py`, `lab/scripts/research_families.py`.

- **Funding as a crowding signal** (perpetual funding over 1, 3 and 7 days,
  standardized against its 90-day history, and its level; forward 1, 3 and 7
  days, returns demeaned per pair-year): no edge (|t| at most 1.2, signs mixed).
- **Demeaned re-test of the scan's survivors:** weekly momentum holds (+17,
  +61, +141 bps per unit at 1, 3, 7 days; t 2.4 to 2.7); fading the last hour's
  move over the next day (-28 bps, t -4.2) and the volatility-spike rebound
  (+140 bps over a week, t 3.2) also hold as mean edges.
- **R1, fading the last hour (overlapping 24-hour holds, volatility targeted):**
  Sharpe -1.16 net; the hourly rebalancing costs more than the edge.
- **V1, volatility-spike position held a week:** Sharpe -0.12 net; the mean edge
  does not survive realistic positions.

## Trend family F: discovery and holdout (2026-10-08)

Pre-registered family (`lab/research/trend.py`, `system/trend.py`):
time-series momentum on each pair, the mean over 7, 14 and 28-day lookbacks of
the volatility-normalized return (clipped, in [-1, 1]), position = score x 2%
daily volatility target / realized daily volatility (at most 1x), rebalanced at
00:00 UTC beyond a 0.1 band. F2 moves hourly instead, only on 24-hour pullbacks
against the move (or when 0.5 away); F3 is long only; F4 uses 3, 7 and 14 days.
Futures taker fees (5 bps a side), slippage (1 to 2 bps a side), and the
actual funding history. Run through the framework itself (hourly bar events,
`Target` manager with exact futures accounting: fixed quantity between
changes, cash, funding on notional) with `python -m lab.scripts.research_framework
discovery|holdout`; equal weight over the 5 pairs.

| Variant | Discovery 2021-2023: Sharpe, return/y, max drawdown | Holdout 2024 to 2026-10: Sharpe, return/y, max drawdown | Holdout by year |
|---|---|---|---|
| F1 7/14/28d | 1.27, 18.3%, -10.5% | 0.80, 12.4%, -13.6% | 2024 1.62, 2025 -0.48, 2026 1.15 |
| **F2 pullback timing (primary)** | **1.53, 19.3%, -10.3%** | **1.02, 14.5%, -13.3%** | 2024 1.48, 2025 -0.11, 2026 1.55 |
| F3 long only | 1.76, 17.3%, -9.0% | 1.27, 13.5%, -13.0% | 2024 2.66, 2025 0.63, 2026 0.23 |
| F4 3/7/14d | 1.13, 16.6%, -9.0% | 0.77, 12.1%, -13.2% | 2024 1.73, 2025 -0.73, 2026 1.20 |

Every variant is positive on every pair in both periods (holdout, F2: BTC 0.92,
ETH 0.88, SOL 0.43, BNB 0.80, XRP 0.79). Deflated Sharpe on discovery (4
variants): 0.94 to 0.98. F2 was chosen as primary on discovery, before the
holdout; the holdout was run once for the family.

**Collaborator over the family (discovery):** Sharpe 0.21. Selecting members
by the t-statistic of their recent holding periods chases performance: trend
returns are positively skewed (many small losses, a few large gains), so
members are demoted right before their gains. Dropped for trend members (stop
rule): diversification across pairs, not selection, is what holds up.

**Accounting note:** a first vectorized version multiplied positions by log
returns, which understates a long position's P&L by the convexity term (about
r^2/2 per hour); the framework's exact futures accounting is the reference.

## Real history, discovery period (2026-10-08)

Data: Binance spot hourly klines, BTC, ETH, SOL, BNB and XRP against USDT,
2021-01-01 to 2023-12-31 (discovery; [PROTOCOL.md](PROTOCOL.md)). Scripts:
`lab/scripts/research_scan.py`, `lab/scripts/research_tradable.py`, `lab/scripts/research_reversal.py`,
`lab/scripts/research_trend.py`.

**Scan 1, rank correlations (70 tests: 14 signals x 5 horizons):** returns
over the last 1 to 24 hours predict the opposite sign over the next 4 to 24
hours in every one of the 15 pair-years (Spearman IC -0.04 to -0.08, t of -7
to -10). Intraday horizons (1 hour) carry 1 to 4 bps: nothing to trade.

**Reversal family (6 pre-registered rules on the composite of 4, 12 and 24-hour
returns):** gross Sharpe ratios -0.63 to +0.02, net -0.86 to -2.37; every
variant loses on every pair and in every year. The reason: the reversal lives
in the medians (BTC, z between -1.5 and -1: median next-day return +35 bps),
while the means are flat or reversed because the largest moves continue (z
above 2: mean next-day +37 bps on BTC, +111 on SOL). A position earns the
mean. Rank correlation was the wrong yardstick; dropped by the stop rule.

**Scan 2, mean-based (56 tests: the P&L of a position proportional to the
clipped signal):** no signal at 4 hours clears costs (at most about 5 bps per
trade per unit position against 12 bps). At one day, fading the last hour or
day earns about 20 to 27 bps per unit (t about -3 to -4, 12 of 15 pair-years).
At days to a week, momentum over a week earns +29 bps (1 day ahead), +94 (3
days) and +216 (a week), in 12 to 14 of 15 pair-years, and a recent volatility
spike precedes a positive week (+91 bps, t 4.7). This is time-series momentum
(Moskowitz, Ooi and Pedersen 2012; in crypto, Liu and Tsyvinski 2021), not an
intraday effect; on perpetual futures held for days, funding must be counted.

## Run 1: combinations alone (2026-10-07)

`python -m lab.scripts.test_combinations`: the 8 combinations of `system/microstructure.py`,
16 seeds x 24 hours per scenario, fees per round trip (half on each side).
Net per trade and P&L per day in bps; "positive" is the share of runs that
made money. (The Sharpe column of this first run was annualized from 15-minute
equity samples inside one day, which is meaningless; the script now reports
the Sharpe ratio of daily P&L across runs.)

| Scenario | Combination | 20 bps: trades/day, net/trade, P&L/day, positive | 4 bps: trades/day, net/trade, P&L/day, positive |
|---|---|---|---|
| no edge | momentum 30m | 15, -11.6, -191, 6% | 17, -0.4, -8, 31% |
| | momentum 30m + flow | 17, -9.8, -187, 6% | 18, 0.0, +1, 31% |
| | kalman trend | 14, -12.0, -190, 6% | 16, -1.4, -23, 31% |
| | momentum 2h gated | 9, -19.9, -204, 19% | 10, -5.2, -56, 19% |
| | reversal 30m | 12, -16.0, -206, 0% | 12, -3.6, -46, 25% |
| | switch 30m | 17, -12.6, -230, 0% | 17, -2.4, -45, 19% |
| | predictor 30m | 2.5, -27.4, -75, 19% | 21, +0.5, +11, 38% |
| | imbalance 10s | 202, -14.9, -3312, 0% | 460, -2.6, -1304, 0% |
| planted trend (20 bps/h per unit, half-life 2 h) | momentum 30m | 14, +2.3, +34, 44% | 15, +16.2, +270, 81% |
| | momentum 30m + flow | 16, +3.3, +57, 44% | 18, +14.1, +272, 69% |
| | kalman trend | 15, +1.9, +31, 50% | 17, +12.6, +232, 62% |
| | momentum 2h gated | 8, +16.1, +144, 50% | 9, +28.6, +271, 56% |
| | reversal 30m | 12, -33.2, -429, 0% | 12, -19.6, -256, 0% |
| | switch 30m | 18, -8.4, -164, 6% | 19, +2.6, +55, 56% |
| | predictor 30m | 10, +20.9, +228, 62% | 29, +13.7, +432, 75% |
| | imbalance 10s | 202, -14.3, -3167, 0% | 461, -2.6, -1307, 0% |
| planted reversion (20 bps/h per sd, half-life 1 h) | momentum 30m | 23, -15.5, -398, 0% | 25, -7.5, -203, 0% |
| | momentum 30m + flow | 26, -13.9, -396, 0% | 27, -6.6, -198, 0% |
| | kalman trend | 20, -19.3, -414, 0% | 20, -10.0, -224, 0% |
| | momentum 2h gated | 12, -19.1, -245, 0% | 12, -6.5, -85, 0% |
| | reversal 30m | 16, -4.3, -75, 6% | 16, +9.5, +165, 81% |
| | switch 30m | 21, -6.0, -137, 6% | 21, +2.7, +63, 56% |
| | predictor 30m | 2.4, +3.5, +9, 31% | 26, +10.3, +297, 94% |
| | imbalance 10s | 135, -17.7, -2629, 0% | 328, -3.3, -1184, 0% |

**Reading:**

- Without an edge every combination loses about its fees: the framework does
  not invent an edge, and the realistic microstructure (about 1 bp) does not
  pay even 4 bps.
- With a planted edge the matching strategies find it (trend strategies on the
  trend, reversal on the reversion), and the mismatched ones lose more than the
  fees: the edge is real and the right side of it matters.
- The online predictor is the only combination that adapts to either kind of
  edge and mostly stands down without one at 20 bps (2.5 trades a day): it
  learns the sign of the structure.
- The variance-ratio switch does not tell the regimes apart well enough.
- Choosing among combinations by their behavior and results is the
  collaborator's job (run 2).
