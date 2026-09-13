import { S, tokName } from '../lib/store.js';
import { esc, nf, usd, price, date, short } from '../lib/fmt.js';
import { icon, tokAv, thead, pager, emptyRow, tokenHref } from '../lib/ui.js';
import { sparkline } from '../lib/charts.js';

const st = { scope: 'traded', q: '', sort: 'traders', dir: -1, page: 0, per: 50 };
const COLS = [
  { k: 'n', label: '#' }, { k: 'tok', label: 'Token' }, { k: 'price', label: 'Price', rt: 1, sort: 1 }, { k: 'liq', label: 'Liquidity', rt: 1, sort: 1 },
  { k: 'vol24', label: '24h vol', rt: 1, sort: 1 }, { k: 'traders', label: 'Traders', rt: 1, sort: 1 }, { k: 'swaps', label: 'Buys / Sells', rt: 1, sort: 1 },
  { k: 'flow', label: 'Net flow est.', rt: 1, sort: 1 }, { k: 'snipers', label: 'Snipers', rt: 1, sort: 1 }, { k: 'bundlers', label: 'Bundlers', rt: 1, sort: 1 },
  { k: 'trend', label: 'Price trend', rt: 1 }, { k: 'pool', label: 'Pool' },
];

function rowsFor() {
  const q = st.q.trim().toLowerCase(), out = [];
  S.tokens.forEach((t, k) => {
    const a = S.tokAgg.get(k), f = S.tokFlags.get(k) || {};
    if (st.scope === 'traded' && !a) return;
    if (st.scope === 'pools' && !t[7]) return;
    if (st.scope === 'flagged' && !(f.SNIPER || f.BUNDLER_SUSPECT || f.DEV || f.INSIDER)) return;
    if (q && !((t[1] || '').toLowerCase().includes(q) || (t[2] || '').toLowerCase().includes(q) || t[0].includes(q))) return;
    out.push({ k, t, a, f, price: t[3] ?? -1, liq: t[4] ?? -1, vol24: t[5] ?? -1, traders: a?.wallets.size ?? 0, swaps: a ? a.nb + a.ns : 0,
      flow: a ? a.so - a.bu : -1e18, snipers: f.SNIPER?.size || 0, bundlers: f.BUNDLER_SUSPECT?.size || 0 });
  });
  out.sort((x, y) => (y[st.sort] - x[st.sort]) * -st.dir);
  return out;
}

export function render(root) {
  const counts = {
    traded: S.tokAgg.size, pools: S.tokens.filter(t => t[7]).length, all: S.tokens.length,
    flagged: [...S.tokFlags.values()].filter(f => f.SNIPER || f.BUNDLER_SUSPECT || f.DEV || f.INSIDER).length,
  };
  const draw = () => {
    const rows = rowsFor(), start = st.page * st.per;
    root.innerHTML = `<div class="page">
      <div class="page-head">
        <h1 class="page-title">Tokens</h1>
        <div class="seg">${[['traded', 'Traded'], ['pools', 'With pool'], ['flagged', 'Flagged'], ['all', 'All']].map(([v, l]) => `<button class="seg-btn ${st.scope === v ? 'is-active' : ''}" data-scope="${v}">${l}</button>`).join('')}</div>
        <div class="end"><label class="search" style="width:280px">${icon('search')}<input class="search-input" id="tok-q" placeholder="Filter by symbol, name, contract" value="${esc(st.q)}" autocomplete="off" spellcheck="false"></label></div>
      </div>
      <div class="page-sub"><span>${icon('coin')}${nf(rows.length)} of ${nf(counts[st.scope])} tokens</span><span>${icon('info')}Price, liquidity and 24h volume from the pool snapshot · traders and flow from local swaps</span></div>
      <section class="panel">
        <div class="table-wrap"><table class="table" style="--min:1320px"><thead>${thead(COLS, st)}</thead><tbody>
        ${rows.slice(start, start + st.per).map((r, j) => { const sp = S.spark[r.k];
          return `<tr class="is-link" data-href="${tokenHref(r.k)}">
            <td class="t3">${start + j + 1}</td>
            <td><div class="who">${tokAv(r.k)}<span><div style="color:var(--text)">${esc(tokName(r.k))}</div><div class="t3" style="font-size:11px;margin-top:3px">${esc(r.t[2] ? r.t[2] + ' · ' : '')}${short(r.t[0])}</div></span></div></td>
            <td class="rt">${price(r.t[3])}</td><td class="rt">${usd(r.t[4])}</td><td class="rt">${usd(r.t[5])}</td>
            <td class="rt">${nf(r.traders)}</td>
            <td class="rt">${r.a ? `<span class="pos">${nf(r.a.nb)}</span> / <span class="neg">${nf(r.a.ns)}</span>` : '<span class="t3">—</span>'}</td>
            <td class="rt ${r.a ? (r.flow >= 0 ? 'pos' : 'neg') : 't3'}">${r.a ? usd(r.flow, true) : '—'}</td>
            <td class="rt ${r.snipers ? '' : 't3'}" style="${r.snipers ? 'color:var(--c-sniper)' : ''}">${r.snipers || '—'}</td>
            <td class="rt ${r.bundlers ? '' : 't3'}" style="${r.bundlers ? 'color:var(--c-bundler)' : ''}">${r.bundlers || '—'}</td>
            <td class="rt">${sparkline(sp?.map(p => p[1]), { w: 104, h: 28 })}</td>
            <td class="t2">${r.t[7] ? `${esc(r.t[7])} · ${esc(r.t[8])}` : '<span class="t3">—</span>'}</td></tr>`; }).join('') || emptyRow(12, 'No tokens match. Clear the filter or switch scope.')}
        </tbody></table></div>
        ${pager(rows.length, st)}
      </section>
    </div>`;
  };
  draw();

  root.addEventListener('click', e => {
    const sc = e.target.closest('[data-scope]');
    if (sc) { st.scope = sc.dataset.scope; st.page = 0; return draw(); }
    const th = e.target.closest('th[data-sort]');
    if (th) { const k = th.dataset.sort; if (st.sort === k) st.dir *= -1; else { st.sort = k; st.dir = -1; } st.page = 0; return draw(); }
    const pg = e.target.closest('[data-page]');
    if (pg && !pg.disabled) { st.page = +pg.dataset.page; draw(); return window.scrollTo(0, 0); }
    const row = e.target.closest('tr[data-href]');
    if (row) location.hash = row.dataset.href;
  });
  let timer;
  root.addEventListener('input', e => {
    if (e.target.id !== 'tok-q') return;
    clearTimeout(timer);
    timer = setTimeout(() => { st.q = e.target.value; st.page = 0; draw(); const i = root.querySelector('#tok-q'); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }, 160);
  });
}
