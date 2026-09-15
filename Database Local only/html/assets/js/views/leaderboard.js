import { S, stats, walletName, tokName } from '../lib/store.js';
import { esc, nf, usd, dur, date } from '../lib/fmt.js';
import { icon, chip, tokStack, rank, hexBadge, thead, pager, dropdown, emptyRow, walletHref, whoCell } from '../lib/ui.js';

const st = { tab: 'traders', metric: 'net', win: '0', sort: 'net', dir: -1, page: 0, per: 50, tag: '' };
const TAG_OPTIONS = () => [{ v: '', l: 'All tags' }].concat(S.labels.filter(l => !l.startsWith('CLUSTER_MEMBER')).map(l => ({ v: l, l })));
const METRICS = [{ v: 'net', l: 'Net flow' }, { v: 'vol', l: 'Volume' }, { v: 'swaps', l: 'Swaps' }];
const WINDOWS = [{ v: '1', l: '1D' }, { v: '7', l: '7D' }, { v: '30', l: '30D' }, { v: '0', l: 'All' }];
const TRADER_COLS = [
  { k: 'r', label: '#' }, { k: 'w', label: 'Trader' },
  { k: 'net', label: 'Net flow', rt: 1, sort: 1 }, { k: 'bu', label: `${icon('arrow-in', 'i-sm')} Bought`.replace('<svg', '<svg style="display:inline;vertical-align:-2px"'), rt: 1, sort: 1 },
  { k: 'so', label: `${icon('arrow-out', 'i-sm')} Sold`.replace('<svg', '<svg style="display:inline;vertical-align:-2px"'), rt: 1, sort: 1 },
  { k: 'nb', label: 'Buys', rt: 1, sort: 1 }, { k: 'ns', label: 'Sells', rt: 1, sort: 1 },
  { k: 'w', label: 'W / L', rt: 1, sort: 1 }, { k: 'hold', label: 'Avg hold', rt: 1, sort: 1 }, { k: 't', label: 'Top tokens', rt: 1 },
];
const SNIPER_COLS = [
  { k: 'r', label: '#' }, { k: 'w', label: 'Sniper' }, { k: 'snipes', label: 'Snipes', rt: 1, sort: 1 },
  { k: 'fastest', label: 'Fastest', rt: 1, sort: 1 }, { k: 't', label: 'Tokens sniped', rt: 1 },
  { k: 'labels', label: 'Labels' }, { k: 'net', label: 'Net flow est.', rt: 1, sort: 1 },
];

function traderRows() {
  const from = +st.win ? S.meta.swap_to - +st.win * 86400 : 0;
  let rows = [];
  for (const ai of S.active) { const s = from ? stats(ai, from) : S.statsAll.get(ai); if (s.swaps) rows.push([ai, s]); }
  if (st.tag) rows = rows.filter(([ai]) => (S.wallets[ai][2] || []).some(li => { const n = S.labels[li]; return n === st.tag || n.startsWith(st.tag + ':'); }));
  const key = st.sort;
  rows.sort((a, b) => ((b[1][key] ?? -1e18) - (a[1][key] ?? -1e18)) * -st.dir);
  return rows;
}

function matchTag(ai) {
  if (!st.tag) return true;
  return (S.wallets[ai][2] || []).some(li => { const n = S.labels[li]; return n === st.tag || n.startsWith(st.tag + ':'); });
}
function sniperRows() {
  const rows = [];
  for (const [key, e] of Object.entries(S.ev)) {
    const sn = e.SNIPER; if (!sn) continue;
    const i = +key;
    if (!matchTag(i)) continue;
    const deltas = sn.snipes.map(s => s.delta_blocks);
    rows.push([i, { snipes: sn.snipe_count, fastest: Math.min(...deltas), toks: [...new Set(sn.snipes.map(s => s.token))], net: S.statsAll.get(i)?.net ?? null }]);
  }
  const key = st.sort;
  const val = r => key === 'fastest' ? -r[1].fastest : (r[1][key] ?? -1e18);
  rows.sort((a, b) => (val(b) - val(a)) * -st.dir);
  return rows;
}

