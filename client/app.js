// app.js: the Rapid Markets Lab client (Preact + htm, uPlot; no build step).

import { html, render, useState, useEffect, useRef, useMemo, PALETTE, fmt, clock, api, Plot, AXIS, Spark } from './common.js';
import { MinerConsole } from './miner.js';

const MODE_COLOR = { warmup: '#5d6678', paper: '#2d5fa8', active: '#3ecf8e' };
const SPEEDS = [[1, '1x'], [10, '10x'], [60, '1 min/s'], [600, '10 min/s'], [3600, '1 h/s'], [0, 'max']];
const TREND_SPEEDS = [[3600, '1 h/s'], [86400, '1 day/s'], [604800, '1 week/s'], [0, 'max']];
const MARKET = [
  ['volatility', 'Volatility 1m', v => fmt(v, 2) + ' bps'],
  ['variance_ratio', 'Variance ratio', v => fmt(v, 2)],
  ['autocorrelation', 'Autocorrelation 10s', v => fmt(v, 3)],
  ['trade_rate', 'Trades / s', v => fmt(v, 1)],
  ['impact', 'Flow-price impact', v => fmt(v, 2)],
  ['imbalance_ic', 'Imbalance IC 10s', v => fmt(v, 3)],
  ['flow_persistence', 'Flow persistence', v => fmt(v, 2)],
];

// Mutable data store: big arrays live here, Preact renders from a version counter.
const store = {
  session: null, structure: {}, times: [], prices: [], trades: [], series: [], detail: null,
  version: 0, listeners: new Set(),
};

function bump() {
  store.version++;
  if (!bump.pending) {
    bump.pending = true;
    setTimeout(() => { bump.pending = false; store.listeners.forEach(f => f(store.version)); }, 200);
  }
}

function useStore() {
  const [, set] = useState(0);
  useEffect(() => { store.listeners.add(set); return () => store.listeners.delete(set); }, []);
  return store;
}


function bps(equity) {
  if (equity === null || equity === undefined) return '–';
  const v = (equity - 1) * 1e4;
  return (v >= 0 ? '+' : '') + v.toFixed(1);
}


function colorOf(name) {
  const names = store.session?.combinations || [];
  const i = names.indexOf(name);
  return PALETTE[(i < 0 ? 0 : i) % PALETTE.length];
}


// Connection ---------------------------------------------------------------------------------------------------

let socket = null;

function connect(id) {
  if (socket) socket.close();
  Object.assign(store, { session: null, structure: {}, times: [], prices: [], trades: [], series: [], detail: null });
  bump();
  socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/${id}`);
  socket.binaryType = 'arraybuffer';
  socket.onmessage = event => {
    const text = typeof event.data === 'string' ? event.data : new TextDecoder().decode(event.data);
    for (const message of JSON.parse(text)) handle(message);
    bump();
  };
  socket.onclose = () => {
    socket = null;
    setTimeout(() => { if (!socket && location.hash.slice(1) === id) connect(id); }, 3000);    // reconnect and resync
  };
}

function handle(m) {
  switch (m.type) {
    case 'history':
      store.session = m.session; store.structure = m.structure;
      store.times = m.ticks[0]; store.prices = m.ticks[1];
      store.trades = m.trades; store.series = m.series; store.detail = m.detail;
      break;
    case 'tick': store.times.push(m.t); store.prices.push(m.p); if (store.session) store.session.time = m.t; break;
    case 'trade': store.trades.push(m); if (store.trades.length > 5000) store.trades.shift(); break;
    case 'series': store.series.push(m); break;
    case 'detail': store.detail = m; break;
    case 'status': if (store.session) { store.session.status = m.status; store.session.error = m.error || ''; } break;
    case 'session': store.session = m.session; break;
    case 'error': store.session = { status: 'failed', error: m.error, combinations: [] }; break;
  }
}

// Charts -------------------------------------------------------------------------------------------------------

function PriceChart({ showPaper }) {
  const s = useStore();
  const options = useMemo(() => ({
    scales: { x: { time: true } },
    axes: [AXIS, { ...AXIS, size: 70 }],
    series: [{}, { label: 'mid', stroke: '#dfe5f0', width: 1 }],
    legend: { show: false },
    cursor: { drag: { x: true, y: false } },
  }), []);
  const data = useMemo(() => [s.times.slice(), s.prices.slice()], [s.version]);

  const draw = u => {
    const ctx = u.ctx;
    const [x0, x1] = [u.scales.x.min, u.scales.x.max];
    ctx.save();
    for (const t of s.trades) {
      if (t.time < x0 || t.time > x1 || t.price == null) continue;
      if (!showPaper && !(t.copied || t.mode === 'active')) continue;
      const x = u.valToPos(t.time, 'x', true), y = u.valToPos(t.price, 'y', true);
      const strong = t.copied || t.mode === 'active';
      ctx.globalAlpha = strong ? 1 : 0.35;
      ctx.fillStyle = colorOf(t.combination);
      ctx.strokeStyle = colorOf(t.combination);
      const r = 5 * devicePixelRatio;
      ctx.beginPath();
      if (t.kind === 'open') {
        const up = t.side === 'long';
        ctx.moveTo(x, y + (up ? -r : r)); ctx.lineTo(x - r, y + (up ? r : -r)); ctx.lineTo(x + r, y + (up ? r : -r)); ctx.closePath(); ctx.fill();
      } else {
        ctx.arc(x, y, r * 0.7, 0, 2 * Math.PI); ctx.lineWidth = 1.5 * devicePixelRatio; ctx.stroke();
      }
    }
    ctx.restore();
  };
  return html`<${Plot} options=${options} data=${data} height=${300} draw=${draw} />`;
}

function EquityChart() {
  const s = useStore();
  const names = s.session?.combinations || [];
  const options = useMemo(() => ({
    scales: { x: { time: true } },
    axes: [AXIS, { ...AXIS, size: 60, values: (u, v) => v.map(x => x.toFixed(0)) }],
    series: [{}, { label: 'collective', stroke: '#ffffff', width: 2.5 },
      ...names.map(n => ({ label: n, stroke: colorOf(n), width: 1, alpha: 0.75 }))],
    legend: { show: false },
  }), [names.join('|')]);
  const data = useMemo(() => {
    const t = s.series.map(p => p.t);
    return [t, s.series.map(p => (p.collective - 1) * 1e4), ...names.map(n => s.series.map(p => ((p.equity[n] ?? 1) - 1) * 1e4))];
  }, [s.version, names.join('|')]);
  return html`<${Plot} options=${options} data=${data} height=${220} />
    <div class="legend"><span style="--c:#fff">collective (bps)</span>${names.map(n => html`<span style=${`--c:${colorOf(n)}`}>${n} (own)</span>`)}</div>`;
}

function tail(array, n) { return array.length > n ? array.slice(array.length - n) : array; }

// Panels -------------------------------------------------------------------------------------------------------

function Kpis() {
  const s = useStore();
  const d = s.detail;
  const members = d ? Object.values(d.combinations).map(c => c.member) : [];
  const active = members.filter(m => m.mode === 'active');
  const trades = d ? Object.values(d.combinations).reduce((a, c) => a + (c.exits || 0), 0) : 0;
  const equity = d?.collective?.equity;
  const pnl = equity != null ? (equity - 1) * 1e4 : null;
  const items = [
    ['Collective P&L', pnl == null ? '–' : (pnl >= 0 ? '+' : '') + pnl.toFixed(1) + ' bps', pnl > 0 ? 'good' : pnl < 0 ? 'bad' : '', 'copied trades only'],
    ['Active members', `${active.length} / ${members.length}`, '', active.map(m => m.weight).length ? 'weights ' + active.map(m => (m.weight * 100).toFixed(0) + '%').join(' ') : 'all in paper or warmup'],
    ['Trades (all members)', trades, '', 'virtual and copied'],
    ['Volatility 1m', d ? fmt(d.market.volatility, 2) + ' bps' : '–', '', 'market behavior'],
    ['Variance ratio', d ? fmt(d.market.variance_ratio, 2) : '–', '', '> 1 trending, < 1 reverting'],
    ['Events', s.session ? (s.session.events || 0).toLocaleString() : '–', '', s.session ? s.session.settings?.source : ''],
  ];
  return html`<div class="kpis span-12">${items.map(([label, value, cls, sub]) => html`
    <div class="card kpi"><div class="label">${label}</div><div class=${'value ' + cls}>${value}</div><div class="sub">${sub}</div></div>`)}</div>`;
}

function Members({ selected, onSelect }) {
  const s = useStore();
  const d = s.detail;
  if (!d) return html`<div class="empty">Waiting for the first snapshot (indicators warm up for about 2 market hours).</div>`;
  const rows = Object.entries(d.combinations);
  return html`<div class="scroll"><table>
    <thead><tr>
      <th>Combination</th><th>Mode</th><th>Weight</th><th>Score</th><th>Trades z</th><th>Behavior z</th>
      <th>Own P&L</th><th>Copied</th><th>Trades</th><th>Position</th><th>Call</th><th>Activity</th><th>IC (horizon)</th><th>Edge/trade</th><th>Fit to regime</th>
    </tr></thead>
    <tbody>${rows.map(([name, c]) => {
      const m = c.member;
      const ic = c.detection[`ic_${m.horizon}s`];
      const score = Math.max(-3, Math.min(3, m.score || 0));
      return html`<tr class=${selected === name ? 'selected' : ''} onClick=${() => onSelect(name)}>
        <td><span class="dot" style=${`background:${colorOf(name)}`}></span>${name}</td>
        <td><span class=${'pill ' + m.mode}>${m.mode}</span></td>
        <td class="mono">${(m.weight * 100).toFixed(0)}%</td>
        <td class="mono">${fmt(m.score, 2)}<span class="bar"><i style=${`left:${score < 0 ? 50 + score / 6 * 100 : 50}%;width:${Math.abs(score) / 6 * 100}%;background:${score >= 0 ? 'var(--good)' : 'var(--bad)'}`}></i></span></td>
        <td class="mono">${fmt(m.trade_z, 2)}</td>
        <td class="mono">${fmt(m.behavior_z, 2)}</td>
        <td class=${'mono ' + ((c.equity - 1) >= 0 ? 'good' : 'bad')}>${bps(c.equity)}</td>
        <td class=${'mono ' + (m.realized >= 0 ? 'good' : 'bad')}>${(m.realized * 1e4).toFixed(1)}</td>
        <td class="mono">${c.exits}</td>
        <td>${c.position || '–'}</td>
        <td>${c.call && c.call !== 'unknown' ? c.call : '–'}</td>
        <td class="mono">${fmt(c.detection.activity, 2)}</td>
        <td class="mono">${fmt(ic, 3)}</td>
        <td class="mono">${c.trading.edge != null ? (c.trading.edge * 1e4).toFixed(1) : '–'}</td>
        <td class="mono">${fmt(c.alignment.regime, 3)}</td>
      </tr>`;
    })}</tbody></table></div>`;
}

function Timeline() {
  const s = useStore();
  const names = s.session?.combinations || [];
  const series = s.series;
  if (series.length < 2) return html`<div class="empty">No history yet.</div>`;
  const t0 = series[0].t, t1 = series[series.length - 1].t, span = t1 - t0 || 1;
  return html`<div class="timeline">${names.map(n => {
    const blocks = [];
    let start = series[0].t, mode = series[0].modes[n];
    for (const p of series) {
      if (p.modes[n] !== mode) { blocks.push([start, p.t, mode]); start = p.t; mode = p.modes[n]; }
    }
    blocks.push([start, t1, mode]);
    return html`<div class="row"><div class="name">${n}</div>
      <svg viewBox="0 0 1000 14" preserveAspectRatio="none">${blocks.map(([a, b, m]) =>
        html`<rect x=${(a - t0) / span * 1000} width=${Math.max((b - a) / span * 1000, 0.5)} y="0" height="14" fill=${MODE_COLOR[m] || '#333'} />`)}</svg></div>`;
  })}
  <div class="legend" style="margin-top:6px"><span style="--c:#5d6678">warmup</span><span style="--c:#2d5fa8">paper</span><span style="--c:#3ecf8e">active</span></div></div>`;
}

function MarketPanel() {
  const s = useStore();
  const history = tail(s.series, 720);
  return html`<div class="metrics">${MARKET.map(([key, label, show]) => html`
    <div class="metric"><div class="label">${label}</div>
      <div class="value">${s.detail ? show(s.detail.market[key]) : '–'}</div>
      <${Spark} values=${history.map(p => p.market[key])} width=${140} height=${26} /></div>`)}</div>`;
}

function BehaviorPanel() {
  const s = useStore();
  const d = s.detail;
  if (!d) return html`<div class="empty">–</div>`;
  const vr = d.market.variance_ratio;
  return html`<div class="scroll"><table>
    <thead><tr><th>Combination</th><th>Activity</th><th>Bias</th><th>Flips / h</th><th>Character 60s</th><th>IC 60s</th><th>IC 300s</th><th>IC 1800s</th><th>Trades / h</th><th>Holding</th><th>Win rate</th><th>Exposure</th></tr></thead>
    <tbody>${Object.entries(d.combinations).map(([n, c]) => html`<tr>
      <td><span class="dot" style=${`background:${colorOf(n)}`}></span>${n}</td>
      <td class="mono">${fmt(c.detection.activity, 2)}</td><td class="mono">${fmt(c.detection.bias, 2)}</td>
      <td class="mono">${fmt(c.detection.flip_rate, 1)}</td>
      <td class=${'mono ' + ((c.detection.character_60s || 0) * (vr - 1) >= 0 ? 'good' : 'bad')}>${fmt(c.detection.character_60s, 2)}</td>
      <td class="mono">${fmt(c.detection.ic_60s, 3)}</td><td class="mono">${fmt(c.detection.ic_300s, 3)}</td><td class="mono">${fmt(c.detection.ic_1800s, 3)}</td>
      <td class="mono">${fmt(c.trading.trade_rate, 1)}</td><td class="mono">${c.trading.holding ? (c.trading.holding / 60).toFixed(0) + ' m' : '–'}</td>
      <td class="mono">${fmt(c.trading.win_rate, 2)}</td><td class="mono">${fmt(c.trading.exposure, 2)}</td>
    </tr>`)}</tbody></table>
    <div class="muted" style="margin-top:6px">Character is green when it agrees with the market's variance ratio (${fmt(vr, 2)}): following in a trending market, fading in a reverting one.</div></div>`;
}

