# Synthetic market: calibration, validity, and the real market's structure

Results of [PLAN.md](PLAN.md) Phase 1. Data: BTC/USDT on Binance, recorded
segments 1 to 4 (72.7 hours, 14 September to 2 October 2026) for calibration
and measurement; segment 5 (18.9 hours, 4 to 5 October) is held out. Segment 5
is used here only to validate the generator's market statistics, never for
strategy choices.

Scripts used (kept in the session scratchpad, reproducible from this
description): one pass of `calibrate` over segments 1 to 4 with hourly
estimates, six separate 12-hour calibrations, `describe` on real windows and
on 20 synthetic replicas, and one-second samples of price, book and flow for
the structure analysis.

## 1. Convergence of the calibration

Estimates at growing amounts of data (one pass over segments 1 to 4), the
change over the last 25 hours, and the spread across six separate 12-hour
windows:

| Parameter | 2 h | 8 h | 24 h | 48 h | 73 h | 48 h to end | 12 h windows (cv) |
|---|---|---|---|---|---|---|---|
| tick, levels, book interval | 0.01, 10, 0.1 s | same | same | same | same | 0% | 0% |
| volatility_bps | 3.5* | 5.06 | 4.97 | 4.61 | 4.63 | +0.3% | 3.5 to 5.4 (14%) |
| volatility_of_volatility | 0.6* | 0.68 | 0.54 | 0.49 | 0.42 | -14% | 0.37 to 0.99 (35%) |
| volatility_halflife (h) | 2* | 48 | 4.2 | 2.75 | 2.28 | -17% | 0.9 to 48 (152%) |
| refresh_rate | 0.115 | 0.179 | 0.241 | 0.247 | 0.274 | +11% | 0.07 to 0.24 (31%) |
| jump_rate (per hour) | 0 | 0.14 | 0.10 | 0.09 | 0.11 | +29% | 0 to 0.36 (124%) |
| order_rate | 3.33 | 4.34 | 4.95 | 4.30 | 4.28 | -0.4% | 2.8 to 4.9 (21%) |
| fills_median, fills_sigma | 0.59, 2.17 | 0.71, 2.20 | 0.67, 2.17 | 0.67, 2.20 | 0.62, 2.27 | -9%, +3% | 23%, 6% |
| fill_size_median, sigma | 6.9e-5, 2.94 | 6.9e-5, 2.87 | 6.9e-5, 2.96 | 6.9e-5, 2.98 | 6.9e-5, 2.98 | 0% | 0%, 2% |
| sign_persistence | 0.70 | 0.71 | 0.70 | 0.65 | 0.63 | -3% | 0.57 to 0.71 (9%) |
| touch / depth size medians | 1.42 / 1.2e-3 | 1.40 / 1.3e-3 | 1.50 / 1.5e-3 | 1.62 / 1.4e-3 | 1.70 / 1.4e-3 | +5% / -3% | 10% / 9% |
| size_persistence | 0.97 | 0.95 | 0.95 | 0.95 | 0.95 | 0% | 1% |
| gap_one_tick, gap_mean_ticks | 0.43, 30 | 0.37, 32 | 0.36, 33 | 0.36, 34 | 0.36, 34 | 0% | 2%, 5% |

(*) the generator's default, kept until three complete hours exist.

- **Converged and stable across windows:** the book and fill-size structure.
- **Converged, but varying between windows (14 to 21%):** volatility level
  and order rate. This is genuine regime variation, not estimation noise.
- **Not identifiable from 73 hours:** the volatility dynamics (volatility of
  volatility, its half-life), jumps, the quote refresh rate, and side
  persistence, which falls steadily from 0.71 to 0.63. Their information
  arrives in volatility episodes of several hours, of which 73 hours hold only
  a handful.

## 2. Synthetic replicas against real data

20 replicas of 12 hours from the final estimates, against the six 12-hour
calibration windows (C) and the two halves of the held-out segment (H). The
number is how many of the 8 real windows fall outside the replicas' 5 to 95%
range.

