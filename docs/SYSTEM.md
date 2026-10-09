# The trading system

What came out of the research ([RESULTS.md](RESULTS.md), protocol in
[PROTOCOL.md](PROTOCOL.md)): the only edge that survived honest testing,
packaged in the framework, with what to expect from it and how to run it.

## What it does

Multi-day trend following on liquid crypto perpetual futures, with
intraday, event-driven entry timing:

- **Signal** (`TrendScore`): for each pair, the mean over 7, 14 and 28-day
  lookbacks of the volatility-normalized return, each clipped to +-2 and
  halved: a score in [-1, 1] (time-series momentum, Moskowitz, Ooi and
  Pedersen 2012; in crypto, Liu and Tsyvinski 2021).
- **Position** (`Target` manager): score x 2% daily volatility target /
  realized daily volatility (30 days of hourly returns), at most 1x the
  pair's capital, long or short.
- **Timing** (the event-driven part): the position moves toward its target
  only on a pullback (the last 24 hours against the move by more than half a
  daily volatility) or when it is more than 0.5 away; otherwise it waits. This
  improved every test (discovery, holdout, unseen pairs).
- **Costs and accounting:** futures taker fees (5 bps a side), slippage (1 bp a
  side on BTC and ETH, 2 elsewhere), the actual funding history, exact linear
  futures accounting (fixed quantity between changes).
- **Portfolio:** equal capital over the pairs; the collaborator runs with
  `select=False` (every member active at an equal weight), because selecting
  trend members by recent results chases performance.

Code: `pipeline/indicators.py` (`TrendScore`), `pipeline/management.py`
(`Target`), `system/trend.py` (the family; F2 is the system),
`lab/scripts/research_framework.py` (backtests through the framework).

## Evidence

| Test | Data | Sharpe | Return / volatility per year | Max drawdown |
|---|---|---|---|---|
| Discovery (design) | 5 pairs, 2021-2023 | 1.39 | 17.5% / 12.6% | -10.8% |
| Holdout, unseen years (run once) | same 5 pairs, 2024 to 2026-10 | 0.96 | 13.6% / 14.3% | -13.5% |
| Unseen assets (run once) | 8 other pairs, 2021 to 2026-10 | 0.71 | 8.0% / 11.3% | -12.6% |
| All 13 pairs, holdout years | 2024 to 2026-10 | 0.72 | 8.6% / 11.9% | -11.8% |
| Fresh pairs (run once, final) | 8 smaller pairs, 2021 to 2026-10 | 0.43 | 4.8% / 11.3% | -16.6% |

These include funding. The first reports (1.53, 1.02, 0.80, 0.78, 0.50) did
not: `funding_of` read pandas 3's millisecond timestamps as nanoseconds, so
every funding time fell in 1970 and none was ever charged (fixed 2026-10-08;
the vectorized research had funding right). Funding costs F2 about 1% a year.
F2 was positive on 19 of the 21 pairs. The edge is strongest on the most
liquid pairs and weakens down the liquidity ladder; trade the liquid ones.
Losing year: 2025 (-0.1 to -0.7 depending on the universe), a choppy year for
trend following.

## What to expect

- A Sharpe ratio around 0.7 to 1.0 on the most liquid pairs (0.4 on smaller
  ones), not the discovery's 1.4: out-of-sample decay is normal, and the
  holdout and unseen-pair tests are the realistic guide.
- Unlevered, about 8 to 14% a year at 12 to 14% volatility. Returns scale
  with leverage (the volatility target), and so do drawdowns: at twice the
  target, expect drawdowns of 25 to 30%.
- Positively skewed: fewer than half the months are positive; the year is made
  by a few trends. Flat or losing years happen.
- Few trades: the positions change a few times a week per pair; costs are
  about 1% a year and funding about 1% a year.

## Risks

- **Regime:** trend following loses in long choppy periods (2025).
- **Crowding and structure:** crypto markets keep changing; an edge measured on
  2021 to 2026 can weaken.
- **Execution:** slippage on smaller pairs at larger size is higher than
  assumed; funding regimes change.
- **Venue:** exchange, custody and liquidation risks are outside the model. The
  framework never sends orders.

## Operating procedure

1. **Paper trade live** from the dashboard (`python -m server.app`): New run,
   system "trend", source "live", select the pairs, Start portfolio. Each pair
   warms up from its last 60 days of hourly bars and then follows the live
   1-minute candles (priced with the same slippage as the backtests); trades
   and equity from the start are appended to `data/sessions/<group>/<pair>.jsonl`.
2. **Check the implementation** by replaying the same period from stored bars
   (source "history") once it is in the bar files: the paper ledger and the
   replay must agree; any difference is an implementation or data problem.
3. **Judge after at least three months** of paper trading: the realized Sharpe
   ratio and drawdown should sit inside the range of the backtests above. A
   few months cannot prove an edge with a Sharpe of about 1 (the noise of a
   quarter is about +-2 in Sharpe), but they can reveal a broken one.
4. **Go live small** only after that, at a fraction of the intended size, and
   keep the paper portfolio running beside it as the reference.

## Optional overlay: funding carry

Long spot and short perpetual on a pair while its funding is high (C1 in
RESULTS.md) earned 11.8% a year on 2021-2023 and 3.9% on 2024-2026 at very
low volatility in the model (basis and margin not modeled). It is a yield on
idle collateral, uncorrelated with the trend system, not part of it.

## What was ruled out (RESULTS.md)

Microstructure signals (about 1 bp of edge against at least 4 bps of costs);
short-term reversal (real in medians, absent in means); funding as a
crowding signal; the volatility-spike rebound; cross-sectional momentum
(failed its holdout); selection of members by recent results; managed
volatility on top of per-pair targeting.
