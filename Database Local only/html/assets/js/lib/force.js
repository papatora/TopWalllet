// Small force-directed simulation: many-body repulsion, link springs, collision, centering.
// Nodes: {x,y,vx,vy,r, fx?,fy? (pinned)}. Links: {s:node, t:node, len?, k?}.
export class ForceSim {
  constructor(nodes = [], links = []) {
    this.alpha = 1; this.alphaMin = 0.004; this.alphaDecay = 0.035; this.alphaTarget = 0;
    this.velocityDecay = 0.55;
    this.charge = 1500; this.gravity = 0.03; this.linkK = 0.07;
    this.set(nodes, links);
  }
  set(nodes, links) {
    this.nodes = nodes; this.links = links;
    const n = nodes.length;
    nodes.forEach((d, i) => {
      if (d.x == null || Number.isNaN(d.x)) {
        const a = i * 2.39996, rad = 14 * Math.sqrt(i + 0.5);   // phyllotaxis seed = stable, even start
        d.x = rad * Math.cos(a); d.y = rad * Math.sin(a);
      }
      d.vx ||= 0; d.vy ||= 0;
    });
    this.degree = new Map();
    for (const l of links) { this.degree.set(l.s, (this.degree.get(l.s) || 0) + 1); this.degree.set(l.t, (this.degree.get(l.t) || 0) + 1); }
    this.n = n;
    this.chargeScale = Math.sqrt(80 / Math.max(80, n)); // big scopes pack tighter, like a bubble map
  }
  reheat(a = 0.6) { this.alpha = Math.max(this.alpha, a); }
  get active() { return this.alpha > this.alphaMin || this.alphaTarget > 0; }

  tick() {
    const { nodes, links } = this, a = this.alpha;
    // springs
    for (const l of links) {
      const s = l.s, t = l.t;
      let dx = t.x - s.x, dy = t.y - s.y, d = Math.hypot(dx, dy) || 1e-6;
      const target = (l.len ?? 60) + s.r + t.r;
      const f = (d - target) / d * a * (l.k ?? this.linkK);
      dx *= f; dy *= f;
      // the lower-degree end moves more (a leaf follows its hub, not the other way round)
      const ds = this.degree.get(s), dt = this.degree.get(t), bs = ds / (ds + dt);
      t.vx -= dx * bs; t.vy -= dy * bs;
      s.vx += dx * (1 - bs); s.vy += dy * (1 - bs);
    }
    // repulsion + collision (O(n²) — fine for the few hundred nodes a scope holds)
    const ch = this.charge * this.chargeScale * a;
    for (let i = 0; i < nodes.length; i++) {
      const p = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const q = nodes[j];
        let dx = q.x - p.x, dy = q.y - p.y, d2 = dx * dx + dy * dy;
        if (d2 < 1e-4) { dx = (Math.random() - .5) * .1; dy = (Math.random() - .5) * .1; d2 = dx * dx + dy * dy; }
        const d = Math.sqrt(d2);
        if (d2 < 360000) {
          const f = ch * (p.mass || 1) * (q.mass || 1) / d2;
          const fx = dx / d * f, fy = dy / d * f;
          p.vx -= fx; p.vy -= fy; q.vx += fx; q.vy += fy;
        }
        const min = p.r + q.r + 3;
        if (d < min) {
          const push = (min - d) / d * 0.5;
          const px = dx * push, py = dy * push;
          p.vx -= px; p.vy -= py; q.vx += px; q.vy += py;
        }
      }
      // gravity to origin keeps disconnected bubbles in the field
      p.vx -= p.x * this.gravity * a; p.vy -= p.y * this.gravity * a;
    }
    for (const p of nodes) {
      if (p.fx != null) { p.x = p.fx; p.y = p.fy; p.vx = p.vy = 0; continue; }
      p.vx *= this.velocityDecay; p.vy *= this.velocityDecay;
      p.x += Math.max(-40, Math.min(40, p.vx)); p.y += Math.max(-40, Math.min(40, p.vy));
    }
    // position-based collision relaxation: bubbles never overlap, even around a busy hub
    for (let it = 0; it < 2; it++) {
      for (let i = 0; i < nodes.length; i++) {
        const p = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const q = nodes[j], min = p.r + q.r + 4;
          const dx = q.x - p.x, dy = q.y - p.y;
          if (Math.abs(dx) > min || Math.abs(dy) > min) continue;
          const d = Math.hypot(dx, dy) || 1e-3;
          if (d >= min) continue;
          const over = (min - d) / d, pw = p.fx != null ? 0 : q.fx != null ? 1 : q.r / (p.r + q.r), qw = q.fx != null ? 0 : 1 - pw;
          p.x -= dx * over * pw; p.y -= dy * over * pw;
          q.x += dx * over * qw; q.y += dy * over * qw;
        }
      }
    }
    this.alpha += (this.alphaTarget - this.alpha) * this.alphaDecay;
  }
}