| Statistic | Replicas 5 to 95% | Real windows | Outside |
|---|---|---|---|
| volatility 1 m (bps) | 3.2 to 7.2 | 3.4 to 7.2 | 0/8 |
| volatility 5 m (bps) | 7.0 to 14.9 | 7.4 to 17.8 | 1/8 |
| kurtosis 1 m | 4.1 to 62 | 4.6 to 14.3 | 0/8 |
| quote changes per snapshot | 0.013 to 0.063 | 0.012 to 0.050 | 0/8 |
| trades per second | 23 to 58 | 21 to 47 | 0/8 |
| volatility clustering | 0.01 to 0.20 | 0.13 to 0.39 | 5/8 |
| volatility of volatility | 0.26 to 0.45 | 0.26 to 0.61 | 2/8 |
| wide-spread share | 0.0006 to 0.0007 | 0.0001 to 0.0010 | 6/8 |
| touch size median | 1.67 to 1.72 | 2.2 to 3.3 | 8/8 |
| depth size median | 0.0014 | 0.0003 to 0.0008 | 8/8 |
| trade burstiness (Fano) | 545 to 2,990 | 181 to 301 | 8/8 |
| trade side autocorrelation, lag 1 | 0.905 to 0.911 | 0.876 to 0.936 | 6/8 |
| trade side autocorrelation, lag 10 | 0.69 to 0.71 | 0.82 to 0.88 | 8/8 |
| fill size mean | 0.0055 to 0.0061 | 0.0043 to 0.0071 | 6/8 |

**Price and activity match.** The structural mismatches and their causes:

- **Book sizes:** calibrated by the mean of log sizes, but real sizes are not
  log-normal, so their medians differ. Calibrate by quantiles instead.
- **Burstiness:** the log-normal number of fills per order has too heavy a
  tail when fitted to the share of single fills and the mean. Use a mixture
  (single fills, plus a log-normal) fitted to the share, the mean and the
  second moment.
- **Side persistence at lag 10:** real order flow persists longer. Model the
  side as a Markov chain at the fill level, fitted to lags 1 and 10.
- **Volatility clustering:** stronger and faster than one slow volatility
  factor allows. Add a fast factor (minutes) to the slow one (hours).
- **Window-to-window variation** (wide spreads, fill sizes, activity): the
  real market changes regime and the generator does not. Let these
  parameters drift slowly.

## 3. Predictable structure of the real market

One-second samples of segments 1 to 4 (72 hours; segment 4 split into
halves, giving 4 sub-samples of at least 3 hours). Correlations are between
a signal at time t and the return over the next h; "top decile" is the move
expected when the signal is in its top 10%, about corr x sd(h) x 1.755.

**Return autocorrelation (lag 1, non-overlapping bars):**

| Bar | Pooled | Standard error | Sub-samples |
|---|---|---|---|
| 10 s | **+0.064** | 0.006 | +0.08 +0.11 +0.11 -0.01 |
| 60 s | **+0.036** | 0.015 | +0.05 +0.00 +0.02 +0.06 |
| 5 min | -0.003 | 0.034 | -0.14 -0.07 +0.07 +0.02 |
| 15 min | -0.042 | 0.060 | -0.28 +0.02 +0.02 -0.03 |
| 1 h | -0.133 | 0.123 | -0.06 -0.32 -0.04 |

Variance ratios against 10 s bars average 1.12 to 1.21 (trending) but range
from 0.59 to 2.17 between sub-samples at the 1-hour scale: the character of
the market changes between regimes.

**Predictive correlations (mean over sub-samples, sign agreement):**

| Signal | Next 10 s (sd 2.2 bps) | Next 60 s (5.8) | Next 5 min (12.7) | Next 15 min (22.2) | Next 1 h (44.6) |
|---|---|---|---|---|---|
| book imbalance (touch) | **+0.241**, 4/4, 0.9 bps | **+0.122**, 4/4, 1.2 bps | +0.040, 4/4, 0.9 bps | +0.003 | -0.046 |
| flow share, last 10 s | **+0.092**, 4/4, 0.4 bps | +0.042, 4/4, 0.4 bps | +0.006 | -0.027 | -0.015 |
| micro-price deviation | +0.055, 4/4 | +0.057, 4/4 | +0.029, 4/4 | +0.006 | -0.047 |
| past return (same scale) | +0.089, 4/4 | +0.019 | -0.063, 3/4 | -0.007 | -0.038 |
| flow share, last 60 s | +0.034, 4/4 | +0.010 | -0.014 | -0.035 | -0.131, 4/4 (se 0.12) |

Standard errors: about 0.006 (10 s), 0.015 (60 s), 0.034 (5 min), 0.059 (15
min), 0.118 (1 h).

**Contemporaneous impact:** the return over an interval correlates with the
flow share over the same interval at about **+0.50** (10 s, 60 s and 5 min,
every sub-sample).

**The calibrated synthetic market** shows none of this: every predictive
correlation is within noise of zero (as designed), and its contemporaneous
impact correlation is only about 0.05 against the real 0.50.

