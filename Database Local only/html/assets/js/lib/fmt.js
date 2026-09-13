// Formatting helpers. All times are UTC.
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const short = (a, n = 6, m = 4) => a ? `${a.slice(0, n)}…${a.slice(-m)}` : '';
export const nf = n => (n ?? 0).toLocaleString('en-US');

export function usd(n, signed = false) {
  if (n == null || Number.isNaN(n)) return '—';
  const a = Math.abs(n), s = n < 0 ? '-' : (signed && n > 0 ? '+' : '');
  const v = a >= 1e9 ? (a / 1e9).toFixed(2) + 'B' : a >= 1e6 ? (a / 1e6).toFixed(2) + 'M' : a >= 1e3 ? (a / 1e3).toFixed(2) + 'K' : a.toFixed(2);
  return `${s}$${v}`;
}
export function price(p) {
  if (p == null) return '—';
  if (p >= 1) return '$' + p.toLocaleString('en-US', { maximumFractionDigits: 2 });
  if (p === 0) return '$0';
  const z = Math.floor(-Math.log10(p));
  if (z >= 4) { const d = (p * 10 ** (z + 3)).toFixed(0); return `$0.0<sub>${z}</sub>${d}`; }
  return '$' + p.toPrecision(4);
}
export function dur(h) {
  if (h == null) return '—';
  const s = h * 3600;
  return s < 60 ? Math.max(1, Math.round(s)) + 's' : s < 3600 ? Math.round(s / 60) + 'm' : h < 48 ? Math.round(h) + 'h' : Math.round(h / 24) + 'd';
}
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const p2 = x => String(x).padStart(2, '0');
export function date(t, withTime = false) {
  const d = new Date(t * 1000);
  return `${MON[d.getUTCMonth()]} ${p2(d.getUTCDate())}` + (withTime ? ` ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}` : '');
}
export function ago(t, ref) {
  const s = Math.max(0, ref - t);
  return s < 3600 ? Math.round(s / 60) + 'm ago' : s < 86400 ? Math.round(s / 3600) + 'h ago' : Math.round(s / 86400) + 'd ago';
}
export const pct = (a, b) => b ? (a / b * 100).toFixed(a / b < 0.01 ? 2 : 1) + '%' : '0%';
export function hue(s) { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }
