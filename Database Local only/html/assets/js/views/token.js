import { S, stats, tokName, walletName } from '../lib/store.js';
import { esc, nf, usd, price, date, short, dur } from '../lib/fmt.js';
import { icon, chip, labelMeta, pretty, tokAv, rank, thead, pager, emptyRow, walletHref, whoCell, txHref, copy, snapMark } from '../lib/ui.js';
import { areaChart, flowChart, bucketDays } from '../lib/charts.js';

const st = { tab: 'traders', sort: 'net', dir: -1, page: 0, per: 25, chart: 'price' };

export function render(root, [addr]) {
  const k = S.tokIndex.get(addr.toLowerCase());
  if (k == null) {
    root.innerHTML = `<div class="page"><h1 class="page-title">Token not indexed</h1><p class="t2" style="margin-top:10px">${esc(addr)} isn’t in the local Robinhood Chain snapshot. <a class="link" href="#/tokens">Browse tokens</a>.</p></div>`;
    return;
  }
  const t = S.tokens[k], a = S.tokAgg.get(k), f = S.tokFlags.get(k) || {}, spark = S.spark[k] || [];
  const swaps = S.all.filter(r => r[1] === k);
  const traders = a ? [...a.wallets].map(i => [i, stats(i, 0, Infinity, k)]) : [];
  const bundles = S.entities.map((e, i) => [e, i]).filter(([e]) => e.kind === 'bundle' && e.data.token === k);
  const flagged = Object.entries(f).flatMap(([lab, set]) => [...set].map(i => [lab, i]));
  if (st._tok !== k) Object.assign(st, { _tok: k, tab: 'traders', sort: 'net', dir: -1, page: 0, chart: spark.length ? 'price' : 'flow' });

  const draw = () => {
    const TR_COLS = [{ k: 'r', label: '#' }, { k: 'w', label: 'Trader' }, { k: 'net', label: 'Net flow est.', rt: 1, sort: 1 }, { k: 'bu', label: 'Bought', rt: 1, sort: 1 }, { k: 'so', label: 'Sold', rt: 1, sort: 1 }, { k: 'swaps', label: 'Swaps', rt: 1, sort: 1 }, { k: 'hold', label: 'Hold', rt: 1, sort: 1 }, { k: 'type', label: 'Type' }];
    let body = '', foot = '';
    if (st.tab === 'traders') {
      const rows = [...traders].sort((x, y) => ((y[1][st.sort] ?? -1e18) - (x[1][st.sort] ?? -1e18)) * -st.dir);
      const start = st.page * st.per;
      body = `<table class="table" style="--min:900px"><thead>${thead(TR_COLS, st)}</thead><tbody>${rows.slice(start, start + st.per).map(([i, s], j) =>
        `<tr class="is-link" data-href="${walletHref(i)}"><td>${rank(start + j + 1)}</td><td>${whoCell(i)}</td><td class="rt ${s.net >= 0 ? 'pos' : 'neg'}">${s.allSnap ? snapMark(1) : ''}${usd(s.net, true)}</td><td class="rt pos">${usd(s.bu)}</td><td class="rt neg">${usd(s.so)}</td><td class="rt">${s.nb} / ${s.ns}</td><td class="rt">${dur(s.hold)}</td><td>${chip(S.types[S.wallets[i][1]])}</td></tr>`).join('') || emptyRow(8, 'No local swaps for this token.')}</tbody></table>`;
      foot = pager(rows.length, st);
    } else if (st.tab === 'swaps') {
      body = `<table class="table is-compact" style="--min:760px"><thead><tr><th>Time (UTC)</th><th>Side</th><th>Wallet</th><th class="rt">USD est.</th><th>Tx</th></tr></thead><tbody>${[...swaps].reverse().slice(0, 200).map(([ai, , ts, sd, u, tx, sn]) =>
        `<tr class="is-link" data-href="${walletHref(ai)}"><td class="t2">${date(ts, true)}</td><td><span class="side ${sd ? 'is-sell' : 'is-buy'}">${sd ? 'SELL' : 'BUY'}</span></td><td>${whoCell(ai, { full: false })}</td><td class="rt">${u >= 0 ? snapMark(sn) + usd(u) : '<span class="t3">unpriced</span>'}</td><td><a class="link" href="${txHref(tx)}" target="_blank" rel="noopener">${tx.slice(0, 10)}…</a></td></tr>`).join('') || emptyRow(5, 'No local swaps for this token.')}</tbody></table>`;
      if (swaps.length > 200) foot = `<div class="panel-note">Showing the latest 200 of ${nf(swaps.length)} swaps.</div>`;
    } else {
      body = `<table class="table is-compact" style="--min:760px"><thead><tr><th>Label</th><th>Wallet</th><th>Evidence</th><th class="rt">Net flow est.</th></tr></thead><tbody>${flagged.map(([lab, i]) => {
        const e = S.ev[i]?.[lab] || {}, s = stats(i, 0, Infinity, k);
        const ev = lab === 'SNIPER' ? `+${e.snipes?.find(x => x.token === k)?.delta_blocks ?? '?'} blocks after pool open` : lab === 'BUNDLER_SUSPECT' ? `${e.distinct_wallets} wallets, one tx, block ${nf(e.block)}` : lab === 'DEV' ? `first buyer, ${e.fast_flips} fast flips` : lab === 'INSIDER' ? (e.kind === 'MINT_ALLOCATION' ? 'alokasi mint dari 0x0'
                                    : e.kind === 'CONFIRMED_INSIDER' ? `transfer murni dari ${Object.keys(e.senders || {}).length} pengirim`
                                    : `${e.sell_count ?? ''} sells without a buy`.trim())
                                    : 'incoming only';
        return `<tr class="is-link" data-href="${walletHref(i)}"><td>${chip(lab)}</td><td>${whoCell(i, { full: false })}</td><td class="t2" style="font-family:var(--sans)">${esc(ev)}</td><td class="rt ${s.swaps ? (s.net >= 0 ? 'pos' : 'neg') : 't3'}">${s.swaps ? (s.allSnap ? snapMark(1) : '') + usd(s.net, true) : '—'}</td></tr>`; }).join('') || emptyRow(4, 'No wallet on this token carries a sniper, bundler, dev or insider label.')}</tbody></table>`;
    }

    root.innerHTML = `<div class="page">
      <div class="profile-head">
        ${tokAv(k, 'is-lg')}
        <div style="min-width:0"><div class="profile-name">${esc(tokName(k))} <span class="t3" style="font-weight:400">${esc(t[2] || '')}</span></div><div class="profile-addr">${t[0]}</div></div>
        <div class="end">
          <button class="btn btn-ghost" data-copy="${t[0]}">${icon('copy', 'i-sm')}Copy</button>
          <a class="btn btn-ghost" href="${S.meta.explorer}/token/${t[0]}" target="_blank" rel="noopener">${icon('external', 'i-sm')}Blockscout</a>
          <a class="btn btn-ghost" href="#/explorer?token=${t[0]}">${icon('list', 'i-sm')}Wallets</a>
          <a class="btn btn-primary" href="#/visualizer?token=${t[0]}">${icon('graph', 'i-sm')}Bubble map</a>
        </div>
      </div>
      <div class="stats" style="--n:6">
        <div class="stat"><div class="eyebrow">Price</div><div class="stat-v">${price(t[3])}</div><div class="stat-c">${t[7] ? `${esc(t[7])} · ${esc(t[8])} pair` : 'no pool indexed'}</div></div>
        <div class="stat"><div class="eyebrow">Liquidity</div><div class="stat-v">${usd(t[4])}</div><div class="stat-c">24h vol ${usd(t[5])}</div></div>
        <div class="stat"><div class="eyebrow">Traders</div><div class="stat-v">${nf(a?.wallets.size || 0)}</div><div class="stat-c">in local swaps</div></div>
        <div class="stat"><div class="eyebrow">Buys / Sells</div><div class="stat-v"><span class="pos">${nf(a?.nb || 0)}</span><span class="t3"> / </span><span class="neg">${nf(a?.ns || 0)}</span></div><div class="stat-c">${a ? `${date(a.first)} → ${date(a.last)}` : '—'}</div></div>
        <div class="stat"><div class="eyebrow">Snipers</div><div class="stat-v" style="color:${f.SNIPER ? 'var(--c-sniper)' : 'var(--text-3)'}">${f.SNIPER?.size || 0}</div><div class="stat-c">≤10 blocks after open</div></div>
        <div class="stat"><div class="eyebrow">Bundled wallets</div><div class="stat-v" style="color:${f.BUNDLER_SUSPECT ? 'var(--c-bundler)' : 'var(--text-3)'}">${f.BUNDLER_SUSPECT?.size || 0}</div><div class="stat-c">${bundles.length} bundle tx${bundles.length === 1 ? '' : 's'}</div></div>
      </div>

      <section class="panel">
        <div class="panel-h"><span class="panel-title">${st.chart === 'price' ? 'Price (USD)' : 'Swap flow (USD est.)'}</span>
          ${bundles.length ? bundles.map(([e, i]) => `<a class="fchip" style="--c:var(--c-bundler)" href="#/visualizer?entity=${i}">${icon('bundle')}${esc(e.title)}</a>`).join('') : ''}
          <div class="end"><div class="seg is-sm"><button class="seg-btn ${st.chart === 'price' ? 'is-active' : ''}" data-chart="price" ${spark.length ? '' : 'disabled'}>Price</button><button class="seg-btn ${st.chart === 'flow' ? 'is-active' : ''}" data-chart="flow">Flow</button></div></div></div>
        <div class="panel-b"><div id="tchart"></div></div>
        ${!spark.length ? `<div class="panel-note">No price points for this token in the local DB yet — the flow chart above uses snapshot-priced USD est.</div>` : ''}
        ${S.meta.calibrated.some(c => c[0] === k) ? `<div class="panel-note">${icon('info', 'i-sm').replace('class="i', 'style="display:inline;vertical-align:-2px;margin-right:6px;color:var(--amber)" class="i')}This pool’s stored price points were on the wrong scale, so the series is rescaled onto the snapshot price. Shape is reliable; absolute USD is approximate.</div>` : ''}
      </section>

      <section class="panel">
        <div class="tabs">
          <button class="tab ${st.tab === 'traders' ? 'is-active' : ''}" data-tab="traders">Traders <span class="t3">${traders.length}</span></button>
          <button class="tab ${st.tab === 'swaps' ? 'is-active' : ''}" data-tab="swaps">Swaps <span class="t3">${swaps.length}</span></button>
          <button class="tab ${st.tab === 'flagged' ? 'is-active' : ''}" data-tab="flagged">Flagged wallets <span class="t3">${flagged.length}</span></button>
        </div>
        <div class="table-wrap">${body}</div>${foot}
      </section>
    </div>`;

    const el = root.querySelector('#tchart');
    if (st.chart === 'price' && spark.length) {
      areaChart(el, { points: spark, color: '--blue-hi', height: 260, yFmt: v => price(v).replace(/<\/?sub>/g, ''), tip: p => `<div class="t3">${date(p[0], true)} UTC</div><div>${price(p[1])}</div>` });
    } else {
      const days = a ? bucketDays(swaps, a.first, a.last, 2, 3, 4) : [];
      flowChart(el, { days, height: 260, yFmt: v => usd(v).replace('.00', ''), tip: d => `<div class="t3">${date(d.t)} UTC</div><div><span class="pos">Buys</span> ${d.nb} · ${usd(d.buy)}</div><div><span class="neg">Sells</span> ${d.ns} · ${usd(d.sell)}</div>` });
    }
  };
  draw();

  root.addEventListener('click', e => {
    const cp = e.target.closest('[data-copy]'); if (cp) return copy(cp.dataset.copy);
    const tb = e.target.closest('[data-tab]'); if (tb) { st.tab = tb.dataset.tab; st.page = 0; return draw(); }
    const ch = e.target.closest('[data-chart]'); if (ch && !ch.disabled) { st.chart = ch.dataset.chart; return draw(); }
    const th = e.target.closest('th[data-sort]');
    if (th) { const s = th.dataset.sort; if (st.sort === s) st.dir *= -1; else { st.sort = s; st.dir = -1; } st.page = 0; return draw(); }
    const pg = e.target.closest('[data-page]'); if (pg && !pg.disabled) { st.page = +pg.dataset.page; return draw(); }
    const row = e.target.closest('tr[data-href]');
    if (row && !e.target.closest('a')) location.hash = row.dataset.href;
  });
}
