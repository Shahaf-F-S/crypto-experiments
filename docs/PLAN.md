# Rebuild plan: an adaptive intraday trading system

This is the master plan for the rebuild that started on 2026-10-07. It covers
every request made for the rebuild, the order of the work, the design, and the
criteria for moving from one phase to the next. Progress is tracked in
[PROGRESS.md](PROGRESS.md). The method survey behind the design is in
[RESEARCH.md](RESEARCH.md).

**Goal:** a dynamic trading system that adapts to the market and generates
profits reliably, from direct market events (`Book` and `Trade` objects).

---

## 1. Requests covered by this plan

Every request is listed here once, with the section that answers it.

| # | Request | Where |
|---|---|---|
| R1 | Compress a snapshot of the current code and save it aside; `rapid_markets` stays as it is | §3 Phase 0 |
| R2 | Remove unused managers and strategies, then start over from the base classes only (same structure and architecture) | §3 Phase 0, §4.1 |
| R3 | Research proven methods for steady, stable intraday crypto trading from direct events, in the direction of dynamic control, optimization and statistical prediction | [RESEARCH.md](RESEARCH.md), §3 Phase 3 |
| R4 | New indicators matching that research (alongside modified existing ones), and new strategies in that spirit | §3 Phase 4, §4.6 |
| R5 | Feedback-based parameter correction: a `DynamicParameter` class with a current value and an update from trading results, an internal evaluation mechanism, a shared information-carrying mechanism, used by strategies and managers (base and child classes), with variants for control, optimization and statistics | §3 Phase 2, §4.2 to §4.4 |
| R6 | Extract the `SyntheticMarket` inputs from the BTC/USDT data in the database over several hours, check that they converge, synthesize from them and check that the result matches; then test on synthetic data, in parallel with different seeds | §3 Phase 1 |
| R7 | Well-documented numerical measures of market behavior, matched to the `SyntheticMarket` inputs where that is meaningful | §3 Phase 2, §4.5 |
| R8 | Characterize each strategy's detection behavior and each manager's trading behavior, beyond performance; adjust dynamic parameters from the differences between market, detection and trading behavior, even without trades | §3 Phase 2, §4.5 |
| R9 | Test on meaningful synthetic data, fast; correct without overfitting | §3 Phase 5, §5 |
| R10 | Once several combinations work on many long synthetic runs (enough trades, good Sharpe ratio): a dynamically optimized collaborator with warm-up, paper and active modes, moving combinations in both directions by performance and by behavior matching | §3 Phase 6, §4.8 |
| R11 | A modern, fast web dashboard (client) and a server that runs tests and simulations (live, database, synthetic) and streams every detail | §3 Phase 7, §4.9 |
| R12 | This plan, plus separate working documents (not long docstrings in code) used as the reference for progress and remaining tasks | §6 |

---

## 2. Starting point and constraints

