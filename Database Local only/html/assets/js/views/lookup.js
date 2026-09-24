// Lookup — paste CA/link (GMGN, DexScreener, Arkham, mentah) → laporan token.
// Goal #4: rating 0-10 (rincian komponen), cluster lokal, deployer/funder,
// sosial, status di-DB. Backend: GET /api/lookup?input=… (lookup_api.py).
import { esc, nf, usd, price, date, short } from '../lib/fmt.js';
import { chip, pretty, extLink } from '../lib/ui.js';

const $ = s => document.querySelector(s);
let lastInput = '';

const panel = (title, body) => `<section class="panel" style="margin-bottom:16px"><div class="panel-b">
  <h2 style="font-size:15px;font-weight:600;margin-bottom:10px">${title}</h2>${body}</div></section>`;

const kv = (k, v) => `<div class="kv-row"><span class="t3">${k}</span><span>${v}</span></div>`;

function ratingColor(r) {
  return r >= 7 ? 'var(--up,#2ecc71)' : r >= 4 ? 'var(--warn,#f1c40f)' : 'var(--down,#e74c3c)';
}

function draw(root, d) {
  if (!d.ok) {
    root.innerHTML = `<div class="page">${root.querySelector('.lookup-box')?.outerHTML || ''}
      <section class="panel"><div class="panel-b"><p class="t2">${esc(d.error || 'gagal')}</p></div></section></div>`;
    return;
  }
  const { ca, db, dex, chain, cluster, bubblemaps: bub, rating, rating_components: comps, links } = d;
  const sym = dex.symbol || db.symbol || ca.slice(0, 8);
  const ageD = dex.pair_created_at ? (Date.now() - dex.pair_created_at) / 864e5 : null;

  const ghost = bub.captured && (bub.top1_pct || 0) >= 50;
  const ghostBox = bub.captured
    ? `<div style="margin-top:8px;padding:10px 12px;border:1px solid ${ghost ? 'var(--down,#e74c3c)' : 'var(--line,#333)'};border-radius:8px">
         <span class="t2">${ghost ? '⚠ GHOST SUPPLY' : 'Supply tersebar'} — top1 holder ${bub.top1_pct?.toFixed(1) ?? '?'}%
         dari ${bub.holders} holder teratas (capture Goal #5)</span>
         ${bub.clusters?.length ? `<div class="t3" style="margin-top:4px">Cluster bubblemaps: ${bub.clusters.map(c => `${c.n} wallet @ ${c.pct}%`).join(' · ')}</div>` : ''}
       </div>`
    : `<div class="t3" style="margin-top:8px">Belum ada capture bubblemaps — jalankan <code>scripts/bubblemaps_capture.py</code> untuk cek konsentrasi supply.</div>`;

  const clusterRows = Object.entries(cluster.groups || {})
    .sort((a, b) => b[1] - a[1])
    .map(([g, n]) => `<span style="margin-right:10px;display:inline-block">${chip(g, `${pretty(g)} × ${n}`)}</span>`)
    .join('') || '<span class="t3">tidak ada wallet berlabel yang menyentuh token ini</span>';

  const compRows = comps.map(c => `<div class="kv-row">
      <span class="t2">${esc(c.component)}</span>
      <span><span style="color:${ratingColor(c.score)}">${c.score}</span> / ${c.max}
      <span class="t3"> — ${esc(c.note)}</span></span></div>`).join('');

  const socials = (dex.socials || []).map(s =>
    `<span style="margin-right:10px">${extLink(s.url, esc(s.type))}</span>`).join('') || '<span class="t3">—</span>';

  const funderEnt = chain.funder_entity ? ` <strong>${esc(chain.funder_entity)}</strong>` : '';
  const depEnt = chain.deployer_entity ? ` <strong>${esc(chain.deployer_entity)}</strong>` : '';

  root.innerHTML = `<div class="page">
    <div class="lookup-box">${root.querySelector('.lookup-box')?.outerHTML || ''}</div>

    <section class="panel" style="margin-bottom:16px"><div class="panel-b" style="display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      <div style="text-align:center;min-width:130px">
        <div style="font-size:44px;font-weight:700;color:${ratingColor(rating)};font-family:IBM Plex Mono,monospace">${rating.toFixed(1)}</div>
        <div class="t3">rating / 10</div>
      </div>
      <div style="flex:1;min-width:260px">${compRows}</div>
    </div></section>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px">
      ${panel('Identitas & pasar (DexScreener)', `
        ${kv('Token', `<strong>${esc(sym)}</strong> — ${esc(dex.name || db.name || '?')}`)}
        ${kv('Harga', dex.price_usd ? price(dex.price_usd) : (db.in_db ? '—' : 'tidak ditemukan'))}
        ${kv('Likuiditas', dex.liquidity_usd ? usd(dex.liquidity_usd) : '—')}
        ${kv('Volume 24 jam', dex.volume_24h_usd ? usd(dex.volume_24h_usd) : '—')}
        ${kv('Usia pair', ageD != null ? ageD.toFixed(1) + ' hari' : '—')}
        ${kv('Sosial', socials)}`)}
      ${panel('Status di snapshot lokal', `
        ${kv('Di DB', db.in_db ? '✅ ya' : '❌ belum (wallet/token belum terekam)')}
        ${db.in_db ? kv('Trader', nf(db.traders)) : ''}
        ${db.in_db ? kv('Swap', `${nf(db.swaps)} (${nf(db.buys || 0)} beli)`) : ''}
        ${db.in_db ? kv('Periode', `${db.first_swap ? date(db.first_swap) : '?'} → ${db.last_swap ? date(db.last_swap) : '?'}`) : ''}
        ${db.in_db ? kv('Pool terbesar', db.pools?.[0] ? `${esc(db.pools[0].dex)} v${db.pools[0].version} · ${usd(db.pools[0].liquidity_usd || 0)}` : '—') : ''}
        ${clusterRows}`)}
      ${panel('Deployer & pendanaan (Etherscan V2)', `
        ${kv('Deployer', chain.deployer ? `${short(chain.deployer)}${depEnt}` : '—')}
        ${kv('Usia kontrak', chain.deploy_age_days != null ? chain.deploy_age_days + ' hari' : '—')}
        ${kv('Funder pertama', chain.funder ? `${short(chain.funder)}${funderEnt}` : '—')}
        ${kv('Catatan', chain.funder_entity ? `funder dikenali: ${esc(chain.funder_entity)}` : 'funder tidak ada di registry entitas lokal')}`)}
    </div>

    ${panel('Konsentrasi supply (Bubblemaps)', ghostBox)}

    ${panel('Tautan', Object.entries(links).map(([k2, u]) =>
      `<span style="margin-right:14px">${extLink(u, k2)}</span>`).join(''))}
  </div>`;

  const inp = root.querySelector('.lookup-input');
  if (inp && lastInput) inp.value = lastInput;
}