function ParametersPanel({ onSelect }) {
  const s = useStore();
  const d = s.detail;
  if (!d) return html`<div class="empty">–</div>`;
  const history = tail(s.series, 720);
  const rows = [];
  for (const [n, c] of Object.entries(d.combinations)) {
    for (const [p, v] of Object.entries(c.parameters)) {
      if (v.kind === 'Fixed') continue;
      rows.push({ n, p, v, values: history.map(h => h.parameters?.[n]?.[p] ?? null) });
    }
  }
  rows.sort((a, b) => Math.abs(b.v.speed || 0) - Math.abs(a.v.speed || 0));
  return html`<div class="scroll"><table>
    <thead><tr><th>Combination</th><th>Parameter</th><th>Kind</th><th>Value</th><th>Estimate</th><th>Speed %/h</th><th>Updates</th><th>History</th></tr></thead>
    <tbody>${rows.map(({ n, p, v, values }) => html`<tr onClick=${() => onSelect(n)}>
      <td><span class="dot" style=${`background:${colorOf(n)}`}></span>${n}</td><td class="mono">${p}</td><td>${v.kind}</td>
      <td class="mono">${fmt(v.value, 3)}</td><td class="mono">${fmt(v.estimate, 3)}</td>
      <td class="mono">${v.speed != null ? (v.speed * 100).toFixed(1) : '–'}</td><td class="mono">${v.updates}</td>
      <td><${Spark} values=${values} color=${colorOf(n)} /></td></tr>`)}</tbody></table></div>`;
}

