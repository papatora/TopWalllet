// Builds visualizer scopes (network / token / entity / wallet) from the store,
// then derives what is drawn from the visibility toggles (Arkham ↔ Bubblemaps).
import { S, stats, tokName, walletName } from './store.js';
import { short } from './fmt.js';

export const CLUSTER_COLORS = ['#F2C94C', '#35C48A', '#E36CB3', '#4C8DFF', '#FF8A4C', '#58B4D1', '#A386FF', '#EF5B63', '#9BD35A', '#2EC4B6', '#F7A1C4', '#C9A76B'];
export const ENTITY_TYPES = ['CEX', 'DEX', 'BRIDGE', 'CONTRACT', 'FUND', 'OTHER'];

const LINK_LEN = { trade: 80, flag: 95, fund: 34, bundle: 34, bond: 10 };
const LINK_K = { trade: 0.06, flag: 0.04, fund: 0.35, bundle: 0.35, bond: 0.6 };

export function buildScope({ mode, ref, limit = 250, from = 0, to = Infinity }) {
  const nodes = new Map(), links = [];
  const known = S.known || {};

  const wallet = i => {
    const id = 'w:' + i;
    if (!nodes.has(id)) {
      const w = S.wallets[i], reg = known[w[0]];
      nodes.set(id, {
        id, kind: reg ? 'entity' : 'wallet', ref: i, addr: w[0],
        label: reg?.name || walletName(i) || short(w[0]), short: short(w[0]),
        etype: reg?.type || null, type: S.types[w[1]], ct: !!w[4], hasSwaps: S.activeSet.has(i), vol: 0, net: 0, swaps: 0,
      });
    }
    return nodes.get(id);
  };
  const token = k => {
    const id = 't:' + k;
    if (!nodes.has(id)) nodes.set(id, { id, kind: 'token', ref: k, addr: S.tokens[k][0], label: tokName(k), short: tokName(k), etype: 'DEX', traders: 0, vol: 0 });
    return nodes.get(id);
  };
  const hub = ei => {
    const e = S.entities[ei], id = (e.kind === 'cluster' ? 'f:' : 'b:') + e.id;
    if (!nodes.has(id)) {
      const reg = known[e.center];
      nodes.set(id, { id, kind: e.kind === 'cluster' ? 'funder' : 'bundle', ref: ei, addr: e.center, label: reg?.name || (e.kind === 'cluster' ? 'Funder ' + short(e.center) : 'Bundle ' + short(e.center)), short: e.title, etype: reg?.type || null });
    }
    return nodes.get(id);
  };
  const tradeLink = (i, k) => {
    const s = stats(i, from, to, k);
    if (!s.swaps) return null;
    const w = wallet(i), t = token(k);
    w.vol += s.vol; w.net += s.net; w.swaps += s.swaps;
    t.traders++; t.vol += s.vol;
    links.push({ s: w, t, kind: 'trade', vol: s.vol, net: s.net, buys: s.nb, sells: s.ns });
    return s;
  };
  const addHubsFor = i => {
    for (const ei of S.memberOf.get(i) || []) links.push({ s: wallet(i), t: hub(ei), kind: S.entities[ei].kind === 'cluster' ? 'fund' : 'bundle' });
  };

  let title = '', sub = '';
  if (mode === 'token') {
    const k = ref, a = S.tokAgg.get(k), f = S.tokFlags.get(k) || {};
    token(k);
    for (const i of a?.wallets || []) tradeLink(i, k);
    for (const [lab, set] of Object.entries(f)) for (const i of set) {
      const has = links.some(l => l.kind === 'trade' && l.s.ref === i && l.t.ref === k);
      if (has) links.find(l => l.kind === 'trade' && l.s.ref === i && l.t.ref === k).flag = lab;
      else links.push({ s: wallet(i), t: token(k), kind: 'flag', flag: lab });
    }
    for (const n of [...nodes.values()]) if (n.kind !== 'token') addHubsFor(n.ref);
    title = tokName(k); sub = 'token map';
  } else if (mode === 'entity') {
    const e = S.entities[ref];
    hub(ref);
    for (const i of e.members) {
      wallet(i); addHubsFor(i);
      const s = S.statsAll.get(i);
      for (const k of (s?.toks || []).slice(0, 5)) tradeLink(i, k);
    }
    if (e.kind === 'bundle') for (const i of e.members) links.push({ s: wallet(i), t: token(e.data.token), kind: 'flag', flag: 'BUNDLER_SUSPECT' });
    title = e.title; sub = e.kind === 'cluster' ? 'funding cluster' : 'same-tx bundle';
  } else if (mode === 'wallet') {
    const me = wallet(ref), s = S.statsAll.get(ref);
    for (const k of s?.toks || []) {
      tradeLink(ref, k);
      const co = [...(S.tokAgg.get(k)?.wallets || [])].filter(j => j !== ref)
        .map(j => [j, stats(j, from, to, k).vol]).sort((x, y) => y[1] - x[1]).slice(0, 20);
      for (const [j] of co) { if (nodes.size > limit) break; tradeLink(j, k); }
    }
    for (const ei of S.memberOf.get(ref) || []) for (const j of S.entities[ei].members) wallet(j);
    for (const n of [...nodes.values()]) if (n.kind !== 'token') addHubsFor(n.ref);
    me.focus = true;
    title = walletName(ref) || short(ref != null ? S.wallets[ref][0] : ''); sub = 'wallet neighborhood';
  } else {
    const ranked = S.active.map(i => [i, stats(i, from, to).vol]).filter(r => r[1] > 0)
      .sort((x, y) => y[1] - x[1]).slice(0, limit);
    const rankedSet = new Set(ranked.map(r => r[0]));
    const inScope = new Set(rankedSet);
    for (const e of S.entities) for (const i of e.members) inScope.add(i);
    const tokCount = new Map(), tokVol = new Map();
    for (const i of rankedSet) {
      for (const k of S.statsAll.get(i)?.toks || []) {
        tokCount.set(k, (tokCount.get(k) || 0) + 1);
        const v = stats(i, from, to, k).vol;
        tokVol.set(k, (tokVol.get(k) || 0) + v);
      }
    }
    // pool nodes dibatasi top by volume — tanpa ini ratusan pool bikin map tidak terbaca
    const POOL_CAP = 20;
    const keepToks = new Set([...tokVol.entries()].sort((a, b) => b[1] - a[1])
      .slice(0, POOL_CAP).map(e => e[0]).filter(k => (tokCount.get(k) || 0) >= 2));
    // anggota cluster/bundle di luar top-N TIDAK dibuang — dilipat ke hub-nya:
    // satu bubble grup sebesar total volume anggota, hover/click = isi anggota
    const foldedInto = new Map();
    for (const e of S.entities) {
      const ei = S.entities.indexOf(e);
      for (const i of e.members) if (!rankedSet.has(i)) foldedInto.set(i, ei);
    }
    for (const i of inScope) {
      const ei = foldedInto.get(i);
      if (ei != null) {
        const h = hub(ei);
        h.foldedCount = (h.foldedCount || 0) + 1;
        h.foldedVol = (h.foldedVol || 0) + (S.statsAll.get(i)?.vol ?? 0);
        continue;
      }
      wallet(i); addHubsFor(i);
      for (const k of S.statsAll.get(i)?.toks || []) if (keepToks.has(k)) tradeLink(i, k);
    }
    title = 'Robinhood network';
    sub = `top ${rankedSet.size} wallets · ${foldedInto.size} folded into hubs · top ${keepToks.size} pools`;
  }

  // de-duplicate links (a wallet can hit the same hub twice via overlapping memberships)
  const seen = new Set();
  const uniq = links.filter(l => { const key = l.s.id + '|' + l.t.id + '|' + l.kind; if (seen.has(key)) return false; seen.add(key); return true; });

  // bubblemaps clusters: connected components over funding/bundle bonds only
  const parent = new Map();
  const find = x => { while (parent.get(x) !== x) { parent.set(x, parent.get(parent.get(x))); x = parent.get(x); } return x; };
  for (const n of nodes.values()) parent.set(n.id, n.id);
  for (const l of uniq) if (l.kind === 'fund' || l.kind === 'bundle') parent.set(find(l.s.id), find(l.t.id));
  const groups = new Map();
  for (const n of nodes.values()) if (n.kind === 'wallet' || n.kind === 'entity') { const r = find(n.id); if (!groups.has(r)) groups.set(r, []); groups.get(r).push(n); }
  const clusters = [...groups.entries()].filter(([, m]) => m.length >= 2).sort((a, b) => b[1].length - a[1].length);
  clusters.forEach(([root, members], ci) => {
    const color = CLUSTER_COLORS[ci % CLUSTER_COLORS.length];
    for (const n of nodes.values()) if (find(n.id) === root) { n.cluster = ci; n.clusterColor = color; }
  });

  // sizing
  const all = [...nodes.values()];
  const maxVol = Math.max(1, ...all.filter(n => n.kind === 'wallet' || n.kind === 'entity').map(n => n.vol));
  const maxTr = Math.max(1, ...all.filter(n => n.kind === 'token').map(n => n.traders));
  for (const n of all) {
    if (n.kind === 'wallet' || n.kind === 'entity') n.r = n.vol > 0 ? 7 + 27 * Math.sqrt(n.vol / maxVol) : 6;
    else if (n.kind === 'funder' || n.kind === 'bundle') n.r = 8 + 18 * Math.sqrt((n.foldedVol || 0) / maxVol);
    else if (n.kind === 'token') n.r = 15 + 11 * Math.sqrt(n.traders / maxTr);
    else n.r = 17;
    if (n.focus) n.r = Math.max(n.r, 22);
    n.mass = n.kind === 'wallet' ? 1 : 1.6;
  }
  for (const l of uniq) { l.len = LINK_LEN[l.kind]; l.k = LINK_K[l.kind]; }

  return { nodes: all, links: uniq, clusters: clusters.map(([, m], ci) => ({ ci, color: CLUSTER_COLORS[ci % CLUSTER_COLORS.length], members: m })), title, sub };
}

