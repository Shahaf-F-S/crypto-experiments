# Research: methods for adaptive intraday crypto trading from market events

The survey behind the rebuild ([PLAN.md](PLAN.md) R3). It covers what is
documented about predicting short-term crypto returns from order-book and
trade events, the methods for adapting parameters (dynamic control,
optimization, statistical prediction), and which of them fit this project.
Findings are summarized with their sources; nothing here is a claim of
profitability for this project until tested.

## Costs

Costs decide which horizons can be traded at all.

| Venue and tier | Maker | Taker | Taker round trip |
|---|---|---|---|
| Binance spot, VIP 0 | 0.10% | 0.10% | 20 bps |
| Binance spot, with BNB discount (25%) | 0.075% | 0.075% | 15 bps |
| Binance USDⓈ-M futures, base tier | 0.02% | 0.05% | 10 bps (4 bps as maker) |

Sources: [Binance fee overview (CryptoPotato, 2025)](https://cryptopotato.com/binance-fees/),
[Binance.US fee schedule](https://binance.us/en/fee/schedule).

On BTC/USDT the spread is one tick (about 0.0013 bps), so the fee is the whole
cost. Measured on the recording: about 4 bps typical 1-minute move, about 8
bps over 5 minutes, about 30 to 60 bps over an hour. A strategy that takes
liquidity at 20 bps round trip must therefore aim at moves of tens of minutes
or longer, or the expected gross gain per trade cannot exceed the fee. All
tests are run at several fee levels (20, 15, 10, 4 bps) to show where each
method could pay.

## Predicting returns from market events (statistical prediction)

**Order-flow imbalance (OFI).** Cont, Kukanov and Stoikov ("The price impact
of order book events", 2014) show that price changes over short intervals are
close to linear in the imbalance between supply and demand at the best quotes
(net order flow at the touch), and that this relation is mostly
contemporaneous. On Bitcoin, trade-flow imbalance explains contemporaneous
price changes better than aggregate order-flow imbalance, and the relation is
linear over long enough intervals ([Silantyev, "Order flow analysis of
cryptocurrency markets", Digital Finance, 2019](https://ideas.repec.org/a/spr/digfin/v1y2019i1d10.1007_s42521-019-00007-w.html)).
Machine-learning models (LSTM) improve on OFI somewhat for direction
classification ([summary](https://math.sustech.edu.cn/seminar_all/12206.html?lang=en)).
In centralized crypto exchanges, limit-order submissions and cancellations
contribute more to price discovery than market orders ([Order flow impact and
price formation in centralized crypto exchanges](https://mlquants.substack.com/p/order-flow-impact-and-price-formation)).
*Use here:* contemporaneous impact is not tradable by a taker; the lagged part
(seconds to minutes) is small against a 20 bps fee. OFI is used as
confirmation and entry timing for slower signals, and as a market behavior
measure (impact per unit of flow).

**Micro-price.** Stoikov ("The micro-price: a high-frequency estimator of
future prices", Quantitative Finance, 2018) shows that an imbalance-adjusted
price predicts short-term mid-price moves better than the mid or the weighted
mid. *Use here:* timing of entries and exits, and a market measure.

**Order-sign persistence and impact decay.** Order signs have long memory
while prices stay close to efficient, because liquidity adjusts (Bouchaud,
Gefen, Potters and Wyart, "Fluctuations and response in financial markets",
2004; Lillo and Farmer, 2004, propagator models). *Use here:* flow persistence
predicts flow more than price; it is a behavior measure and a synthetic-market
input (already calibrated as `sign_persistence`).

**Flow toxicity.** VPIN (Easley, López de Prado and O'Hara, "Flow toxicity and
liquidity in a high-frequency world", 2012) measures volume imbalance in
volume time and anticipates volatility and liquidity stress. *Use here:* a
risk gate and a regime measure, not a direction signal.

**Self-exciting order arrivals.** Hawkes processes describe the clustering of
order arrivals and their cross-excitation (Bacry, Mastromatteo and Muzy,
"Hawkes processes in finance", 2015). *Use here:* short-term activity and
volatility forecasting (for sizing and for exits).

**Intraday time-series momentum and reversal in crypto.**
- Bitcoin: the first half-hour return positively predicts the last half-hour
  return, most strongly in high-volume, high-volatility sessions, with
  economically meaningful timing gains, especially in downturns ([Shen,
  Urquhart and Wang, "Bitcoin intraday time series momentum", Financial
  Review, 2022](https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/)).
- Across cryptocurrencies, intraday returns show both momentum and reversal
  ([Wen, Bouri, Xu and Zhao, "Intraday return predictability in the
  cryptocurrency markets: momentum, reversal, or both", North American
  Journal of Economics and Finance, 2022](https://ideas.repec.org/a/eee/ecofin/v62y2022ics1062940822000833.html)).
- Significant negative first-order autocorrelation at 1, 2 and 4 hours
  (systematic mean reversion), with stronger reversals after larger moves
  ([Brunel repository](https://bura.brunel.ac.uk/handle/2438/20686?mode=full)).
- Return predictability around quarter-hour marks (minutes 15, 30, 45) in
  crypto futures, attributed to periodic algorithmic trading ([The
  quarter-hour effect, 2026 preprint](https://arxiv.org/pdf/2607.09426)).

*Use here:* the main direction signals. Horizons of 30 minutes to 4 hours are
the ones whose typical moves exceed the fee. This agrees with this project's
own measurements (anti-persistent results of short-horizon members, reversal
after large moves).

**Volatility forecasting.** Realized-volatility models such as HAR-RV (Corsi,
2009) forecast volatility well from multi-scale realized variance.
Volatility-managed portfolios (Moreira and Muir, "Volatility-managed
portfolios", Journal of Finance, 2017) raise Sharpe ratios by scaling exposure
inversely to recent variance. *Use here:* position sizing and the scale of
thresholds, take-profits and stops.

**Regime detection.** Variance ratios (Lo and MacKinlay, 1988) separate
trending from mean-reverting behavior; hidden Markov models (Hamilton, 1989)
and Bayesian online changepoint detection (Adams and MacKay, 2007) detect
regime switches online. *Use here:* gating between momentum and reversal,
and the alignment between a strategy's character and the market.

**Online regression.** Recursive least squares and Kalman-filter regression
with forgetting predict forward returns from event features and track
drifting coefficients. *Use here:* a learned predictor strategy with
cost-aware thresholds.

## Adapting parameters (dynamic control and optimization)

| Method | Source | Use for |
|---|---|---|
| Stochastic approximation | Robbins and Monro (1951); Kiefer and Wolfowitz (1952) | step-size schedules for any online update |
| SPSA | Spall, "Multivariate stochastic approximation using a simultaneous perturbation gradient approximation", IEEE TAC, 1992 | optimizing a parameter from noisy trade outcomes with two evaluations per step, whatever the dimension |
| Thompson sampling, discounted | Thompson (1933); Agrawal and Goyal (2012); Garivier and Moulines (2011) for non-stationary bandits | choosing a value from a grid (take-profit, stop multiples) under drifting conditions |
| UCB | Auer, Cesa-Bianchi and Fischer (2002) | the same, deterministic |
| PI / PID control | Åström and Murray, *Feedback Systems* (2008) | holding a measured behavior at a target (detection rate, trade rate, exposure) without waiting for trades |
| Model reference adaptive control (MIT rule) | Åström and Wittenmark, *Adaptive Control* | adapting gains so a behavior follows a reference model |
| Kalman filter on parameters | Kalman (1960); time-varying regression | tracking a drifting optimum |
| Kelly criterion, fractional | Kelly (1956); Thorp; MacLean, Thorp and Ziemba (2010) | sizing from estimated edge and variance, shrunk for estimation error |
| Volatility targeting | Moreira and Muir (2017) | exposure scaling |
| Fixed-Share / exponentiated gradient | Herbster and Warmuth (1998); Helmbold et al. (1998) | capital shares across combinations (collaborator) |
| CMA-ES | Hansen and Ostermeier (2001) | population search over parameter vectors (collaborator variants) |

## Market making (noted, not in scope yet)

Most documented steady intraday profits come from providing liquidity:
Avellaneda and Stoikov ("High-frequency trading in a limit order book", 2008)
and Guéant, Lehalle and Fernandez-Tapia (2013) give inventory-controlled
quoting. It needs a fill simulator with queue positions (passive fills
depend on the queue and on adverse selection), which the database replay and
the synthetic market do not model. It is a candidate extension once a fill
model exists, and it is the natural route to the 4 bps maker cost level.

## Fit to this project

Ranked by fit to taker execution at 10 to 20 bps round trip, from event data:

1. **Volatility-scaled intraday time-series momentum (30 to 60 minutes)**,
   confirmed by order-flow imbalance, sized by volatility targeting, exits by
   adaptive brackets.
2. **Reversal after large moves (1 to 4 hours)**, gated by regime (variance
   ratio, toxicity), with adaptive entry depth.
3. **Regime-gated switching** between 1 and 2 (variance ratio, changepoint).
4. **A learned linear predictor** of net forward returns from event features
   (online regression), trading only when the predicted move clears the fee.
5. **Flow-timed entries**: micro-price and OFI used to time the entries of 1
   to 4, not as standalone signals.

Every threshold, scale, bracket and size is a dynamic parameter adapted by
the methods above, from both trade outcomes and behavior measures.
