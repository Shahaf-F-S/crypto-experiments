// common.js: what the dashboard's pages share (Preact + htm, uPlot; no build step).

import { html, render, useState, useEffect, useRef, useMemo } from 'https://unpkg.com/htm@3.1.1/preact/standalone.module.js';

export { html, render, useState, useEffect, useRef, useMemo };

export const PALETTE = ['#6aa9ff', '#3ecf8e', '#f5b84b', '#ff6b6b', '#c38bff', '#4dd4e6', '#ff9f6b', '#a3d977', '#ff7ab8', '#b0b8c8'];

export function fmt(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '–';
  return Number(v).toFixed(digits);
}

export function clock(t) {
  if (!t) return '–';
  return new Date(t * 1000).toISOString().replace('T', ' ').slice(0, 19);
}

export function day(t) { return t ? new Date(t * 1000).toISOString().slice(0, 10) : '–'; }

export function ago(t) {
  if (!t) return '–';
  const s = Math.max(0, Date.now() / 1000 - t);
  if (s < 90) return `${Math.round(s)} s ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 172800) return `${(s / 3600).toFixed(1)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

export async function api(path, body) {
  const response = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  return response.json();
}

export function annualSharpe(values) {
  const x = (values || []).filter(v => Number.isFinite(v));
  if (x.length < 2) return null;
  const mean = x.reduce((a, b) => a + b, 0) / x.length;
  const sd = Math.sqrt(x.reduce((a, b) => a + (b - mean) ** 2, 0) / (x.length - 1));
  return sd > 0 ? mean / sd * Math.sqrt(365) : null;
}

// Charts -------------------------------------------------------------------------------------------------------

export function useWidth(ref) {
  const [width, setWidth] = useState(800);
  useEffect(() => {
    const observer = new ResizeObserver(entries => setWidth(Math.max(200, Math.floor(entries[0].contentRect.width))));
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  return width;
}

export const AXIS = { stroke: '#8b95a8', grid: { stroke: '#1e2533', width: 1 }, ticks: { stroke: '#232b3b' } };
export const UTC = ts => uPlot.tzDate(new Date(ts * 1e3), 'Etc/UTC');      // charts in market (UTC) time, like the clock

export function Plot({ options, data, height = 260, draw }) {
  const box = useRef(null);
  const plot = useRef(null);
  const drawRef = useRef(draw);
  drawRef.current = draw;
  const width = useWidth(box);

  useEffect(() => {
    const opts = {
      width, height, tzDate: UTC, ...options,
      hooks: { draw: [u => drawRef.current && drawRef.current(u)] },
    };
    plot.current = new uPlot(opts, data, box.current);
    return () => plot.current.destroy();
  }, [options]);

  useEffect(() => { plot.current && plot.current.setSize({ width, height }); }, [width, height]);
  useEffect(() => { plot.current && plot.current.setData(data); }, [data]);
  return html`<div class="chart" ref=${box}></div>`;
}

export function Spark({ values, width = 120, height = 28, color = '#6aa9ff' }) {
  const finite = (values || []).filter(v => v !== null && Number.isFinite(v));
  if (finite.length < 2) return html`<svg width=${width} height=${height}></svg>`;
  const lo = Math.min(...finite), hi = Math.max(...finite), span = hi - lo || 1;
  const points = values.map((v, i) => v === null || !Number.isFinite(v) ? null :
    `${(i / (values.length - 1)) * width},${height - 2 - ((v - lo) / span) * (height - 4)}`).filter(Boolean).join(' ');
  return html`<svg width=${width} height=${height}><polyline points=${points} fill="none" stroke=${color} stroke-width="1.4" /></svg>`;
}
