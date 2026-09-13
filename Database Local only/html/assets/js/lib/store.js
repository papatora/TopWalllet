// Dataset store: loads /api/dataset (built from the local DB by server.py) and derives indexes.
import { short } from './fmt.js';

export const S = {};

export async function load() {
  const res = await fetch('/api/dataset', { cache: 'no-store' });
  if (!res.ok) throw new Error(`Dataset request failed (${res.status}). Is server.py running?`);
  init(await res.json());
}

export const tokName = k => S.tokens[k][1] || short(S.tokens[k][0]);
export function walletName(i) {
  const w = S.wallets[i];
  if (w[4]) return w[4];
  const t = S.types[w[1]];
  return t === 'GENERALIST' ? '' : t.startsWith('CLUSTER_MEMBER:') ? 'Cluster ' + t.split('_').pop() : t.replace(/_/g, ' ');
}

/** Per-wallet trading stats over [from, to). USD values < 0 are unpriced and skipped in sums. */
export function stats(ai, from = 0, to = Infinity, onlyTok = null) {
  const per = new Map();
  let nb = 0, ns = 0, bu = 0, so = 0, unp = 0, first = 0, last = 0;
  for (const [k, t, sd, u] of S.swaps[ai] || []) {
    if (t < from || t >= to || (onlyTok != null && k !== onlyTok)) continue;
    let p = per.get(k);
    if (!p) { p = { n: 0, nb: 0, ns: 0, bu: 0, so: 0, fb: null, ls: null }; per.set(k, p); }
    p.n++; first = first || t; last = t;
    if (sd) { ns++; p.ns++; p.ls = t; if (u >= 0) { so += u; p.so += u; } else unp++; }
    else { nb++; p.nb++; if (p.fb == null) p.fb = t; if (u >= 0) { bu += u; p.bu += u; } else unp++; }
  }
  let w = 0, l = 0; const holds = [];
  for (const p of per.values()) {
    if (p.ls == null) continue;
    p.so >= p.bu ? w++ : l++;
    if (p.fb != null && p.ls >= p.fb) holds.push((p.ls - p.fb) / 3600);
  }
  holds.sort((a, b) => a - b);
  const toks = [...per.entries()].sort((a, b) => (b[1].bu + b[1].so) - (a[1].bu + a[1].so));
  return {
    nb, ns, bu, so, net: so - bu, vol: bu + so, swaps: nb + ns, w, l, unp, first, last,
    hold: holds.length ? holds[Math.floor(holds.length / 2)] : null,
    toks: toks.map(e => e[0]), per,
  };
}

function init(d) {
  for (const k of Object.keys(S)) delete S[k];
  Object.assign(S, d);
  S.addrIndex = new Map(d.wallets.map((w, i) => [w[0], i]));
  S.tokIndex = new Map(d.tokens.map((t, i) => [t[0], i]));
  S.active = Object.keys(d.swaps).map(Number);
  S.activeSet = new Set(S.active);
  S.statsAll = new Map(S.active.map(ai => [ai, stats(ai)]));
  S.labelIndex = Object.fromEntries(d.labels.map((l, i) => [l, i]));

  // flat, time-sorted swap list: [walletIdx, tokenIdx, ts, side, usd, tx]
  S.all = [];
  for (const ai of S.active) for (const s of d.swaps[ai]) S.all.push([ai, s[0], s[1], s[2], s[3], s[4]]);
  S.all.sort((a, b) => a[2] - b[2]);

  // per-token trade aggregates
  S.tokAgg = new Map();
  for (const [ai, k, t, sd, u] of S.all) {
    let a = S.tokAgg.get(k);
    if (!a) { a = { wallets: new Set(), nb: 0, ns: 0, bu: 0, so: 0, first: t, last: t }; S.tokAgg.set(k, a); }
    a.wallets.add(ai); a.last = t;
    if (sd) { a.ns++; if (u >= 0) a.so += u; } else { a.nb++; if (u >= 0) a.bu += u; }
  }

  // classification evidence per token
  S.tokFlags = new Map();
  const flag = (k, lab, ai) => {
    let f = S.tokFlags.get(k);
    if (!f) { f = {}; S.tokFlags.set(k, f); }
    (f[lab] ||= new Set()).add(ai);
  };
  for (const [key, e] of Object.entries(d.ev)) {
    const ai = +key;
    for (const s of e.SNIPER?.snipes || []) flag(s.token, 'SNIPER', ai);
    if (e.BUNDLER_SUSPECT) flag(e.BUNDLER_SUSPECT.token, 'BUNDLER_SUSPECT', ai);
    for (const s of e.DEV?.sample || []) flag(s.token, 'DEV', ai);
    for (const k of e.INSIDER?.tokens || []) flag(k, 'INSIDER', ai);
    for (const k of e.AIRDROP_FARMER?.tokens || []) flag(k, 'AIRDROP_FARMER', ai);
  }

  // entity membership
  S.entities = [
    ...d.clusters.map(c => ({ kind: 'cluster', id: c.id, title: 'Cluster ' + c.id.split('_').pop(), center: c.funder, members: c.members, data: c })),
    ...d.bundles.map(b => ({ kind: 'bundle', id: b.tx, title: 'Bundle ' + short(b.tx), center: b.tx, members: b.members, data: b })),
  ];
  S.memberOf = new Map();
  S.entities.forEach((e, ei) => e.members.forEach(i => { if (!S.memberOf.has(i)) S.memberOf.set(i, []); S.memberOf.get(i).push(ei); }));
}
