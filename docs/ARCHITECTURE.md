# Architecture (as built)

Technical design of the rebuilt system. Plans are in [PLAN.md](PLAN.md); this
document describes what exists and how to use it.

## Modules

What runs the system sits at the top level; research and experimentation are
under `lab/` (see `lab/README.md`), and nothing at the top level imports from
it.

| Module | Contents |
|---|---|
| `rapid_markets/` | events (`Book`, `Trade`), tick database, live feeds, `SyntheticMarket`, `calibrate`, `describe` (unchanged) |
| `pipeline/generators.py`, `filters.py` | feature generators (including `FlowShare`, `KalmanTrend`) |
| `pipeline/features.py` | `Features`, `compute_features` |
| `pipeline/indicators.py` | `Detection`, `BaseDetector`, `Indicator`; `Threshold`, `Momentum`, `Trend`, `Flow`, `Imbalance`, `Gauge`, `TrendScore` |
| `pipeline/strategy.py` | `Strategy`; `Follow`, `Confirmed`, `Gated`, `Switch`, `Vote`, `Predictor` |
| `pipeline/management.py` | `Position`, `Entry`, `Exit`, `PositionStats`, `Manager`; `Brackets`, `Adaptive`, `Target` (continuous positions, futures accounting) |
| `pipeline/dynamic.py` | `DynamicParameter` family, `Feedback` bus, `TradeRecord`, `State`, `discover` |
| `pipeline/behavior.py` | `MarketBehavior`, `DetectionBehavior`, `TradingBehavior`, `RealizedVolatility`, `alignment` |
| `pipeline/combination.py`, `collaborator.py`, `runner.py` | `Combination`; `Collaborator`, `Member`; `run`, `run_synthetic`, `run_seeds` |
| `system/trend.py` | the trading system: the trend family on hourly bars, futures costs and funding ([SYSTEM.md](SYSTEM.md)) |
| `system/mined.py` | the full system per pair: F2 and the breadth miner's two sleeves, each following its catalog |
| `miner/formula.py` | the formula language: typed nodes, parsing, causal finite-window operators, scores ([MINER.md](MINER.md)) |
| `miner/search.py`, `fitness.py` | generation, mutation, crossover, simplification, the MAP-Elites archive; screening fitness, exact tracks, worker processes |
| `miner/simulate.py`, `panel.py`, `stats.py` | `Target`'s accounting in numpy (equal to the framework to 1e-12); the hourly panel of the universe; Sharpe, deflation, the haircut |
| `miner/breadth.py`, `__main__.py` | `Breadth`, the miner that runs (version 2: the pool of random formulas on 78 pairs, the crowd and selected sleeves, their catalogs); the live service (`python -m miner`) |
| `miner/miner.py` | `Miner`, version 1 (genetic search, incubation, haircut), kept with its pre-registered replay |
| `miner/components.py` | `FormulaValue` (bars from events, a formula per closed bar), `CatalogSignal` (a catalog's blend as it changes over time), `Formula`, `Blend`, `following()`, `combination()` |
| `system/microstructure.py` | the tick-level combinations ([COMPONENTS.md](COMPONENTS.md)) |
| `system/history.py` | Binance klines and funding (fetch, incremental update, store in `data/`, load, recent bars for warm starts), tick-database segments |
| `system/bars.py` | bars as `Book` and `Trade` events (the replay and warm-start source) |
| `simulation/` | synthetic generator v2: `MarketModel`, `calibrate`, `fit`, `Market`, `structure` ([SYNTHETIC.md](SYNTHETIC.md)) |
| `server/` | `Session` (paced runs and live paper trading, streaming to clients), `live` (market cache, candle feed, hourly bar poll), `miner` (`MinerHub`: the miner's records and live files, streamed to the console), `app` (aiohttp) |
| `client/` | the dashboard (no build step; [DASHBOARD.md](DASHBOARD.md)): `app.js` (sessions), `miner.js` (the miner's console), `common.js` (shared pieces) |
| `tests/` | unit and end-to-end tests (`python -m unittest discover tests`) |
| `data/` | klines, funding, the market-list cache, paper-trading ledgers, miner state and catalogs (`data/miner/<run>/`) |
| `lab/` | research and experiments: `scripts/` (run as `python -m lab.scripts.<name>`), `research/`, `experiment/`, `results/`, `archive/` |

## Flow of one event

```
source event (Book or Trade)
  -> MarketBehavior.update(event)                 every event, shared by all combinations
  -> compute_features(...)                        all generators, every event
  -> for each Combination (on book snapshots):
       Manager(values)                            runs Strategy -> Indicators -> Detection, manages the position
         on entry: Feedback.opened(...)           records every parameter's value in force
         on exit:  Feedback.closed(...)           net return, holding time, reason, best/worst excursion
       DetectionBehavior.update(...)              once per second
       TradingBehavior.update(...)                once per second (exposure)
       every 10 s: Feedback.observe(State(...))   every parameter observes market, detection, trading, equity
```

Decisions are made on book snapshots only (about 10 per second); trades still
feed the features and the market behavior. `decide_on_trades=True` changes
this. Positions are closed at the end of each source (segment).

## Dynamic parameters

Components declare parameters as dataclass fields holding a
`DynamicParameter`, and read `parameter.value` when deciding:

```python
threshold: DynamicParameter = field(default_factory=lambda: Tracking(
    value=0.3, low=0.01, high=0.99, measure=lambda s: s.detection.activity, target=0.2, sign=-1.0
))
```

`discover` finds them in managers, strategies, indicators (nested, in lists)
and inside other parameters (a `Tracking` target or a `Scaled` coefficient
that is itself dynamic), and names them by path, for example
`strategy.indicators[0].threshold`.

| Variant | Learns from | Notes |
|---|---|---|
| `Fixed` | nothing | baseline |
| `Tracking` | `observe` (behavior) | incremental PI controller, log steps with `relative`; `sign` is +1 if raising the value raises the measure |
| `SPSA` | trade outcomes, or equity over windows | alternates value x exp(+-step); `objective` = `trade`, `efficiency` (per hour held), `rate` (equity per hour over alternating `window`s, for parameters that decide whether to trade); `estimate` is the Polyak-averaged iterate |
| `Bandit` | trade outcomes | discounted Thompson sampling over `grid` |
| `Scaled` | `observe` | `coefficient` x `measure(state)` |

Every parameter keeps `history` (estimate every 10 s), `speed` (relative
change per hour), `updates`, and `evaluation()` (its internal evaluation:
error and target, gradient and pair counts, per-arm means).

**Credit assignment:** the bus records each parameter's value at entry in the
`TradeRecord`; `SPSA` and `Bandit` remember which perturbation or arm each
open trade used, so outcomes are credited to the value that produced them.

**Lessons from the tests** (see [PROGRESS.md](PROGRESS.md)):

- A controller must act on a measure faster than itself. The detection
  behavior therefore has two time scales: call statistics over 5 minutes
  (for control) and information coefficients over 1 hour (for evaluation).
- `Tracking` is in incremental form; a positional integral term on top of a
  value that already integrates the error makes a double integrator, which
  oscillated.
- Profit-rate optimization is slow: with realistic noise, `SPSA` on equity
  windows needs hundreds of hours to settle. Fast adaptation comes from
  behavior tracking; outcome-based optimization adjusts targets slowly.

## Behavior measures

**`MarketBehavior`** (exponentially weighted, default half-life 30 minutes):

| Measure | Definition | SyntheticMarket input |
|---|---|---|
| `volatility` | sd of 1-minute log returns, bps | `volatility_bps` |
| `volatility_10s` | sd of 10-second returns, bps | |
| `variance_ratio`, `variance_ratio_5m` | var(1 m) / 6 var(10 s); var(5 m) / 5 var(1 m) | |
| `autocorrelation`, `autocorrelation_1m` | lag-1 autocorrelation of 10 s and 1 m returns | |
| `trade_rate` | trades per second | `order_rate` x fills per order |
| `burstiness` | variance / mean of trades per second | (describe: trade burstiness) |
| `flow_persistence` | lag-1 autocorrelation of 10 s flow share | `sign_persistence` (order level) |
| `impact`, `impact_slope` | correlation and slope (bps per unit flow share) of the 10 s return on the 10 s flow share | |
| `imbalance_ic` | correlation of touch imbalance with the next 10 s return | |
| `spread` | in ticks | `wide_spread_rate` |
| `quote_rate` | share of snapshots whose mid changed | `refresh_rate` x snapshot interval |
| `touch_size` | geometric mean of the touch size | `touch_size_median` |

Validated: with a very long half-life it matches `describe()` on the same
synthetic stream, and on real data it reproduces the Phase 1 measurements
(impact about 0.5, imbalance IC about 0.24).

**`DetectionBehavior`** (per strategy, sampled once per second): `activity`,
`bias`, `flip_rate`, `confidence`, `duration` (5-minute half-life), and
`ic(h)`, `character(h)` for h = 10, 60, 300 s (1-hour half-life).

**`TradingBehavior`** (per manager): `trade_rate`, `holding`, `exposure`,
`edge`, `win_rate`, `payoff`, `capture`, `adverse`, and the share of each exit
reason (`tp`, `sl`, `time`, `signal`, `flatten`).

**`alignment(market, detection)`**: `regime` = (variance ratio - 1) x
character over 1 minute (positive when the strategy follows a trending market
or fades a reverting one), and `predictive` = information coefficient over 1
minute.

## Running

```python
result = await run([db.simulate_market(limits) for limits in segments], combinations)
results = run_seeds(build, MarketModel.load('simulation/btc_usdt.model'), seeds=range(20), hours=24)
results = run_seeds(build, Market(model=model, edge_bps=20.0), seeds=range(20), hours=24)   # a planted edge
```

`build` must be a top-level function (or a `functools.partial` of one): each
worker process builds its own combinations.

`run` returns, per combination, its `snapshot()` (capital, trades, Sharpe per
trade, behaviors, alignment, parameters) plus `sharpe_annual` and
`max_drawdown` from equity sampled every 15 minutes. One combination runs at
about 66,000 events per second; 8 seeds in parallel at about 250,000.

## Collaborator

`Collaborator(combinations)` holds every combination as a `Member` in one of
three modes. Every member always trades on its own virtual capital; the modes
only decide which trades are copied into the collective account.

| Mode | Meaning | Leaves when |
|---|---|---|
| `warmup` | parameters adapting; nothing counts as evidence | `warmup` seconds have passed (default 3 h) |
| `paper` | trades are virtual and build evidence | score above `promote` (default 1.5) with at least `minimum` (8) trades |
| `active` | new trades are copied at `weight` | score below `demote` (default 0) |

**Evidence (score)** = t-statistic of the member's last 30 net trade returns
(net of fees) + 0.5 x behavior z. The behavior z is the significance of the
information coefficient at the member's own horizon above the IC that only
breaks even after fees: (IC - fee / typical move over the horizon) x
sqrt(2 x IC half-life / horizon). It needs no trades, so a member can be
demoted or promoted as its calls stop or start matching the market, before
trades accumulate. Without the cost term the 10-second imbalance strategy
looked excellent (IC z of 5) while losing on every trade.

**Weights:** active members share the capital in proportion to their
scores, at most `cap` (0.5) each. **Copied trades** start only while a member
is active and finish when the member closes them: a mode change neither
adopts an open position nor abandons one (adoption cost about 40 bps a trade
in the earlier system). The collective P&L is the weighted sum of the copied
trades' net returns.

`run(..., collaborator=...)` and `run_synthetic(..., collaborate={...})` run
it; `lab/scripts/test_collaborator.py` compares it with the members alone, equal weight,
and the best member in hindsight.

## Server and dashboard

`python -m server.app` serves the dashboard on http://127.0.0.1:8765. A
`Session` runs the catalog's combinations under a collaborator on a synthetic
market (optionally with a planted edge or regime switches), a recorded
segment, or the live Binance feed, paced in market time (`speed` market
seconds per second, 0 for as fast as possible) with pause, resume and stop.
It streams over a WebSocket, in batches every 100 ms:

| Message | When | Content |
|---|---|---|
| `history` | on connect | session, price ticks (columns), trades, series, latest detail, structure |
| `tick` | each market second | time, mid |
| `trade` | each open and close | combination, side, price, net, reason, mode, copied |
| `series` | every 10 market seconds | collective and member equities, modes, weights, scores, market measures, parameter values, activity |
| `detail` | every 10 market seconds (only the latest kept) | full market, detection and trading behavior, alignment, every parameter's state and evaluation, member evidence |
| `status`, `session` | on changes | status, settings |

The session yields to the server every 256 events, so the server stays
responsive while the indicators warm up.
