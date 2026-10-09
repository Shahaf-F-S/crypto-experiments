# Components (Phase 4)

Indicators, strategies and managers built on the base classes, and how their
dynamic parameters are meant to be set. Code: `pipeline/indicators.py`,
`pipeline/strategy.py`, `pipeline/management.py`, `pipeline/generators.py`.
Tests: `tests/test_components.py`.

## Generators added

| Generator | Output | Reference |
|---|---|---|
| `FlowShare(window)` | signed over total traded quantity in the window, in [-1, 1] | order-flow imbalance (Cont, Kukanov and Stoikov 2014, trade form) |
| `KalmanTrend(key, resolution, window, level, slope)` | z-score of the slope of a local linear trend of the log price, Kalman-filtered on bars; noise variances relative to the measured bar variance | Harvey 1989, structural time-series models |

Existing generators used: `TimeReturn`, `TimeVolatility`, `VarianceRatio`
(Lo and MacKinlay 1988), `RollingOBI`, `MicroPriceDeviation` (Stoikov 2018).

## Indicators

`Threshold` is the common form: a continuous `signal`, a call when it passes a
dynamic `threshold` (against it when `follow=False`); confidence 0.5 at the
threshold, 1 at twice the threshold.

| Indicator | Signal | Typical use |
|---|---|---|
| `Momentum(ret, vol)` | log return over the window in units of its typical size (volatility-normalized time-series momentum, Moskowitz, Ooi and Pedersen 2012) | trend following; `follow=False` fades large moves (reversal) |
| `Trend(kalman)` | Kalman slope z-score | trend detection with a statistical threshold |
| `Flow(share)` | flow share | confirmation, entry timing |
| `Imbalance(imbalance)` | touch imbalance or micro-price deviation | confirmation, entry timing (about 1 bp of edge, section 3 of SYNTHETIC.md) |
| `Gauge(gen)` | none: always UNKNOWN, the value travels as `confidence` | regime gates and switches |

## Strategies

| Strategy | Rule | Parameters |
|---|---|---|
| `Follow` | the first indicator | |
| `Confirmed` | the first indicator's call, if no other indicator opposes it and a share `agree` agrees | `agree` |
| `Gated` | the first indicator's call while the gauge (last indicator) reads in [`low`, `high`] | `low`, `high` |
| `Switch` | first indicator above `upper` on the gauge, second below `lower`, nothing between | `upper`, `lower` |
| `Vote` | confidence-weighted vote beyond `quorum` | `quorum` |
| `Predictor` | online recursive least squares with forgetting (Haykin) of the next `horizon` return (bps) on the indicators' signals; calls when the forecast exceeds `edge` bps | `edge`, `forgetting`, `horizon` |

`Predictor.skill` is the recent correlation of forecasts with outcomes; its
learning is checked in the tests on a planted relation (weight 2.52 learned
for 2.59 planted). Forgetting trades bias for noise: at 0.999 per sample (10 s)
the effective sample is about 33 independent 5-minute outcomes, too few for a
weak signal.

## Managers

Brackets are net of fees in this framework (`Entry.is_tp`, `is_sl`): a stop
tighter than the round-trip fee fires at once.

| Manager | Rules | Parameters |
|---|---|---|
| `Brackets` | fixed-fraction take-profit and stop, a share of capital | `tp`, `sl`, `fraction` |
| `Adaptive` | take-profit at `take` typical moves over `horizon` (from `vol`); stop at the fee drag plus `stop` typical moves; stake targeting `target` volatility per horizon, scaled by `kelly` x (mean / variance of the last `memory` net trade returns), never below `floor` (so it keeps trading and learning); exits when the strategy reverses and after `hold` horizons | `take`, `stop`, `hold`, `kelly` |

## Setting the dynamic parameters

Each parameter is chosen by what it controls and how fast its information
arrives (lessons in ARCHITECTURE.md):

| Parameter | Controls | Variant | Learns from |
|---|---|---|---|
| indicator `threshold` | how often the strategy calls | `Tracking` of detection activity to a target | behavior, every 10 s, no trades needed |
| the activity target | whether calling more pays | `SPSA` with the `rate` objective | equity per hour over alternating windows (slow) |
| gate `low` / `high`, switch `upper` / `lower` | when a regime counts as trending | `Fixed` near 1, or `SPSA` rate | slow |
| `take`, `stop` | exits | `Bandit` over a grid, or `SPSA` with the `efficiency` objective | each trade's net return per hour held |
| `hold` | time stop | `Scaled` by the detection duration, or `Bandit` | behavior / trades |
| `kelly` | stake | `Fixed` fraction (0.25 to 0.5) | the trade records directly |
| `Predictor.edge` | when a forecast is worth a trade | `Fixed` at the round-trip cost, or `SPSA` rate | slow |

Behavior-matching adjustments (no trades needed): a `Tracking` target can
itself be a `Scaled` parameter of a market measure, e.g. a momentum
strategy's activity target proportional to how trending the market measures
(variance ratio), so it calls more in trending regimes and less in reverting
ones.
