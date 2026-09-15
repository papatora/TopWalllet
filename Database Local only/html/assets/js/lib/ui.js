// Component renderers — HTML-string builders that map 1:1 to components.css.
import { S, tokName, walletName } from './store.js';
import { esc, short, hue, nf } from './fmt.js';

const SPRITE = '/assets/icons/sprite.svg';
export const icon = (n, cls = '') => `<svg class="i ${cls}" aria-hidden="true"><use href="${SPRITE}#i-${n}"/></svg>`;

export const LABEL = {
  DEV:             { c: 'var(--c-dev)', icon: 'code', desc: 'First buyer within 300 blocks of pool creation, then fast flips.' },
  SNIPER:          { c: 'var(--c-sniper)', icon: 'bolt', desc: 'First buy within 10 blocks of the pool’s first swap.' },
  BUNDLER_SUSPECT: { c: 'var(--c-bundler)', icon: 'bundle', desc: 'Bought in the same tx as 5+ other wallets in the pool’s first block.' },
  INSIDER:         { c: 'var(--c-insider)', icon: 'eye', desc: 'Holds and sells a token it never bought after pool open.' },
  AIRDROP_FARMER:  { c: 'var(--c-airdrop)', icon: 'gift', desc: '100% incoming transfers, zero buy swaps.' },
  CT_ATTRIBUTED:   { c: 'var(--c-ct)', icon: 'at', desc: 'Linked to a named crypto-Twitter account.' },
  MEV_BOT:         { c: 'var(--c-mev)', icon: 'bot', desc: 'Median hold ≤10 min across 30+ round trips.' },
  SMART_TRACKER:   { c: 'var(--c-smart)', icon: 'star', desc: 'Passed verifier R1–R3 and the consistency bar.' },
  CLUSTER:         { c: 'var(--c-cluster)', icon: 'cluster', desc: 'Shares a first-funding source with 3+ other wallets.' },
  GENERALIST:      { c: 'var(--c-generalist)', icon: 'wallet', desc: 'No taxonomy signal matched.' },
  PHISHING_TARGET: { c: 'var(--c-phishing)', icon: 'gift', desc: 'Received tokens from a mass-spreader (>=20 wallets / <=100 blocks) - airdrop/scam campaign target.' },
  TRADER_COVERAGE_GAP: { c: 'var(--c-gap)', icon: 'refresh', desc: 'Former insider label overturned on-chain - the wallet really bought; awaiting re-enrichment.' },
  BOT:             { c: 'var(--c-bot)', icon: 'bot', desc: 'Machine cadence: constant multi-second swaps across many random tokens.' },
  SNIPER_BOT:      { c: 'var(--c-bot)', icon: 'bolt', desc: 'Bot that specializes in sniping MANY fresh tokens at the earliest blocks.' },
  WHALE:           { c: 'var(--c-whale)', icon: 'trophy', desc: 'Organic whale: est. net PnL >=$100K with NO airdrop/insider/cluster linkage.' },
  WHALE_SUS:       { c: 'var(--c-whalesus)', icon: 'eye', desc: 'High est. PnL but linked to airdrop/insider/cluster - wealth may come from allocations.' },
};
export const labelMeta = n => LABEL[n?.startsWith('CLUSTER_MEMBER') ? 'CLUSTER' : n] || LABEL.GENERALIST;
export const pretty = n => n?.startsWith('CLUSTER_MEMBER:') ? 'CLUSTER ' + n.split('_').pop() : String(n).replace(/_/g, ' ');
export const chip = (n, text) => `<span class="chip" style="--c:${labelMeta(n).c}">${esc(text ?? pretty(n))}</span>`;

