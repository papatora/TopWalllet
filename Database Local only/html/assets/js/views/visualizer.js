// Visualizer — force-directed bubble map (Bubblemaps) with entity icons & flows (Arkham).
import { S, tokName, walletName } from '../lib/store.js';
import { esc, nf, usd, date, short, pct } from '../lib/fmt.js';
import { icon, chip, tokAv, walletHref, tokenHref, addrExt, txHref, copy, toast } from '../lib/ui.js';
import { buildScope, visibleGraph, ENTITY_TYPES } from '../lib/graph-data.js';
import { GraphCanvas } from '../lib/graph.js';
import { bucketDays } from '../lib/charts.js';

const LS = 'tw.viz.v12';
const DEFAULT_SHOW = { dex: true, funders: true, bundles: true, tradeEdges: true, labelOnly: true, icons: true, labels: true, flow: true, etype_CEX: true, etype_DEX: true, etype_BRIDGE: true, etype_CONTRACT: true, etype_FUND: true, etype_OTHER: true };
const saved = (() => { try { return JSON.parse(localStorage.getItem(LS)) || {}; } catch { return {}; } })();
const st = {
  show: { ...DEFAULT_SHOW, ...(saved.show || {}) }, colorMode: saved.colorMode || 'label', limit: saved.limit || 150,
  grouped: true, listQ: '', range: null, hidden: new Set(), collapsed: new Set(),
};
const persist = () => { try { localStorage.setItem(LS, JSON.stringify({ show: st.show, colorMode: st.colorMode, limit: st.limit, paused: g?.paused || false })); } catch { /* storage blocked */ } };

const LAYERS = [
  ['dex', 'DEX pools', 'coin'], ['etype_CEX', 'CEX', 'wallet'], ['etype_BRIDGE', 'Bridges', 'tx'], ['etype_CONTRACT', 'Contracts', 'code'],
  ['funders', 'Funders', 'cluster'], ['bundles', 'Bundle tx', 'bundle'], ['tradeEdges', 'Trade edges', 'graph'], ['labelOnly', 'Label-only wallets', 'eye'],
  ['icons', 'Entity icons & badges', 'star'], ['labels', 'Address labels', 'list'], ['flow', 'Flow dots', 'arrow-out'],
];

