// miner.js: the alpha miner's console, live from the server's miner hub (/ws/miner).

import { html, useState, useEffect, useRef, useMemo, fmt, clock, day, ago, api, annualSharpe, Plot, AXIS, Spark } from './common.js';

const SLEEVES = [
  ['system', 'system (three sleeves)', '#ffffff', 2.2],
  ['trend', 'trend (F2)', '#6aa9ff', 1.2],
  ['crowd', 'crowd', '#3ecf8e', 1.2],
  ['selected', 'selected', '#f5b84b', 1.2],
];
const FAMILY_COLOR = { price: '#6aa9ff', volume: '#f5b84b', flow: '#3ecf8e', 'volume+flow': '#c38bff' };
const BUSY = ['updating data', 'extending the records', 'searching', 'reviewing', 'saving the record and the catalogs', 'loaded', 'round', 'selected', 'crowd'];

// The live connection -------------------------------------------------------------------------------------------

function useMiner(run) {
  const [snap, setSnap] = useState(null);
  const [log, setLog] = useState([]);
  const [live, setLive] = useState({ status: null, service: null });
  const [version, setVersion] = useState(0);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let socket = null, alive = true, timer = null;
    const handle = m => {
      if (m.type === 'snapshot') { setSnap(m); setLog(m.log || []); setLive({ status: m.status, service: m.service }); setVersion(v => v + 1); }
      else if (m.type === 'status') setLive({ status: m.status, service: m.service });
      else if (m.type === 'log') setLog(l => [...l, ...m.lines].slice(-600));
      else if (m.type === 'asked') setLog(l => [...l, `                         requested from the console: ${m.action} (picked up within half a minute)`]);
      else if (m.type === 'record') api(`/api/miner?run=${run || ''}`).then(s => { if (s.run === m.run) { setSnap(s); setVersion(v => v + 1); } });
    };
    const open = () => {
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/miner${run ? '?run=' + run : ''}`);
      socket.binaryType = 'arraybuffer';
      socket.onopen = () => setConnected(true);
      socket.onmessage = event => {
        const text = typeof event.data === 'string' ? event.data : new TextDecoder().decode(event.data);
        for (const m of JSON.parse(text)) handle(m);
      };
      socket.onclose = () => { setConnected(false); if (alive) timer = setTimeout(open, 3000); };
    };
    open();
    return () => { alive = false; clearTimeout(timer); socket && socket.close(); };
  }, [run]);

  return { snap, log, live, version, connected };
}

// Pieces ----------------------------------------------------------------------------------------------------------

function sharpeClass(v) { return v == null ? '' : v > 0 ? 'good' : v < 0 ? 'bad' : ''; }

function FamilyTag({ family }) {
  return html`<span class="tag" style=${`border-color:${FAMILY_COLOR[family] || '#333'};color:${FAMILY_COLOR[family] || 'inherit'}`}>${family}</span>`;
}

function Diverging({ value, width = 90 }) {
  // A position or score in [-1, 1]: red to the left of the middle, green to the right.
  if (value == null || !Number.isFinite(value)) return html`<span class="diverging" style=${`width:${width}px`}></span>`;
  const v = Math.max(-1, Math.min(1, value));
  const style = v >= 0 ? `left:50%;width:${v * 50}%;background:var(--good)` : `left:${50 + v * 50}%;width:${-v * 50}%;background:var(--bad)`;
  return html`<span class="diverging" style=${`width:${width}px`}><i style=${style}></i></span>`;
}

function StatusBar({ snap, live, connected, run, setRun, onAsk, onService, message }) {
  const status = live.status, service = live.service || {};
  const tone = !service.running ? 'stopped' : status?.state === 'error' ? 'error' : BUSY.includes(status?.state) ? 'busy' : 'idle';
  const label = { stopped: 'stopped', error: 'error', busy: 'working', idle: 'running' }[tone];
  return html`<div class="card span-12 statusbar">
    <div class="pairs">
      <span class=${'beacon ' + tone}></span>
      <b>Live miner: ${label}</b>
      ${status ? html`<span class="muted">${status.state}${status.event ? ': ' + status.event : ''} · ${ago(status.time)}</span>` : ''}
      ${status?.next ? html`<span class="muted">· next check ${clock(status.next).slice(11, 16)} UTC</span>` : ''}
      ${status?.error ? html`<span class="error">${status.error}</span>` : ''}
      <span class="spacer"></span>
      <span class=${'muted ' + (connected ? '' : 'error')}>${connected ? 'streaming' : 'reconnecting…'}</span>
      <label class="muted">Record <select value=${snap?.run || run} onChange=${e => setRun(e.target.value)}>${(snap?.runs || []).map(r => html`<option value=${r}>${r}</option>`)}</select></label>
      ${service.running ? html`
        <button onClick=${() => onAsk('search')} title="simulate fresh random formulas into the pool now">Search now</button>
        <button onClick=${() => onAsk('review')} title="refresh the crowd and choose the selected sleeve again now">Review now</button>` : ''}
      ${service.child ? html`<button onClick=${() => onService('stop')}>Stop</button>` : ''}
      ${!service.running ? html`<button class="primary" onClick=${() => onService('start')}>Start live miner</button>` : ''}
    </div>
    ${message ? html`<div class="muted" style="margin-top:6px">${message}</div>` : ''}
    ${service.running && !service.child ? html`<div class="faint" style="margin-top:4px">started outside the dashboard (python -m miner): requests reach it through data/miner/live/control.json</div>` : ''}
  </div>`;
}

function Kpis({ snap }) {
  const sum = snap.summary || {}, perf = snap.performance || {};
  const system = perf.system || (perf.crowd && perf.selected ? perf.crowd.map((v, i) => (v + perf.selected[i]) / 2) : null);
  const items = [
    ['System Sharpe', fmt(annualSharpe(system), 2), sharpeClass(annualSharpe(system)), `three sleeves, since ${day(perf.days?.[0] * 86400)}`],
    ['Trend · crowd · selected', [perf.trend, perf.crowd, perf.selected].map(x => fmt(annualSharpe(x), 2)).join(' · '), '', 'Sharpe of each sleeve, as traded'],
    ['Pool', (sum.pool ?? 0).toLocaleString(), '', `random formulas on ${sum.pairs ?? '–'} pairs`],
    ['Search rounds', snap.rounds ?? 0, '', '200 fresh formulas a week'],
    ['Selected', sum.selected ?? '–', '', `best over ${snap.plan?.window ?? '–'} days, chosen monthly`],
    ['Crowd', sum.crowd ?? '–', '', `random, never chosen; ${snap.plan?.refresh ?? '–'} replaced a month`],
  ];
  return html`<div class="kpis span-12">${items.map(([label, value, cls, sub]) => html`
    <div class="card kpi"><div class="label">${label}</div><div class=${'value ' + cls}>${value}</div><div class="sub">${sub}</div></div>`)}</div>`;
}

function SleeveChart({ perf }) {
  const [range, setRange] = useState('all');
  const [hidden, setHidden] = useState({});
  const options = useMemo(() => ({
    scales: { x: { time: true } },
    axes: [AXIS, { ...AXIS, size: 56, values: (u, v) => v.map(x => x.toFixed(0) + '%') }],
    series: [{}, ...SLEEVES.map(([key, label, stroke, width]) => ({ label, stroke, width, show: !hidden[key] }))],
    legend: { show: false }, cursor: { drag: { x: true, y: false } },
  }), [JSON.stringify(hidden)]);
  const data = useMemo(() => {
    if (!perf?.days?.length) return null;
    const keep = { all: perf.days.length, '1y': 365, '90d': 90 }[range];
    const start = Math.max(perf.days.length - keep, 0);
    const system = perf.system || perf.crowd.map((v, i) => (v + perf.selected[i]) / 2);
    const series = { system, trend: perf.trend, crowd: perf.crowd, selected: perf.selected };
    const curve = values => { if (!values) return perf.days.slice(start).map(() => null); let e = 1; return values.slice(start).map(v => { e *= 1 + v; return (e - 1) * 100; }); };
    return [perf.days.slice(start).map(d => d * 86400), ...SLEEVES.map(([key]) => curve(series[key]))];
  }, [perf, range]);
  if (!data) return html`<div class="empty">No record yet.</div>`;
  return html`<div>
    <div class="pairs" style="margin-bottom:6px">
      <div class="segmented">${['90d', '1y', 'all'].map(r => html`<button class=${range === r ? 'on' : ''} onClick=${() => setRange(r)}>${r}</button>`)}</div>
      <span class="spacer"></span>
      <div class="legend">${SLEEVES.map(([key, label, color]) => html`<span class=${'toggle ' + (hidden[key] ? 'off' : '')} style=${`--c:${color}`}
        onClick=${() => setHidden({ ...hidden, [key]: !hidden[key] })}>${label}</span>`)}</div>
    </div>
    <${Plot} options=${options} data=${data} height=${260} />
  </div>`;
}

function LiveLog({ lines, running }) {
  const box = useRef(null);
  const [follow, setFollow] = useState(true);
  useEffect(() => { if (follow && box.current) box.current.scrollTop = box.current.scrollHeight; }, [lines, follow]);
  return html`<div>
    <div class="log" ref=${box} onScroll=${e => { const el = e.target; setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 30); }}>
      ${lines.length ? lines.map(line => html`<div class=${/error/.test(line) ? 'error' : /selected|round|crowd/.test(line) ? 'hl' : ''}>${line}</div>`)
        : html`<div class="faint">${running ? 'Waiting for the miner to write its log (data/miner/live/log.txt)…' : 'The live miner is not running.'}</div>`}
    </div>
    ${!follow ? html`<button class="ghost" style="margin-top:6px" onClick=${() => setFollow(true)}>Follow the log</button>` : ''}
  </div>`;
}

function Signals({ signals }) {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('system');
  if (!signals?.pairs) return html`<div class="empty">No signals in this record yet (written with each save of the live miner).</div>`;
  const rows = Object.entries(signals.pairs).map(([symbol, s]) => {
    const stakes = ['trend', 'crowd', 'selected'].map(k => s[k]?.stake).filter(v => v != null);
    return { symbol, ...s, system: stakes.length ? stakes.reduce((a, b) => a + b, 0) / 3 : null };
  }).filter(r => r.symbol.toLowerCase().includes(query.toLowerCase()));
  const key = r => sort === 'system' ? -Math.abs(r.system ?? 0) : sort === 'name' ? r.symbol : -Math.abs(r[sort]?.stake ?? 0);
  rows.sort((a, b) => key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0);
  const longs = rows.filter(r => (r.system ?? 0) > 0.02).length, shorts = rows.filter(r => (r.system ?? 0) < -0.02).length;
  return html`<div>
    <div class="pairs" style="margin-bottom:8px">
      <input placeholder="Filter pairs" style="max-width:180px" value=${query} onInput=${e => setQuery(e.target.value)} />
      <label class="muted">Sort <select value=${sort} onChange=${e => setSort(e.target.value)}>
        <option value="system">largest system position</option><option value="trend">trend</option><option value="crowd">crowd</option><option value="selected">selected</option><option value="name">name</option></select></label>
      <span class="spacer"></span>
      <span class="muted">${longs} long · ${shorts} short · at ${clock(signals.time)} UTC</span>
    </div>
    <div class="scroll signals"><table>
      <thead><tr><th>Pair</th><th>Trend</th><th></th><th>Crowd</th><th></th><th>Selected</th><th></th><th>System position</th><th></th></tr></thead>
      <tbody>${rows.map(r => html`<tr>
        <td class="mono">${r.symbol.replace('USDT', '')}</td>
        ${['trend', 'crowd', 'selected'].map(k => html`<td class=${'mono ' + sharpeClass(r[k]?.stake)}>${fmt(r[k]?.stake, 2)}</td><td><${Diverging} value=${r[k]?.stake} /></td>`)}
        <td class=${'mono ' + sharpeClass(r.system)}><b>${fmt(r.system, 2)}</b></td><td><${Diverging} value=${r.system} width=${120} /></td>
      </tr>`)}</tbody></table></div>
    <div class="faint" style="margin-top:6px">Each sleeve's target position on a pair, a signed fraction of its capital there (volatility-targeted to 2% a day, at most 1); the system holds their mean. Paper only: no orders are ever sent.</div>
  </div>`;
}

function FormulaTable({ rows, onOpen, empty }) {
  if (!rows?.length) return html`<div class="empty">${empty || 'Nothing here.'}</div>`;
  return html`<div class="scroll"><table>
    <thead><tr><th>Formula</th><th>Data</th><th>2 years</th><th>1 year</th><th>90 days</th><th>Last year</th></tr></thead>
    <tbody>${rows.map(r => html`<tr onClick=${() => onOpen(r.formula)}>
      <td class="mono formula">${r.formula}${r.selected ? html` <span class="pill active">selected</span>` : ''}${r.crowd ? html` <span class="pill paper">crowd</span>` : ''}</td>
      <td><${FamilyTag} family=${r.family} /></td>
      <td class=${'mono ' + sharpeClass(r.sharpe_730)}>${fmt(r.sharpe_730)}</td>
      <td class=${'mono ' + sharpeClass(r.sharpe_365)}>${fmt(r.sharpe_365)}</td>
      <td class=${'mono ' + sharpeClass(r.sharpe_90)}>${fmt(r.sharpe_90)}</td>
      <td><${Spark} values=${r.spark || []} width=${110} height=${24} color=${(r.sharpe_365 ?? 0) >= 0 ? '#3ecf8e' : '#ff6b6b'} /></td>
    </tr>`)}</tbody></table></div>`;
}

function Lifecycle({ run, version, onOpen }) {
  const [data, setData] = useState(null);
  useEffect(() => { api(`/api/miner/timeline?run=${run}`).then(setData); }, [run, version]);
  if (!data) return html`<div class="empty">Loading…</div>`;
  if (!data.rows?.length) return html`<div class="empty">No selections yet.</div>`;
  const columns = `minmax(160px, 260px) repeat(${data.months.length}, minmax(6px, 1fr))`;
  return html`<div>
    <div class="faint" style="margin-bottom:8px">${data.rows.length} formulas have been in the selected sleeve. Each row is one, each column a month, lit while it was selected:
      alphas arrive, hold a while, fade and drop out as fresher ones rank higher. Click a row for the formula.</div>
    <div class="lifecycle">
      <div class="lifegrid head" style=${`grid-template-columns:${columns}`}>
        <div></div>${data.months.map(m => html`<div class="month">${m.endsWith('-01') || m === data.months[0] ? m.slice(0, 4) : ''}</div>`)}
      </div>
      <div class="lifebody">${data.rows.map(r => html`
        <div class="lifegrid row" style=${`grid-template-columns:${columns}`} onClick=${() => onOpen(r.formula)}
          title=${`${r.formula}\n${r.months} months selected; 90-day Sharpe ${fmt(r.sharpe_90)}`}>
          <div class="label mono">${r.formula}</div>
          ${r.cells.map(on => html`<div class=${on ? ((r.sharpe_90 ?? 0) >= 0 ? 'cell on' : 'cell fading') : 'cell'}></div>`)}
        </div>`)}</div>
    </div>
    <div class="legend" style="margin-top:6px"><span style="--c:#3ecf8e">selected, still earning (90-day Sharpe above 0)</span><span style="--c:#f5b84b">selected, fading now</span></div>
  </div>`;
}

function PoolExplorer({ run, version, onOpen }) {
  const [query, setQuery] = useState('');
  const [typed, setTyped] = useState('');
  const [family, setFamily] = useState('');
  const [which, setWhich] = useState('');
  const [sort, setSort] = useState('sharpe_730');
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);
  useEffect(() => { const t = setTimeout(() => { setQuery(typed); setPage(0); }, 300); return () => clearTimeout(t); }, [typed]);
  useEffect(() => {
    const q = new URLSearchParams({ run, q: query, family, which, sort, limit: 25, offset: page * 25 });
    api(`/api/miner/pool?${q}`).then(setData);
  }, [run, query, family, which, sort, page, version]);
  const pages = data ? Math.max(Math.ceil(data.total / 25), 1) : 1;
  return html`<div>
    <div class="pairs" style="margin-bottom:8px">
      <input placeholder="Search formulas (e.g. volume, corr, flow)" style="max-width:280px" value=${typed} onInput=${e => setTyped(e.target.value)} />
      <label class="muted">Data <select value=${family} onChange=${e => { setFamily(e.target.value); setPage(0); }}>
        <option value="">all</option>${(data?.families || []).map(f => html`<option value=${f}>${f}</option>`)}</select></label>
      <div class="segmented">${[['', 'all'], ['selected', 'selected'], ['crowd', 'crowd']].map(([v, l]) => html`
        <button class=${which === v ? 'on' : ''} onClick=${() => { setWhich(v); setPage(0); }}>${l}</button>`)}</div>
      <label class="muted">Sort <select value=${sort} onChange=${e => setSort(e.target.value)}>
        <option value="sharpe_730">2-year Sharpe</option><option value="sharpe_365">1-year Sharpe</option><option value="sharpe_90">90-day Sharpe</option><option value="size">simplest</option></select></label>
      <span class="spacer"></span>
      <span class="muted">${data ? data.total.toLocaleString() : '–'} formulas</span>
      <button class="ghost" disabled=${page === 0} onClick=${() => setPage(page - 1)}>‹</button>
      <span class="muted">${page + 1} / ${pages}</span>
      <button class="ghost" disabled=${page + 1 >= pages} onClick=${() => setPage(page + 1)}>›</button>
    </div>
    <${FormulaTable} rows=${data?.rows} onOpen=${onOpen} empty="No formula matches." />
  </div>`;
}

function TreeNode({ node }) {
  if (!node.args.length) return html`<span class="leaf">${node.op}</span>`;
  return html`<div class="tnode"><span class="op">${node.op}</span>${node.window ? html`<span class="win">${node.window}h</span>` : ''}
    <div class="kids">${node.args.map(a => html`<${TreeNode} node=${a} />`)}</div></div>`;
}

function FormulaDrawer({ run, formula, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => { setData(null); api(`/api/miner/formula?run=${run}&f=${encodeURIComponent(formula)}`).then(setData); }, [run, formula]);
  const options = useMemo(() => ({
    scales: { x: { time: true } }, axes: [AXIS, { ...AXIS, size: 50, values: (u, v) => v.map(x => (x * 100).toFixed(0) + '%') }],
    series: [{}, { label: 'record', stroke: '#6aa9ff', width: 1.5, fill: 'rgba(106,169,255,0.08)' }], legend: { show: false },
  }), []);
  return html`<div class="drawer">
    <div class="pairs"><h3>Formula</h3><span class="spacer"></span><button class="ghost" onClick=${onClose}>Close</button></div>
    <div class="mono formula-text">${formula}</div>
    ${!data ? html`<div class="empty">Loading…</div>` : data.error ? html`<div class="error">${data.error}</div>` : html`
      <div class="pairs" style="margin-top:8px"><${FamilyTag} family=${data.family} /><span class="tag">${data.size} nodes</span>
        ${data.selected ? html`<span class="pill active">selected now</span>` : ''}${data.crowd ? html`<span class="pill paper">in the crowd</span>` : ''}
        ${data.terminals.map(t => html`<span class="tag">${t}</span>`)}</div>
      <section><h4>Record on all pairs</h4>
        <div class="kv"><div>Sharpe, last 2 years</div><div class=${sharpeClass(data.sharpe_730)}>${fmt(data.sharpe_730)}</div>
          <div>last year</div><div class=${sharpeClass(data.sharpe_365)}>${fmt(data.sharpe_365)}</div>
          <div>last 90 days</div><div class=${sharpeClass(data.sharpe_90)}>${fmt(data.sharpe_90)}</div></div>
        ${data.curve ? html`<${Plot} options=${options} data=${[data.curve.t, data.curve.v]} height=${180} />` : html`<div class="faint">Not in this record's pool.</div>`}
        <div class="faint">Daily P&L of its own daily-rebalanced position on every pair, equal weight, futures costs and funding, summed.</div></section>
      ${data.years ? html`<section><h4>By year</h4><div class="pairs">${Object.entries(data.years).map(([y, v]) => html`
        <span class="tag">${y}: <span class=${sharpeClass(v)}>${fmt(v)}</span></span>`)}</div></section>` : ''}
      <section><h4>In the selected sleeve</h4>${data.months.length ? html`<div class="pairs">${data.months.map(m => html`<span class="tag">${m}</span>`)}</div>`
        : html`<div class="faint">Never selected.</div>`}</section>
      <section><h4>Structure</h4><div class="tree"><${TreeNode} node=${data.tree} /></div>
        <div class="faint">price and volume are log levels, ret the hourly log return, flow the taker-buy share (2 x buy / volume - 1); windows in hours; the result is scaled to its last 30 days and clipped to a score in [-1, 1].</div></section>`}
  </div>`;
}

function Events({ events }) {
  return html`<div class="scroll events">${(events || []).slice().reverse().slice(0, 200).map(e => html`
    <div class="event"><span class="mono muted">${day(e.time)}</span> <span class=${'pill ' + (e.kind === 'selected' ? 'active' : e.kind === 'round' ? 'warmup' : 'paper')}>${e.kind}</span> ${e.text}</div>`)}</div>`;
}

function Trade({ options, onStarted }) {
  const [pairs, setPairs] = useState(['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']);
  const [message, setMessage] = useState('');
  const trade = async source => {
    const result = await api('/api/portfolios', { catalog: 'mined', source, start: '2025-01-01', speed: 0, symbols: pairs });
    if (result.error) setMessage(result.error); else onStarted(result.sessions[0].id);
  };
  return html`<div>
    <div class="muted" style="line-height:1.6;margin-bottom:8px">Per pair, three sleeves on equal capital: <b>trend</b> (F2), the <b>crowd</b>
      (random formulas, never chosen by results) and the <b>selected</b> (the best two-year records, chosen again each month). Each mined sleeve
      follows the miner's catalog as it changes, with no warm-up and no flattening.</div>
    <div class="pairs">${(options?.pairs || []).map(p => html`
      <label class="check"><input type="checkbox" checked=${pairs.includes(p)} onChange=${() => setPairs(pairs.includes(p) ? pairs.filter(x => x !== p) : [...pairs, p])} /> ${p.replace('/USDT', '')}</label>`)}</div>
    <div class="pairs" style="margin-top:8px"><button class="primary" onClick=${() => trade('live')}>Paper-trade live</button>
      <button onClick=${() => trade('history')}>Replay since 2025</button>${message ? html`<span class="error">${message}</span>` : ''}</div>
  </div>`;
}

// The breadth miner -------------------------------------------------------------------------------------------

function BreadthConsole({ snap, log, live, version, run, options, onStarted }) {
  const [open, setOpen] = useState(null);
  const [tab, setTab] = useState('signals');
  const showLog = (snap.run === 'live');
  return html`
    <${Kpis} snap=${snap} />
    <div class=${'card ' + (showLog ? 'span-8' : 'span-12')}><h2>The sleeves as traded <span class="hint">cumulative return, walk-forward: every choice reads only the days before it</span></h2>
      <${SleeveChart} perf=${snap.performance} /></div>
    ${showLog ? html`<div class="card span-4"><h2>Live log <span class="hint">data/miner/live/log.txt</span></h2><${LiveLog} lines=${log} running=${live.service?.running} /></div>` : ''}
    <div class="card span-12">
      <div class="tabs">${[['signals', 'Signals now'], ['selected', `Selected sleeve (${snap.selected?.length ?? 0})`], ['lifecycle', 'Lifecycle'], ['pool', 'Pool explorer'], ['events', 'Events'], ['trade', 'Trade it']].map(([k, l]) => html`
        <button class=${tab === k ? 'on' : ''} onClick=${() => setTab(k)}>${l}</button>`)}
        <span class="spacer"></span><span class="muted">record at ${clock(snap.now)} · saved ${ago(snap.updated)}</span></div>
      ${tab === 'signals' ? html`<${Signals} signals=${snap.signals} />` : ''}
      ${tab === 'selected' ? html`<${FormulaTable} rows=${snap.selected} onOpen=${setOpen} empty="Nothing selected yet." />` : ''}
      ${tab === 'lifecycle' ? html`<${Lifecycle} run=${snap.run} version=${version} onOpen=${setOpen} />` : ''}
      ${tab === 'pool' ? html`<${PoolExplorer} run=${snap.run} version=${version} onOpen=${setOpen} />` : ''}
      ${tab === 'events' ? html`<${Events} events=${snap.events} />` : ''}
      ${tab === 'trade' ? html`<${Trade} options=${options} onStarted=${onStarted} />` : ''}
    </div>
    ${open ? html`<${FormulaDrawer} run=${snap.run} formula=${open} onClose=${() => setOpen(null)} />` : ''}`;
}

// Version 1's records (replay, null, planted) -----------------------------------------------------------------

const STATE_COLOR = { incubating: '#2d5fa8', active: '#3ecf8e', retired: '#f5b84b', rejected: '#5d6678' };

function HaircutChart({ alphas, kappa, minimum }) {
  const points = alphas.filter(a => (a.forward?.days || 0) >= minimum && Number.isFinite(a.forward?.sharpe) && Number.isFinite(a.insample?.sharpe));
  const w = 360, h = 240, pad = 34;
  const xs = points.map(a => a.insample.sharpe), ys = points.map(a => a.forward.sharpe);
  const x0 = 0, x1 = Math.max(3, ...xs), y0 = Math.min(-3, ...ys), y1 = Math.max(3, ...ys);
  const X = v => pad + (v - x0) / (x1 - x0) * (w - pad - 8), Y = v => h - pad - (v - y0) / (y1 - y0) * (h - pad - 8);
  return html`<svg width="100%" viewBox=${`0 0 ${w} ${h}`} class="scatter">
    <line x1=${X(x0)} x2=${X(x1)} y1=${Y(0)} y2=${Y(0)} stroke="#2a3346" />
    <line x1=${X(0)} x2=${X(Math.min(x1, y1))} y1=${Y(0)} y2=${Y(Math.min(x1, y1))} stroke="#3a4558" stroke-dasharray="2 4" />
    <line x1=${X(0)} x2=${X(x1)} y1=${Y(0)} y2=${Y(kappa * x1)} stroke="#f5b84b" stroke-dasharray="4 3" />
    ${points.map(a => html`<circle cx=${X(a.insample.sharpe)} cy=${Y(a.forward.sharpe)} r="3.2" fill=${STATE_COLOR[a.state]} opacity="0.85"><title>${a.id} ${a.formula}: in-sample ${fmt(a.insample.sharpe)}, forward ${fmt(a.forward.sharpe)} (${a.forward.days} days)</title></circle>`)}
    <text x=${w / 2} y=${h - 6} fill="#8b95a8" font-size="11" text-anchor="middle">in-sample Sharpe</text>
    <text x="10" y=${h / 2} fill="#8b95a8" font-size="11" transform=${`rotate(-90 10 ${h / 2})`} text-anchor="middle">forward Sharpe</text>
    <text x=${w - 10} y="16" fill="#f5b84b" font-size="11" text-anchor="end">haircut ${fmt(kappa, 2)}</text>
  </svg>`;
}

function AlphaTable({ alphas }) {
  if (!alphas.length) return html`<div class="empty">None.</div>`;
  return html`<div class="scroll"><table>
    <thead><tr><th>Alpha</th><th>Formula</th><th>Rebalance</th><th>Born</th><th>In-sample</th><th>Forward</th><th>Days</th><th>Expected</th><th>State</th></tr></thead>
    <tbody>${alphas.map(a => html`<tr>
      <td class="mono"><span class="dot" style=${`background:${STATE_COLOR[a.state]}`}></span>${a.id}</td>
      <td class="mono formula">${a.formula}</td><td>${a.timing ? 'pullback' : 'daily'}</td><td class="mono">${day(a.born)}</td>
      <td class="mono">${fmt(a.insample?.sharpe)}</td><td class=${'mono ' + sharpeClass(a.forward?.sharpe)}>${fmt(a.forward?.sharpe)}</td>
      <td class="mono">${a.forward?.days ?? 0}</td><td class="mono">${fmt(a.forward?.expected)}</td><td>${a.state}</td></tr>`)}</tbody></table></div>`;
}

function FirstMiner({ snap }) {
  const portfolio = snap.portfolio;
  const options = useMemo(() => ({
    scales: { x: { time: true } }, axes: [AXIS, { ...AXIS, size: 56, values: (u, v) => v.map(x => x.toFixed(0) + '%') }],
    series: [{}, { stroke: '#3ecf8e', width: 2 }, { stroke: '#f5b84b', width: 1 }, { stroke: '#6aa9ff', width: 1 }], legend: { show: false },
  }), []);
  const chart = useMemo(() => {
    if (!portfolio?.days?.length) return null;
    const curve = values => { let e = 1; return values.map(v => { e *= 1 + v; return (e - 1) * 100; }); };
    return [portfolio.days.map(d => d * 86400), curve(portfolio.blended || portfolio.active), curve(portfolio.active), curve(portfolio.tracked)];
  }, [portfolio]);
  const alphas = (snap.alphas || []).slice().sort((a, b) => b.born - a.born);
  const traded = alphas.filter(a => a.promoted != null);
  return html`
    <div class="card span-12"><div class="muted">Version 1 of the miner (genetic search, incubation, a learned haircut): ${snap.rounds} rounds, ${(snap.trials || 0).toLocaleString()} trials,
      ${alphas.length} alphas incubated, ${traded.length} traded; haircut ${fmt(snap.haircut?.kappa)}. Kept as a record (docs/MINER.md); version 2 is the miner that runs.</div></div>
    <div class="card span-8"><h2>What it traded <span class="hint">green: traded alphas blended, yellow: each alone, blue: every alpha it tracked</span></h2>
      ${chart ? html`<${Plot} options=${options} data=${chart} height=${240} />` : html`<div class="empty">No record.</div>`}</div>
    <div class="card span-4"><h2>Haircut <span class="hint">in-sample against forward Sharpe</span></h2>
      <${HaircutChart} alphas=${alphas} kappa=${snap.haircut?.kappa ?? 0.25} minimum=${snap.settings?.incubation_days ?? 90} /></div>
    <div class="card span-12"><h2>Alphas</h2><${AlphaTable} alphas=${alphas} /></div>
    <div class="card span-12"><h2>Events</h2><${Events} events=${snap.events} /></div>`;
}

// The page ------------------------------------------------------------------------------------------------------

export function MinerConsole({ options, onStarted }) {
  const [run, setRun] = useState('');
  const [message, setMessage] = useState('');
  const { snap, log, live, version, connected } = useMiner(run);
  const ask = async action => { await api('/api/miner', { action }); setMessage(`Asked the live miner to ${action}; it picks the request up within half a minute.`); };
  const service = async action => { const r = await api('/api/miner', { action }); setMessage(r.running ? 'The live miner is starting.' : 'The live miner is stopped.'); };
  if (!snap) return html`<div class="card span-12"><div class="empty">Connecting to the miner…</div></div>`;
  return html`
    <${StatusBar} snap=${snap} live=${live} connected=${connected} run=${run} setRun=${setRun} onAsk=${ask} onService=${service} message=${message} />
    ${snap.kind === 'breadth' ? html`<${BreadthConsole} snap=${snap} log=${log} live=${live} version=${version} run=${run} options=${options} onStarted=${onStarted} />`
      : snap.alphas ? html`<${FirstMiner} snap=${snap} />` : html`<div class="card span-12"><div class="empty">No record in ${snap.run || 'this folder'} yet.</div></div>`}`;
}