### What this means

1. **The real market has robust short-horizon structure.** Book imbalance,
   recent flow and recent returns predict the next seconds to minutes, with
   the same sign in every sub-sample, and order flow moves price
   contemporaneously.
2. **Its economic size is about 1 bp.** The best signal's top-decile move is
   0.9 to 1.2 bps, against 20 bps round trip at spot fees and 4 bps at the
   cheapest (futures maker) level. With a one-tick spread (about 0.0013 bps),
   providing liquidity does not earn a spread either.
3. **Beyond 15 minutes nothing is significant with 72 hours of data.** The
   one-hour standard error (0.12) is as large as the effects reported in the
   literature; months of data would be needed to establish them here. The
   synthetic replicas show chance correlations of 0.2 to 0.4 per sub-sample
   at one hour.
4. **Consequence for testing:** a synthetic generator that reproduces the
   measured structure (imbalance-driven drift, short-term momentum,
   flow-price impact) makes engineering tests realistic for event-based
   features, but by the numbers above it does not make taker trading at 10 to
   20 bps profitable. Profit tests must be read against the fee level, and
   claims at hour horizons need more data.

## 4. How the real market moves (mechanics behind the structure)

Measured on 100 ms snapshots and the trades between them (segments 1 to 4),
before designing generator v2:

- **Price moves are queue depletions.** About 0.4 touch moves per second
  (median 0.26 to 0.36 bps, 90th percentile 1 bp); 98% of the moves go
  toward the near-empty side of the touch (imbalance just before a move
  correlates 0.92 to 0.94 with its direction); 95% come with trades on the
  move's side in the same interval, and those sweeps carry 40 to 67% of all
  traded volume.
- **Moves come in runs.** 60% of moves are followed by another within a
  second, 92 to 94% of those in the same direction; later moves still keep
  the direction 67 to 69% of the time.
- **Order signs have long memory.** Autocorrelation of aggressive-order signs:
  0.29 at lag 1, 0.16 at lag 10, 0.02 at lag 100, still 0.01 at lag 1000
  (an order-splitting signature).
- **Yet prices stay nearly efficient.** Flow persists over minutes and moves
  with price (0.5 at every scale), but past flow does not predict returns
  beyond 10 s; past returns do predict flow (0.05 to 0.07 at 60 s): part of the
  slow flow follows price rather than leading it.
- **Activity clusters at every scale.** Orders per second autocorrelate 0.37
  to 0.52 at 1 s and still 0.05 to 0.17 at 15 minutes.
- **Volatility is superlinear in activity.** Per minute, realized variance
  grows as orders^2 (moves as orders^1.4, mean squared move as orders^0.55).
- **The book is persistent when quiet.** Imbalance autocorrelation at 10 s is
  0.31 to 0.48 in the quietest third of the time and 0.07 to 0.16 in the
  busiest.

## 5. Generator v2: design

Package `simulation/` (`rapid_markets` is unchanged): `MarketModel` (all
parameters and tables), `calibrate` (one pass over a recorded stream, hourly
estimates), `fit` (simulated moments), `Market` (the event stream) and
`structure` (the validation statistics of section 6, the same code for real
and synthetic streams).

| Component | Model | Estimated by |
|---|---|---|
| Touch | Markov chain on (bid size bucket, ask size bucket), 8 x 8 states, one step per book interval; transitions conditioned on the orders in the interval (none, buys, sells, both) and on recent activity (quiet, normal, busy: orders per interval averaged over about 10 s, against the mean, cut at 0.7 and 1.4) | counting, symmetrized (bid/ask mirror), thin cells pooled |
| Moves | hazard of a move per interval by (activity, orders, state); the state after a move by (activity, state); every move comes with a sweeping order; move sizes from the empirical distribution, growing with activity | counting; size elasticity per minute |
| Active flow | each order's sign follows a two-state regime with a memory of about 13 orders, and drives the touch chain | least squares on the order-sign autocorrelation |
| Feedback flow | a share of orders follows the trend of the last minutes (absorbed: it trades, but liquidity providers anticipate it, so it does not move the book) | share fitted to return -> flow at 60 s |
| Activity | three log-normal factors (half-lives 2 s, 5 min, 8 h) multiply the order rate | linear least squares on the autocovariance of orders per second |
| Marginals | fills per order, fill sizes, sweep fills and volume, move sizes, depth sizes and gaps, wide spreads | empirical quantile tables |

