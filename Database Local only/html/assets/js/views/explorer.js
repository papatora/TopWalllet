import { S, tokName } from '../lib/store.js';
import { esc, nf, usd, date, short } from '../lib/fmt.js';
import { icon, chip, labelMeta, pretty, thead, pager, emptyRow, walletHref, whoCell, snapMark } from '../lib/ui.js';

const st = { tab: 'wallets', q: '', type: null, label: null, act: 'all', token: null, sort: 'signal', dir: -1, page: 0, per: 50 };
const COLS = [
  { k: 'n', label: '#' }, { k: 'w', label: 'Wallet' }, { k: 'type', label: 'Primary type' }, { k: 'labels', label: 'Labels', sort: 1 },
  { k: 'signal', label: 'Confidence', sort: 1 }, { k: 'swaps', label: 'Swaps', rt: 1, sort: 1 }, { k: 'net', label: 'Net flow est.', rt: 1, sort: 1 }, { k: 'last', label: 'Last swap', rt: 1, sort: 1 },
];

const maxConf = w => Math.max(0, ...w[3]);
function rows() {
  const q = st.q.trim().toLowerCase();
  const typeI = st.type == null ? null : S.types.indexOf(st.type);
  const labelI = st.label == null ? null : S.labelIndex[st.label];
  const tokSet = st.token != null ? S.tokAgg.get(st.token)?.wallets || new Set() : null;
  const out = [];
  for (let i = 0; i < S.wallets.length; i++) {
    const w = S.wallets[i];
    if (typeI != null && w[1] !== typeI) continue;
    if (labelI != null && !w[2].includes(labelI)) continue;
    if (st.act === 'on' && !S.activeSet.has(i)) continue;
    if (st.act === 'off' && S.activeSet.has(i)) continue;
    if (tokSet && !tokSet.has(i)) continue;
    if (q && !(w[0].includes(q) || w[4].toLowerCase().includes(q) || w[2].some(l => S.labels[l].toLowerCase().includes(q)))) continue;
    out.push(i);
  }
  const val = i => {
    const s = S.statsAll.get(i), w = S.wallets[i];
    switch (st.sort) {
      case 'signal': return maxConf(w) - (S.types[w[1]] === 'GENERALIST' ? 1 : 0);
      case 'labels': return w[2].length;
      case 'swaps': return s ? s.swaps : -1;
      case 'net': return s ? s.net : -1e18;
      case 'last': return s ? s.last : 0;
    }
    return 0;
  };
  out.sort((a, b) => (val(b) - val(a)) * -st.dir || (S.wallets[a][0] < S.wallets[b][0] ? -1 : 1));
  return out;
}

