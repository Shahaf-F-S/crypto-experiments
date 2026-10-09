# Progress

Task board and dated work log for the rebuild ([PLAN.md](PLAN.md)). Newest log
entries first.

## Task board

| Phase | Task | State |
|---|---|---|
| 0 | Snapshot of the code | done |
| 0 | Reset to base classes | done |
| 0 | Plan and research documents | done |
| 1 | Calibration convergence on the database | done ([SYNTHETIC.md](SYNTHETIC.md)) |
| 1 | Synthetic replicas against held-out real data | done |
| 1 | Predictable structure of the real market | done |
| 1 | Synthetic generator v2 reproducing it | done (`simulation/`, [SYNTHETIC.md](SYNTHETIC.md) sections 4 to 6) |
| 2 | Event-loop speed | done (66,000 events/s per combination) |
| 2 | Feedback bus and trade records | done |
| 2 | DynamicParameter family, unit tested | done (Fixed, Tracking, SPSA, Bandit, Scaled) |
| 2 | Base class integration | done |
| 2 | Market, detection and trading behavior | done |
| 2 | Combination, runner, parallel runner | done |
| 4 | Indicators, strategies, managers | first set done ([COMPONENTS.md](COMPONENTS.md)) |
| 5 | Long synthetic runs, fee levels, held-out confirmation | done on synthetic data; then real history (below) |
| 6 | Collaborator v2 | done (selective for short-horizon members, equal-weight for trend members) |
| 7 | Server and dashboard | done ([DASHBOARD.md](DASHBOARD.md)) |
| 8 | Real-history research ([PROTOCOL.md](PROTOCOL.md)) | done: one robust edge, the trend system ([SYSTEM.md](SYSTEM.md)) |
| 9 | Live paper trading of the trend system | ready; to run for at least three months before any capital |
| 10 | Alpha miner ([MINER.md](MINER.md)) | version 2 (breadth miner) running design; version 1 replay done; paper trading of the full system next |

## Log

### 2026-10-08: alpha miner, then the search for other alphas

- Built the alpha miner (docs/MINER.md): formula language, exact `Target` simulator (framework parity 1e-12),
  genetic search with a quality-diversity archive, incubation, a learned haircut, catalogs, the live service, the
  dashboard page. Fixed on the way: funding was never charged in framework runs (pandas 3 time units; F2 corrected:
  discovery 1.39, holdout 0.96, unseen 0.71, fresh 0.43), and the bar stream's first bar never reached generators.
- Its pre-registered replay since 2022: traded alphas 0.35 against F2's 0.69; haircut learned down to 0.
- Then other angles (docs/RESULTS.md): recent-performance rotation, an online learner, calendar effects, BTC
  lead-lag, cross-sectional factors and formulas: none holds. What holds: trend on 57 untouched pairs (0.87), the
  plain mean of random formulas (0.7-1.0, no selection), and selection on long windows across 78 pairs (forward
  0.69; found the trading-volume family, 1.27 on unseen 2021 data, strong in 2023-24, fading in 2025-26).
- Built version 2, the breadth miner, from that: three sleeves (trend, crowd of 400 random formulas, the 20 best
  of the last two years re-chosen monthly) traded on equal capital, each mined sleeve following its catalog live
  (`CatalogSignal`). Walk-forward 2024-01 to 2026-10 on 78 pairs: Sharpe 1.02, 6.7%/y at 6.5% volatility, max
  drawdown -6.4%.
- Its final pre-registered test on a third universe (57 thin, never-used pairs): -0.04, not met; trend itself died
  there after 2023. The design is bounded to liquid and mid-sized coins (the 78). Controls of version 1: the planted
  edge was found (2.63); the first null leaked the decision day's first hour through its own construction, corrected
  and run again.

### 2026-10-08: repository structure

- Research and experimentation moved under `lab/` (scripts, analysis modules,
  results, archive including the pre-rebuild snapshot); the modules the system
  needs from the former `research/` and `experiment/` packages are in
  `system/` (`history`, `bars`, `trend`, `microstructure`). Scripts run as
  modules from the root (`python -m lab.scripts.research_framework holdout`);
  tests pass and the holdout result reproduces exactly.
- Synthetic hourly bars against real ones (`lab/scripts/research_synthetic_bars.py`,
  16 replicas against 98 real 21-day BTC windows): the typical volatility,
  hourly autocorrelation and variance ratio match, but the tails are too thin
  (kurtosis 4.6 against 10.1), high-volatility regimes are missing (95th
  percentile 49 bps an hour against 101), volatility has no memory across
  days, hourly flow does not persist, and there is no multi-day trend. Not a
  replacement for real bars beyond engineering and null tests.

### 2026-10-08: live paper feed fixed