export function render(root, _params, query) {
  let scopeDef = { mode: 'network', ref: null };
  if (query.has('token')) { const k = S.tokIndex.get(query.get('token').toLowerCase()); if (k != null) scopeDef = { mode: 'token', ref: k }; }
  else if (query.has('entity') && S.entities[+query.get('entity')]) scopeDef = { mode: 'entity', ref: +query.get('entity') };
  else if (query.has('wallet')) { const i = S.addrIndex.get(query.get('wallet').toLowerCase()); if (i != null) scopeDef = { mode: 'wallet', ref: i }; }
  if (st.lastScope !== JSON.stringify(scopeDef)) { st.hidden.clear(); st.range = null; st.lastScope = JSON.stringify(scopeDef); }

  root.innerHTML = `<div class="viz">
    <div class="viz-stage"><canvas id="cv"></canvas></div>
    <div class="viz-top">
      <div class="viz-toolbar">
        <button class="btn btn-primary" data-act="more" style="height:36px">More info ${icon('chevron-right', 'i-sm')}</button>
        <div class="viz-addwrap"><input class="viz-add" id="viz-add" placeholder="Add an entity, address, or token" autocomplete="off" spellcheck="false"><div class="pop" id="viz-pop" hidden></div></div>
      </div>
      <div class="viz-chips" id="chips"></div>
    </div>
    <aside class="viz-panel viz-left" id="left"></aside>
    <aside class="viz-panel viz-right" id="right"></aside>
    <button class="viz-tab viz-tab-left" id="tabLeft" data-act="show-left" hidden title="Buka panel kiri">${icon('chevron-right')}</button>
    <button class="viz-tab viz-tab-right" id="tabRight" data-act="show-right" hidden title="Buka address list">${icon('chevron-left')}</button>
    <div class="viz-rail">
      <button class="rail-btn" data-act="fit" title="Fit to screen">${icon('grid')}</button>
      <button class="rail-btn" data-act="zin" title="Zoom in">+</button>
      <span class="rail-zoom" id="zoom">100%</span>
      <button class="rail-btn" data-act="zout" title="Zoom out">−</button>
      <button class="rail-btn" data-act="unpin" title="Unpin all dragged nodes">${icon('refresh')}</button>
    </div>
    <div class="viz-time" id="time"></div>
    <div class="viz-tip" id="tip" hidden></div>
  </div>`;

  const $ = s => root.querySelector(s);
  const g = new GraphCanvas($('#cv'), {
    insets: { left: 330, right: 400, top: 110, bottom: 96 },
    onSelect: () => { drawRight(); drawChips(); },
    onHover: (n, x, y) => showTip(n, x, y),
    onOpen: n => openNode(n),
    onPinChange: () => drawChips(),
  });
  let scope, graph;
  if (saved.paused) queueMicrotask(() => g.setPaused(true));
  window.__viz = g; // console handle for local debugging

  const rebuild = ({ refit = true } = {}) => {
    const from = st.range ? st.range[0] : 0, to = st.range ? st.range[1] : Infinity;
    const prev = new Map((scope?.nodes || []).map(n => [n.id, n]));
    scope = buildScope({ ...scopeDef, limit: st.limit, from, to });
    for (const n of scope.nodes) { const p = prev.get(n.id); if (p) Object.assign(n, { x: p.x, y: p.y, fx: p.fx, fy: p.fy, pinned: p.pinned }); }
    if (refit) { g.fitted = false; g.userMoved = false; }
    applyVisibility(0.9);
    drawLeft(); drawTimeline();
  };
  const applyVisibility = (heat = 0.5) => {
    graph = visibleGraph(scope, st.show, st.hidden);
    Object.assign(g.opt, { colorMode: st.colorMode, icons: st.show.icons, labels: st.show.labels, flow: st.show.flow });
      g.singleCluster = (scope.clusters.length <= 1);
    g.setGraph(graph.nodes, graph.links, { reheat: heat });
    drawChips(); drawRight(); drawLayers(); syncPanels();
  };

  function syncPanels() {
    $('#left')?.classList.toggle('is-hidden', !!st.hideLeft);
    $('#right')?.classList.toggle('is-hidden', !!st.hideRight);
    const tl = $('#tabLeft'), tr = $('#tabRight');
    if (tl) tl.hidden = !st.hideLeft;
    if (tr) tr.hidden = !st.hideRight;
  }

  /* ---------- chips ---------- */
  function drawChips() {
    const scopeColor = { network: 'var(--blue-hi)', token: '#FF4FA3', entity: 'var(--c-cluster)', wallet: 'var(--c-ct)' }[scopeDef.mode];
    const pins = g.pinnedCount();
    $('#chips').innerHTML = `
      <span class="fchip" style="--c:${scopeColor}">${scopeDef.mode !== 'network' ? `<a href="#/visualizer" title="Back to network">${icon('x')}</a>` : icon('graph')}${esc(scopeDef.mode)} · ${esc(scope?.title || '')}</span>
      <div class="dd" data-dd="color"><button class="fchip" data-dd-toggle style="--c:#2EC4B6">Color · ${st.colorMode}${icon('chevron-down')}</button>
        <div class="pop" hidden>${['cluster', 'label', 'flow'].map(m => `<button class="pop-item ${m === st.colorMode ? 'is-active' : ''}" data-dd-value="${m}">${{ cluster: 'Cluster (Bubblemaps)', label: 'Classification', flow: 'Net flow' }[m]}</button>`).join('')}</div></div>
      ${st.range ? `<button class="fchip" data-act="range-clear" style="--c:var(--blue-hi)">${icon('x')}${date(st.range[0])} → ${date(st.range[1] - 1)}</button>` : ''}
      <button class="fchip" data-act="toggle-flow" style="--c:var(--c-mev)">Flow ${st.show.flow ? 'all' : 'off'}</button>
      <span class="viz-presets"><button class="fchip ${isPreset('arkham') ? 'is-on' : ''}" data-preset="arkham" style="--c:var(--text)">Arkham</button><button class="fchip ${isPreset('raw') ? 'is-on' : ''}" data-preset="raw" style="--c:var(--text)">Bubblemaps raw</button></span>
      ${pins ? `<button class="fchip" data-act="unpin" style="--c:var(--blue-hi)">${icon('x')}${pins} pinned</button>` : ''}
      ${st.hidden.size ? `<button class="fchip" data-act="unhide" style="--c:var(--text-2)">${icon('eye')}${st.hidden.size} hidden · show</button>` : ''}`;
  }
  const PRESETS = {
    arkham: { show: { ...DEFAULT_SHOW }, colorMode: 'label' },
    raw: { show: { ...DEFAULT_SHOW, dex: false, funders: false, bundles: false, tradeEdges: false, icons: false, labels: false, flow: false, etype_CEX: false, etype_DEX: false, etype_BRIDGE: false, etype_CONTRACT: false, etype_FUND: false, etype_OTHER: false }, colorMode: 'cluster' },
  };
  const isPreset = p => st.colorMode === PRESETS[p].colorMode && Object.entries(PRESETS[p].show).every(([k, v]) => st.show[k] === v);

  /* ---------- left: trace overview + scope + layers ---------- */
  function drawLeft() {
    const wallets = scope.nodes.filter(n => n.kind === 'wallet' || n.kind === 'entity');
    const vol = wallets.reduce((a, n) => a + n.vol, 0), toks = scope.nodes.filter(n => n.kind === 'token').length;
    const modes = [['network', 'Network'], ['token', 'Token'], ['entity', 'Entity'], ['wallet', 'Wallet']];
    let picker = '';
    if (scopeDef.mode === 'token' || scopeDef.mode === 'network') {
      const top = [...S.tokAgg.entries()].sort((a, b) => b[1].wallets.size - a[1].wallets.size).slice(0, 14);
      picker = `<h5 class="micro" style="margin:4px 16px 6px">Map a token</h5>` + top.map(([k, a]) => `<a class="ent-item ${scopeDef.mode === 'token' && scopeDef.ref === k ? 'is-active' : ''}" href="#/visualizer?token=${S.tokens[k][0]}">${tokAv(k, 'is-md')}<span style="min-width:0"><div class="t">${esc(tokName(k))}</div><div class="d">${a.wallets.size} traders</div></span></a>`).join('');
    }
    if (scopeDef.mode === 'entity' || scopeDef.mode === 'network') {
      picker += `<h5 class="micro" style="margin:12px 16px 6px">Clusters & bundles</h5>` + S.entities.map((e, i) => `<a class="ent-item ${scopeDef.mode === 'entity' && scopeDef.ref === i ? 'is-active' : ''}" href="#/visualizer?entity=${i}"><span class="avatar" style="width:26px;height:26px;color:${e.kind === 'cluster' ? 'var(--c-cluster)' : 'var(--c-bundler)'}">${icon(e.kind === 'cluster' ? 'cluster' : 'bundle', 'i-sm')}</span><span style="min-width:0"><div class="t">${esc(e.title)}</div><div class="d">${e.members.length} wallets</div></span></a>`).join('');
    }
    if (scopeDef.mode === 'wallet') {
      const i = scopeDef.ref;
      picker = `<div class="viz-sec"><div class="addr" style="font-size:12px;word-break:break-all">${S.wallets[i][0]}</div><div class="chips" style="margin-top:8px">${S.wallets[i][2].map(l => chip(S.labels[l])).join('')}</div>
        <a class="btn btn-ghost btn-sm" style="margin-top:10px" href="${walletHref(i)}">${icon('wallet', 'i-sm')}Open profile</a></div>`;
    }
    if (scopeDef.mode === 'token') {
      const k = scopeDef.ref;
      picker = `<div class="viz-sec"><div class="who">${tokAv(k)}<span><div style="color:var(--text)">${esc(tokName(k))}</div><div class="t3 mono" style="font-size:11px">${short(S.tokens[k][0])}</div></span></div><a class="btn btn-ghost btn-sm" style="margin-top:10px" href="${tokenHref(k)}">${icon('coin', 'i-sm')}Token page</a></div>` + picker;
    }
    $('#left').innerHTML = `
      <div class="panel-h" style="min-height:50px"><span class="panel-title" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(scope.title)}</span><span class="end micro">${esc(scope.sub.split(' ')[0])}</span><button class="al-eye" data-act="hide-left" title="Sembunyikan panel kiri">${icon('x', 'i-sm')}</button></div>
      <div class="scroll">
        <div class="viz-sec"><h5 class="micro">Trace overview</h5><div class="kv">
          <div class="kv-row"><span>Transfer volume est.</span><span>${usd(vol)}</span></div>
          <div class="kv-row"><span>Wallets</span><span>${nf(wallets.length)}</span></div>
          <div class="kv-row"><span>Tokens</span><span>${nf(toks)}</span></div>
          <div class="kv-row"><span>Clusters</span><span>${scope.clusters.length}</span></div>
          <div class="kv-row"><span>Chain</span><span>Robinhood 4663</span></div>
        </div></div>
        <div class="viz-sec"><div class="seg is-sm" style="width:100%;display:flex">${modes.map(([m, l]) => `<button class="seg-btn ${scopeDef.mode === m ? 'is-active' : ''}" style="flex:1" data-mode="${m}">${l}</button>`).join('')}</div>
          ${scopeDef.mode === 'network' ? `<div class="kv-row" style="margin-top:8px"><span>Wallet cap</span><span><select class="viz-select" id="limit">${[50, 150, 300, 600].map(v => `<option ${v === st.limit ? 'selected' : ''}>${v}</option>`).join('')}</select></span></div>` : ''}</div>
        <div class="viz-sec"><h5 class="micro">Tampilan</h5>
          <div style="display:flex;gap:8px">
            <button class="btn btn-ghost btn-sm" data-act="freeze" style="flex:1">${g.paused ? icon('bolt', 'i-sm') + ' Resume' : icon('clock', 'i-sm') + ' Freeze'}</button>
            <button class="btn btn-ghost btn-sm" data-act="resetviz" style="flex:1" title="Kembalikan semua ke default">${icon('refresh', 'i-sm')} Reset</button>
            <button class="btn btn-ghost btn-sm" data-act="fs" style="flex:1" title="Fullscreen">${icon('grid', 'i-sm')} Full</button>
          </div></div>
        <div id="layers"></div>
        <div style="padding:6px 0 10px">${picker}</div>
      </div>`;
    drawLayers();
  }
  function drawLayers() {
    const el = $('#layers'); if (!el || !scope) return;
    const count = key => {
      if (key === 'dex') return scope.nodes.filter(n => n.kind === 'token').length;
      if (key === 'funders') return scope.nodes.filter(n => n.kind === 'funder').length;
      if (key === 'bundles') return scope.nodes.filter(n => n.kind === 'bundle').length;
      if (key.startsWith('etype_')) return scope.nodes.filter(n => n.kind === 'entity' && n.etype === key.slice(6)).length;
      if (key === 'tradeEdges') return scope.links.filter(l => l.kind === 'trade' || l.kind === 'flag').length;
      if (key === 'labelOnly') return scope.nodes.filter(n => n.kind === 'wallet' && !n.hasSwaps).length;
      return null;
    };
    const subOf = k => {
      if (k === 'dex') return scope.nodes.filter(n => n.kind === 'token');
      if (k === 'funders') return scope.nodes.filter(n => n.kind === 'funder');
      if (k === 'bundles') return scope.nodes.filter(n => n.kind === 'bundle');
      return null;
    };
    const rows = LAYERS.map(([k, l, ic]) => {
      const n = count(k);
      const subs = subOf(k);
      const chev = subs ? `<button class="al-eye" data-explayer="${k}" title="Buka sub-layer (hide per-item)" style="color:var(--text-3)">${icon(st.expLayer === k ? 'chevron-down' : 'chevron-right', 'i-sm')}</button>` : '';
      let sub = '';
      if (chev && st.expLayer === k) {
        sub = `<div style="max-height:150px;overflow-y:auto;border:1px solid var(--line-soft);border-radius:6px;margin:2px 0 6px">` +
          (subs.length ? subs.map(it => {
            const hid = st.hidden.has(it.id);
            return `<div class="al-row ${hid ? 'is-hidden' : ''}" style="padding:4px 10px"><button class="al-eye" data-eye="${it.id}" title="${hid ? 'Show' : 'Hide'}">${icon(hid ? 'x' : 'eye', 'i-sm')}</button><span class="al-addr" style="font-size:11px">${esc(it.label)}</span><span class="t3 mono" style="margin-left:auto">${usd(it.vol || 0)}</span></div>`;
          }).join('') : `<div class="t3" style="padding:6px 10px">kosong di scope ini</div>`) + `</div>`;
      }
      const main = `<label class="switch-row"><span class="t2">${icon(ic, 'i-sm')}${l}</span>${n != null ? `<span class="t3 mono">${nf(n)}</span>` : ''}<input type="checkbox" data-layer="${k}" ${st.show[k] ? 'checked' : ''}><span class="switch"></span></label>`;
      return main + sub + (chev ? `<div style="margin:-6px 0 6px;text-align:right">${chev}</div>` : '');
    }).join('');
    el.innerHTML = `<div class="viz-sec"><h5 class="micro">Layers</h5>${rows}
      <p class="t3" style="font-size:11px;margin-top:8px;line-height:1.45">CEX / bridge icons come from <span class="mono">data/known_entities.json</span>. No CEX address is registered for Robinhood Chain yet.</p></div>`;
  }

  /* ---------- right: selected node card + address list ---------- */
  function drawRight() {
    if (!scope) return;
    const sel = g.sel, el = $('#right');
    const wallets = scope.nodes.filter(n => n.kind === 'wallet' || n.kind === 'entity').sort((a, b) => b.vol - a.vol || (a.addr < b.addr ? -1 : 1));
    const total = wallets.reduce((a, n) => a + n.vol, 0) || 1;
    const rankOf = new Map(wallets.map((n, i) => [n, i + 1]));
    const q = st.listQ.trim().toLowerCase();
    const match = n => !q || n.addr.includes(q) || n.label.toLowerCase().includes(q);
    const row = n => { const hid = st.hidden.has(n.id);
      return `<div class="al-row ${hid ? 'is-hidden' : ''} ${sel === n ? 'is-sel' : ''}" data-focus="${n.id}">
        <button class="al-eye" data-eye="${n.id}" title="${hid ? 'Show' : 'Hide'} on map">${icon(hid ? 'x' : 'eye', 'i-sm')}</button>
        <span class="al-rank">#${rankOf.get(n)}</span>
        <span class="al-addr">${n.kind === 'entity' || n.ct ? `<b>${esc(n.label)}</b>` : short(n.addr)}</span>
        ${n.type && n.type !== 'GENERALIST' ? `<span class="al-dot" style="background:${g.labelColor(n.type)}" title="${esc(n.type)}"></span>` : ''}
        <span class="al-pct">${n.vol ? pct(n.vol, total) : '—'}</span></div>`; };
    let list = '';
    if (st.grouped) {
      const inCluster = new Set();
      for (const c of scope.clusters) {
        const mem = c.members.filter(match); if (!mem.length) continue;
        mem.forEach(n => inCluster.add(n));
        const open = !st.collapsed.has(c.ci), share = mem.reduce((a, n) => a + n.vol, 0);
        list += `<div class="al-row al-cluster" data-collapse="${c.ci}"><span class="al-eye" style="color:${c.color}">●</span><span class="al-addr"><b style="color:${c.color}">Cluster ${c.ci + 1}</b> <span class="t3">(${mem.length})</span></span>${icon(open ? 'chevron-down' : 'chevron-right', 'i-sm')}<span class="al-pct">${pct(share, total)}</span></div>`;
        if (open) list += mem.sort((a, b) => b.vol - a.vol).map(row).join('');
      }
      list += wallets.filter(n => !inCluster.has(n) && match(n)).map(row).join('');
    } else list = wallets.filter(match).map(row).join('');

    let card = '';
    if (sel) {
      const isW = sel.kind === 'wallet' || sel.kind === 'entity';
      const e = sel.kind === 'funder' || sel.kind === 'bundle' ? S.entities[sel.ref] : null;
      card = `<div class="node-card">
        <div class="who" style="align-items:flex-start">
          ${sel.kind === 'token' ? tokAv(sel.ref) : `<span class="avatar">${icon(sel.kind === 'funder' ? 'cluster' : sel.kind === 'bundle' ? 'bundle' : sel.ct ? 'at' : 'wallet', 'i-sm')}</span>`}
          <div style="min-width:0;flex:1"><div class="addr" style="font-size:12.5px;word-break:break-all;line-height:1.35">${sel.kind === 'token' ? esc(sel.label) : sel.addr}</div>
            <div class="t2" style="font-size:12px;margin-top:3px">${isW ? (walletName(sel.ref) ? esc(walletName(sel.ref)) + ' · ' : '') + (sel.vol ? usd(sel.vol) + ' volume est.' : 'no priced swaps in range') : sel.kind === 'token' ? `${sel.traders} traders in scope · ${usd(sel.vol)} est.` : e ? `${e.members.length} wallets · ${e.kind === 'cluster' ? 'shared first funding' : 'one tx, block ' + nf(e.data.block)}` : ''}</div></div>
        </div>
        ${isW ? `<div class="chips" style="margin-top:10px">${S.wallets[sel.ref][2].map(l => chip(S.labels[l])).join('')}</div>` : ''}
        ${sel.kind === 'group' ? (() => {
          const mem = sel.members || [];
          return `<div style="margin-top:10px;padding:9px 10px;background:var(--panel-2);border:1px solid var(--line);border-radius:8px">
            <div class="t3">GRUP — berisi ${mem.length} wallet receh</div>
            <div class="t3" style="margin:2px 0 4px">Volume grup est. <b>${usd(sel.vol || 0)}</b></div>
            <div style="max-height:96px;overflow-y:auto">${mem.slice(0, 12).map(mi => `<div class="kv-row"><span style="font-family:var(--mono);font-size:10.5px">${short(S.wallets[mi][0], 8, 6)}</span><a class="link" href="${walletHref(mi)}">open</a></div>`).join('')}${mem.length > 12 ? `<div class="t3" style="margin-top:4px">+${mem.length - 12} lainnya…</div>` : ''}</div></div>`;
        })() : ''}
        ${(sel.kind === 'funder' || sel.kind === 'bundle') ? (() => {
          const e = S.entities[sel.ref];
          const folded = sel.foldedCount || 0;
          return `<div style="margin-top:10px;padding:9px 10px;background:var(--panel-2);border:1px solid var(--line);border-radius:8px">
            <div class="t3">GRUP — berisi ${e.members.length} wallet${folded ? ` (${folded} terlipat)` : ''}</div>
            <div class="t3" style="margin:2px 0 4px">Volume grup est. <b>${usd(sel.foldedVol || 0)}</b></div>
            <div style="max-height:96px;overflow-y:auto">${e.members.slice(0, 12).map(mi => `<div class="kv-row"><span style="font-family:var(--mono);font-size:10.5px">${short(S.wallets[mi][0], 8, 6)}</span><a class="link" href="${walletHref(mi)}">open</a></div>`).join('')}${e.members.length > 12 ? `<div class="t3" style="margin-top:4px">+${e.members.length - 12} lainnya…</div>` : ''}</div></div>`;
        })() : ''}
        ${isW && S.origins && S.origins[S.wallets[sel.ref][0]] ? (() => {
          const o = S.origins[S.wallets[sel.ref][0]];
          const rows = (o.senders || []).map(s => {
            const who = s.kind === 'MASS_SPREAD' ? 'mass-spreader (bot sebaran)' : s.kind === 'FUNDER' ? 'funder cluster' : s.kind === 'TRANSFER' ? 'wallet pengirim' : s.kind || 'pengirim';
            return `<div class="kv-row"><span>${who}</span><a class="link mono" style="font-size:11px" href="${addrExt(s.addr)}" target="_blank" rel="noopener">${s.addr.slice(0, 10)}…</a></div>`;
          }).join('');
          return `<div style="margin-top:10px;padding:9px 10px;background:var(--panel,#111a2e);border:1px solid var(--line,#1e2a44);border-radius:8px">
            <div class="t3" style="letter-spacing:.5px">INDUKAN — ASAL TOKEN</div>
            <div class="t2" style="font-size:11.5px;margin:2px 0 4px">${esc(o.label || o.kind)}</div>
            ${rows || '<div class="t3">mint langsung dari 0x0</div>'}</div>`;
        })() : ''}
        <div class="node-acts">
          <button class="btn btn-ghost btn-sm" data-act="open" title="Open page">${icon('external', 'i-sm')}Open</button>
          <button class="btn btn-ghost btn-sm" data-copy="${sel.addr}" title="Copy">${icon('copy', 'i-sm')}</button>
          <button class="btn btn-ghost btn-sm" data-eye="${sel.id}" title="Hide">${icon('eye', 'i-sm')}Hide</button>
          ${sel.kind !== 'bundle' && sel.kind !== 'funder' ? `<button class="btn btn-primary btn-sm" data-act="expand">+ Expand</button>` : `<button class="btn btn-primary btn-sm" data-act="expand">+ Map entity</button>`}
        </div></div>`;
    }
    el.innerHTML = `<div class="panel-h" style="min-height:50px"><button class="al-eye" data-act="hide-right" title="Sembunyikan address list">${icon('x', 'i-sm')}</button><span class="panel-title">Address list</span>
        <span class="end"><button class="fchip ${st.grouped ? '' : 'is-on'}" data-act="group" style="--c:var(--c-cluster);height:24px">${st.grouped ? 'Ungroup clusters' : 'Group clusters'}</button></span></div>
      ${card}
      <div class="al-search"><label class="ex-search">${icon('search')}<input id="al-q" placeholder="Search addresses" value="${esc(st.listQ)}" autocomplete="off" spellcheck="false"></label><span class="micro">${nf(wallets.length)}</span></div>
      <div class="scroll al-list">${list || '<p class="t3" style="padding:16px">No wallet matches.</p>'}</div>`;
  }

  /* ---------- tooltip ---------- */
  function showTip(n, x, y) {
    const tip = $('#tip');
    if (!n) { tip.hidden = true; return; }
    const lines = [];
    if (n.kind === 'wallet' || n.kind === 'entity') {
      const nm = walletName(n.ref);
      lines.push(`<div class="addr" style="font-size:12px">${short(n.addr, 8, 6)}</div>`);
      if (nm) lines.push(`<div class="t2">${esc(nm)}</div>`);
      lines.push(`<div>Volume est. <b>${usd(n.vol)}</b></div>`, `<div>Net <span class="${n.net >= 0 ? 'pos' : 'neg'}">${usd(n.net, true)}</span> · ${n.swaps} swaps</div>`);
      if (n.cluster != null) lines.push(`<div style="color:${n.clusterColor}">Cluster ${n.cluster + 1}</div>`);
    } else if (n.kind === 'token') lines.push(`<div><b>${esc(n.label)}</b> <span class="t3">Uniswap pool</span></div>`, `<div>${n.traders} traders · ${usd(n.vol)} est.</div>`);
    else if (n.kind === 'group') {
      lines.push(`<div><b>${esc(n.label)}</b></div>`, `<div class="t3">Grup wallet receh (bukan insider)</div>`);
      lines.push(`<div>Berisi <b>${(n.members || []).length}</b> wallet · vol est. <b>${usd(n.vol || 0)}</b> — klik untuk daftar</div>`);
    }
    else {
      const e = S.entities[n.ref];
      lines.push(`<div><b>${esc(n.label)}</b></div>`, `<div class="t3">${n.kind === 'funder' ? 'Funding source' : 'Bundle transaction'}</div>`);
      if (e) lines.push(`<div>${e.members.length} wallets</div>`);
    }
    lines.push(`<div class="t3" style="margin-top:4px">click select · drag to pin · double-click open</div>`);
    tip.innerHTML = lines.join(''); tip.hidden = false;
    tip.style.left = Math.min(x + 16, root.clientWidth - tip.offsetWidth - 10) + 'px';
    tip.style.top = Math.min(y + 16, root.clientHeight - tip.offsetHeight - 10) + 'px';
  }

  function openNode(n) {
    if (n.kind === 'wallet' || n.kind === 'entity') location.hash = walletHref(n.ref);
    else if (n.kind === 'token') location.hash = tokenHref(n.ref);
    else { const e = S.entities[n.ref]; window.open(e.kind === 'cluster' ? addrExt(e.center) : txHref(e.center), '_blank', 'noopener'); }
  }

  /* ---------- timeline brush ---------- */
  function drawTimeline() {
    const el = $('#time'), m = S.meta;
    const ids = new Set(scope.nodes.filter(n => n.kind === 'wallet' || n.kind === 'entity').map(n => n.ref));
    const days = bucketDays(S.all.filter(r => ids.has(r[0])), m.swap_from, m.swap_to, 2, 3, 4);
    const W = Math.max(300, el.clientWidth - 24), H = 54, slot = W / days.length;
    const peak = Math.max(1, ...days.map(d => d.nb + d.ns));
    const selA = st.range ? Math.round((st.range[0] - days[0].t) / 86400) : -1, selB = st.range ? Math.round((st.range[1] - days[0].t) / 86400) : -1;
    const ticks = days.map((d, j) => [d, j]).filter(([, j]) => j % Math.max(1, Math.ceil(days.length / 16)) === 0);
    el.innerHTML = `<div class="time-head"><span class="micro">Timeline · ${st.range ? 'drag to change range · double-click to reset' : 'drag across days to filter the map'}</span></div>
      <svg id="tsvg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
        ${st.range ? `<rect x="${selA * slot}" y="0" width="${(selB - selA) * slot}" height="38" fill="rgba(30,111,241,.16)" stroke="rgba(76,141,255,.6)"/>` : ''}
        <line x1="0" x2="${W}" y1="38" y2="38" stroke="#222834"/>
        ${days.map((d, j) => { const n = d.nb + d.ns, h = n ? Math.max(2, n / peak * 32) : 0, inR = !st.range || (j >= selA && j < selB); return h ? `<rect x="${j * slot + slot * .14}" y="${38 - h}" width="${Math.max(1, slot * .72)}" height="${h}" rx="1" fill="${inR ? '#1E6FF1' : '#1B2A44'}"/>` : ''; }).join('')}
        ${ticks.map(([d, j]) => `<text x="${j * slot + slot / 2}" y="51" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="9.5" fill="#667085">${date(d.t)}</text>`).join('')}
      </svg>`;
    const svg = el.querySelector('#tsvg');
    let a0 = null;
    const dayAt = e => { const r = svg.getBoundingClientRect(); return Math.max(0, Math.min(days.length - 1, Math.floor((e.clientX - r.left) / r.width * days.length))); };
    svg.onpointerdown = e => { a0 = dayAt(e); svg.setPointerCapture(e.pointerId); };
    svg.onpointerup = e => {
      if (a0 == null) return;
      const b = dayAt(e), lo = Math.min(a0, b), hi = Math.max(a0, b) + 1;
      a0 = null;
      if (hi - lo >= days.length) st.range = null; else st.range = [days[lo].t, days[0].t + hi * 86400];
      rebuild({ refit: false });
    };
    svg.ondblclick = () => { st.range = null; rebuild({ refit: false }); };
  }

  /* ---------- add / search box ---------- */
  const addInput = $('#viz-add'), pop = $('#viz-pop');
  addInput.addEventListener('input', () => {
    const q = addInput.value.trim().toLowerCase();
    if (!q) { pop.hidden = true; return; }
    const items = [];
    S.tokens.forEach((t, k) => { if (items.length < 5 && S.tokAgg.has(k) && ((t[1] || '').toLowerCase().includes(q) || t[0].includes(q))) items.push([`#/visualizer?token=${t[0]}`, `${tokAv(k, 'is-md')}<span>${esc(tokName(k))}</span><span class="end t3 mono" style="font-size:11px">token</span>`]); });
    S.entities.forEach((e, i) => { if (items.length < 9 && (e.title.toLowerCase().includes(q) || e.center.includes(q))) items.push([`#/visualizer?entity=${i}`, `<span class="avatar" style="width:24px;height:24px">${icon(e.kind === 'cluster' ? 'cluster' : 'bundle', 'i-sm')}</span><span>${esc(e.title)}</span><span class="end t3 mono" style="font-size:11px">entity</span>`]); });
    for (let i = 0; i < S.wallets.length && items.length < 14; i++) { const w = S.wallets[i]; if (w[0].includes(q) || w[4].toLowerCase().includes(q)) items.push([`#/visualizer?wallet=${w[0]}`, `<span class="avatar" style="width:24px;height:24px">${icon('wallet', 'i-sm')}</span><span class="addr" style="font-size:12px">${short(w[0], 8, 6)}</span><span class="end t3 mono" style="font-size:11px">wallet</span>`]); }
    pop.innerHTML = items.map(([h, inner]) => `<a class="pop-item" href="${h}">${inner}</a>`).join('') || `<div class="pop-empty">Nothing on Robinhood Chain matches.</div>`;
    pop.hidden = false;
  });
  addInput.addEventListener('blur', () => setTimeout(() => { pop.hidden = true; }, 150));

  /* ---------- events ---------- */
  root.addEventListener('click', e => {
    const t = e.target;
    const eye = t.closest('[data-eye]');
    if (eye) { e.stopPropagation(); const id = eye.dataset.eye; st.hidden.has(id) ? st.hidden.delete(id) : st.hidden.add(id); if (g.sel?.id === id) g.select(null); return applyVisibility(0.3); }
    const ex = e.target.closest('[data-explayer]');
    if (ex) { st.expLayer = st.expLayer === ex.dataset.explayer ? '' : ex.dataset.explayer; return drawLayers(); }
    const rz = e.target.closest('[data-act="resetviz"]');
    if (rz) {
      st.show = { ...DEFAULT_SHOW }; st.colorMode = 'label'; st.limit = 150;
      st.hidden.clear(); st.collapsed.clear(); st.range = null; st.grouped = true;
      st.listQ = ''; st.page = 0; st.expLayer = ''; st.hideLeft = false; st.hideRight = false;
      g.setPaused(false); g.userMoved = false;
      persist(); rebuild(); applyVisibility(0.5);
      g.userMoved = false; g.fit();
      syncPanels();
      toast('Visualizer kembali ke default');
      return;
    }
    const fsb = e.target.closest('[data-act="fs"]');
    if (fsb) {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen?.();
      return;
    }
    const hl = e.target.closest('[data-act="hide-left"]');
    if (hl) { st.hideLeft = true; syncPanels(); return; }
    const hr = e.target.closest('[data-act="hide-right"]');
    if (hr) { st.hideRight = true; syncPanels(); return; }
    const sl = e.target.closest('[data-act="show-left"]');
    if (sl) { st.hideLeft = false; syncPanels(); return; }
    const sr = e.target.closest('[data-act="show-right"]');
    if (sr) { st.hideRight = false; syncPanels(); return; }
    const col = t.closest('[data-collapse]'); if (col) { const c = +col.dataset.collapse; st.collapsed.has(c) ? st.collapsed.delete(c) : st.collapsed.add(c); return drawRight(); }
    const foc = t.closest('[data-focus]');
    if (foc) { const n = graph.nodes.find(x => x.id === foc.dataset.focus); if (n) { g.select(n); g.centerOn(n); } return; }
    const pre = t.closest('[data-preset]');
    const fz = e.target.closest('[data-act="freeze"]');
    if (fz) {
      g.setPaused(!g.paused);
      persist(); g.fit();
      document.querySelectorAll('[data-act="freeze"]').forEach(b => b.innerHTML = (g.paused ? icon('bolt', 'i-sm') + ' Resume' : icon('clock', 'i-sm') + ' Freeze'));
      toast(g.paused ? 'Animasi dibekukan — hemat lag' : 'Animasi jalan lagi');
      return;
    }
    if (pre) { const p = PRESETS[pre.dataset.preset]; st.show = { ...p.show }; st.colorMode = p.colorMode; persist(); toast(pre.dataset.preset === 'raw' ? 'Bubblemaps raw: wallets and cluster bonds only' : 'Arkham: entities, pools and flows on'); return applyVisibility(0.5); }
    const md = t.closest('[data-mode]');
    if (md) {
      const m = md.dataset.mode;
      if (m === 'network') location.hash = '#/visualizer';
      else if (m === 'token') { const k = [...S.tokAgg.entries()].sort((a, b) => b[1].wallets.size - a[1].wallets.size)[0][0]; location.hash = `#/visualizer?token=${S.tokens[k][0]}`; }
      else if (m === 'entity') location.hash = '#/visualizer?entity=0';
      else { const n = g.sel && (g.sel.kind === 'wallet' || g.sel.kind === 'entity') ? g.sel : scope.nodes.filter(x => x.kind === 'wallet').sort((a, b) => b.vol - a.vol)[0]; if (n) location.hash = `#/visualizer?wallet=${n.addr}`; }
      return;
    }
    const cp = t.closest('[data-copy]'); if (cp) return copy(cp.dataset.copy);
    const act = t.closest('[data-act]')?.dataset.act;
    if (!act) return;
    if (act === 'fit') g.fit();
    else if (act === 'zin') g.zoomBy(1.25);
    else if (act === 'zout') g.zoomBy(0.8);
    else if (act === 'group') { st.grouped = !st.grouped; return drawRight(); }
    else if (act === 'unpin') { for (const n of g.nodes) { n.pinned = false; n.fx = n.fy = null; } g.sim.reheat(0.2); return drawChips(); }
    else if (act === 'range-clear') { st.range = null; return rebuild(); }
    else if (act === 'toggle-flow') { st.show.flow = !st.show.flow; persist(); return applyVisibility(0); }
    else if (act === 'unhide') { st.hidden.clear(); return applyVisibility(0.3); }
    else if (act === 'open') { if (g.sel) openNode(g.sel); return; }
    else if (act === 'more') {
      if (g.sel && (g.sel.kind === 'wallet' || g.sel.kind === 'entity')) location.hash = walletHref(g.sel.ref);
      else if (g.sel && g.sel.kind === 'token') location.hash = tokenHref(g.sel.ref);
      else if (g.sel && (g.sel.kind === 'group' || g.sel.kind === 'funder' || g.sel.kind === 'bundle')) location.hash = walletHref(S.entities[g.sel.ref].members[0]);
      return;
    }
    else if (act === 'expand') {
      if (g.sel && g.sel.kind === 'wallet') location.hash = `#/visualizer?wallet=${g.sel.addr}`;
      else if (g.sel && g.sel.kind === 'token') location.hash = `#/visualizer?token=${S.tokens[g.sel.ref][0]}`;
      else if (g.sel && (g.sel.kind === 'funder' || g.sel.kind === 'bundle' || g.sel.kind === 'group')) location.hash = `#/visualizer?entity=${g.sel.ref}`;
      return;
    }
  });
  root.addEventListener('change', e => {
    const lay = e.target.closest('[data-layer]');
    if (lay) { st.show[lay.dataset.layer] = lay.checked; persist(); return applyVisibility(0.35); }
    if (e.target.id === 'limit') { st.limit = +e.target.value; persist(); rebuild(); }
  });
  root.addEventListener('input', e => { if (e.target.id === 'al-q') { st.listQ = e.target.value; const pos = e.target.selectionStart; drawRight(); const i = root.querySelector('#al-q'); i.focus(); i.setSelectionRange(pos, pos); } });
  root.addEventListener('dd:change', e => { if (e.detail.id === 'color') { st.colorMode = e.detail.value; persist(); applyVisibility(0); } });

  const zoomEl = $('#zoom');
  const zoomTimer = setInterval(() => { if (!root.isConnected) { clearInterval(zoomTimer); g.destroy(); return; } zoomEl.textContent = Math.round(g.view.k * 100) + '%'; }, 250);
  new ResizeObserver(() => scope && drawTimeline()).observe($('#time'));

  rebuild();
}
