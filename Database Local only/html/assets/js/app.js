// App shell: router, global search, dropdowns, dataset rebuild.
import { S, load, tokName, walletName } from './lib/store.js';
import { esc, short, nf, date } from './lib/fmt.js';
import { icon, chip, tokAv, pretty, toast } from './lib/ui.js';
import * as dashboard from './views/dashboard.js';
import * as leaderboard from './views/leaderboard.js';
import * as explorer from './views/explorer.js';
import * as visualizer from './views/visualizer.js';
import * as tokens from './views/tokens.js';
import * as token from './views/token.js';
import * as guide from './views/guide.js';
import * as address from './views/address.js';

const $ = s => document.querySelector(s);
const ROUTES = [
  [/^\/?$/, dashboard, 'dashboard'],
  [/^\/leaderboard$/, leaderboard, 'leaderboard'],
  [/^\/explorer$/, explorer, 'explorer'],
  [/^\/visualizer$/, visualizer, 'visualizer'],
  [/^\/tokens$/, tokens, 'tokens'],
  [/^\/guide$/, guide, 'guide'],
  [/^\/token\/(0x[0-9a-f]+)$/i, token, 'tokens'],
  [/^\/address\/(0x[0-9a-f]+)$/i, address, ''],
];

function route() {
  const raw = location.hash.replace(/^#/, '') || '/';
  const [path, qs] = raw.split('?');
  const query = new URLSearchParams(qs || '');
  for (const [re, view, nav] of ROUTES) {
    const m = path.match(re);
    if (!m) continue;
    document.querySelectorAll('[data-nav]').forEach(a => a.classList.toggle('is-active', a.dataset.nav === nav));
    const app = $('#app'), root = document.createElement('div');
    root.className = 'view';
    app.replaceChildren(root);
    view.render(root, m.slice(1), query);
    window.scrollTo(0, 0);
    return;
  }
  $('#app').innerHTML = `<div class="page"><h1 class="page-title">Page not found</h1><p class="t2" style="margin-top:10px">That route doesn’t exist. <a class="link" href="#/">Back to dashboard</a>.</p></div>`;
}

/* ---------- dropdowns (global delegation) ---------- */
document.addEventListener('click', e => {
  const tog = e.target.closest('[data-dd-toggle]');
  const val = e.target.closest('[data-dd-value]');
  document.querySelectorAll('.dd .pop').forEach(p => { if (!tog || p !== tog.nextElementSibling) p.hidden = true; });
  if (tog) { const p = tog.nextElementSibling; p.hidden = !p.hidden; return; }
  if (val) {
    const dd = val.closest('[data-dd]');
    dd.dispatchEvent(new CustomEvent('dd:change', { bubbles: true, detail: { id: dd.dataset.dd, value: val.dataset.ddValue } }));
  }
});

/* ---------- global search ---------- */
let results = [], active = 0;
function search(q) {
  q = q.trim().toLowerCase();
  const pop = $('#search-pop');
  if (!q) { pop.hidden = true; return; }
  const ws = [];
  const exact = S.addrIndex.get(q);
  if (exact != null) ws.push(exact);
  for (let i = 0; i < S.wallets.length && ws.length < 7; i++) {
    const w = S.wallets[i];
    if (i !== exact && (w[0].includes(q) || w[4].toLowerCase().includes(q))) ws.push(i);
  }
  const ts = [];
  S.tokens.forEach((t, k) => { if (ts.length < 5 && (S.tokAgg.has(k) || t[1]) && ((t[1] || '').toLowerCase().includes(q) || (t[2] || '').toLowerCase().includes(q) || t[0].includes(q))) ts.push(k); });
  const es = S.entities.map((e, i) => [e, i]).filter(([e]) => e.title.toLowerCase().includes(q) || e.id.toLowerCase().includes(q) || e.center.toLowerCase().includes(q)).slice(0, 4);
  const ls = S.labels.filter(l => pretty(l).toLowerCase().includes(q) || l.toLowerCase().includes(q)).slice(0, 4);

  results = [
    ...ws.map(i => '#/address/' + S.wallets[i][0]),
    ...ts.map(k => '#/token/' + S.tokens[k][0]),
    ...es.map(([, i]) => '#/visualizer?entity=' + i),
    ...ls.map(l => '#/explorer?label=' + encodeURIComponent(l)),
  ];
  active = 0;
  let n = 0;
  const item = inner => `<button class="pop-item ${n === 0 ? 'is-active' : ''}" data-r="${n++}">${inner}</button>`;
  let h = '';
  if (ws.length) h += `<div class="pop-h micro">Addresses</div>` + ws.map(i => { const w = S.wallets[i], nm = walletName(i);
    return item(`<span class="avatar" style="width:26px;height:26px">${icon(w[4] ? 'at' : 'wallet', 'i-sm')}</span><span class="addr" style="font-size:12.5px">${short(w[0], 10, 6)}</span>${nm ? `<span class="t2">${esc(nm)}</span>` : ''}<span class="end">${S.activeSet.has(i) ? `<span class="t3 mono" style="font-size:11px">${nf(S.statsAll.get(i).swaps)} swaps</span>` : ''}</span>`); }).join('');
  if (ts.length) h += `<div class="pop-h micro">Tokens</div>` + ts.map(k => item(`${tokAv(k, 'is-md')}<span>${esc(tokName(k))}</span><span class="t3">${esc(S.tokens[k][2] || '')}</span><span class="end t3 mono" style="font-size:11px">${S.tokAgg.get(k)?.wallets.size || 0} traders</span>`)).join('');
  if (es.length) h += `<div class="pop-h micro">Entities</div>` + es.map(([e]) => item(`<span class="avatar" style="width:26px;height:26px">${icon(e.kind === 'cluster' ? 'cluster' : 'bundle', 'i-sm')}</span><span>${esc(e.title)}</span><span class="end t3 mono" style="font-size:11px">${e.members.length} wallets</span>`)).join('');
  if (ls.length) h += `<div class="pop-h micro">Labels</div>` + ls.map(l => item(`${chip(l)}<span class="end t3 mono" style="font-size:11px">${nf(S.meta.label_counts[l])}</span>`)).join('');
  pop.innerHTML = h || `<div class="pop-empty">Nothing on Robinhood Chain matches “${esc(q)}”.</div>`;
  pop.hidden = false;
}
function pick(i) {
  if (!results[i]) return;
  $('#search-pop').hidden = true;
  $('#search-input').value = '';
  $('#search-input').blur();
  location.hash = results[i];
}
$('#search-input').addEventListener('input', e => search(e.target.value));
$('#search-input').addEventListener('keydown', e => {
  const items = [...$('#search-pop').querySelectorAll('.pop-item')];
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    active = (active + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % Math.max(1, items.length);
    items.forEach((b, j) => b.classList.toggle('is-active', j === active));
    items[active]?.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter') pick(active);
  else if (e.key === 'Escape') { $('#search-pop').hidden = true; e.target.blur(); }
});
$('#search-pop').addEventListener('mousedown', e => { const b = e.target.closest('[data-r]'); if (b) { e.preventDefault(); pick(+b.dataset.r); } });
$('#search-input').addEventListener('blur', () => setTimeout(() => { $('#search-pop').hidden = true; }, 120));
document.addEventListener('keydown', e => {
  if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); $('#search-input').focus(); }
});