- The paper sessions kept "reconnecting after RequestTimeout ... exchangeInfo":
  every (re)connection downloaded Binance's whole market list (spot plus
  futures), which takes 68 s on this link against a 60 s timeout, five sessions
  at once, on top of five 100 ms order-book streams. Now the spot market list
  is loaded once and cached on disk (`server/live.py`), and trend sessions
  follow the 1-minute candle stream (the backtests' execution model) instead
  of tick books.
- The ledger also held the 60-day warm-up (simulated history); it now starts at
  the session's start. The first paper portfolio's ledger (about 8 hours of
  live paper history mixed with warm-up) is in
  `data/sessions/archive/7a28aa_with_warmup`; the paper record restarted as
  group 79cc89.

### 2026-10-08: real history, the trend system, live paper trading

- The synthetic tests confirmed the framework (planted edges found, no edge
  invented) but the real market's tradable structure had to be measured on
  years of data: Binance hourly klines for 21 pairs and funding history
  (`system/history.py`), a written protocol (discovery 2021-2023, holdout
  2024 on, unseen pairs, deflated Sharpe, stop rule).
- Tried and dropped: reversal families (median, not mean, edge), funding,
  volatility spikes, fading the last hour, cross-sectional momentum (failed
  its holdout), collaborator selection on trend members, managed volatility.
- Kept: multi-day trend following with pullback-timed entries (F2), Sharpe 1.53
  on discovery, 1.02 on the holdout years, 0.80 on unseen pairs, through the
  framework with exact futures accounting (`Target` manager), fees, slippage
  and funding. Write-up: [SYSTEM.md](SYSTEM.md).
- Bugs found by implausible results and fixed: log-return accounting in the
  first vectorized backtest; the collective's mark-to-market and the cost of
  holding periods with `Target`; the bar-gap threshold of the event adapter.
- Dashboard: trend portfolios (one session per pair), history replay, live
  paper trading with a 60-day warm start and a ledger on disk.
- Tests: 23 (`tests/test_target.py` checks the futures accounting).

### 2026-10-07: Phase 5 first results, Phase 7 started (session cut short by usage limit)

- `lab/scripts/test_combinations.py`, no planted edge, 16 seeds x 24 h: at 20 bps every
  combination loses about the fee per trade (-10 to -27 bps per trade); at 4
  bps the trend strategies are about break-even (-5 to +0.5 bps per trade); the
  imbalance control (about 1 bp of edge) loses at both levels (-15 and -2.6 bps
  per trade, 200 to 460 trades a day). The planted-trend and planted-reversion
  scenarios were still running.
- Fixed in `Market`: trades now take the spread of the last book shown, and
  fills are time-ordered inside their interval.
- Added `Adaptive.trail` (trailing stop) for trend capture.
- Next: read the planted-edge results; tune components on train seeds only;
  revise the Phase 5 gate (30-minute strategies make about 15 trades a day, so
  200 trades per run is out of reach: count trades over all held-out runs);
  server app (aiohttp: REST + WebSocket on `Session`), client (no-build ES
  modules), then Phase 6.

### 2026-10-07: Phase 4 components (first set)

- Generators `FlowShare`, `KalmanTrend`; indicators `Threshold` (with
  `Momentum`, `Trend`, `Flow`, `Imbalance`) and `Gauge`; strategies `Follow`,
  `Confirmed`, `Gated`, `Switch`, `Vote`, `Predictor` (online RLS); managers
  `Brackets`, `Adaptive` (volatility brackets, Kelly-scaled stake, reversal
  and time exits). Details in [COMPONENTS.md](COMPONENTS.md).
- Tests (`tests/test_components.py`, 5): the Kalman trend tells a trend from a
  random walk; the predictor learns a planted relation (2.53 for 2.59); the
  manager's brackets and Kelly stake behave as specified.
- Lessons: a threshold controller on a slow signal (z-scores persisting tens of
  minutes) needs an activity measure over about an hour and a slower
  controller; an online predictor with a short memory learns the recent drift
  (an intercept of -15 bps per 30 minutes), so it has no intercept and a long
  memory with shrinkage.
- Experiment harness: `system/microstructure.py` (combinations), and
  `lab/scripts/test_combinations.py` (scenarios: no edge, planted trend, planted reversion;
  fee levels; 16 seeds of 24 hours in parallel).

### 2026-10-07: Phase 1.4 synthetic generator v2

- New package `simulation/` (`rapid_markets` unchanged): a queue-reactive
  touch (Markov chain on bid and ask size buckets, conditioned on the orders in
  each interval and on recent activity), active order flow with a persistent
  sign regime, absorbed trend-following flow, multi-scale activity, empirical
  marginals, five simulated-moment corrections. 220,000 events per second.
- Calibrated on segments 1 to 4 and validated on replicas against them and the
  held-out segment: price, volatility clustering and tails, microstructure
  moves, and the predictive structure at 10 s to 5 minutes match; known
  deviations (contemporaneous impact, imbalance persistence, burstiness) are
  documented. Model: `simulation/btc_usdt.model`; reproduce with
  `python -m lab.scripts.test_synthetic`.
- What failed on the way (kept in SYNTHETIC.md): trade sides conditioned on
  the book double-counted feedback; steering toward a latent efficient price
  caused mean reversion; a slow sign regime that moves the book caused
  momentum the real market does not have.
- Tests: `tests/test_simulation.py` (well-formed events, calibration
  round trip, planted edge).

### 2026-10-07: Phase 2 core framework

- New modules `pipeline/dynamic.py`, `behavior.py`, `combination.py`,
  `runner.py`; base classes extended (`Manager` emits trade records with exit
  reasons and best/worst excursions; `BaseDetector` and `Manager` discover
  their dynamic parameters). Design in [ARCHITECTURE.md](ARCHITECTURE.md).
- Tests (`tests/`): 11 pass. Parameter variants reach known optima and
  targets; behavior measures match `describe()` and the Phase 1 real-data
  measurements; an end-to-end toy combination runs at about 66,000 events per
  second, 8 seeds in parallel at about 250,000.
- Bugs found by the tests and fixed:
  - the PI controller wound up and was a double integrator (it oscillated
    between its bounds); it is now in incremental form;
  - the detection activity measure had a 1-hour half-life, far slower than
    the controller using it, which made it oscillate; call statistics now use
    5 minutes, information coefficients 1 hour;
  - exponential averages without a warm start read zero for a long time;
  - `run_seeds` did not pass options to the workers.
- Profit-rate SPSA is slow by nature (signal-to-noise about 0.1 per window
  pair): it is for slow target adjustment; behavior tracking does the fast
  adaptation.

### 2026-10-07: Phase 1 market data and synthetic validity

- Calibration converges for the book and fill structure (under 5% change over
  the last 25 hours); volatility level and order rate converge but vary 14 to
  21% between 12-hour windows (regimes); volatility dynamics, jumps and side
  persistence are not identifiable from 73 hours.
- Synthetic replicas match real price and activity statistics, including the
  held-out segment; book size medians, burstiness, lag-10 side persistence and
  volatility clustering do not match (causes and fixes in
  [SYNTHETIC.md](SYNTHETIC.md)).
- **Predictable structure:** book imbalance, recent flow and recent returns
  predict the next 10 s to 5 min with the same sign in every sub-sample (touch
  imbalance: correlation 0.24 at 10 s, 0.12 at 1 min); flow and price move
  together (0.5). But the top-decile expected move is about 1 bp, against 20
  bps round trip (4 bps at the cheapest maker level). Nothing is significant
  beyond 15 minutes with 72 hours of data. The calibrated synthetic market has
  none of this structure.

### 2026-10-07: Phase 0

- **Snapshot:** `lab/archive/snapshot_2026-10-07_before_rebuild.zip` holds the
  43 code files of the project as they were (pipeline, experiment,
  rapid_markets, root scripts, reports, the saved calibration), verified byte
  for byte. The database and virtual environment are not included.
- **Reset:** removed every specific indicator (16 classes), strategy (17),
  manager (11), the adaptive and learning strategies, the old collaborator,
  the three experiment systems (intraday, statistical, fast), and the four
  test scripts that depended on them (`test_offline.py`, `lab/scripts/test_synthetic.py`,
  `test_collaboration.py`, and `test_features.py`, which was already broken).
  Also removed the `MUTABLE`/`mutate` mutation support (superseded by dynamic
  parameters).
- **Kept:** generators and filters (features), `compute_features`, targets,
  dataset and analysis utilities, `Detection`, `DetectorStats`,
  `BaseDetector`, `Indicator`, `Strategy`, `Position`, `Entry`, `Exit`,
  `PositionStats`, `Manager`, the `Performance` and `Activity` reports, and
  `test_record.py` and `test_emulate.py`.
- **Check:** the package imports; feature loops run on synthetic data (1 h:
  166,000 events/s generated, 83,000 feature vectors/s with four generators)
  and on the database (1 h: 151,000 events/s read, 79,000 vectors/s). This is
  the speed baseline for Phase 2.

## Findings carried over

From the previous system (details in the snapshot and its reports):

- No strategy showed an edge net of 20 bps round-trip fees over about 91 hours.
- Apparent winners came from a position held across a 15-day recording gap.
  Positions are now closed at the end of every segment.
- Short-horizon member results reversed rather than persisted (correlation of
  consecutive trades -0.60 in one 3-hour window).
- Adopting an open trade on promotion cost about 40 bps per trade (an extra
  fee, and brackets set from the original entry).
- The calibrated synthetic market is a martingale; only planted edges are
  predictable in it.

## Decisions

- **Code documentation:** short docstrings in code; explanations in `docs/`.
- **Synthetic validity before strategy work:** strategies are developed only
  after the real market's predictable structure has been measured and either
  reproduced in the synthetic generator or found absent (PLAN Phase 1).