export function tokAv(k, size = '') {
  const t = S.tokens[k];
  const txt = (t[1] || t[0].slice(2)).replace(/[^a-z0-9]/gi, '').slice(0, 2) || '??';
  return `<span class="tok ${size}" style="--h:${hue(t[0])}" title="${esc(tokName(k))}">${esc(txt)}</span>`;
}
export function tokStack(ks, max = 3) {
  const extra = ks.length - max;
  return `<span class="tok-stack">${ks.slice(0, max).map(k => tokAv(k)).join('')}${extra > 0 ? `<span class="tok tok-more">+${extra}</span>` : ''}</span>`;
}
export const rank = r => `<span class="rank ${r <= 3 ? 'is-' + r : ''}">${r}</span>`;
export const hexBadge = (n, col) => `<svg class="hex" viewBox="0 0 38 38" aria-label="Rank ${n}"><path d="M19 2.5 33.3 10.75v16.5L19 35.5 4.7 27.25v-16.5z" fill="rgba(7,8,12,.35)" stroke="${col}" stroke-width="2" stroke-linejoin="round"/><text x="19" y="24" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-weight="600" font-size="14" fill="${col}">${n}</text></svg>`;

export const walletHref = i => `#/address/${S.wallets[i][0]}`;
export const tokenHref = k => `#/token/${S.tokens[k][0]}`;
export const txHref = h => `${S.meta.explorer}/tx/${h}`;
export const addrExt = a => `${S.meta.explorer}/address/${a}`;
export const extLink = (href, text) => `<a class="link" href="${href}" target="_blank" rel="noopener">${text}</a>`;

export function whoCell(i, { full = true, sub = true } = {}) {
  const w = S.wallets[i], nm = walletName(i);
  return `<div class="who"><span class="addr">${full ? w[0] : short(w[0])}</span>${sub && nm ? chip(w[4] ? 'CT_ATTRIBUTED' : S.types[w[1]], nm) : ''}</div>`;
}

/** Sortable header. cols: [{k,label,rt,sort}] */
export function thead(cols, st) {
  return `<tr>${cols.map(c => {
    const on = c.sort && c.k === st.sort;
    return `<th class="${c.rt ? 'rt' : ''} ${c.sort ? 'is-sort' : ''} ${on ? 'is-on' : ''}" ${c.sort ? `data-sort="${c.k}"` : ''}>${c.label}${c.sort ? `<span class="sort">${on && st.dir === 1 ? '▲' : '▼'}</span>` : ''}</th>`;
  }).join('')}</tr>`;
}
export function pager(total, st) {
  const pages = Math.max(1, Math.ceil(total / st.per));
  st.page = Math.min(st.page, pages - 1);
  const a = total ? st.page * st.per + 1 : 0, b = Math.min(total, (st.page + 1) * st.per);
  return `<div class="pager"><span>${nf(a)}–${nf(b)} of ${nf(total)}</span><span class="end">
    <button class="btn btn-ghost btn-sm" data-page="0" ${st.page ? '' : 'disabled'}>First</button>
    <button class="btn btn-ghost btn-sm" data-page="${st.page - 1}" ${st.page ? '' : 'disabled'}>${icon('chevron-left', 'i-sm')}</button>
    <span class="t3" style="padding:0 6px">${st.page + 1} / ${pages}</span>
    <button class="btn btn-ghost btn-sm" data-page="${st.page + 1}" ${st.page < pages - 1 ? '' : 'disabled'}>${icon('chevron-right', 'i-sm')}</button></span></div>`;
}
/** Boxed dropdown. Emits `dd:change` {id,value} from the root on select. */
export function dropdown(id, ico, options, value) {
  const cur = options.find(o => o.v === value) || options[0];
  return `<div class="dd" data-dd="${id}"><button class="dd-btn" data-dd-toggle aria-haspopup="listbox">${ico ? icon(ico) : ''}${esc(cur.l)}${icon('chevron-down', 'chev')}</button>
    <div class="pop" hidden role="listbox">${options.map(o => `<button class="pop-item ${o.v === value ? 'is-active' : ''}" data-dd-value="${esc(o.v)}">${esc(o.l)}</button>`).join('')}</div></div>`;
}
export const emptyRow = (cols, msg) => `<tr class="empty"><td colspan="${cols}">${esc(msg)}</td></tr>`;

let toastTimer;
export function toast(msg) {
  let t = document.querySelector('.toast');
  if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.append(t); }
  t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 1700);
}
export function copy(text) {
  navigator.clipboard?.writeText(text).then(() => toast('Copied to clipboard'), () => toast('Clipboard blocked by the browser'));
}
