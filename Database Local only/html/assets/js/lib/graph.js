// Canvas renderer + interaction for the visualizer: drag nodes, pan, zoom, hover, select, flow dots.
import { ForceSim } from './force.js';
import { hue } from './fmt.js';

const TAU = Math.PI * 2;
const GLYPH = {
  cluster: new Path2D('M12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6zM4.5 3.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6zM19.5 3.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6zM4.5 17.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6zM19.5 17.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6zM6 6.4l3.8 3.4M18 6.4l-3.8 3.4M6 17.6l3.8-3.4M18 17.6l-3.8-3.4'),
  bundle: new Path2D('M12 3 20 7.5v9L12 21l-8-4.5v-9zM4 7.5 12 12l8-4.5M12 12v9'),
};
const ETYPE_COLOR = { CEX: '#F2C94C', DEX: '#FF4FA3', BRIDGE: '#4C8DFF', CONTRACT: '#7D8698', FUND: '#35C48A', OTHER: '#A386FF' };
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

function rgba(hex, a) {
  const h = hex.replace('#', ''), n = parseInt(h.length === 3 ? h.replace(/./g, c => c + c) : h, 16);
  return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`;
}

export class GraphCanvas {
  constructor(canvas, { onSelect, onHover, onOpen, onPinChange, insets } = {}) {
    this.cv = canvas; this.ctx = canvas.getContext('2d');
    this.cb = { onSelect, onHover, onOpen, onPinChange };
    this.insets = insets || { left: 0, right: 0, top: 0, bottom: 0 };
    this.sim = new ForceSim();
    this.nodes = []; this.links = [];
    this.view = { k: 1, x: 0, y: 0 };
    this.opt = { colorMode: 'cluster', icons: true, labels: true, flow: true, frozen: false };
    this.paused = false;
    this.sel = null; this.hover = null; this.neigh = null;
    const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    this.c = this.readTheme();
    new MutationObserver(() => { this.c = this.readTheme(); this.dirty = true; })
      .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    this.labelColor = t => {
      const key = t?.startsWith('CLUSTER_MEMBER') ? 'cluster' : ({ DEV: 'dev', SNIPER: 'sniper', BUNDLER_SUSPECT: 'bundler', INSIDER: 'insider', AIRDROP_FARMER: 'airdrop', CT_ATTRIBUTED: 'ct', MEV_BOT: 'mev', SMART_TRACKER: 'smart', BOT: 'bot', SNIPER_BOT: 'bot', WHALE: 'whale', WHALE_SUS: 'whalesus', PHISHING_TARGET: 'phishing', TRADER_COVERAGE_GAP: 'gap' }[t] || 'generalist');
      return css('--c-' + key);
    };
    this.resize = this.resize.bind(this);
    this.ro = new ResizeObserver(this.resize); this.ro.observe(canvas.parentElement);
    this.bind();
    this.resize();
    this.raf = requestAnimationFrame(this.frame.bind(this));
  }

  destroy() { cancelAnimationFrame(this.raf); this.ro.disconnect(); this.dead = true; }

  setGraph(nodes, links, { reheat = 0.8 } = {}) {
    this.nodes = nodes; this.links = links;
    this.sim.set(nodes, links);
    if (reheat) this.sim.reheat(reheat);
    this.maxVol = Math.max(1, ...links.filter(l => l.vol).map(l => l.vol));
    if (this.sel && !nodes.includes(this.sel)) this.select(null);
    this.computeNeigh(); this.dirty = true;
  }

  resize() {
    const r = this.cv.parentElement.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    this.w = r.width; this.h = r.height;
    this.cv.width = Math.round(r.width * dpr); this.cv.height = Math.round(r.height * dpr);
    this.cv.style.width = r.width + 'px'; this.cv.style.height = r.height + 'px';
    this.dpr = dpr;
    if (!this.fitted) { this.view.x = this.w / 2; this.view.y = this.h / 2; }
    this.dirty = true;
  }

  toWorld(sx, sy) { return [(sx - this.view.x) / this.view.k, (sy - this.view.y) / this.view.k]; }

  fit(pad = 60) {
    if (!this.nodes.length) return;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const n of this.nodes) { x0 = Math.min(x0, n.x - n.r); y0 = Math.min(y0, n.y - n.r); x1 = Math.max(x1, n.x + n.r); y1 = Math.max(y1, n.y + n.r + 14); }
    const { left, right, top, bottom } = this.insets;
    const aw = this.w - left - right - pad * 2, ah = this.h - top - bottom - pad * 2;
    const k = Math.max(0.15, Math.min(2.2, Math.min(aw / (x1 - x0 || 1), ah / (y1 - y0 || 1))));
    this.view.k = k;
    this.view.x = left + pad + aw / 2 - (x0 + x1) / 2 * k;
    this.view.y = top + pad + ah / 2 - (y0 + y1) / 2 * k;
    this.fitted = true; this.dirty = true;
  }
  zoomBy(f, sx = this.w / 2, sy = this.h / 2) {
    this.userMoved = true;
    const k = Math.max(0.12, Math.min(5, this.view.k * f)), [wx, wy] = this.toWorld(sx, sy);
    this.view.k = k; this.view.x = sx - wx * k; this.view.y = sy - wy * k; this.dirty = true;
  }
  centerOn(n) {
    const { left, right, top, bottom } = this.insets;
    this.view.x = left + (this.w - left - right) / 2 - n.x * this.view.k;
    this.view.y = top + (this.h - top - bottom) / 2 - n.y * this.view.k;
    this.dirty = true;
  }
  select(n) { this.sel = n; this.computeNeigh(); this.dirty = true; this.cb.onSelect?.(n); }
  unpinAll() { for (const n of this.nodes) { n.fx = n.fy = null; n.pinned = false; } this.sim.reheat(0.5); this.cb.onPinChange?.(0); }
  pinnedCount() { return this.nodes.filter(n => n.pinned).length; }

  computeNeigh() {
    const focus = this.hover || this.sel;
    if (!focus) { this.neigh = null; return; }
    const s = new Set([focus]);
    for (const l of this.links) { if (l.s === focus) s.add(l.t); if (l.t === focus) s.add(l.s); }
    this.neigh = s;
  }

  hit(sx, sy) {
    const [wx, wy] = this.toWorld(sx, sy);
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const n = this.nodes[i];
      if (Math.hypot(n.x - wx, n.y - wy) <= n.r + 3 / this.view.k) return n;
    }
    return null;
  }

  bind() {
    const cv = this.cv;
    let drag = null, pan = null, down = null;
    const pos = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    cv.addEventListener('pointerdown', e => {
      const [sx, sy] = pos(e), n = this.hit(sx, sy);
      cv.setPointerCapture(e.pointerId);
      down = { sx, sy, n, moved: false };
      if (n) { drag = n; n.fx = n.x; n.fy = n.y; this.sim.alphaTarget = 0.25; this.sim.reheat(0.3); }
      else pan = { x: this.view.x - sx, y: this.view.y - sy };
      cv.style.cursor = n ? 'grabbing' : 'move';
      this.userMoved = true;
    });
    cv.addEventListener('pointermove', e => {
      const [sx, sy] = pos(e);
      if (down && Math.hypot(sx - down.sx, sy - down.sy) > 4) down.moved = true;
      if (drag) { const [wx, wy] = this.toWorld(sx, sy); drag.fx = wx; drag.fy = wy; this.dirty = true; return; }
      if (pan) { this.view.x = pan.x + sx; this.view.y = pan.y + sy; this.dirty = true; return; }
      const n = this.hit(sx, sy);
      if (n !== this.hover) { this.hover = n; this.computeNeigh(); this.dirty = true; }
      cv.style.cursor = n ? 'pointer' : 'grab';
      this.cb.onHover?.(n, sx, sy);
    });
    const up = e => {
      if (drag) {
        this.sim.alphaTarget = 0;
        if (down?.moved) { drag.pinned = true; this.cb.onPinChange?.(this.pinnedCount()); }
        else if (!drag.pinned) { drag.fx = drag.fy = null; }
      }
      if (down && !down.moved) this.select(down.n);
      drag = pan = down = null;
      cv.style.cursor = 'grab';
    };
    cv.addEventListener('pointerup', up);
    cv.addEventListener('pointercancel', up);
    cv.addEventListener('pointerleave', () => { if (this.hover) { this.hover = null; this.computeNeigh(); this.dirty = true; } this.cb.onHover?.(null); });
    cv.addEventListener('wheel', e => { e.preventDefault(); this.userMoved = true; const [sx, sy] = pos(e); this.zoomBy(Math.exp(-e.deltaY * 0.0015), sx, sy); }, { passive: false });
    cv.addEventListener('dblclick', e => { const [sx, sy] = pos(e), n = this.hit(sx, sy); if (n) this.cb.onOpen?.(n); });
  }

  setPaused(p) { this.paused = !!p; this.dirty = true; }

  frame(t) {
    if (this.dead) return;
    if (this.paused) {
      if (this.dirty) this.draw(t / 1000);   // interaksi masih render, animasi mati
      this.dirty = false;
      this.raf = requestAnimationFrame(this.frame.bind(this));
      return;
    }
    if (this.sim.active && !this.opt.frozen) {
      this.sim.tick(); if (this.sim.alpha > 0.3) this.sim.tick();
      this.dirty = true;
      this.frameN = (this.frameN || 0) + 1;
      if (!this.userMoved && this.frameN % 8 === 0) this.fit();   // follow the layout until the user takes over
    }
    if (this.dirty || this.opt.flow) this.draw(t / 1000);
    this.dirty = false;
    this.raf = requestAnimationFrame(this.frame.bind(this));
  }

  readTheme() {
    return { text: css('--text'), text2: css('--text-2'), text3: css('--text-3'), panel: css('--panel'), sunk: css('--bg-sunk'), green: css('--green'), red: css('--red'), blue: css('--blue-hi'), pink: css('--c-cluster'), amber: css('--c-bundler'), line: css('--line-strong') };
  }

  nodeColor(n) {
    const m = this.opt.colorMode;
    if (n.kind === 'token') return m === 'flow' ? '#5B6B8C' : '#4E5E80'; // pool: beda dari wallet
    if (m === 'label') return this.labelColor(n.type);
    if (m === 'flow') return n.net > 0 ? this.c.green : n.net < 0 ? this.c.red : '#7D8698';
    // cluster mode: kalau semuanya jadi SATU mega-cluster (terhubung pool),
    // jatuh ke warna label — mencegah dinding satu warna.
    const cc = n.clusterColor || null;
    if (cc === '#F2C94C' && this.singleCluster) return this.labelColor(n.type);
    return cc;
  }

  curve(l) {
    const { s, t } = l, mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2, dx = t.x - s.x, dy = t.y - s.y;
    const bend = l.kind === 'bond' ? 0 : 0.12;
    return [s.x, s.y, mx - dy * bend, my + dx * bend, t.x, t.y];
  }

  draw(time) {
    const { ctx, dpr, view, c } = this, focus = this.neigh;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, this.w, this.h);
    ctx.setTransform(dpr * view.k, 0, 0, dpr * view.k, dpr * view.x, dpr * view.y);
    const lw = 1 / view.k;

    // edges
    for (const l of this.links) {
      const on = !focus || (focus.has(l.s) && focus.has(l.t));
      const [x0, y0, cx, cy, x1, y1] = this.curve(l);
      let col, width = 1, alpha = on ? 0.42 : 0.07, dash = null;
      if (l.kind === 'trade') { col = l.net > 0 ? c.red : c.green; width = 0.7 + 2.6 * Math.sqrt((l.vol || 0) / this.maxVol); alpha = on ? (focus ? 0.8 : 0.32) : 0.05; }
      else if (l.kind === 'flag') { col = this.labelColor(l.flag); dash = [4, 4]; alpha = on ? 0.55 : 0.06; }
      else if (l.kind === 'fund') col = l.s.clusterColor && this.opt.colorMode === 'cluster' ? l.s.clusterColor : c.pink;
      else if (l.kind === 'bundle') col = l.s.clusterColor && this.opt.colorMode === 'cluster' ? l.s.clusterColor : c.amber;
      else { col = l.s.clusterColor || '#6E86C9'; alpha = on ? 0.85 : 0.1; width = 1.2; }
      ctx.strokeStyle = rgba(col, alpha); ctx.lineWidth = width * Math.max(lw, 0.6);
      ctx.setLineDash(dash ? dash.map(v => v * lw) : []);
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.quadraticCurveTo(cx, cy, x1, y1); ctx.stroke();
    }
    ctx.setLineDash([]);

    // flow dots — trade: towards the pool when buys dominate, towards the wallet when sells dominate
    if (this.opt.flow) {
      for (const l of this.links) {
        if (!(l.kind === 'trade' || l.kind === 'fund' || l.kind === 'bundle')) continue;
        if (focus && !(focus.has(l.s) && focus.has(l.t))) continue;
        const [x0, y0, cx, cy, x1, y1] = this.curve(l);
        const toHub = l.kind === 'trade' ? l.net <= 0 : false;
        const col = l.kind === 'trade' ? (l.net > 0 ? c.red : c.green) : l.kind === 'fund' ? c.pink : c.amber;
        const count = l.kind === 'trade' ? 1 + Math.min(2, Math.floor(Math.log10(1 + (l.vol || 0)) / 2)) : 1;
        ctx.fillStyle = rgba(col, 0.95);
        for (let d = 0; d < count; d++) {
          let u = ((time * 0.35 + d / count + (l.s.x * 0.001 % 1)) % 1 + 1) % 1;
          if (!toHub) u = 1 - u;
          const a = 1 - u, px = a * a * x0 + 2 * a * u * cx + u * u * x1, py = a * a * y0 + 2 * a * u * cy + u * u * y1;
          ctx.beginPath(); ctx.arc(px, py, 1.9 * Math.max(lw, 0.7), 0, TAU); ctx.fill();
        }
      }
    }

    // nodes
    ctx.textAlign = 'center';
    for (const n of this.nodes) {
      const on = !focus || focus.has(n);
      ctx.globalAlpha = on ? 1 : 0.22;
      if (n.kind === 'wallet') this.drawBubble(n);
      else if (n.kind === 'token') this.drawToken(n);
      else if (n.kind === 'entity') this.drawEntity(n);
      else if (n.kind === 'group') this.drawGroup(n);
      else this.drawHub(n);
      if (n === this.sel || n === this.hover) {
        ctx.strokeStyle = n === this.sel ? '#FFFFFF' : 'rgba(255,255,255,.5)'; ctx.lineWidth = 1.6 * lw;
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r + 4 * lw + 1, 0, TAU); ctx.stroke();
      }
      if (n.pinned && this.opt.icons) { ctx.fillStyle = c.blue; ctx.beginPath(); ctx.arc(n.x - n.r * 0.72, n.y - n.r * 0.72, 2.6 * Math.max(lw, 0.8), 0, TAU); ctx.fill(); }
      const hot = n === this.sel || n === this.hover || n.focus;
      const roomy = n.kind === 'wallet' || n.kind === 'entity' ? n.r * view.k >= 16 : n.kind === 'token' ? n.r * view.k >= 13 : view.k >= 0.95;
      if (this.opt.labels && (hot || (roomy && (!focus || focus.has(n))))) {
        const fs = Math.max(9, Math.min(12, 10.5)) * lw;
        ctx.font = `${n.kind === 'wallet' ? 400 : 500} ${fs}px "IBM Plex Mono", monospace`;
        ctx.fillStyle = n.kind === 'wallet' ? c.text2 : c.text;
        ctx.fillText(n.kind === 'wallet' ? (n.ct ? n.label : n.short) : n.label.length > 22 ? n.label.slice(0, 21) + '…' : n.label, n.x, n.y + n.r + 13 * lw);
      }
    }
    ctx.globalAlpha = 1;
  }

  drawBubble(n) {
    const { ctx, c } = this, lw = 1 / this.view.k, col = this.nodeColor(n);
    const g = ctx.createRadialGradient(n.x - n.r * 0.35, n.y - n.r * 0.35, n.r * 0.1, n.x, n.y, n.r);
    if (col) { g.addColorStop(0, rgba(col, 0.42)); g.addColorStop(1, rgba(col, 0.14)); }
    else { g.addColorStop(0, 'rgba(78,104,170,.42)'); g.addColorStop(1, 'rgba(38,54,98,.30)'); }
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, TAU); ctx.fill();
    ctx.strokeStyle = col ? rgba(col, 0.9) : 'rgba(96,124,196,.55)'; ctx.lineWidth = (col ? 1.5 : 1) * lw; ctx.stroke();
    if (n.focus) { ctx.strokeStyle = '#FFFFFF'; ctx.lineWidth = 2 * lw; ctx.stroke(); }
    if (this.opt.icons) {
      const br = Math.max(2.6 * lw, Math.min(5, n.r * 0.26));
      ctx.fillStyle = n.hasSwaps ? c.green : '#454C5B'; ctx.strokeStyle = c.sunk; ctx.lineWidth = 1.5 * lw;
      ctx.beginPath(); ctx.arc(n.x + n.r * 0.72, n.y + n.r * 0.72, br, 0, TAU); ctx.fill(); ctx.stroke();
      if (n.ct) {
        ctx.fillStyle = c.blue; ctx.beginPath(); ctx.arc(n.x + n.r * 0.72, n.y - n.r * 0.72, Math.max(br, 4 * lw), 0, TAU); ctx.fill();
        ctx.fillStyle = '#fff'; ctx.font = `600 ${Math.max(br, 4 * lw) * 1.3}px "IBM Plex Mono",monospace`; ctx.fillText('@', n.x + n.r * 0.72, n.y - n.r * 0.72 + Math.max(br, 4 * lw) * 0.45);
      }
    }
  }

  drawToken(n) {
    const { ctx, c } = this, lw = 1 / this.view.k, h = hue(n.addr);
    if (!this.opt.icons) { ctx.fillStyle = 'rgba(120,130,150,.18)'; ctx.strokeStyle = 'rgba(160,168,183,.55)'; ctx.lineWidth = lw; ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, TAU); ctx.fill(); ctx.stroke(); }
    else {
      ctx.fillStyle = `hsl(${h} 36% 19%)`; ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, TAU); ctx.fill();
      ctx.strokeStyle = `hsl(${h} 70% 62%)`; ctx.lineWidth = 2 * lw; ctx.stroke();
      const bx = n.x + n.r * 0.74, by = n.y - n.r * 0.74, br = Math.max(5 * lw, n.r * 0.3);
      ctx.fillStyle = '#FF4FA3'; ctx.beginPath(); ctx.arc(bx, by, br, 0, TAU); ctx.fill();
      ctx.strokeStyle = c.sunk; ctx.lineWidth = 1.5 * lw; ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.font = `700 ${br * 1.15}px Inter, sans-serif`; ctx.fillText('U', bx, by + br * 0.4);
    }
    ctx.fillStyle = this.opt.icons ? `hsl(${h} 80% 78%)` : c.text2;
    ctx.font = `600 ${Math.max(8, n.r * 0.55)}px "IBM Plex Mono",monospace`;
    ctx.fillText(n.label.replace(/[^a-z0-9]/gi, '').slice(0, 3).toUpperCase() || '?', n.x, n.y + n.r * 0.2);
  }

  drawGroup(n) {
    const { ctx, c } = this, lw = 1 / this.view.k;
    ctx.fillStyle = c.panel; ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, TAU); ctx.fill();
    ctx.setLineDash([4 * lw, 3 * lw]);
    ctx.strokeStyle = 'rgba(140,152,184,.9)'; ctx.lineWidth = 1.6 * lw; ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = c.text2; ctx.font = `600 ${Math.max(7, n.r * 0.42)}px "IBM Plex Mono",monospace`;
    ctx.fillText('×' + (n.members ? n.members.length : n.foldedCount || '?'), n.x, n.y + n.r * 0.18);
    ctx.fillStyle = c.text3; ctx.font = `400 ${Math.max(7, n.r * 0.3)}px "IBM Plex Mono",monospace`;
    ctx.fillText('grup', n.x, n.y + n.r * 0.5);
  }

  drawHub(n) {
    const { ctx, c } = this, lw = 1 / this.view.k, col = n.kind === 'funder' ? c.pink : c.amber;
    ctx.fillStyle = c.panel; ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, TAU); ctx.fill();
    ctx.strokeStyle = col; ctx.lineWidth = 2 * lw; ctx.stroke();
    if (this.opt.icons) {
      const s = n.r * 1.05 / 24;
      ctx.save(); ctx.translate(n.x - 12 * s, n.y - 12 * s); ctx.scale(s, s);
      ctx.strokeStyle = col; ctx.lineWidth = 1.9; ctx.lineJoin = 'round'; ctx.stroke(n.kind === 'funder' ? GLYPH.cluster : GLYPH.bundle);
      ctx.restore();
    }
  }

  drawEntity(n) {
    const { ctx, c } = this, lw = 1 / this.view.k, r = Math.max(n.r, 14), col = ETYPE_COLOR[n.etype] || ETYPE_COLOR.OTHER;
    ctx.fillStyle = this.opt.icons ? '#F4F6FA' : 'rgba(120,130,150,.2)'; ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, TAU); ctx.fill();
    ctx.strokeStyle = col; ctx.lineWidth = 2 * lw; ctx.stroke();
    ctx.fillStyle = this.opt.icons ? '#07080C' : c.text2; ctx.font = `700 ${r * 0.62}px Inter, sans-serif`;
    ctx.fillText(n.label.replace(/[^a-z0-9]/gi, '').slice(0, 2).toUpperCase(), n.x, n.y + r * 0.22);
    if (this.opt.icons) { ctx.fillStyle = col; ctx.beginPath(); ctx.arc(n.x + r * 0.74, n.y + r * 0.74, Math.max(3.5 * lw, r * 0.22), 0, TAU); ctx.fill(); }
  }
}