function Drawer({ name, onClose }) {
  const s = useStore();
  const c = s.detail?.combinations?.[name];
  const st = s.structure[name];
  if (!c || !st) return null;
  const history = tail(s.series, 720);
  const recent = s.trades.filter(t => t.combination === name && t.kind === 'close').slice(-15).reverse();
  const kv = obj => html`<div class="kv">${Object.entries(obj).map(([k, v]) => html`<div>${k}</div><div>${typeof v === 'number' ? fmt(v, 4) : (v ?? '–')}</div>`)}</div>`;
  return html`<div class="drawer">
    <div style="display:flex;align-items:center;gap:10px">
      <span class="dot" style=${`display:inline-block;width:12px;height:12px;border-radius:50%;background:${colorOf(name)}`}></span>
      <h3>${name}</h3><span class=${'pill ' + c.member.mode}>${c.member.mode}</span>
      <span class="spacer"></span><button class="ghost" onClick=${onClose}>Close</button></div>
    <div class="muted">${st.strategy} strategy, ${st.manager} manager; collaborator horizon ${c.member.horizon} s</div>

    <section><h4>Indicators</h4>${st.indicators.map((ind, i) => html`<div style="margin-bottom:6px">
      <b>${ind.type}</b>${ind.follow === false ? ' (fading)' : ''} — now <span class="mono">${c.signals[i]?.direction ?? '–'}</span>
      ${c.signals[i]?.threshold != null ? html` · threshold <span class="mono">${fmt(c.signals[i].threshold, 3)}</span>` : ''}
      <div>${ind.generators.map(g => html`<span class="tag">${g}</span>`)}</div></div>`)}</section>

    <section><h4>Dynamic parameters</h4><table><thead><tr><th>Name</th><th>Kind</th><th>Value</th><th>Speed %/h</th><th>History</th></tr></thead>
      <tbody>${Object.entries(c.parameters).map(([p, v]) => html`<tr>
        <td class="mono">${p}</td><td>${v.kind}</td><td class="mono">${fmt(v.value, 3)}</td>
        <td class="mono">${v.speed != null ? (v.speed * 100).toFixed(1) : '–'}</td>
        <td><${Spark} values=${history.map(h => h.parameters?.[name]?.[p] ?? null)} width=${90} color=${colorOf(name)} /></td></tr>`)}</tbody></table></section>

    <section><h4>Collaborator evidence</h4>${kv({ score: c.member.score, 'trades z': c.member.trade_z, 'behavior z': c.member.behavior_z, weight: c.member.weight, promotions: c.member.promotions, demotions: c.member.demotions, 'copied P&L (bps)': c.member.realized * 1e4 })}
      <${Spark} values=${history.map(h => h.scores?.[name] ?? null)} width=${520} height=${40} color=${colorOf(name)} /></section>
    <section><h4>Detection behavior</h4>${kv(c.detection)}</section>
    <section><h4>Trading behavior</h4>${kv(c.trading)}</section>
    ${c.skill != null ? html`<section><h4>Predictor</h4>${kv({ skill: c.skill, 'forecast (bps)': c.forecast })}</section>` : ''}
    <section><h4>Recent trades</h4><table><thead><tr><th>Closed</th><th>Side</th><th>Net (bps)</th><th>Reason</th><th>Mode</th></tr></thead>
      <tbody>${recent.map(t => html`<tr><td class="mono">${clock(t.time).slice(11)}</td><td>${t.side}</td>
        <td class=${'mono ' + (t.net >= 0 ? 'good' : 'bad')}>${(t.net * 1e4).toFixed(1)}</td><td>${t.reason}</td><td>${t.mode}</td></tr>`)}</tbody></table></section>
  </div>`;
}