export function render(root, _params, query) {
  if (query.has('label')) Object.assign(st, { label: query.get('label'), type: null, token: null, tab: 'wallets', page: 0 });
  if (query.has('type')) Object.assign(st, { type: query.get('type'), label: null, token: null, tab: 'wallets', page: 0 });
  if (query.has('token')) { const k = S.tokIndex.get(query.get('token').toLowerCase()); Object.assign(st, { token: k ?? null, tab: 'wallets', page: 0 }); }

  const m = S.meta;
  const facet = (group, value, label, n, c, on) => `<button class="facet-item ${on ? 'is-active' : ''}" data-f="${group}" data-v="${esc(value)}" style="--c:${c}"><span class="sw"></span><span class="lb">${esc(label)}</span><span class="n">${nf(n)}</span></button>`;

  const draw = () => {
    const list = st.tab === 'wallets' ? rows() : [];
    const start = st.page * st.per;
    const filters = [];
    if (st.act !== 'all') filters.push(['act', st.act === 'on' ? 'Has swaps' : 'Label only', 'var(--blue-hi)']);
    if (st.type) filters.push(['type', 'Type · ' + pretty(st.type), labelMeta(st.type).c]);
    if (st.label) filters.push(['label', 'Label · ' + pretty(st.label), labelMeta(st.label).c]);
    if (st.token != null) filters.push(['token', 'Traded ' + tokName(st.token), 'var(--blue-hi)']);
    if (st.q) filters.push(['q', `“${st.q}”`, 'var(--text-2)']);

    root.innerHTML = `<div class="explorer">
      <aside class="ex-side">
        <label class="ex-search">${icon('search')}<input id="ex-q" placeholder="Filter wallets" value="${esc(st.q)}" autocomplete="off" spellcheck="false"></label>
        <div class="facet"><h5 class="micro">Activity</h5>
          ${facet('act', 'all', 'All wallets', S.wallets.length, 'var(--text-3)', st.act === 'all')}
          ${facet('act', 'on', 'Has swaps', S.active.length, 'var(--blue)', st.act === 'on')}
          ${facet('act', 'off', 'Label only', S.wallets.length - S.active.length, 'var(--text-4)', st.act === 'off')}</div>
        <div class="facet"><h5 class="micro">Primary type</h5>
          ${Object.entries(m.type_counts).sort((a, b) => b[1] - a[1]).map(([t, n]) => facet('type', t, pretty(t), n, labelMeta(t).c, st.type === t)).join('')}</div>
        <div class="facet"><h5 class="micro">Labels</h5>
          ${Object.entries(m.label_counts).sort((a, b) => b[1] - a[1]).map(([t, n]) => facet('label', t, pretty(t), n, labelMeta(t).c, st.label === t)).join('')}</div>
      </aside>
      <div class="ex-main">
        <div class="ex-tabs">
          <button class="ex-tab ${st.tab === 'wallets' ? 'is-active' : ''}" data-tab="wallets">WALLETS</button>
          <button class="ex-tab ${st.tab === 'labels' ? 'is-active' : ''}" data-tab="labels">LABELS</button>
          <div class="end"><span class="micro">${st.tab === 'wallets' ? `${nf(list.length)} of ${nf(S.wallets.length)}` : `${S.labels.length} labels`}</span></div>
        </div>
        ${st.tab === 'labels' ? `<div class="label-cards">${Object.entries(m.label_counts).sort((a, b) => b[1] - a[1]).map(([l, n]) => { const lm = labelMeta(l);
          return `<button class="lcard" data-open-label="${esc(l)}" style="--c:${lm.c}"><span class="avatar is-lg">${icon(lm.icon)}</span><span><div class="lcard-t">${esc(pretty(l))}</div><div class="lcard-s micro">${nf(n)} wallets · ${icon('chevron-right', 'i-sm').replace('class="i', 'style="display:inline;vertical-align:-2px" class="i')}</div><div class="lcard-d">${esc(lm.desc)}</div></span></button>`; }).join('')}</div>`
        : `${filters.length ? `<div class="active-filters">${filters.map(([k, t, c]) => `<button class="fchip" data-clear="${k}" style="--c:${c}">${icon('x')}${esc(t)}</button>`).join('')}<button class="btn btn-ghost btn-sm" data-clear="all">Clear all</button></div>` : ''}
        <section class="panel">
          <div class="table-wrap"><table class="table" style="--min:1040px"><thead>${thead(COLS, st)}</thead><tbody>
          ${list.slice(start, start + st.per).map((i, j) => { const w = S.wallets[i], s = S.statsAll.get(i), mc = maxConf(w);
            return `<tr class="is-link" data-href="${walletHref(i)}">
              <td class="t3">${nf(start + j + 1)}</td>
              <td><div class="who"><span class="addr">${short(w[0], 10, 6)}</span>${w[4] ? `<span class="t2" style="font-family:var(--sans)">${esc(w[4])}</span>` : ''}</div></td>
              <td>${chip(S.types[w[1]])}</td>
              <td><div class="chips">${w[2].map(l => chip(S.labels[l])).join('')}</div></td>
              <td><span class="conf"><span class="bar"><b style="width:${mc * 100}%"></b></span><span class="t2">${mc.toFixed(2)}</span></span></td>
              <td class="rt">${s ? nf(s.swaps) : '<span class="t3">—</span>'}</td>
              <td class="rt ${s ? (s.net >= 0 ? 'pos' : 'neg') : 't3'}">${s ? (s.allSnap ? snapMark(1) : '') + usd(s.net, true) : '—'}</td>
              <td class="rt t2">${s ? date(s.last, true) : '<span class="t3">—</span>'}</td></tr>`; }).join('') || emptyRow(8, 'No wallets match these filters. Clear a filter to widen the search.')}
          </tbody></table></div>
          ${pager(list.length, st)}
        </section>`}
      </div></div>`;
  };
  draw();

  root.addEventListener('click', e => {
    const f = e.target.closest('[data-f]');
    if (f) {
      const g = f.dataset.f, v = f.dataset.v;
      if (g === 'act') st.act = v; else st[g] = st[g] === v ? null : v;
      st.tab = 'wallets'; st.page = 0; return draw();
    }
    const c = e.target.closest('[data-clear]');
    if (c) {
      const k = c.dataset.clear;
      if (k === 'all') Object.assign(st, { q: '', type: null, label: null, act: 'all', token: null });
      else if (k === 'act') st.act = 'all'; else if (k === 'q') st.q = ''; else st[k] = null;
      st.page = 0; history.replaceState(null, '', '#/explorer'); return draw();
    }
    const t = e.target.closest('[data-tab]');
    if (t) { st.tab = t.dataset.tab; return draw(); }
    const ol = e.target.closest('[data-open-label]');
    if (ol) { Object.assign(st, { tab: 'wallets', label: ol.dataset.openLabel, type: null, page: 0 }); return draw(); }
    const th = e.target.closest('th[data-sort]');
    if (th) { const k = th.dataset.sort; if (st.sort === k) st.dir *= -1; else { st.sort = k; st.dir = -1; } st.page = 0; return draw(); }
    const pg = e.target.closest('[data-page]');
    if (pg && !pg.disabled) { st.page = +pg.dataset.page; draw(); return window.scrollTo(0, 0); }
    const row = e.target.closest('tr[data-href]');
    if (row) location.hash = row.dataset.href;
  });
  let timer;
  root.addEventListener('input', e => {
    if (e.target.id !== 'ex-q') return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      st.q = e.target.value; st.page = 0; draw();
      const inp = root.querySelector('#ex-q'); inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length);
    }, 160);
  });
}
