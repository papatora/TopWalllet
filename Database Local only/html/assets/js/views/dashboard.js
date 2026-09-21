import { S, tokName } from '../lib/store.js';
import { esc, nf, usd, date, pct, price, short } from '../lib/fmt.js';
import { icon, chip, labelMeta, pretty, tokAv, rank, whoCell, walletHref, tokenHref, txHref, emptyRow } from '../lib/ui.js';
import { flowChart, bucketDays, sparkline } from '../lib/charts.js';

const st = { mode: 'usd' };

export function render(root) {
  const m = S.meta, days = bucketDays(S.all, m.swap_from, m.swap_to, 2, 3, 4);
  const clusterMembers = S.clusters.reduce((a, c) => a + c.members.length, 0);
  const bundleMembers = S.bundles.reduce((a, b) => a + b.members.length, 0);
  const pools = S.tokens.filter(t => t[7]).length;
  const typeRows = Object.entries(m.type_counts).sort((a, b) => b[1] - a[1]);
  const total = S.wallets.length;

  const topNet = [...S.statsAll.entries()].sort((a, b) => b[1].net - a[1].net).slice(0, 8);
  const biggest = S.all.filter(r => r[4] >= 0).sort((a, b) => b[4] - a[4]).slice(0, 8);
  const hotTokens = [...S.tokAgg.entries()].sort((a, b) => b[1].wallets.size - a[1].wallets.size).slice(0, 8);

  root.innerHTML = `<div class="page page-dash">
    <div class="page-head" style="grid-template-columns:1fr auto">
      <div><div class="eyebrow">Robinhood Chain · local snapshot</div><h1 class="page-title" style="margin-top:8px">Overview</h1></div>
      <div class="end"><a class="btn btn-ghost" href="#/visualizer">${icon('graph', 'i-sm')}Open visualizer</a><a class="btn btn-primary" href="#/leaderboard">${icon('trophy', 'i-sm')}Leaderboard</a></div>
    </div>

    <div class="stats" style="--n:6">
      <div class="stat"><div class="eyebrow">Wallets classified</div><div class="stat-v">${nf(total)}</div><div class="stat-c">${S.types.length} primary types · ${nf(m.label_counts ? Object.values(m.label_counts).reduce((a, b) => a + b, 0) : 0)} labels</div></div>
      <div class="stat"><div class="eyebrow">Active traders</div><div class="stat-v">${nf(S.active.length)}</div><div class="stat-c">${pct(S.active.length, total)} of classified wallets</div></div>
      <div class="stat"><div class="eyebrow">Swaps indexed</div><div class="stat-v">${nf(m.swaps_total)}</div><div class="stat-c">${pct(m.priced, m.swaps_total)} priced · ${date(m.swap_from)} → ${date(m.swap_to)}</div></div>
      <div class="stat"><div class="eyebrow">Tokens tracked</div><div class="stat-v">${nf(pools)}</div><div class="stat-c">with a Uniswap pool</div></div>
      <div class="stat"><div class="eyebrow">Funding clusters</div><div class="stat-v">${S.clusters.length}</div><div class="stat-c">${clusterMembers} member wallets</div></div>
      <div class="stat"><div class="eyebrow">Same-tx bundles</div><div class="stat-v">${S.bundles.length}</div><div class="stat-c">${bundleMembers} bundled wallets</div></div>
    </div>

    <div class="grid grid-21">
      <section class="panel">
        <div class="panel-h"><span class="panel-title">Swap flow</span><span class="legend"><span style="--c:var(--green)"><i></i>Buys</span><span style="--c:var(--red)"><i></i>Sells</span></span>
          <span class="flow-badge"><i></i>INDEXED ${date(m.swap_from)} → ${date(m.swap_to)}</span>
          <div class="end"><div class="seg is-sm" data-mode><button class="seg-btn ${st.mode === 'usd' ? 'is-active' : ''}" data-v="usd">USD est.</button><button class="seg-btn ${st.mode === 'count' ? 'is-active' : ''}" data-v="count">Count</button></div></div></div>
        <div class="panel-b"><div id="flow"></div></div>
        <div class="panel-note">Daily buys above the line, sells below. ${m.pricing_mode === 'mixed' ? 'USD is estimated from pool price points where a series exists, else the token’s last snapshot price' : m.pricing_mode && m.pricing_mode !== 'historical' ? 'USD is estimated from each token’s last snapshot price — the local DB has no price points, so treat totals as rough' : 'USD is estimated from the nearest pool price point'}; ${nf(m.unpriced)} swaps without a usable price are counted but not valued.</div>
      </section>
      <section class="panel">
        <div class="panel-h"><span class="panel-title">Classification mix</span><span class="end t3 mono" style="font-size:11px">primary type</span></div>
        <div class="panel-b">
          <div class="mix-bar">${typeRows.map(([t, n]) => `<span style="--c:${labelMeta(t).c};flex:${Math.max(n / total, 0.004)}" title="${esc(pretty(t))} ${nf(n)}"></span>`).join('')}</div>
          ${typeRows.map(([t, n]) => `<a class="mix-row" href="#/explorer?type=${encodeURIComponent(t)}"><span class="mix-sw" style="--c:${labelMeta(t).c}"></span><span class="mix-name">${esc(pretty(t))}</span><span class="mix-n num">${nf(n)}</span><span class="mix-p">${pct(n, total)}</span></a>`).join('')}
        </div>
      </section>
    </div>

    <div class="grid grid-11">
      <section class="panel">
        <div class="panel-h"><span class="panel-title">Top net flow</span><span class="t3 mono" style="font-size:11px">est.</span><a class="end link mono" style="font-size:12px" href="#/leaderboard">View leaderboard ${icon('chevron-right', 'i-sm')}</a></div>
        <div class="table-wrap"><table class="table is-compact" style="--min:560px"><thead><tr><th>#</th><th>Wallet</th><th class="rt">Net flow</th><th class="rt">Swaps</th><th class="rt">Tokens</th></tr></thead><tbody>
          ${topNet.map(([i, s], j) => `<tr class="is-link" data-href="${walletHref(i)}"><td>${rank(j + 1)}</td><td>${whoCell(i, { full: false })}</td><td class="rt ${s.net >= 0 ? 'pos' : 'neg'}">${usd(s.net, true)}</td><td class="rt">${nf(s.swaps)}</td><td class="rt">${s.toks.length}</td></tr>`).join('')}
        </tbody></table></div>
      </section>
      <section class="panel">
        <div class="panel-h"><span class="panel-title">Largest swaps</span><span class="t3 mono" style="font-size:11px">est.</span></div>
        <div class="table-wrap"><table class="table is-compact" style="--min:560px"><thead><tr><th>Time (UTC)</th><th>Wallet</th><th>Side</th><th>Token</th><th class="rt">USD</th><th>Tx</th></tr></thead><tbody>
          ${biggest.length ? biggest.map(([ai, k, t, sd, u, tx]) => `<tr class="is-link" data-href="${walletHref(ai)}"><td class="t2">${date(t, true)}</td><td><span class="addr" style="font-size:12.5px">${short(S.wallets[ai][0])}</span></td><td><span class="side ${sd ? 'is-sell' : 'is-buy'}">${sd ? 'SELL' : 'BUY'}</span></td><td><a class="who" href="${tokenHref(k)}">${tokAv(k, 'is-md')}${esc(tokName(k))}</a></td><td class="rt">${usd(u)}</td><td><a class="link" href="${txHref(tx)}" target="_blank" rel="noopener">${tx.slice(0, 8)}…</a></td></tr>`).join('') : emptyRow(6, 'No priced swaps yet.')}
        </tbody></table></div>
      </section>
    </div>

    <div class="grid grid-21">
      <section class="panel">
        <div class="panel-h"><span class="panel-title">Most traded tokens</span><a class="end link mono" style="font-size:12px" href="#/tokens">All tokens ${icon('chevron-right', 'i-sm')}</a></div>
        <div class="table-wrap"><table class="table is-compact" style="--min:680px"><thead><tr><th>Token</th><th class="rt">Price</th><th class="rt">Liquidity</th><th class="rt">Traders</th><th class="rt">Buys / Sells</th><th class="rt">Price trend</th></tr></thead><tbody>
          ${hotTokens.map(([k, a]) => { const t = S.tokens[k], sp = S.spark[k];
            return `<tr class="is-link" data-href="${tokenHref(k)}"><td><div class="who">${tokAv(k, 'is-md')}<span style="color:var(--text)">${esc(tokName(k))}</span><span class="t3" style="font-family:var(--sans)">${esc(t[2] || '')}</span></div></td><td class="rt">${price(t[3])}</td><td class="rt">${usd(t[4])}</td><td class="rt">${nf(a.wallets.size)}</td><td class="rt"><span class="pos">${nf(a.nb)}</span> / <span class="neg">${nf(a.ns)}</span></td><td class="rt">${sparkline(sp?.map(p => p[1]), { w: 96, h: 26 })}</td></tr>`; }).join('')}
        </tbody></table></div>
      </section>
      <section class="panel">
        <div class="panel-h"><span class="panel-title">Pipeline checkpoints</span><span class="end t3 mono" style="font-size:11px">local DB</span></div>
        <div class="panel-b"><div class="kv">
          ${Object.entries(m.checkpoints).map(([k, v]) => `<div class="kv-row"><span style="text-transform:capitalize">${esc(k)}</span><span>${esc(v.slice(0, 16))} UTC</span></div>`).join('')}
          <div class="kv-row"><span>Labels generated</span><span>${esc(m.labels_generated.slice(0, 16).replace('T', ' '))} UTC</span></div>
          <div class="kv-row"><span>Dataset built</span><span>${esc(m.built.slice(0, 16).replace('T', ' '))} UTC</span></div>
          <div class="kv-row"><span>Price points (local DB)</span><span>${nf(m.price_points || 0)}</span></div>
          <div class="kv-row"><span>Priced from series / snapshot</span><span>${nf(m.priced_series || 0)} / ${nf(m.priced_fallback || 0)}</span></div>
          <div class="kv-row"><span>Price outliers dropped</span><span>${nf(m.outliers)}</span></div>
        </div></div>
      </section>
    </div>

    <div class="dash-ticker" title="Swap terakhir yang ter-index di database lokal — bukan feed live">
      <span class="tk-label"><i></i>LATEST INDEXED</span>
      <span class="tk-clip"><span class="tk-track" id="tkTrack"></span></span>
    </div>
  </div>`;

  // count-up: angka target NYATA dari dataset, cuma dianimasikan masuknya
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
    root.querySelectorAll('.stat-v').forEach(el => {
      const target = parseFloat((el.textContent || '').replace(/,/g, ''));
      if (!Number.isFinite(target) || target === 0) return;
      const t0 = performance.now(), dur = 900 + Math.random() * 400;
      const tick = now => {
        const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
        el.textContent = nf(Math.round(target * e));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }

  // ticker = 14 swap TER-AKHIR menurut data (satu pass, tanpa sort penuh)
  const recent = [];
  for (const r of S.all) {
    if (r[4] == null) continue;
    if (recent.length < 14) { recent.push(r); recent.sort((a, b) => b[2] - a[2]); }
    else if (r[2] > recent[13][2]) { recent[13] = r; recent.sort((a, b) => b[2] - a[2]); }
  }
  const items = recent.map(r =>
    `<span class="tk"><b>${short(S.wallets[r[0]][0])}</b><span class="${r[3] ? 'neg' : 'pos'}">${r[3] ? 'SELL' : 'BUY'}</span><span>${usd(r[4])}</span><span class="t3">${esc(tokName(r[1]))}</span><span class="t3">${date(r[2], true)}</span></span>`).join('');
  root.querySelector('#tkTrack').innerHTML = items + items; // duplikat = loop mulus

  const drawFlow = () => flowChart(root.querySelector('#flow'), {
    days: st.mode === 'usd' ? days : days.map(d => ({ ...d, buy: d.nb, sell: d.ns })),
    yFmt: st.mode === 'usd' ? v => usd(v).replace('.00', '') : v => nf(Math.round(v)),
    tip: d => { const o = days.find(x => x.t === d.t); return `<div class="t3">${date(d.t)} UTC</div><div><span class="pos">Buys</span> ${nf(o.nb)} · ${usd(o.buy)}</div><div><span class="neg">Sells</span> ${nf(o.ns)} · ${usd(o.sell)}</div><div>Net ${usd(o.sell - o.buy, true)}</div>`; },
  });
  drawFlow();

  root.addEventListener('click', e => {
    const b = e.target.closest('[data-mode] [data-v]');
    if (b) { st.mode = b.dataset.v; b.parentElement.querySelectorAll('.seg-btn').forEach(x => x.classList.toggle('is-active', x === b)); drawFlow(); return; }
    const row = e.target.closest('tr[data-href]');
    if (row && !e.target.closest('a')) location.hash = row.dataset.href;
  });
}