function NewRun({ options, onStarted }) {
  const defaults = options?.defaults || {};
  const [form, setForm] = useState({ catalog: 'trend', source: 'history', start: '2024-01-01', end: '', seed: 0, hours: 24, fee_bps: 20, edge_bps: 0,
    edge_kind: 'trend', edge_hours: 2, edge_switch_hours: 0, segment: 4, speed: 86400, ...defaults, catalog: 'trend', source: 'history', speed: 86400 });
  const [pairs, setPairs] = useState(['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']);
  const set = key => event => setForm({ ...form, [key]: event.target.type === 'number' ? Number(event.target.value) : event.target.value });
  const trend = form.catalog === 'trend' || form.catalog === 'mined';
  const sources = trend ? ['history', 'live'] : ['synthetic', 'database', 'live'];
  const [error, setError] = useState('');
  const start = async () => {
    if (trend) {
      const result = await api('/api/portfolios', { ...form, symbols: pairs });
      if (result.error) { setError(result.error); return; }
      onStarted(result.sessions[0].id);
    } else {
      const session = await api('/api/sessions', form);
      onStarted(session.id);
    }
  };
  const field = (key, label, type = 'number', extra = {}) => html`<label>${label}<input type=${type} value=${form[key]} onInput=${set(key)} ...${extra} /></label>`;
  const toggle = pair => setPairs(pairs.includes(pair) ? pairs.filter(p => p !== pair) : [...pairs, pair]);
  return html`<div class="form">
    <label>System<select value=${form.catalog} onChange=${e => { const catalog = e.target.value; const hourly = catalog !== 'microstructure'; setForm({ ...form, catalog, source: hourly ? 'history' : 'synthetic', speed: hourly ? 86400 : 600 }); }}>
      <option value="trend">trend (hourly, paper)</option><option value="mined">full system: trend + mined (hourly, paper)</option><option value="microstructure">microstructure (tick)</option></select></label>
    <label>Source<select value=${form.source} onChange=${set('source')}>${sources.map(v => html`<option value=${v}>${v}</option>`)}</select></label>
    ${trend && form.source === 'history' ? html`${field('start', 'From (UTC date)', 'text')}${field('end', 'To (empty: latest)', 'text')}` : ''}
    ${!trend && form.source === 'synthetic' ? html`${field('seed', 'Seed')}${field('edge_bps', 'Planted edge (bps/h)', 'number', { step: 5 })}
      <label>Edge kind<select value=${form.edge_kind} onChange=${set('edge_kind')}><option value="trend">trend</option><option value="reversion">reversion</option></select></label>
      ${field('edge_hours', 'Edge half-life (h)', 'number', { step: 0.5 })}${field('edge_switch_hours', 'Switch regime every (h, 0 off)', 'number', { step: 1 })}` : ''}
    ${!trend && form.source === 'database' ? html`<label>Segment<select value=${form.segment} onChange=${set('segment')}>${(options?.segments || []).map(s => html`<option value=${s.index}>${s.index}: ${s.start.slice(0, 16)} (${s.hours} h)</option>`)}</select></label>` : ''}
    ${!trend && form.source !== 'live' ? field('hours', 'Hours') : ''}
    ${!trend ? field('fee_bps', 'Round-trip fee (bps)', 'number', { step: 1 }) : ''}
    ${form.source !== 'live' ? html`<label>Speed<select value=${form.speed} onChange=${e => setForm({ ...form, speed: Number(e.target.value) })}>${(trend ? TREND_SPEEDS : SPEEDS).map(([v, l]) => html`<option value=${v}>${l}</option>`)}</select></label>` : ''}
    <button class="primary" onClick=${start}>Start ${trend ? 'portfolio' : 'run'}</button>
    ${error ? html`<span class="error">${error}</span>` : ''}
    ${trend ? html`<div style="grid-column: 1 / -1" class="pairs">${(options?.pairs || []).map(p => html`
      <label class="check"><input type="checkbox" checked=${pairs.includes(p)} onChange=${() => toggle(p)} /> ${p}</label>`)}
      <span class="muted">${trend ? 'Futures taker fees, slippage and funding; paper only (no orders are ever sent).' : ''}</span></div>` : ''}
  </div>`;
}