**Literature:** queue-reactive order books (Cont, Stoikov and Talreja 2010;
Cont and de Larrard 2013; Huang, Lehalle and Rosenbaum 2015); long memory of
order signs from order splitting (Lillo and Farmer 2004; Lillo, Mike and
Farmer 2005) and the efficiency of predictable flow (Bouchaud et al. 2004;
Farmer, Gerig, Lillo and Mike 2006); feedback trading (De Long, Shleifer,
Summers and Waldmann 1990); activity driving volatility (Clark 1973; Ane and
Geman 2000); simulated moments (McFadden 1989; Duffie and Singleton 1993).

**Simulated moments** (`fit`): five scalars no counting can give, corrected
in turn by short parallel runs (16 seeds x 4 hours, damped multiplicative
steps; activity factors slower than the run are left out, their mean being
one): `boost` (order rate, to the trade rate), `pace` (move hazards, to the
move rate), `hazard_activity` (extra growth of move hazards with activity, to
the per-minute elasticity of moves), `feedback` (to return -> flow at 60 s)
and `scale` (move sizes, to the 1-minute volatility).

**Planted edge** (for engineering tests): `Market(edge_bps=..., edge_halflife=...)`
chooses the direction of some moves after a hidden OU signal, drifting the
price by about `edge_bps` per hour per unit of signal.

**Speed:** about 220,000 events per second in one process.

**Design history** (what failed, kept for the record): a plain imbalance
chain with sides conditioned on the book double-counted the flow-book
feedback (twice the real predictability); conditioning on the expected flow
helped little; steering the chain toward a latent efficient price added
moves and strong mean reversion; an exogenous slow sign regime moving the
book created momentum the real market does not have. The absorbed feedback
flow, the activity levels and the forced sweeps each removed one of the
remaining mismatches.

## 6. Generator v2: convergence and validation

Reproduce with `python -m lab.scripts.test_synthetic` (calibration on segments 1 to 4
with estimates every 6 hours, the simulated-moment fit, the model saved to
`simulation/btc_usdt.model`, then the validation table; about 15 minutes).

**Convergence** (estimates at 6, 24, 48 and 72.7 hours):

| Quantity | 6 h | 24 h | 48 h | 72.7 h |
|---|---|---|---|---|
| volatility 1 m (bps) | 5.35 | 5.92 | 5.77 | 5.71 |
| trades per second | 35.4 | 42.4 | 39.1 | 39.6 |
| quote moves per second | 0.337 | 0.430 | 0.398 | 0.388 |
| active flow regime: strength / memory (orders) | 0.89 / 13 | 0.89 / 12 | 0.76 / 12 | 0.69 / 13 |
| slow order-sign component | 0.24 | 0.26 | 0.23 | 0.19 |
| return -> flow at 60 s | -0.015 | 0.049 | 0.065 | 0.057 |
| activity factors (half-life: sd of log) | 1 s: 0.66, 5 min: 0.50 | 2 s: 0.50, 5 min: 0.40, 8 h: 0.43 | 2 s: 0.54, 5 min: 0.46, 8 h: 0.46 | 2 s: 0.56, 5 min: 0.46, 8 h: 0.42 |

Levels settle within a day and then vary with the regime of each recorded
segment (as in section 1); the flow-regime strength falls from 0.89 to 0.69
as the long segment 4, whose order flow is less persistent, enters. The
transition counts and quantile tables are stable from the first day.

**Simulated moments** (6 rounds of 16 runs of 4 hours): `boost` 0.98, `pace`
0.91, `hazard_activity` 0.06, `feedback` 0.050, `scale` 0.84; the last round
measured volatility 5.70 (target 5.71), trades per second 40.9 (39.6), moves
per second 0.414 (0.388), move elasticity 1.31 (1.33), return -> flow 0.036 to
0.076 across rounds (0.057).