What the previous system established (details in the snapshot and in
[PROGRESS.md](PROGRESS.md#findings-carried-over)):

- **No strategy had an edge net of fees** over the roughly 91 recorded hours.
  The apparent winners came from a position held across a 15-day recording gap
  (fixed by closing positions at the end of each segment).
- **Costs dominate.** The default fee is 0.1% per side (20 bps round trip). The
  BTC/USDT spread is one tick (about 0.0013 bps), so the fee is the whole cost.
  The typical 1-minute move is about 4 bps and the typical 1-hour move about
  30 to 60 bps, so a trade must target moves of many minutes to an hour to pay.
- **Results of individual strategies did not persist** in the last measured
  window (correlation of consecutive trades of a member: -0.60), and recent
  literature reports reversal at 1 to 4 hour horizons in Bitcoin.
- **The calibrated synthetic market is a martingale.** By construction nothing
  in it is predictable, so no strategy can earn there except by luck or from a
  planted edge. Synthetic testing is meaningful only once the predictable
  structure that real data actually has (if any) is measured and reproduced.
  This is the main risk of the plan and is handled in Phase 1.

Fixed constraints:

- `rapid_markets/` is not modified (it already contains `SyntheticMarket`,
  `calibrate` and `describe`).
- The architecture stays: generators compute features from events
  (`compute_features`), indicators and strategies detect, managers open and
  close positions, and tests are scripts with one visible main loop.
- Code carries short docstrings only; explanations go into `docs/`.

---

## 3. Phases

Each phase ends with a check recorded in [PROGRESS.md](PROGRESS.md). A phase
starts only once the previous phase's acceptance criteria are met, unless
noted.

### Phase 0: snapshot and reset (R1, R2)

1. Compress the current code (everything except the database and the virtual
   environment) to `lab/archive/snapshot_2026-10-07_before_rebuild.zip` and
   verify it byte for byte. **Done.**
2. Remove every specific indicator, strategy, manager, and the systems and
   collaborator built on them. Keep: generators (features), `compute_features`,
   targets, `Detection`, `BaseDetector`, `Indicator`, `Strategy`, `Position`,
   `Entry`, `Exit`, `PositionStats`, `Manager`, and the metrics helpers. The
   snapshot keeps everything removed.
3. Keep the old test scripts out of the root (they import removed code); new
   entry points are written per phase.

Acceptance: the package imports, and a plain feature loop runs on database
and synthetic data.

### Phase 1: market data and synthetic validity (R6, R7 first part)

1. Run `calibrate` on the BTC/USDT database over growing windows (2, 4, 8, 12,
   24 hours and everything), and record how each estimate converges (relative
   change between windows, and the spread across separate windows of the same
   length).
2. Synthesize markets from the converged estimates, with several seeds, and
   compare them with held-out real data with `describe` (percentile of each
   real statistic among the replicas).
3. **Measure the predictable structure of the real market**, the part that
   decides whether synthetic testing can mean anything:
   - return autocorrelation and variance ratios at 10 s to 4 h;
   - the response of later returns to order-flow imbalance and to book
     imbalance (lead-lag regressions, with out-of-sample checks);
   - the persistence of order-flow sign and its decay;
   - how these vary over time (regimes).
4. If real predictable structure is found, extend the synthetic generator to
   reproduce it (calibrated, not invented): for example a slowly varying
   "alpha" component of the efficient price driven by order flow, with
   strength and persistence fitted to the measurements, and regime switching.
   If none is found, synthetic data is used only for engineering tests and
   for planted, time-varying edges that check whether the adaptive machinery
   can find and track an edge. It is not used for claims of profitability.

Acceptance: estimates converge (relative change under 10% between the last
two windows for the stable parameters); real statistics fall inside the
replica bands except for documented, understood differences; the predictable
structure is measured and either reproduced or documented as absent.

### Phase 2: core framework (R5, R7, R8)

1. **Speed.** Profile and speed up the event loop: a fast path in
   `BaseGenerator.get`, decisions on book snapshots or a decision clock rather
   than every trade, and multiprocessing over seeds. Target at least 10,000
   events per second for one combination, and linear scaling over CPU cores
   for seeds.
2. **Feedback bus and records.** A `Feedback` object per combination carries
   everything the adaptive parts need: trade openings and closings, with the
   values every dynamic parameter had at the entry; the market behavior; the
   strategy's detection behavior; and the manager's trading behavior (§4.2).
3. **`DynamicParameter` family** (§4.3): a base class with a current value,
   bounds, a history, an internal evaluation, and update hooks for trade
   outcomes (`on_close`) and for behavior (`observe`, frequent, works without
   trades). Variants: fixed, PI controller (behavior tracking), SPSA (gradient
   from paired perturbed trades), Thompson sampling over a value grid
   (discounted, for non-stationarity), Kalman-tracked optimum, and
   volatility-scaled values. Each is unit tested on problems with a known
   answer before use.
4. **Base class integration.** `Strategy`, `Indicator` and `Manager` discover
   their dynamic parameters (fields of child classes included), attach them
   to the combination's feedback bus, and record their values at each entry.
5. **Behavior measurement** (§4.5): `MarketBehavior` (online, shared by all
   combinations on a stream), `DetectionBehavior` (per strategy) and
   `TradingBehavior` (per manager), plus alignment measures between them.
6. **Combination and runner**: a `Combination` (strategy, manager, feedback,
   behaviors), a runner for one source, and a parallel runner over seeds that
   returns summaries and telemetry.

Acceptance: unit tests pass (each parameter variant reaches the known optimum
or target within tolerance on noisy test problems); a combination runs on
database and synthetic data at the target speed; behavior measures are
checked against known synthetic inputs.

### Phase 3: research (R3)

Done before Phase 4 and kept up to date in [RESEARCH.md](RESEARCH.md): methods
for event-based intraday crypto trading, ranked by fit to this project's cost
structure, with the dynamic control, optimization and statistical prediction
methods that adapt them.

### Phase 4: components (R4, R5, R8)

1. Indicators from the research (§4.6): order-flow imbalance (Cont, Kukanov
   and Stoikov), micro-price deviation, trade-flow toxicity (VPIN-like),
   self-exciting trade intensity, volatility-normalized multi-horizon
   momentum, Ornstein-Uhlenbeck deviation, variance-ratio regime, Kalman trend,
   changepoint drift. Existing generators are reused where they fit.
2. Strategies: intraday time-series momentum with flow confirmation, reversal
   after large moves, regime-gated switching between the two, a learned linear
   predictor of net forward returns, and flow-timed entries. Every threshold,
   scale and gate is a dynamic parameter.
3. Managers: adaptive bracket (take-profit and stop-loss in volatility units,
   optimized from outcomes), volatility-targeted size with fractional Kelly,
   adaptive trailing stop, and an adaptive time stop.
4. Each component's dynamic parameters are paired with suitable variants
   (for example: entry threshold by PI control of the detection rate toward a
   target that is itself optimized by SPSA from outcomes; take-profit and
   stop-loss by Thompson sampling over a grid; size by volatility targeting).

Acceptance: each component has a unit test on synthetic data with a planted
property it must detect or exploit.

### Phase 5: testing and correction (R9)

1. Long runs on synthetic data (many seeds, in parallel), at several fee levels
   (20, 15, 10 and 4 bps round trip, see [RESEARCH.md](RESEARCH.md#costs)).
2. Train/test discipline against overfitting: design choices are made on one
   set of seeds and judged on another; nothing is tuned on the held-out real
   segment, which is used once, at the end, for confirmation.
3. Corrections are made to rules (how a parameter adapts), not to fitted
   numbers for particular data.

Acceptance (the gate for Phase 6): at least three combinations, each with at
least 200 trades per run and an annualized Sharpe ratio above 1.5 net of fees
on at least 80% of held-out seeds, and not losing on the held-out real data.

### Phase 6: collaborator (R10)

A collaborator over combinations with three modes: warm-up (adaptive
parameters learn, no evaluation), paper (evaluated, no capital), active (real
capital). A combination moves up when its paper performance and its behavior
alignment with the market are both good, and moves down when either fails;
behavior mismatch acts faster than trade results, since it is measured
continuously. Capital shares are optimized online (§4.8).

Acceptance: on held-out seeds, the collaborator's Sharpe ratio beats the
average of its members and the best member chosen in hindsight is not needed.

### Phase 7: server and dashboard (R11)

A server that runs simulations and live paper trading and streams telemetry,
and a web client that controls runs and shows everything live (§4.9).

Acceptance: a run can be started, watched and stopped from the browser on
each source (live, database, synthetic), with every panel of §4.9 updating
live without slowing the run noticeably.

### Phase 8: real-history research (added 2026-10-08)

Synthetic data reproduces the real market only up to minutes, and there the
only structure is about 1 bp, which no fee pays (Phase 1). The Phase 5 gate
was therefore unreachable on honest data, and the search moved to years of
real bars under a written protocol ([PROTOCOL.md](PROTOCOL.md)): discovery
2021-2023, holdout 2024 on, unseen pairs, deflated Sharpe ratios, a stop
rule. Outcome: one robust edge, multi-day trend following with pullback-timed
entries ([SYSTEM.md](SYSTEM.md), [RESULTS.md](RESULTS.md)).

### Phase 9: live paper trading (added 2026-10-08)

The trend system runs on the live feed from the dashboard (one session per
pair, a 60-day warm start, reconnection, a ledger on disk). Acceptance for any
real capital: at least three months of paper trading inside the range of the
backtests, and the ledger agreeing with a replay of the same period.

### Phase 10: the alpha miner (added 2026-10-08)

Grow the system into an independent miner that keeps generating, screening,
recombining, incubating, trading and retiring alphas, each one an ordinary
combination of the trading system ([MINER.md](MINER.md)). Acceptance: exact
parity of mined combinations between the miner's simulation and the
framework; a pre-registered replay since 2022 reported in full; a null-market
control that earns nothing; the live service and its dashboard page.

---

## 4. Design

The detailed technical design is kept in [ARCHITECTURE.md](ARCHITECTURE.md)
as it is built. This section fixes the main decisions.

### 4.1 Layers

```
rapid_markets (unchanged)         events: Book, Trade (live, database, synthetic)
pipeline/generators, features     features from events (unchanged design)
pipeline/indicators, strategy     detection (base classes + new components)
pipeline/management               positions and managers (base + new components)
pipeline/dynamic                  DynamicParameter family and Feedback bus (new)
pipeline/behavior                 market, detection and trading behavior (new)
pipeline/combination, runner      a strategy with a manager, and running them (new)
pipeline/collaboration            collaborator v2 (Phase 6)
server/, dashboard/               execution server and web client (Phase 7)
```

### 4.2 Feedback bus

Each combination owns one `Feedback` object, which every dynamic parameter of
its strategy, indicators and manager is attached to. It carries:

- **trade records**: on opening, the values of all attached parameters (so
  each parameter can credit the outcome to the value it had); on closing, the
  net return after fees, the holding time, the exit reason, and the maximum
  favorable and adverse excursions;
- **market behavior**: the current `MarketBehavior` snapshot;
- **detection behavior** of the strategy and **trading behavior** of the
  manager.

Parameters receive `on_open`, `on_close` and `observe` calls from the bus,
never from each other, so any combination of variants can be used together.

### 4.3 DynamicParameter

A `DynamicParameter` has a current `value`, bounds, a value history, and an
internal evaluation of the outcomes it has seen. Variants:

| Variant | Method | Updates from |
|---|---|---|
| `Fixed` | constant (the baseline) | nothing |
| `Tracking` | PI controller driving a measured behavior to a target | behavior (`observe`) |
| `SPSA` | simultaneous-perturbation stochastic approximation (Spall) | trade outcomes |
| `Bandit` | discounted Thompson sampling over a value grid | trade outcomes |
| `KalmanOptimum` | Kalman filter on a drifting optimum, from outcome-weighted values | trade outcomes |
| `Scaled` | value = coefficient times a market measure (for example volatility), the coefficient itself dynamic | behavior and outcomes |

The internal evaluation keeps, per parameter, the outcomes credited to the
values used (per arm, per perturbation sign, or as a regression of outcome on
value), so its own learning can be inspected and shown on the dashboard.

### 4.4 Strategy and manager integration

`Strategy`, `Indicator` and `Manager` find their dynamic parameters
automatically (any attribute that is a `DynamicParameter`, in base and child
classes) and attach them to the combination's bus. The manager emits the
trade records; the strategy and manager each update their behavior record.
Components read parameters as `self.threshold.value`, so fixed and adaptive
versions are interchangeable.

### 4.5 Behavior measurement

- **Market** (online, one per stream): realized volatility at several scales,
  variance ratios, return autocorrelation, volatility of volatility, trade
  intensity and burstiness, order-flow imbalance and its sign persistence,
  price impact per unit of flow (Kyle's lambda), spread, depth, book
  imbalance, and jump share (bipower variation). Where they coincide, these
  use the same definitions as the `SyntheticMarket` inputs.
- **Detection** (per strategy): activity (share of time with a call), long
  and short shares, flip rate, mean confidence, mean call duration, and
  causal information coefficients (correlation of calls with the later
  return, measured once the horizon has passed) and character (correlation
  with the past return: trend-following or contrarian).
- **Trading** (per manager): trades per hour, holding time, exposure share,
  exit reasons, win rate, payoff ratio, captured share of the favorable
  excursion.
- **Alignment**: the strategy's character against the market regime (for
  example trend-following while the variance ratio is above 1), the
  information coefficient, and the holding time against the market's
  decorrelation time. These drive frequent parameter adjustments and the
  collaborator's mode changes.

### 4.6 Components

Chosen from [RESEARCH.md](RESEARCH.md); listed with their state in
[PROGRESS.md](PROGRESS.md).

### 4.7 Testing harness

- Sources: live (`watch_market`), database (`simulate_market` per segment,
  positions closed at segment ends), synthetic (`SyntheticMarket.stream`).
- Parallel runner: one process per seed; each returns a summary (net Sharpe
  ratio, trades, drawdown, behavior statistics) and optional telemetry.
- Reports: the performance table, behavior tables, parameter adaptation
  traces, and Sharpe distributions over seeds.

### 4.8 Collaborator v2

Modes per combination: warm-up, paper, active. Promotion requires both paper
performance (lower confidence bound of the per-trade return above zero) and
behavior alignment; demotion is triggered by either. Capital shares by
online optimization (Fixed-Share or exponentiated gradient on risk-adjusted
returns), with volatility targeting and a drawdown controller for total
exposure. Its decisions are measured (selection value, next-trade results
after decisions), as in the previous collaborator.

### 4.9 Server and dashboard

- **Server**: Python `aiohttp` (already installed), running simulations in
  worker processes and streaming JSON telemetry over WebSockets; a REST API
  to start, stop and configure runs on each source.
- **Client**: a single-page application (TypeScript, Vite, React; charts with
  TradingView Lightweight Charts and uPlot for fast streaming series), built
  to static files served by the server.
- **Panels**: live market (price, trades, book imbalance); combinations (equity
  curves, trades on the price chart, the performance table); market behavior
  metrics over time; detection and trading behavior per combination, against
  each other and against the market; dynamic parameters (value traces, rate
  of adaptation, internal evaluation); component inspector (indicators and
  parameters of a strategy, a manager and its parameters); run control.

---

## 5. Avoiding overfitting

- Fixed train and test seed sets; real data split into calibration segments
  and a held-out segment used once.
- Adaptive rules are judged on long runs and many seeds, never on single runs.
- Every reported Sharpe ratio comes with the number of trades and a
  confidence interval; claims require held-out confirmation.
- The number of variants tried is recorded, so selection bias can be judged.

---

## 6. Documents

| Document | Purpose |
|---|---|
| [PLAN.md](PLAN.md) | this plan (updated when the plan changes) |
| [PROGRESS.md](PROGRESS.md) | task board and dated work log, findings, decisions |
| [RESEARCH.md](RESEARCH.md) | methods and references |
| [ARCHITECTURE.md](ARCHITECTURE.md) | technical design as built |
| [SYNTHETIC.md](SYNTHETIC.md) | calibration, convergence, synthetic validity |
| [RESULTS.md](RESULTS.md) | test results per phase |