function Portfolio({ group, onPick }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    let alive = true;
    const pull = async () => { try { const d = await api(`/api/groups/${group}`); if (alive) setData(d); } catch { } };
    pull();
    const timer = setInterval(pull, 4000);
    return () => { alive = false; clearInterval(timer); };
  }, [group]);
  const options = useMemo(() => ({
    scales: { x: { time: true } }, axes: [AXIS, { ...AXIS, size: 60, values: (u, v) => v.map(x => x.toFixed(0)) }],
    series: [{}, { label: 'portfolio', stroke: '#ffffff', width: 2 }], legend: { show: false },
  }), []);
  if (!data || data.error) return html`<div class="empty">Loading the portfolio…</div>`;
  const chart = [data.equity.t, data.equity.v.map(v => (v - 1) * 1e4)];
  const last = data.equity.v.length ? (data.equity.v[data.equity.v.length - 1] - 1) * 1e4 : null;
  return html`<div>
    <div class="muted" style="margin-bottom:6px">Equal weight over ${data.sessions.length} pairs · portfolio P&L <b class=${last >= 0 ? 'good' : 'bad'}>${last == null ? '–' : (last >= 0 ? '+' : '') + last.toFixed(0) + ' bps'}</b></div>
    ${data.equity.t.length > 1 ? html`<${Plot} options=${options} data=${chart} height=${180} />` : ''}
    <div class="pairs" style="margin-top:8px">${data.sessions.map(x => html`<button class="ghost" onClick=${() => onPick(x.id)}>
      ${x.settings.symbol} <span class=${'pill ' + x.status}>${x.status}</span> <span class=${'mono ' + ((x.equity ?? 1) >= 1 ? 'good' : 'bad')}>${bps(x.equity)}</span></button>`)}</div>
  </div>`;
}

