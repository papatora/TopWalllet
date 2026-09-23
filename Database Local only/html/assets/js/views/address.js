import { S, tokName, walletName } from '../lib/store.js';
import { esc, nf, usd, date, short, dur } from '../lib/fmt.js';
import { icon, chip, labelMeta, pretty, tokAv, dropdown, emptyRow, walletHref, tokenHref, txHref, addrExt, copy, snapMark } from '../lib/ui.js';
import { areaChart, flowChart, bucketDays } from '../lib/charts.js';
import { evidenceBlocks } from '../lib/evidence.js';

const st = { chart: 'cum', side: 'all', tok: 'all', minUsd: true, tokSort: 'vol' };

export function render(root, [addr]) {
  const i = S.addrIndex.get(addr.toLowerCase());
  if (i == null) {
    root.innerHTML = `<div class="page"><h1 class="page-title">Address not indexed</h1><p class="t2" style="margin-top:10px;max-width:64ch">${esc(addr)} has no classification in the local Robinhood Chain snapshot. <a class="link" href="${addrExt(addr)}" target="_blank" rel="noopener">Look it up on Blockscout</a>.</p></div>`;
    return;
  }
  if (st._i !== i) Object.assign(st, { _i: i, chart: 'cum', side: 'all', tok: 'all', minUsd: true });
  const w = S.wallets[i], s = S.statsAll.get(i), sw = S.swaps[i] || [], nm = walletName(i), ptype = S.types[w[1]];
  const ents = (S.memberOf.get(i) || []).map(ei => [S.entities[ei], ei]);
  const mates = [...new Set(ents.flatMap(([e]) => e.members))].filter(j => j !== i);
  const lm = labelMeta(ptype);

  const draw = () => {
    const tokOpts = [{ v: 'all', l: 'All tokens' }, ...(s?.toks || []).map(k => ({ v: String(k), l: tokName(k) }))];
    const rows = [...sw].reverse().filter(r => (st.side === 'all' || (st.side === 'sell') === !!r[2]) && (st.tok === 'all' || String(r[0]) === st.tok) && (!st.minUsd || r[3] >= 1));
    const tokRows = s ? [...s.per.entries()].map(([k, p]) => ({ k, ...p, net: p.so - p.bu, vol: p.bu + p.so })).sort((a, b) => b[st.tokSort] - a[st.tokSort]) : [];

    root.innerHTML = `<div class="page">
      <div class="profile-head">
        <span class="avatar is-lg" style="color:${lm.c}">${icon(w[4] ? 'at' : lm.icon)}</span>
        <div style="min-width:0">
          <div class="profile-name">${esc(nm || 'Unlabeled wallet')}</div>
          <div class="profile-addr">${w[0]}</div>
          <div class="chips" style="margin-top:8px">${w[2].map(l => chip(S.labels[l])).join('')}<span class="chip no-dot" style="--c:var(--text-2)">ROBINHOOD CHAIN</span></div>
        </div>
        <div class="end">
          <button class="btn btn-ghost" data-copy="${w[0]}">${icon('copy', 'i-sm')}Copy</button>
          <a class="btn btn-ghost" href="${addrExt(w[0])}" target="_blank" rel="noopener">${icon('external', 'i-sm')}Blockscout</a>
          <a class="btn btn-primary" href="#/visualizer?wallet=${w[0]}">${icon('graph', 'i-sm')}Visualize</a>
        </div>
      </div>

      <div class="stats" style="--n:6">
        <div class="stat"><div class="eyebrow">Net flow est.</div><div class="stat-v ${s ? (s.net >= 0 ? 'pos' : 'neg') : 't3'}">${s ? (s.allSnap ? snapMark(1) : '') + usd(s.net, true) : '—'}</div><div class="stat-c">sold minus bought</div></div>
        <div class="stat"><div class="eyebrow">Bought</div><div class="stat-v">${s ? usd(s.bu) : '—'}</div><div class="stat-c">${s ? `${nf(s.nb)} buys` : 'no swaps'}</div></div>
        <div class="stat"><div class="eyebrow">Sold</div><div class="stat-v">${s ? usd(s.so) : '—'}</div><div class="stat-c">${s ? `${nf(s.ns)} sells` : 'no swaps'}</div></div>
        <div class="stat"><div class="eyebrow">W / L tokens</div><div class="stat-v">${s ? `<span class="pos">${s.w}</span><span class="t3"> / </span><span class="neg">${s.l}</span>` : '—'}</div><div class="stat-c">${s ? `${s.toks.length} tokens traded` : '—'}</div></div>
        <div class="stat"><div class="eyebrow">Avg hold</div><div class="stat-v">${s ? dur(s.hold) : '—'}</div><div class="stat-c">median first buy → last sell</div></div>
        <div class="stat"><div class="eyebrow">Active</div><div class="stat-v" style="font-size:18px">${s ? date(s.last) : '—'}</div><div class="stat-c">${s ? `since ${date(s.first)}` : 'label only'}</div></div>
      </div>

      <div class="profile">
        <div class="profile-side">
          <section class="panel">
            <div class="panel-h"><span class="panel-title">Overview</span></div>
            <div class="panel-b" style="padding-top:6px;padding-bottom:6px"><div class="kv">
              <div class="kv-row"><span>Primary type</span><span>${chip(ptype)}</span></div>
              ${(S.origins && S.origins[w[0]]) ? (() => { const o = S.origins[w[0]]; return `<div class=\"kv-row\"><span>INDUKAN</span><span>${esc(o.label || o.kind)}</span></div><div class=\"kv-row\"><span>Pengirim</span><span>${(o.senders || []).map(s => `<a class=\"link mono\" href=\"${addrExt(s.addr)}\" target=\"_blank\" rel=\"noopener\">${s.addr.slice(0, 10)}…</a>`).join(' · ') || 'mint 0x0'}</span></div>`; })() : ''}
              <div class="kv-row"><span>Top confidence</span><span>${Math.max(...w[3]).toFixed(2)}</span></div>
              <div class="kv-row"><span>Labels</span><span>${w[2].length}</span></div>
              <div class="kv-row"><span>Swaps</span><span>${nf(sw.length)}</span></div>
              ${s?.unp ? `<div class="kv-row"><span>Unpriced swaps</span><span class="t2">${s.unp}</span></div>` : ''}
              ${s?.snap ? `<div class="kv-row"><span title="Priced at the token’s last snapshot price — no price series in the local DB">Snapshot-priced swaps ~</span><span class="t2">${s.snap}</span></div>` : ''}
              <div class="kv-row"><span>Entities</span><span>${ents.length ? ents.map(([e, ei]) => `<a class="link" href="#/visualizer?entity=${ei}">${esc(e.title)}</a>`).join(', ') : '—'}</span></div>
              ${S.ev[i]?._score?.realized != null ? `<div class="kv-row"><span>Realized PnL · verified</span><span class="${S.ev[i]._score.realized >= 0 ? 'pos' : 'neg'}">${usd(S.ev[i]._score.realized, true)}</span></div>` : ''}
            </div></div>
          </section>
          <section class="panel">
            <div class="panel-h"><span class="panel-title">Related wallets</span><span class="end micro">${mates.length}</span></div>
            ${mates.length ? `<div style="max-height:360px;overflow-y:auto">${mates.slice(0, 60).map(j => { const ms = S.statsAll.get(j);
              return `<a class="ent-item" href="${walletHref(j)}"><span class="avatar" style="width:26px;height:26px;color:${labelMeta(S.types[S.wallets[j][1]]).c}">${icon(labelMeta(S.types[S.wallets[j][1]]).icon, 'i-sm')}</span><span style="min-width:0;flex:1"><div class="t">${short(S.wallets[j][0], 8, 6)}</div><div class="d">${esc(pretty(S.types[S.wallets[j][1]]))}</div></span><span class="mono ${ms ? (ms.net >= 0 ? 'pos' : 'neg') : 't3'}" style="font-size:11.5px">${ms ? (ms.allSnap ? snapMark(1) : '') + usd(ms.net, true) : '—'}</span></a>`; }).join('')}</div>`
              : `<p class="panel-note" style="border:0">Not part of a funding cluster or same-tx bundle.</p>`}
          </section>
        </div>

        <div class="profile-main">
          <section class="panel">
            <div class="panel-h"><span class="panel-title">${st.chart === 'cum' ? 'Cumulative net flow' : 'Daily swap flow'}</span><span class="t3 mono" style="font-size:11px" title="${S.meta.pricing_mode === 'historical' ? 'USD valued at the nearest pool price point' : S.meta.pricing_mode === 'mixed' ? 'USD: series price where available, else last snapshot price' : 'Local DB has no price points — USD valued at the token’s last snapshot price'}">USD est.${S.meta.pricing_mode === 'mixed' ? ' · mixed px' : S.meta.pricing_mode && S.meta.pricing_mode !== 'historical' ? ' · snapshot px' : ''}</span>
              <div class="end"><div class="seg is-sm"><button class="seg-btn ${st.chart === 'cum' ? 'is-active' : ''}" data-chart="cum">Cumulative</button><button class="seg-btn ${st.chart === 'daily' ? 'is-active' : ''}" data-chart="daily">Daily</button></div></div></div>
            <div class="panel-b"><div id="achart"></div></div>
          </section>

          <div class="grid grid-11">
            <section class="panel">
              <div class="tabs"><span class="tab is-active">Tokens</span>
                <div class="tabs-end"><div class="seg is-sm">${[['vol', 'Volume'], ['net', 'Net'], ['n', 'Tx']].map(([k, l]) => `<button class="seg-btn ${st.tokSort === k ? 'is-active' : ''}" data-toksort="${k}">${l}</button>`).join('')}</div></div></div>
              <div class="table-wrap"><table class="table is-compact" style="--min:480px"><thead><tr><th>Token</th><th class="rt">Tx</th><th class="rt">Bought</th><th class="rt">Sold</th><th class="rt">Net</th></tr></thead><tbody>
                ${tokRows.map(p => `<tr class="is-link" data-href="${tokenHref(p.k)}"><td><div class="who">${tokAv(p.k, 'is-md')}<span style="color:var(--text)">${esc(tokName(p.k))}</span></div></td><td class="rt">${p.n}</td><td class="rt pos">${usd(p.bu)}</td><td class="rt neg">${usd(p.so)}</td><td class="rt ${p.net >= 0 ? 'pos' : 'neg'}">${p.allSnap ? snapMark(1) : ''}${usd(p.net, true)}</td></tr>`).join('') || emptyRow(5, 'No swaps in the local snapshot.')}
              </tbody></table></div>
            </section>
            <section class="panel">
              <div class="tabs">${[['all', 'Swaps'], ['buy', 'Buys'], ['sell', 'Sells']].map(([k, l]) => `<button class="tab ${st.side === k ? 'is-active' : ''}" data-side="${k}">${l}</button>`).join('')}
                <div class="tabs-end">${sw.length ? dropdown('tok', 'filter', tokOpts, st.tok) : ''}</div></div>
              <div style="padding:10px 14px;border-bottom:1px solid var(--line-soft);display:flex;gap:8px;align-items:center">
                <button class="fchip ${st.minUsd ? '' : 'is-off'}" data-minusd style="--c:${st.minUsd ? 'var(--blue-hi)' : 'var(--text-3)'}">${st.minUsd ? icon('x') : ''}USD ≥ $1</button>
                <span class="t3 mono" style="font-size:11px;margin-left:auto">${nf(rows.length)} rows</span></div>
              <div class="table-wrap" style="max-height:520px;overflow-y:auto"><table class="table is-compact" style="--min:520px"><thead><tr><th>Time (UTC)</th><th>Side</th><th>Token</th><th class="rt">USD</th><th>Tx</th></tr></thead><tbody>
                ${rows.slice(0, 300).map(([k, t, sd, u, tx, sn]) => `<tr><td class="t2">${date(t, true)}</td><td><span class="side ${sd ? 'is-sell' : 'is-buy'}">${sd ? 'SELL' : 'BUY'}</span></td><td><a class="who" href="${tokenHref(k)}">${tokAv(k, 'is-md')}${esc(tokName(k))}</a></td><td class="rt">${u >= 0 ? snapMark(sn) + usd(u) : '<span class="t3">unpriced</span>'}</td><td><a class="link" href="${txHref(tx)}" target="_blank" rel="noopener">${tx.slice(0, 10)}…</a></td></tr>`).join('') || emptyRow(5, sw.length ? 'No swaps match. Remove the USD filter or pick another token.' : 'No swaps in the local snapshot.')}
              </tbody></table></div>
            </section>
          </div>

          <section class="panel">
            <div class="panel-h"><span class="panel-title">Classification evidence</span><span class="end t3 mono" style="font-size:11px">labels ${esc(S.meta.labels_generated.slice(0, 10))}</span></div>
            <div class="evidence">${evidenceBlocks(i)}</div>
          </section>
        </div>
      </div>
    </div>`;

    const el = root.querySelector('#achart');
    if (!sw.length) { el.innerHTML = '<p class="t3" style="padding:60px 0;text-align:center">No swaps for this wallet in the local snapshot — its labels come from the VPS classifier run.</p>'; return; }
    if (st.chart === 'cum') {
      let acc = 0;
      const pts = sw.filter(r => r[3] >= 0).map(r => { acc += r[2] ? r[3] : -r[3]; return [r[1], acc]; });
      if (pts.length) pts.unshift([pts[0][0] - 1, 0]);
      const up = (pts.at(-1)?.[1] || 0) >= 0;
      areaChart(el, { points: pts, color: up ? '--green' : '--red', height: 250, baseline: true, yFmt: v => usd(v, true).replace('.00', ''), tip: p => `<div class="t3">${date(p[0], true)} UTC</div><div>Net <span class="${p[1] >= 0 ? 'pos' : 'neg'}">${usd(p[1], true)}</span></div>` });
    } else {
      const days = bucketDays(sw, s.first, s.last, 1, 2, 3);
      flowChart(el, { days, height: 250, yFmt: v => usd(v).replace('.00', ''), tip: d => `<div class="t3">${date(d.t)} UTC</div><div><span class="pos">Buys</span> ${d.nb} · ${usd(d.buy)}</div><div><span class="neg">Sells</span> ${d.ns} · ${usd(d.sell)}</div>` });
    }
  };
  draw();

  root.addEventListener('click', e => {
    const cp = e.target.closest('[data-copy]'); if (cp) return copy(cp.dataset.copy);
    const ch = e.target.closest('[data-chart]'); if (ch) { st.chart = ch.dataset.chart; return draw(); }
    const sd = e.target.closest('[data-side]'); if (sd) { st.side = sd.dataset.side; return draw(); }
    const ts = e.target.closest('[data-toksort]'); if (ts) { st.tokSort = ts.dataset.toksort; return draw(); }
    if (e.target.closest('[data-minusd]')) { st.minUsd = !st.minUsd; return draw(); }
    const row = e.target.closest('tr[data-href]');
    if (row && !e.target.closest('a')) location.hash = row.dataset.href;
  });
  root.addEventListener('dd:change', e => { if (e.detail.id === 'tok') { st.tok = e.detail.value; draw(); } });
}
