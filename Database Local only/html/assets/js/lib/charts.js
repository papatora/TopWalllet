// Hand-rolled SVG charts on one scale each. Colors come from CSS tokens.
import { date } from './fmt.js';

let uid = 0;
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || v;

function niceStep(range, count) {
  const raw = range / Math.max(1, count), p = 10 ** Math.floor(Math.log10(raw || 1)), n = raw / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}
function yTicks(min, max, count = 4) {
  if (min === max) { max = min + 1; }
  const step = niceStep(max - min, count), lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step;
  const ticks = []; for (let v = lo; v <= hi + step / 2; v += step) ticks.push(+v.toPrecision(12));
  return ticks;
}
function timeTicks(t0, t1, width) {
  const n = Math.max(2, Math.min(8, Math.floor(width / 110))), day = 86400;
  const stepDays = Math.max(1, Math.ceil((t1 - t0) / day / n));
  const out = []; let t = Math.ceil(t0 / day) * day;
  for (; t <= t1; t += stepDays * day) out.push(t);
  return out;
}

/** Resize-aware mount: calls draw(width) now and whenever the element width changes. */
function mount(el, draw) {
  let w = 0;
  const run = () => { const nw = Math.round(el.clientWidth); if (nw && nw !== w) { w = nw; draw(w); } };
  el._ro?.disconnect();
  el._ro = new ResizeObserver(run); el._ro.observe(el); run();
}

function tipAt(el, html, x, y) {
  let tip = el.querySelector('.chart-tip');
  if (!tip) { tip = document.createElement('div'); tip.className = 'chart-tip'; el.append(tip); }
  tip.innerHTML = html; tip.hidden = false;
  const r = el.getBoundingClientRect(), tw = tip.offsetWidth;
  tip.style.left = Math.min(Math.max(0, x + 14), r.width - tw) + 'px';
  tip.style.top = Math.max(0, y - 10) + 'px';
}