export function render(root) {
  const draw = () => {
    const traders = st.tab === 'traders';
    const rows = traders ? traderRows() : sniperRows();
    const start = st.page * st.per, page = rows.slice(start, start + st.per);
    const metricLabel = METRICS.find(m => m.v === st.metric).l;
    const winTxt = +st.win ? `${st.win}D window ending ${date(S.meta.swap_to, true)} UTC` : `All swaps ${date(S.meta.swap_from)} → ${date(S.meta.swap_to)}`;

    const pod = traders ? rows.slice(0, 3) : [];
    const cls = ['is-1', 'is-2', 'is-3'], col = ['#F2C94C', '#B8C1D1', '#D38B4F'];
    const order = pod.length === 3 ? [1, 0, 2] : pod.map((_, i) => i);
    const bigOf = s => st.metric === 'swaps' ? `<span class="pod-big">${nf(s.swaps)}</span>` : `<span class="pod-big ${st.metric === 'net' ? (s.net >= 0 ? 'pos' : 'neg') : ''}">${usd(s[st.metric], st.metric === 'net')}</span>`;

    root.innerHTML = `<div class="page">
      <div class="page-head">
        <h1 class="page-title">Leaderboard</h1>
        <div class="seg" data-tabs><button class="seg-btn ${traders ? 'is-active' : ''}" data-tab="traders">Top traders</button><button class="seg-btn ${!traders ? 'is-active' : ''}" data-tab="snipers">Snipers</button></div>
        <div class="end">${traders ? dropdown('metric', 'trophy', METRICS, st.metric) + dropdown('win', 'clock', WINDOWS, st.win) + dropdown('tag', 'filter', TAG_OPTIONS(), st.tag) : ''}</div>
      </div>
      <div class="page-sub"><span>${icon('wallet')}${nf(rows.length)} ${traders ? 'active wallets' : 'sniper wallets'}</span>${traders ? `<span>${icon('clock')}${winTxt}</span><span>${icon('info')}USD estimated from pool price points · not verified PnL</span>` : `<span>${icon('bolt')}First buy within 10 blocks of a pool’s first swap</span>`}</div>

      ${pod.length ? `<div class="podium">${order.map(j => { const [ai, s] = pod[j], nm = walletName(ai);
        return `<a class="pod ${cls[j]}" href="${walletHref(ai)}">
          <div class="pod-addr">${S.wallets[ai][0]}</div>${hexBadge(j + 1, col[j])}
          <div class="pod-mid"><div><div class="pod-k">${metricLabel}${nm ? ` · <span style="color:${col[j]}">${esc(nm)}</span>` : ''}</div>${bigOf(s)}</div>
            <div style="text-align:right"><div class="pod-k">Top tokens</div>${tokStack(s.toks)}</div></div>
          <div class="pod-foot">
            <div><div class="pod-k">Bought</div><div class="v pos">${usd(s.bu)}</div></div>
            <div><div class="pod-k">Sold</div><div class="v neg">${usd(s.so)}</div></div>
            <div><div class="pod-k">W / L</div><div class="v">${s.w} / ${s.l}</div></div>
            <span class="pill">${icon('clock')}${dur(s.hold)}</span>
          </div></a>`; }).join('')}</div>` : ''}

      <section class="panel">
        <div class="table-wrap"><table class="table" style="--min:1080px">
          <thead>${thead(traders ? TRADER_COLS : SNIPER_COLS, st)}</thead>
          <tbody>${page.length ? page.map(([ai, s], j) => { const r = start + j + 1, w = S.wallets[ai];
            return traders
              ? `<tr class="is-link" data-href="${walletHref(ai)}"><td>${rank(r)}</td><td>${whoCell(ai)}</td>
                  <td class="rt ${s.net >= 0 ? 'pos' : 'neg'}">${usd(s.net, true)}</td><td class="rt pos">${usd(s.bu)}</td><td class="rt neg">${usd(s.so)}</td>
                  <td class="rt">${nf(s.nb)}</td><td class="rt">${nf(s.ns)}</td><td class="rt"><span class="pos">${s.w}</span> / <span class="neg">${s.l}</span></td>
                  <td class="rt">${dur(s.hold)}</td><td class="rt">${tokStack(s.toks)}</td></tr>`
              : `<tr class="is-link" data-href="${walletHref(ai)}"><td>${rank(r)}</td><td>${whoCell(ai)}</td>
                  <td class="rt">${nf(s.snipes)}</td><td class="rt">+${s.fastest} block${s.fastest === 1 ? '' : 's'}</td><td class="rt">${tokStack(s.toks, 4)}</td>
                  <td><div class="chips">${w[2].map(l => chip(S.labels[l])).join('')}</div></td>
                  <td class="rt ${s.net == null ? 't3' : s.net >= 0 ? 'pos' : 'neg'}">${s.net == null ? '—' : usd(s.net, true)}</td></tr>`;
          }).join('') : emptyRow(10, 'No swaps in this window. Try 30D or All.')}</tbody>
        </table></div>
        ${pager(rows.length, st)}
      </section>
    </div>`;
  };
  draw();

  root.addEventListener('click', e => {
    const tab = e.target.closest('[data-tab]');
    if (tab) { st.tab = tab.dataset.tab; st.sort = st.tab === 'traders' ? st.metric : 'snipes'; st.dir = -1; st.page = 0; return draw(); }
    const th = e.target.closest('th[data-sort]');
    if (th) { const k = th.dataset.sort; if (st.sort === k) st.dir *= -1; else { st.sort = k; st.dir = -1; } st.page = 0; return draw(); }
    const pg = e.target.closest('[data-page]');
    if (pg && !pg.disabled) { st.page = +pg.dataset.page; draw(); return window.scrollTo(0, 0); }
    const row = e.target.closest('tr[data-href]');
    if (row) location.hash = row.dataset.href;
  });
  root.addEventListener('dd:change', e => {
    const { id, value } = e.detail;
    if (id === 'metric') { st.metric = value; st.sort = value; st.dir = -1; }
    if (id === 'win') st.win = value;
    if (id === 'tag') st.tag = value;
    st.page = 0; draw();
  });
}
