// Human-readable classification evidence blocks.
import { S, tokName } from './store.js';
import { esc, nf, usd } from './fmt.js';
import { icon, chip, labelMeta, pretty, tokenHref, txHref, addrExt } from './ui.js';

const row = (k, v) => `<div class="kv-row"><span>${k}</span><span>${v}</span></div>`;
const tx = h => `<a class="link" href="${txHref(h)}" target="_blank" rel="noopener">${h.slice(0, 10)}…</a>`;
const tok = k => `<a class="link" href="${tokenHref(k)}">${esc(tokName(k))}</a>`;
const addrL = a => `<a class="link mono" href="${addrExt(a)}" target="_blank" rel="noopener">${a.slice(0, 10)}…</a>`;
const spreadTxt = sp => sp && sp.max_recipients ? `${sp.max_recipients} wallet/${'≤'}100 blok` : '';
const entLink = id => { const i = S.entities.findIndex(e => e.id === id); return i < 0 ? '' : `<div class="kv-row"><span></span><span><a class="link" href="#/visualizer?entity=${i}">${icon('graph', 'i-sm').replace('class="i', 'style="display:inline;vertical-align:-2px;margin-right:5px" class="i')}Open in visualizer</a></span></div>`; };

export function evidenceBlocks(i) {
  const w = S.wallets[i], e = S.ev[i] || {};
  const out = w[2].map((li, j) => {
    const L = S.labels[li], d = e[L], lm = labelMeta(L);
    let body = '';
    if (!d) body = L === 'GENERALIST' ? row('Signal', 'No taxonomy signal matched') : '';
    else if (L === 'SNIPER') body = row('Snipes', d.snipe_count) + (d.snipes || []).slice(0, 6).map(s => row(`${tok(s.token)} · +${s.delta_blocks} blk`, tx(s.tx_hash))).join('');
    else if (L === 'BUNDLER_SUSPECT') body = row('Token', tok(d.token)) + row('Block', nf(d.block)) + row('Wallets in same tx', d.distinct_wallets) + row('Transaction', tx(d.tx_hash)) + entLink(d.tx_hash);
    else if (L === 'DEV') body = row('First buyer ≤300 blocks', d.first_buyer_tokens_le_300_blocks) + row('Fast flips', d.fast_flips) + (d.sample || []).slice(0, 5).map(s => row(tok(s.token), `+${s.delta_blocks} blocks`)).join('');
    else if (L === 'INSIDER') {
      if (d.kind === 'MINT_ALLOCATION') {
        body = row('Bukti on-chain', '<b>PROVEN</b> — mint langsung dari 0x0, tanpa Swap log')
          + row('Jumlah', `${nf(d.mint?.amount || 0)} unit token`)
          + (d.mint?.blocks || []).slice(0, 3).map(b => row(`block ${nf(b)}`, '')).join('')
          + row('Tokens', (d.tokens || []).map(tok).join(', '));
      } else if (d.kind === 'CONFIRMED_INSIDER') {
        const lines = Object.entries(d.senders || {}).map(([sa, si]) =>
          row(addrL(sa), `${(si || {}).kind === 'MASS_SPREAD' ? 'mass-spreader (' + spreadTxt((si || {}).spread) + ')' : (si || {}).kind === 'FUNDER' ? 'funder cluster' : 'transfer personal'}`)).join('');
        body = row('Bukti on-chain', '<b>PROVEN</b> — terima transfer murni, tanpa Swap log di tx')
          + (lines ? `<div class="kv-row"><span>Indukan (pengirim)</span><span></span></div>` + lines : '')
          + row('Tokens', (d.tokens || []).map(tok).join(', '));
      } else {
        body = row('Tokens', (d.tokens || []).map(tok).join(', ')) + row('Sells without a buy', d.sell_count ?? '')
          + (d.sample_sells || []).slice(0, 4).map(s => row(`block ${nf(s.block)}`, tx(s.tx_hash))).join('');
      }
    }
    else if (L === 'AIRDROP_FARMER' || L === 'PHISHING_TARGET') {
      const sps = Object.values(d.senders || {});
      const mx = sps.reduce((m, s) => Math.max(m, (s && s.spread && s.spread.max_recipients) || 0), 0);
      body = (mx ? row('Pola pengirim', `mass-spread: ${mx} wallet dalam <=100 blok`) : '')
        + row('Tokens', (d.tokens || []).map(tok).join(', '))
        + row('Artinya', 'token dikirim bot sebaran — wallet ini target/korban, bukan insider');
    }
    else if (L === 'AIRDROP_FARMER') body = row('Swaps', d.swaps) + row('Tokens', (d.tokens || []).map(tok).join(', ')) + row('Pattern', 'incoming only, zero buys');
    else if (L === 'CT_ATTRIBUTED') body = row('Name', esc(d.name || '—')) + row('X account', d.twitter_username ? `<a class="link" href="https://x.com/${encodeURIComponent(d.twitter_username)}" target="_blank" rel="noopener">@${esc(d.twitter_username)}</a>` : '—') + row('Source', esc(d.source || ''));
    else if (L.startsWith('CLUSTER_MEMBER')) body = row('Funder', `<a class="link" href="${addrExt(d.funder)}" target="_blank" rel="noopener">${d.funder.slice(0, 10)}…</a>`) + row('Members', d.member_count ?? d.funded_wallets ?? '—') + entLink(d.cluster_id);
    else if (L === 'MEV_BOT') body = row('Round trips', d.round_trips) + row('Median hold', d.median_hold_minutes + ' min');
    else if (L === 'SMART_TRACKER') body = row('Composite score', d.composite_score) + row('Rank', '#' + d.rank) + row('Verdict', esc(d.verdict));
    else body = Object.entries(d).map(([k, v]) => row(esc(k), esc(typeof v === 'object' ? JSON.stringify(v) : v))).join('');
    return `<div class="evi"><div class="evi-h">${chip(L)}<span class="end">confidence ${w[3][j].toFixed(2)}</span></div><div class="evi-d">${esc(lm.desc)}</div>${body ? `<div class="evi-b kv">${body}</div>` : ''}</div>`;
  });
  const sc = e._score;
  if (sc) out.push(`<div class="evi"><div class="evi-h"><span class="chip" style="--c:var(--blue-hi)">PIPELINE SCORE</span>${sc.verified ? `<span class="end">verifier ${esc(sc.verified)}</span>` : ''}${sc.tag ? `<span class="end" style="color:var(--green)">on-chain: ${esc(sc.tag)}</span>` : ''}</div>
    <div class="evi-d">Scored by the analyze stage. Realized PnL here is the verified calculation, not the estimate.</div><div class="evi-b kv">
    ${sc.score != null ? row('Composite score', sc.score) : ''}${sc.style ? row('Style', esc(sc.style)) : ''}
    ${sc.realized != null ? row('Realized PnL · verified', `<span class="${sc.realized >= 0 ? 'pos' : 'neg'}">${usd(sc.realized, true)}</span>`) : ''}
    ${sc.unrealized != null ? row('Unrealized', usd(sc.unrealized, true)) : ''}${sc.win_rate != null ? row('Win rate', Math.round(sc.win_rate * 100) + '%') : ''}
    ${sc.group ? row('Scenario', esc(pretty(sc.group))) : ''}${sc.top_rank ? row('Top list rank', '#' + sc.top_rank) : ''}
    ${sc.flags?.length ? row('Risk flags', esc(sc.flags.join(', '))) : ''}</div></div>`);
  return out.join('');
}