function TopBar({ sessions, current, onPick, onNew }) {
  const s = useStore();
  const session = current === 'miner' ? null : s.session;
  const act = async (action, value) => { if (current) { await api(`/api/sessions/${current}`, { action, value }); } };
  return html`<div class="top">
    <div class="brand">Rapid Markets <span>Lab</span></div>
    <select value=${current || ''} onChange=${e => onPick(e.target.value)}>
      <option value="">— runs —</option>
      ${sessions.map(x => html`<option value=${x.id}>${x.settings.group ? 'portfolio ' + x.settings.group + ' · ' + x.settings.symbol : x.id} · ${x.settings.catalog} · ${x.settings.source}${x.settings.source === 'synthetic' ? ' seed ' + x.settings.seed : ''} · ${x.status}</option>`)}
    </select>
    <button onClick=${onNew}>New run</button>
    <button class=${current === 'miner' ? 'primary' : ''} onClick=${() => onPick('miner')}>Miner</button>
    ${session ? html`<span class=${'pill ' + session.status}>${session.status}</span>
      <button onClick=${() => act(session.status === 'paused' ? 'resume' : 'pause')}>${session.status === 'paused' ? 'Resume' : 'Pause'}</button>
      <button onClick=${() => act('stop')}>Stop</button>
      ${session.settings?.source !== 'live' ? html`<select value=${session.settings?.speed} onChange=${e => act('speed', Number(e.target.value))}>${(session.settings?.catalog !== 'microstructure' ? TREND_SPEEDS : SPEEDS).map(([v, l]) => html`<option value=${v}>${l}</option>`)}</select>` : html`<span class="muted">live paper</span>`}
      ${session.error ? html`<span class="error">${session.error}</span>` : ''}` : ''}
    <span class="spacer"></span>
    <span class="clock">${clock(session?.time)}</span></div>`;
}