/** Area/line chart. points: [[t, v]] sorted by t. */
export function areaChart(el, { points, color = '--blue-hi', height = 240, yFmt = v => v, tip, baseline = false }) {
  el.classList.add('chart'); el.style.height = height + 'px';
  if (!points.length) { el.innerHTML = '<div class="t3" style="padding:40px;text-align:center">No data points in this range.</div>'; return; }
  mount(el, W => {
    const H = height, m = { l: 62, r: 14, t: 12, b: 26 }, iw = W - m.l - m.r, ih = H - m.t - m.b;
    const ts = points.map(p => p[0]), vs = points.map(p => p[1]);
    const t0 = ts[0], t1 = ts[ts.length - 1] === t0 ? t0 + 3600 : ts[ts.length - 1];
    let lo = Math.min(...vs), hi = Math.max(...vs);
    if (baseline) { lo = Math.min(0, lo); hi = Math.max(0, hi); }
    const yt = yTicks(lo, hi, 4); lo = yt[0]; hi = yt[yt.length - 1];
    const x = t => m.l + (t - t0) / (t1 - t0) * iw, y = v => m.t + ih - (v - lo) / (hi - lo || 1) * ih;
    const c = css(color), id = 'g' + (++uid);
    const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('');
    const base = y(Math.max(lo, Math.min(hi, 0)));
    const area = `${line}L${x(points.at(-1)[0]).toFixed(1)},${base}L${x(t0).toFixed(1)},${base}Z`;
    const last = points.at(-1);
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">
      <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c}" stop-opacity=".24"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></linearGradient></defs>
      <g class="grid">${yt.map(v => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/>`).join('')}</g>
      ${baseline && lo < 0 ? `<line x1="${m.l}" x2="${W - m.r}" y1="${base}" y2="${base}" stroke="${css('--line-strong')}" stroke-dasharray="3 3"/>` : ''}
      <g class="axis">${yt.map(v => `<text x="${m.l - 10}" y="${y(v) + 3}" text-anchor="end">${yFmt(v)}</text>`).join('')}
        ${timeTicks(t0, t1, iw).map(t => `<text x="${x(t)}" y="${H - 6}" text-anchor="middle">${date(t)}</text>`).join('')}</g>
      <path d="${area}" fill="url(#${id})"/>
      <path d="${line}" fill="none" stroke="${c}" stroke-width="1.6" stroke-linejoin="round"/>
      <circle cx="${x(last[0])}" cy="${y(last[1])}" r="3.5" fill="${c}" stroke="${css('--panel')}" stroke-width="2"/>
      <g class="hover" visibility="hidden"><line y1="${m.t}" y2="${m.t + ih}" stroke="${css('--line-strong')}"/><circle r="4" fill="${c}" stroke="${css('--panel')}" stroke-width="2"/></g>
      <rect x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent" class="hit"/></svg>`;
    const svg = el.querySelector('svg'), hov = svg.querySelector('.hover'), hit = svg.querySelector('.hit');
    hit.onmousemove = e => {
      const r = svg.getBoundingClientRect(), mx = (e.clientX - r.left) * (W / r.width);
      const tt = t0 + (mx - m.l) / iw * (t1 - t0);
      let a = 0, b = ts.length - 1; while (b - a > 1) { const mid = (a + b) >> 1; ts[mid] < tt ? a = mid : b = mid; }
      const i = Math.abs(ts[a] - tt) < Math.abs(ts[b] - tt) ? a : b, px = x(ts[i]), py = y(vs[i]);
      hov.setAttribute('visibility', 'visible');
      hov.querySelector('line').setAttribute('x1', px); hov.querySelector('line').setAttribute('x2', px);
      hov.querySelector('circle').setAttribute('cx', px); hov.querySelector('circle').setAttribute('cy', py);
      tipAt(el, tip ? tip(points[i], i) : `${date(ts[i], true)}<br>${yFmt(vs[i])}`, px * r.width / W, py * r.height / H);
    };
    hit.onmouseleave = () => { hov.setAttribute('visibility', 'hidden'); const t = el.querySelector('.chart-tip'); if (t) t.hidden = true; };
  });
}

/** Mirrored flow bars: buys above zero (green), sells below (red). days: [{t, buy, sell, n}] */
export function flowChart(el, { days, height = 260, yFmt, tip }) {
  el.classList.add('chart'); el.style.height = height + 'px';
  if (!days.length) { el.innerHTML = '<div class="t3" style="padding:40px;text-align:center">No swaps in this range.</div>'; return; }
  mount(el, W => {
    const H = height, m = { l: 62, r: 14, t: 12, b: 26 }, iw = W - m.l - m.r, ih = H - m.t - m.b;
    const peak = Math.max(1e-9, ...days.map(d => Math.max(d.buy, d.sell)));
    const step = niceStep(peak, 2), top = Math.ceil(peak / step) * step;
    const yt = []; for (let v = -top; v <= top + step / 2; v += step) yt.push(v);
    const y = v => m.t + ih / 2 - v / top * (ih / 2);
    const slot = iw / days.length, bw = Math.max(1, Math.min(18, slot * .72));
    const t0 = days[0].t, t1 = days.at(-1).t, x = i => m.l + slot * i + slot / 2;
    const g = css('--green'), r = css('--red');
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">
      <g class="grid">${yt.map(v => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/>`).join('')}</g>
      <line x1="${m.l}" x2="${W - m.r}" y1="${y(0)}" y2="${y(0)}" stroke="${css('--line-strong')}"/>
      <g class="axis">${yt.map(v => `<text x="${m.l - 10}" y="${y(v) + 3}" text-anchor="end">${yFmt(Math.abs(v))}</text>`).join('')}
        ${timeTicks(t0, t1 || t0 + 1, iw).map(t => { const i = Math.round((t - t0) / 86400); return i >= 0 && i < days.length ? `<text x="${x(i)}" y="${H - 6}" text-anchor="middle">${date(t)}</text>` : ''; }).join('')}</g>
      ${days.map((d, i) => `<rect x="${x(i) - bw / 2}" y="${y(d.buy)}" width="${bw}" height="${Math.max(0, y(0) - y(d.buy))}" rx="1.5" fill="${g}" fill-opacity=".85"/><rect x="${x(i) - bw / 2}" y="${y(0)}" width="${bw}" height="${Math.max(0, y(-d.sell) - y(0))}" rx="1.5" fill="${r}" fill-opacity=".85"/>`).join('')}
      <rect class="hl" y="${m.t}" height="${ih}" width="${slot}" fill="#fff" fill-opacity=".04" visibility="hidden"/>
      <rect x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent" class="hit"/></svg>`;
    const svg = el.querySelector('svg'), hl = svg.querySelector('.hl'), hit = svg.querySelector('.hit');
    hit.onmousemove = e => {
      const rc = svg.getBoundingClientRect(), mx = (e.clientX - rc.left) * (W / rc.width);
      const i = Math.max(0, Math.min(days.length - 1, Math.floor((mx - m.l) / slot)));
      hl.setAttribute('x', m.l + slot * i); hl.setAttribute('visibility', 'visible');
      tipAt(el, tip(days[i]), x(i) * rc.width / W, m.t + 10);
    };
    hit.onmouseleave = () => { hl.setAttribute('visibility', 'hidden'); const t = el.querySelector('.chart-tip'); if (t) t.hidden = true; };
  });
}

/** Inline sparkline SVG string. */
export function sparkline(values, { w = 110, h = 30, color } = {}) {
  if (!values || values.length < 2) return `<span class="t3">—</span>`;
  const lo = Math.min(...values), hi = Math.max(...values), rng = hi - lo || 1;
  const up = values.at(-1) >= values[0], c = color || (up ? css('--green') : css('--red'));
  const pts = values.map((v, i) => [(i / (values.length - 1)) * (w - 4) + 2, h - 3 - ((v - lo) / rng) * (h - 6)]);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('');
  const id = 's' + (++uid);
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:inline-block;vertical-align:middle"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c}" stop-opacity=".22"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></linearGradient></defs><path d="${d}L${w - 2},${h}L2,${h}Z" fill="url(#${id})"/><path d="${d}" fill="none" stroke="${c}" stroke-width="1.4"/></svg>`;
}

/** Bucket swap rows [.., ts at idx, side, usd] into UTC days between t0 and t1. */
export function bucketDays(rows, t0, t1, tsI, sideI, usdI) {
  const day = 86400, start = Math.floor(t0 / day) * day, n = Math.floor((t1 - start) / day) + 1;
  const days = Array.from({ length: n }, (_, i) => ({ t: start + i * day, buy: 0, sell: 0, nb: 0, ns: 0 }));
  for (const r of rows) {
    const d = days[Math.floor((r[tsI] - start) / day)]; if (!d) continue;
    if (r[sideI]) { d.ns++; if (r[usdI] >= 0) d.sell += r[usdI]; } else { d.nb++; if (r[usdI] >= 0) d.buy += r[usdI]; }
  }
  return days;
}