/** Apply toggles. Hidden hubs collapse into direct wallet↔wallet bonds so clusters still hold together. */
export function visibleGraph(scope, show, hidden) {
  const vis = n => {
    if (hidden.has(n.id)) return false;
    if (n.kind === 'token') return show.dex;
    if (n.kind === 'funder') return show.funders;
    if (n.kind === 'bundle') return show.bundles;
    if (n.kind === 'entity') return show['etype_' + n.etype] !== false;
    if (n.kind === 'wallet' && !n.hasSwaps && !show.labelOnly && !n.focus) return false;
    return true;
  };
  const nodes = scope.nodes.filter(vis), keep = new Set(nodes);
  const links = scope.links.filter(l => keep.has(l.s) && keep.has(l.t) && (show.tradeEdges || (l.kind !== 'trade' && l.kind !== 'flag')));
  const bonds = new Map();
  for (const l of scope.links) {
    if ((l.kind === 'fund' || l.kind === 'bundle') && keep.has(l.s) && !keep.has(l.t) && !hidden.has(l.t.id)) {
      if (!bonds.has(l.t)) bonds.set(l.t, []);
      bonds.get(l.t).push(l.s);
    }
  }
  // star onto the heaviest member: compact blobs instead of long tangled chains
  for (const [, members] of bonds) {
    const core = members.reduce((a, b) => (b.vol > a.vol ? b : a), members[0]);
    for (const m of members) if (m !== core) links.push({ s: core, t: m, kind: 'bond', len: LINK_LEN.bond, k: LINK_K.bond });
  }
  return { nodes, links };
}