function App() {
  const [options, setOptions] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [current, setCurrent] = useState(location.hash.slice(1) || null);
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState(null);
  const [showPaper, setShowPaper] = useState(true);
  useStore();

  const refresh = async () => { try { setSessions(await api('/api/sessions')); } catch { /* server restarting */ } };
  useEffect(() => { api('/api/options').then(setOptions); refresh(); const timer = setInterval(refresh, 3000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    if (current === 'miner') { if (socket) socket.close(); location.hash = 'miner'; }
    else if (current) { connect(current); location.hash = current; }
  }, [current]);
  useEffect(() => {
    const follow = () => setCurrent(location.hash.slice(1) || null);
    addEventListener('hashchange', follow);
    return () => removeEventListener('hashchange', follow);
  }, []);

  const started = id => { setCreating(false); setCurrent(id); refresh(); };

  return html`
    <${TopBar} sessions=${sessions} current=${current} onPick=${id => setCurrent(id || null)} onNew=${() => setCreating(!creating)} />
    <main>
      ${current === 'miner' && !creating ? html`<${MinerConsole} options=${options} onStarted=${started} />` : ''}
      ${creating || !current ? html`<div class="card span-12"><h2>New run <span class="hint">synthetic data from the calibrated model (with an optional planted edge), recorded data, or the live market</span></h2>
        <${NewRun} options=${options} onStarted=${started} /></div>` : ''}
      ${current && current !== 'miner' ? html`
        ${store.session?.settings?.group ? html`<div class="card span-12"><h2>Portfolio <span class="hint">${store.session.settings.group}; click a pair to open it</span></h2>
          <${Portfolio} group=${store.session.settings.group} onPick=${id => setCurrent(id)} /></div>` : ''}
        <${Kpis} />
        <div class="card span-8"><h2>Market <span class="hint">▲▼ entries, ○ exits; solid when copied by the collaborator</span>
          <span class="spacer"></span><label class="muted"><input type="checkbox" style="width:auto" checked=${showPaper} onChange=${e => setShowPaper(e.target.checked)} /> paper trades</label></h2>
          <${PriceChart} showPaper=${showPaper} /></div>
        <div class="card span-4"><h2>Equity <span class="hint">bps</span></h2><${EquityChart} /></div>
        <div class="card span-12"><h2>Members <span class="hint">click a row for its components</span></h2><${Members} selected=${selected} onSelect=${setSelected} /></div>
        <div class="card span-6"><h2>Modes over time</h2><${Timeline} /></div>
        <div class="card span-6"><h2>Market behavior</h2><${MarketPanel} /></div>
        <div class="card span-12"><h2>Detection and trading behavior <span class="hint">how each strategy calls and each manager trades</span></h2><${BehaviorPanel} /></div>
        <div class="card span-12"><h2>Dynamic parameters <span class="hint">sorted by how fast they adapt</span></h2><${ParametersPanel} onSelect=${setSelected} /></div>
      ` : ''}
    </main>
    ${selected ? html`<${Drawer} name=${selected} onClose=${() => setSelected(null)} />` : ''}`;
}

render(html`<${App} />`, document.getElementById('app'));