**Validation:** the statistics of `structure` (section 3's analysis and more)
on the calibration segments 2 to 4 (real 1 to 3), the held-out segment 5, and
12 synthetic replicas of 12 hours (5th percentile, mean, 95th percentile):

| Statistic | real 1 | real 2 | real 3 | held out | synthetic 5% | mean | 95% |
|---|---|---|---|---|---|---|---|
| moves per second | 0.45 | 0.44 | 0.37 | 0.21 | 0.29 | 0.46 | 0.65 |
| move median / p90 (bps) | 0.26 / 1.02 | 0.30 / 1.07 | 0.36 / 1.07 | 0.38 / 1.16 | | 0.31 / 1.06 | |
| move sign autocorrelation | 0.69 | 0.67 | 0.67 | 0.66 | 0.58 | 0.60 | 0.62 |
| P(same direction, next move within 1 s) | 0.94 | 0.92 | 0.93 | 0.94 | 0.89 | 0.90 | 0.90 |
| imbalance just before a move | 0.94 | 0.92 | 0.93 | 0.92 | 0.87 | 0.88 | 0.88 |
| volatility 1 m (bps) | 6.1 | 6.1 | 5.6 | 4.2 | 4.4 | 6.2 | 8.1 |
| kurtosis 1 m | 6.2 | 10.3 | 13.1 | 11.7 | 5.0 | 6.6 | 8.8 |
| volatility clustering | 0.22 | 0.31 | 0.30 | 0.25 | 0.14 | 0.23 | 0.29 |
| return autocorrelation 10 s / 60 s | 0.07 / 0.01 | 0.09 / -0.04 | 0.09 / 0.03 | 0.12 / -0.05 | | 0.06 / 0.02 | |
| imbalance IC 10 s | 0.24 | 0.23 | 0.24 | 0.25 | 0.19 | 0.22 | 0.25 |
| imbalance IC 60 s | 0.10 | 0.13 | 0.11 | 0.18 | 0.06 | 0.09 | 0.13 |
| imbalance IC 300 s | 0.03 | 0.05 | 0.02 | 0.09 | -0.02 | 0.04 | 0.10 |
| flow (10 s) IC 10 s / 60 s | 0.07 / 0.02 | 0.08 / 0.04 | 0.10 / 0.05 | 0.14 / 0.12 | | 0.07 / 0.03 | |
| past return IC 10 s / 60 s | 0.08 / 0.00 | 0.08 / 0.00 | 0.10 / 0.05 | 0.11 / 0.00 | | 0.07 / 0.01 | |
| impact 10 s | 0.56 | 0.49 | 0.50 | 0.52 | 0.31 | 0.36 | 0.40 |
| impact 60 s / 300 s | 0.52 / 0.50 | 0.52 / 0.45 | 0.52 / 0.50 | 0.56 / 0.64 | | 0.45 / 0.48 | |
| return -> flow 60 s | 0.048 | 0.057 | 0.065 | 0.068 | 0.009 | 0.068 | 0.123 |
| imbalance autocorrelation 10 s | 0.20 | 0.26 | 0.33 | 0.41 | 0.08 | 0.14 | 0.20 |
| trades per second | 47 | 41 | 38 | 29 | 31 | 46 | 65 |
| trade burstiness | 216 | 191 | 247 | 251 | 94 | 107 | 123 |
| order sign autocorrelation 1 / 10 | 0.46 / 0.24 | 0.39 / 0.19 | 0.20 / 0.12 | 0.17 / 0.09 | | 0.23 / 0.13 | |
| touch size median | 2.2 | 2.2 | 2.5 | 3.2 | | 2.4 | |
| fill size median / mean | 7e-5 / 0.0043 | 7e-5 / 0.0066 | 7e-5 / 0.0061 | 6e-5 / 0.0053 | | 7e-5 / 0.0058 | |

**What matches:** price (volatility, its clustering and fat tails), the
microstructure moves, the predictive structure at 10 s, 60 s and 5 minutes
(imbalance, flow and past return: what strategies can use), flow following
price, impact at 5 minutes, activity and sizes. The held-out segment (quieter,
4.2 bps) sits inside or at the edge of the replicas' range for most
statistics.

**Known deviations** (kept, documented, not tuned away):

- Contemporaneous impact at 10 s and 60 s is lower (0.36 and 0.45 against
  about 0.5): flow and price move together slightly less within a minute.
  It does not affect the predictive statistics above.
- Moves are a little less tied to the touch (0.88 against 0.93) and runs a
  little shorter (sign autocorrelation 0.60 against 0.67). Finer size buckets
  (10, dense at small sizes) did not change either.
- The book imbalance persists less (0.14 against 0.20 to 0.41 at 10 s): an
  imbalance strategy flips more often on synthetic data, so it trades more
  and pays more fees than it would on real data (a conservative bias).
- Trade burstiness is half the real one; book sizes and order-flow
  persistence do not drift between regimes (the real segments differ, e.g.
  order sign autocorrelation 0.17 to 0.46).

**Consequence for testing:** v2 is a faithful null market at horizons beyond
a few minutes (as far as 73 hours can tell) with realistic microstructure.
Strategies that need longer-horizon structure can only show an edge on it
when one is planted (`edge_bps`, trend or reversion), which tests whether
they find an edge, not whether the real market has one.