export function render(root) {
  root.innerHTML = `<div class="page">
    <h1 class="page-title">Cek Token (paste-CA)</h1>
    <p class="t2" style="margin:4px 0 14px">Tempel CA mentah atau link GMGN / DexScreener / Arkham — apa pun yang mengandung alamat 0x…. Data: snapshot lokal + DexScreener + Etherscan (lokal, bukan VPS).</p>
    <div class="lookup-box" style="display:flex;gap:8px;margin-bottom:18px">
      <input class="lookup-input" type="text" placeholder="0x… atau https://gmgn.ai/robinhood/token/0x…"
        style="flex:1;padding:10px 12px;border:1px solid var(--line,#333);border-radius:8px;background:var(--bg,#0b0d12);color:var(--fg,#eee);font-family:IBM Plex Mono,monospace">
      <button class="lookup-go" style="padding:10px 18px;border-radius:8px;cursor:pointer">Cek</button>
    </div>
    <div class="lookup-out"></div>
  </div>`;
  const out = root.querySelector('.lookup-out');
  const run = async () => {
    const v = root.querySelector('.lookup-input').value.trim();
    if (!v) return;
    lastInput = v;
    out.innerHTML = '<p class="t3">mengambil data…</p>';
    try {
      const r = await fetch('/api/lookup?input=' + encodeURIComponent(v));
      draw(out, await r.json());
    } catch (e) {
      out.innerHTML = `<section class="panel"><div class="panel-b"><p class="t2">gagal: ${esc(String(e))}</p></div></section>`;
    }
  };
  root.querySelector('.lookup-go').addEventListener('click', run);
  root.querySelector('.lookup-input').addEventListener('keydown', e => { if (e.key === 'Enter') run(); });
}