/* ---------- rebuild ---------- */
$('#rebuild').addEventListener('click', async () => {
  const b = $('#rebuild');
  if (b.classList.contains('is-busy')) return;
  b.classList.add('is-busy');
  try {
    const r = await fetch('/api/rebuild', { method: 'POST' });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error);
    await load(); footer(); route();
    toast('Dataset rebuilt from local database');
  } catch (err) {
    toast('Rebuild failed: ' + err.message);
  } finally { b.classList.remove('is-busy'); }
});

function footer() {
  const m = S.meta;
  $('#foot').innerHTML = [
    'TopWallet', `Robinhood Chain ${m.chain_id}`, `swaps ${date(m.swap_from)} → ${date(m.swap_to)}`,
    `labels ${m.labels_generated.slice(0, 10)}`, `built ${m.built.slice(0, 16).replace('T', ' ')} UTC`,
    '<a href="/design/styleguide.html">Design system</a>', 'Local only',
  ].map(s => `<span>${s}</span>`).join('');
}

// theme cycler: dark -> white -> space (persist di localStorage)
const THEMES = ['dark', 'white', 'space'];
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem('tw-theme', t);
}
applyTheme(localStorage.getItem('tw-theme') || 'dark');
document.getElementById('themeBtn')?.addEventListener('click', () => {
  const cur = document.documentElement.dataset.theme || 'dark';
  applyTheme(THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length]);
});

window.addEventListener('hashchange', route);
load().then(() => { footer(); route(); }).catch(err => {
  $('#app').innerHTML = `<div class="page"><h1 class="page-title">Dataset unavailable</h1><p class="t2" style="margin-top:10px;max-width:64ch">${esc(err.message)} Start it with <span class="mono">python server.py</span> inside <span class="mono">Database Local only/html</span>, then reload.</p></div>`;
});
