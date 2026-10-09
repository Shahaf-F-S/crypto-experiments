# Research protocol (real history)

Written before looking at the data, to keep the search honest. Changes to
this protocol are logged at the end with their reason.

## Why real history

On the recorded 91 hours the only predictable structure is microstructure
(about 1 bp per trade at best), which no fee level available to us pays; the
synthetic generator reproduces exactly that. Anything profitable must live at
longer horizons (tens of minutes to a day), where 91 hours say nothing. Years
of 1-minute bars (Binance spot klines, public API: OHLC, volume, trade count,
taker-buy volume, which is the aggressive order flow) let us measure it.

## Data

- Pairs: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT (the most liquid; chosen
  before any analysis, not by results).
- **Discovery period:** 2021-01-01 to 2023-12-31. All exploration, design and
  any fitting happen here.
- **Holdout period:** 2024-01-01 to the end of the data. Used once per
  strategy family, after its design is frozen. Results are reported whatever
  they are.

## Costs

| Venue | Per side | Round trip |
|---|---|---|
| Spot, taker (VIP 0) | 10 bps | 20 bps |
| USDS-M futures, taker | 5 bps | 10 bps |
| Futures, maker entry and taker exit | 2 + 5 bps | 7 bps |

Plus slippage of 1 bp a side on BTC and ETH and 2 bps on the others.
Futures funding is ignored for positions shorter than a day (about 1 bp per 8
hours on average, both signs). The main case is futures taker plus slippage
(12 bps round trip on BTC); maker entries are only credited when a later bar
trades through the limit price.

## Rules against fooling ourselves

1. **No look-ahead.** Signals use completed bars only; a decision at the close
   of a bar executes at that close plus slippage. Dynamic parameters learn
   only from the past (they are causal by construction); any parameter fitted
   offline is fitted on data strictly before where it is used (walk forward).
2. **Every variant counts.** Every strategy variant evaluated on discovery data
   is logged with its result. The best one's Sharpe ratio is judged by the
   deflated Sharpe ratio (Bailey and Lopez de Prado 2014), which accounts for
   the number of variants tried and the non-normality of returns.
3. **Breadth.** A strategy must work on most pairs and in most years of the
   discovery period, not on one pair or one year.
4. **Economic size first.** A signal is only pursued if its expected move at
   the decision threshold is a multiple of the round-trip cost.
5. **Stop rule.** A direction that fails after a reasonable number of
   variations is dropped and logged, not tuned further.

## What counts as success

On the holdout, at futures taker costs, after slippage and funding:
annualized Sharpe of daily returns above 1, positive in most quarters, worst
drawdown smaller than half the annual return, on most pairs; and the
collaborator over the combinations no worse than its best member.

## Log of changes

- 2026-10-08: 1-minute bars were too slow to download (about 60 KB/s); the
  research uses hourly bars (15-minute bars fetched in the background). The
  horizons that matter (hours to days) do not need finer bars.
- 2026-10-08: tradability is judged by mean-based edges (what a position
  earns), not rank correlations: the reversal family failed on that difference
  (RESULTS.md).
- 2026-10-08: funding rates (Binance perpetuals, public API) are applied to
  every position held across a funding time.
