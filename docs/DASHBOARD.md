# Dashboard

```bash
python -m server.app
```

Then open http://127.0.0.1:8765. The client is plain ES modules served by the
server (`client/`); Preact, htm and uPlot load from public CDNs, so the browser
needs internet access, but nothing has to be installed or built.

## Starting a run

**New run** opens the form. **System "trend"** (the default) runs the trading
system of [SYSTEM.md](SYSTEM.md) as a portfolio, one session per selected
pair: source **history** replays stored hourly bars from a date (e.g. at 1
day per second), source **live** paper-trades on the Binance feed after a
warm start from the last 60 days of hourly bars and writes a ledger to
`data/sessions/<group>/<pair>.jsonl` (from the session's start only: the
warm-up is simulated history). Live trend sessions follow the 1-minute candle
stream (a few hundred bytes a second per pair; prices carry the backtests'
slippage), and reconnect by themselves after network failures; the Binance
market list (about 15 MB, over a minute on a slow link) is loaded once and
cached in `data/markets/` for a day. Starting a portfolio with an existing
`group` continues its ledger. The **Portfolio** panel shows the
group's equal-weight equity and each pair; click a pair for its details.

**System "full system"** runs, per pair, the three sleeves of
[MINER.md](MINER.md) on equal capital: the trend system (F2), the miner's
crowd and its selected formulas. Its warm start is 110 days (the blends need
up to 105), and live sessions take the
closed hourly bars from the public API a few seconds after each hour, because
formulas read volumes and taker volumes that the candle stream does not carry
(prices move on the dashboard once an hour). Each mined sleeve runs as one
position per pair (`CatalogSignal`: the mean score of the formulas it holds at
each time, so opposite calls net out). It follows the miner by itself: a live session
picks up promotions and retirements at the next bar, with no new warm-up and
no flattening (the position moves to the new target, paying only the change);
a history replay trades what the miner traded at each time; while the miner
trades nothing the position is flat.

**Miner** (top bar) is the miner's console, live over a WebSocket (`/ws/miner`) from the server's miner hub
(`server/miner.py`). The hub watches the live miner's files every two seconds - its heartbeat
(`data/miner/live/status.json`), its log (`log.txt`) and its record (`state.json`) - and pushes every change, so
the console follows the miner whether the dashboard started it (**Start live miner**) or it runs in a terminal
(`python -m miner`).

- **Status bar**: a beacon (green running, pulsing amber while it works, red on an error, grey stopped), the
  current stage and how long ago, the next check; **Search now** (fresh random formulas into the pool) and
  **Review now** (refresh part of the crowd, choose the selected sleeve again) reach the running miner through
  `control.json` within half a minute; the record selector (`live`, `breadth`, or version 1's `replay`, `null`,
  `planted`).
- **Cards**: the system's Sharpe ratio and each sleeve's, the pool, search rounds, the selected and the crowd.
- **The sleeves as traded**: cumulative return of the system and of each sleeve (trend, crowd, selected),
  walk-forward; 90 days, a year or all; click a legend entry to hide a curve.
- **Live log**: the miner's log as it is written, following the end (scroll up to stop, **Follow the log** to
  resume).
- **Signals now**: per pair, each sleeve's target position (a signed fraction of its capital there) and the
  system's (their mean), as diverging bars; filter and sort.
- **Selected sleeve**: its formulas with their Sharpe ratio over two years, a year and 90 days, and a sparkline
  of the last year.
- **Lifecycle**: every formula ever selected, one row each, one column a month, lit while it was selected (green
  while it still earns, amber once its last 90 days turned negative): alphas arriving, holding and fading.
- **Pool explorer**: the whole pool, searchable by text, data family (price, volume, flow), membership (selected,
  crowd), sorted by a Sharpe ratio or simplicity, paged.
- **Events** and **Trade it** (a paper portfolio of the full system on chosen pairs, live or replayed).
- Clicking a formula anywhere opens its drawer: its record on all pairs (curve, Sharpe ratio by window and
  year), the months it spent in the selected sleeve, and its structure as a tree.

Version 1's records show its own view (traded alphas, the haircut scatter, the alphas and events).

The server answers the console at `/api/miner` (a record), `/api/miner/pool`, `/api/miner/formula`,
`/api/miner/timeline`, and `POST /api/miner` (`start`, `stop`, `search`, `review`). Client files are sent with
`Cache-Control: no-cache`, so a browser always runs the current version.

**System "microstructure"** runs the tick-level research combinations:

- **Source:** `synthetic` (the calibrated generator: seed, an optional planted
  edge in bps per hour, its kind (trend or reversion), its half-life, and a
  regime switch every N hours), `database` (a recorded segment) or `live`
  (Binance BTC/USDT through the recorder's feed; no orders are ever sent).
- **Hours** (not for live), the **round-trip fee**, and the **speed** (market
  time per wall second; `max` runs as fast as the machine allows).

Runs keep going when the page closes; the **runs** menu reconnects to any of
them, and a reconnecting page receives the whole history first. Pause,
resume, stop and speed act on the selected run.

## Panels

| Panel | Shows |
|---|---|
| Top cards | collective P&L (copied trades only), active members and their weights, trades, market volatility and variance ratio, events processed |
| Market | the mid price with every member's entries (triangles) and exits (circles), solid when copied by the collaborator; paper trades can be hidden |
| Equity | the collective (white) and each member's own virtual equity, in bps |
| Members | mode, weight, evidence score and its two parts (trades and behavior z), own and copied P&L, trades, position, current call, call activity, IC at the member's horizon, recent edge per trade, fit to the market regime; click a row for details |
| Modes over time | each member's warmup, paper and active periods |
| Market behavior | the online market measures with their recent history |
| Detection and trading behavior | how each strategy calls (activity, bias, flips, character, ICs) and each manager trades (rate, holding, win rate, exposure), with the character colored by whether it fits the market's variance ratio |
| Dynamic parameters | every adaptive parameter: kind, value, estimate, speed of adaptation (%/h), updates, history |
| Detail drawer | a combination's indicators (generators, current calls, thresholds), parameters, collaborator evidence over time, detection and trading behavior, predictor skill, recent trades |
