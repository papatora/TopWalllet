# Round D — Audit Adversarial (fokus: TEMA · PERFORMANCE · EDGE CASE)

Tanggal: 2026-09-16 · Scope: `Database Local only/html` (audit saja — tidak ada file proyek yang diubah).
Metode: baca line-by-line seluruh JS/CSS yang relevan; grep sistematis hardcoded color di `assets/js/**/*.js` + `assets/css/*.css`; `node --check` file kunci lolos; runtime `python server.py --port 8805` (`/api/dataset` HTTP 200, 14,5 MB) **dimatikan lagi setelah pengujian**; dua harness Node (di `%TEMP%\roundd`, bukan di proyek) menjalankan `buildScope()`/`visibleGraph()`/`ForceSim` ASLI terhadap payload produksi; `dataset.build()` diukur langsung.

State DB: 32.456 wallet, 290.680 swap priced, 1.378 token, 18 bundle, 2 cluster, 737 origins, 20 entitas. `price_points` masih kosong (fallback snapshot).

---

## VERDICT FIX ROUND C

### 1. `visibleGraph` kind 'group' mengikuti layer funders/bundles → **VALID**
- `graph-data.js:199-202`: `if (n.kind === 'group') { const e = S.entities[n.ref]; return e ? (e.kind === 'cluster' ? show.funders : show.bundles) : true; }` — persis saran Round C.
- **Bukti runtime (dataset asli, limit 150/300/600):**
  - Preset "Bubblemaps raw" (dex/funders/bundles/tradeEdges off): **0 group node visible** di semua limit; **0 dangling link**. Grup yatim `g:1`…`g:19` dari Round C hilang total.
  - Default (semua on): 20 group muncul, **0 group orphan**, 0 dangling.
  - Funders OFF saja (bundles on): grup cluster hilang (sisa 18 grup = bundle grup, benar), 0 orphan, 0 dangling.
- Catatan: dengan grup ikut tersembunyi, sisa floaters di raw kini 100% wallet individual — lihat P2-D1.

### 2. Sub-layer list `usd(it.foldedVol ?? it.vol ?? 0)` → **VALID**
- `visualizer.js:188` sudah `foldedVol` dulu. Runtime: dari 20 hub, **0 yang menampilkan $0.00** (sebelumnya 20/20 $0.00). Contoh: `f:cluster_f70d` → $16.084, `b:0xbcb5…` → $563.237 (foldedVol riil; `hub.vol` memang tetap 0/dead field — konsisten).
- Sisa: di **mode entity** hub tidak punya `foldedVol` → baris sub-layer tetap $0.00 (P2-D2, satu keluarga dengan P2-C3).

### 3. Trace overview KPI menghitung volume grup → **VALID**
- `visualizer.js:117-119`: `vol = wallet+entity vol + Σ group.vol`.
- Runtime L150: KPI **$95.740.919** vs lama $91.050.006 (+$4,69 J volume 461 anggota terlipat — angka cocok dengan P2-C3 Round C). L600: $124,74 J (di L600 semua anggota masuk ranked → 0 folded, KPI = individual).
- Nit: KPI "Wallets" masih `wallets.length` (152 di L150) padahal peta mewakili 152+461 — separuh saran Round C yang dijalankan.

### 4. `expand` untuk kind entity → **BROKEN** (cabang ada, tapi target salah — temuan P1-D1)
- `visualizer.js:431`: `else if (g.sel?.kind === 'entity') location.hash = '#/visualizer?entity=' + g.sel.ref;`
- **Bukti runtime:** satu-satunya wallet terdaftar di `known_entities.json` yang ada di dataset adalah Burn address `0x…dead` = **wallet index 0** → node kind 'entity' punya `ref: 0` (ref = INDEX WALLET, `graph-data.js:21`). Handler membuka `#/visualizer?entity=0` → `S.entities[0]` = **Cluster be41** (funder cluster yang sama sekali lain). Klik "+ Expand" pada Burn address membuka peta cluster be41, bukan profil/scope wallet itu.
- Round C menyarankan `walletHref(g.sel.ref)`; yang diimplementasikan justru `entity=` + ref wallet. Karena `data-act="expand"` kini hidup (fix #3 Round C), bug ini live. Fix: `#/visualizer?wallet=${g.sel.addr}` (atau sembunyikan Expand untuk kind entity).
- Catatan edge yang aman: `0x0000…0000` (Null) TIDAK ada di wallets → URL `#/visualizer?wallet=0x…0000` jatuh ke guard `i != null` (visualizer.js:28) → network scope, tanpa crash.

### 5. Freeze label sinkron via syncPanels + resume reheat 0.15 → **PARTIAL**
- Resume: `graph.js:158` `setPaused(false) → sim.reheat(0.15)` — runtime: dari alpha 0, `active=true`, settle **200 ticks** → Resume benar-benar menghidupkan sim (P2-B2 Round B tuntas untuk jalur resume). Label sinkron benar di handler Freeze (visualizer.js:396) dan di `syncPanels()` (visualizer.js:90-92).
- **Sisa P2-C6:** jalur reload-saat-paused (`visualizer.js:64` `queueMicrotask(() => g.setPaused(true))`) TIDAK memanggil `syncPanels`/`drawLeft` setelahnya — microtask jalan setelah `rebuild()` sinkron, jadi tombol terlanjur dirender "Freeze" padahal state paused, dan `setPaused(true)` meng-nol-kan alpha sebelum tick pertama → layout permanen di formasi phyllotaxis. Tidak diubah dari Round C.

### 6. Observer tema tersimpan benar → **VALID**
- `graph.js:31-32`: kini dua pernyataan — `this.themeObs = new MutationObserver(...); this.themeObs.observe(document.documentElement, {attributes:true, attributeFilter:['data-theme']});`. `destroy()` (`:44`) `this.themeObs?.disconnect()` kini benar-benar memutus. Callback me-rebuild `this.c` (termasuk ent_fill/ent_text) + `dirty=true` → redraw saat ganti tema.
- Dipanggil: `zoomTimer` (visualizer.js:445) memanggil `g.destroy()` saat `root` tak terhubung → siklus mount/unmount visualizer tidak lagi menumpuk observer tema (P2-C5 tuntas untuk observer ini; observer lain lihat P2-D4).

### 7. Selection/focus ring theme-aware → **VALID**
- `graph.js:257`: ring seleksi `this.c.text` (dulu `#FFFFFF`); `graph.js:280` ring fokus `this.c.text` (dulu putih). `readTheme()` me-refresh via observer → dark (teks terang) / white (teks gelap `#141922` di stage `#ECEEF2`) / space (`#E9ECFF`) semuanya kontras.
- Nit: ring **hover** masih hardcoded `'rgba(128,140,170,.55)'` — mid-tone yang cukup terbaca di ketiga tema (blend di white ≈ #B0B8CA vs #ECEEF2 — subtle tapi kelihatan), jadi tidak digrade.

---

## TEMA AUDIT

### dark — bersih
Tidak ada masalah baru. Semua var terdefinisi; baseline timeline `#222834` di panel `rgba(16,19,26,.96)` nyaris tak terlihat (kosmetik, nit).

### white — 3 sisa (semua P2, tidak ada yang membuat fitur rusak)
1. **P2-D5 — timeline hierarki terbalik:** bar out-of-range `#1B2A44` (navy gelap, visualizer.js:324) di panel putih justru LEBIH menonjol daripada bar in-range `#1E6FF1` → range yang DIPILIH tampak "redup" dan bagian yang dibuang tampak utama. Baseline `#222834` (`:323`) di dark/space juga nyaris invisible. Fix: pakai `var(--line)`/`var(--blue)` (SVG dalam DOM bisa pakai CSS var) atau hex per tema.
2. **P2-D6 — kontras aksen emas/perak/perunggu:** `.rank.is-1/2/3` (components.css:103-105) pakai `--gold #F2C94C` dst. tanpa override white → teks emas di panel putih ≈ kontras 1,9:1; `hexBadge` (ui.js:40) masih `fill="rgba(7,8,12,.35)"` (sisa P2-B6 Round C yang tidak pernah dijalankan). Ketiganya di leaderboard/podium white.
3. Kosmetik yang hilang tanpa merusak: highlight-hover chart `fill="#fff" fill-opacity=".04"` (charts.js:104) invisible di white; dot-grid stage `rgba(255,255,255,.045)` (views.css:73) invisible di white; `.al-cluster` tint dan stripe baris tabel `rgba(255,255,255,.012)` sama sekali tak terlihat di kedua tema terang/gelap; scrollbar `#232A37` (base.css:19) gelap di tema putih (berfungsi, hanya estetika).

### space — layak, 2 nit kecil
- Teks terbaca: `--text #E9ECFF` di panel `rgba(11,14,28,.66)` di atas starfield #020308 — aman; `.viz-panel`/`.node-card` dapat `backdrop-filter:blur(6px)` (tokens.css:64).
- **Nit-1:** blur TIDAK diberikan ke `.viz-rail`, `.viz-time`, `.pop`, `.toast`, `.chart-tip` → bintang kelap-kelip tembus di belakang dropdown/tooltip/toaste translusen (shimmer halus di belakang teks; alpha .82/.66 cukup menutup, murni kosmetik).
- **Nit-2:** `--text-3 #6C74BE` di panel space ≈ kontras 3,4:1 untuk teks micro 10px (`.micro`, `.eyebrow`, label timeline) — lebih redup dari dark (#667085 ≈ 4:1). Masih terbaca, tapi jadi teks paling redup di seluruh app.

### Canvas renderer per tema (drawBubble/drawToken/drawHub/drawGroup/drawEntity/drawTimeline) — diperiksa satu per satu
`drawBubble` fallback biru `rgba(78,104,170,.42)`, `drawToken` `hsl(h 36% 19%)` + teks `hsl(h 80% 78%)` (di dalam lingkaran gelap), `drawGroup` fill `c.panel` + stroke `rgba(140,152,184,.9)` + teks `c.text2/text3`, `drawHub` fill `c.panel` + stroke pink/amber, `drawEntity` `--ent-fill/--ent-text` per tema, label node `c.text/c.text2` — semuanya aman di 3 tema. `.fchip`/`.fchip.is-on`/`.seg-btn.is-active`/`.pill` sudah var/override per tema ✓. Tooltip `.viz-tip` = `--panel-2` + border `--line-strong` ✓. Satu-satunya hardcoded canvas yang menyisakan masalah nyata adalah timeline (P2-D5).

---

## PERFORMANCE (angka ukuran, mesin audit; Node 24)

- **dataset.build(): 3,75 s** (290.680 swap diprice, 32.456 wallet, 1.378 token) — `/api/rebuild` memblokir POST ±4 s, GET tetap dilayani gz lama (thread-safety sudah diverifikasi Round B).
- **buildScope network (payload asli):** L150 = 81-85 ms → visible 209 node / 192 link; **L300 = 79-89 ms → 359 node / 304 link**; **L600 = 78-80 ms → 659 node / 542 link**. `visibleGraph` < 1 ms. Build bukan masalah.
- **Force settle (reheat 0,9 → alphaMin 0,004, decay 0,018) = 271 ticks di semua ukuran:**
  - L150 (209 node): 4,9 ms/tick → wall 1,3 s — halus.
  - L300 (359 node): 15,6 ms/tick → wall 3,9-4,2 s — pas di boundary frame budget.
  - **L600 (659 node): 49-52 ms/tick → wall 13-14 s** — 3× frame budget 16,7 ms → 10-20 fps selama ±14 detik tiap kali sim reheat.
  - **Mode token terbesar (769 node / 768 link — P2-11 lama: semua wallet ter-flag ditambahkan di luar slice limit): 64 ms/tick → wall 17,3 s** — skenario terberat, lebih berat dari L600.
  - Resume (reheat 0,15) di L600 = **200 ticks ≈ 10 s churn** — interaksi Freeze/Resume di cap tinggi terasa "mati" 10 detik.
- **Frame loop saat paused: benar-benar idle** — `graph.js:165-169`: hanya `if (this.dirty) draw()`; tidak ada tick, tidak ada flow; rAF kosong berjalan (trivial). Flow dots saat un-paused memaksa redraw penuh tiap frame (`dirty || opt.flow`, `:177`) — pada 659 node draw + tick 49 ms sudah tertelan biaya tick; draw murni ±1-3 ms (aman).

Kesimpulan perf: default (L150) sehat; **setiap pilihan "Wallet cap" 300/600 dan mode token besar membuat setiap reheat (toggle layer 0,35 ≈ 246 ticks, eye 0,3, resume 0,15) menjadi 4-17 detik tampilan patah-patah** — ini P1-D2.

---

## P0/P1/P2 BARU

### P0
Tidak ada. Tidak ditemukan crash baru; guard URL wallet/entity bekerja; keempat mode scope + preset aman di payload asli.

### P1-D1 — `expand` kind 'entity' membuka scope ENTITAS YANG SALAH (verdict fix #4)
- **File:line:** `visualizer.js:431`.
- **Bukti runtime:** node entity `0x…dead` (wallet idx 0) → handler membuka `#/visualizer?entity=0` → `S.entities[0]` = Cluster be41 (terverifikasi harness). ref untuk kind 'entity' adalah index WALLET (graph-data.js:21), bukan index entitas; guard `S.entities[+q]` lolos karena 0 valid → salah senyap tanpa feedback.
- **Dampak:** satu-satunya node entity yang ada di app saat ini membawa user ke peta cluster yang tidak berkaitan. Klik "Open"/tooltip/more untuk kind yang sama sudah benar (walletHref) — hanya Expand yang salah.
- **Saran:** `location.hash = '#/visualizer?wallet=' + g.sel.addr;` (3 char beda dari Round C yang benar).

### P1-D2 — force sim meledak di cap 300/600 & mode token: 49-64 ms/tick, churn 13-17 s per reheat
- **File:line:** `force.js:5` (alphaDecay 0,018 → 271 ticks per reheat 0,9), `force.js:44-62,72-86` (repulsion O(n²) + 2 pass collision O(n²)), pemicu reheat besar: `visualizer.js:73,368,438` (0,9/0,5/0,35) dan `graph.js:158` (0,15).
- **Bukti runtime:** L600 = 49-52 ms/tick (13-14 s), token 769 node = 64 ms/tick (17,3 s), resume L600 = 200 ticks ≈ 10 s; single tick worst 52 ms vs budget 16,7 ms. Round C menyebut "659 node masih ringan" — terbantahkan: hanya L150 yang ringan.
- **Dampak:** pengguna yang memilih Wallet cap 300/600 (opsi pertama di panel kiri) atau membuka token besar mendapat 4-17 detik map patah-patah SETIAP toggle layer/eye/limit/resume — bukan sekadar settle awal.
- **Saran:** (a) naikkan alphaDecay saat n besar (mis. `alphaDecay = n > 400 ? 0.035 : 0.018` → ±140 ticks); (b) batasi tick kedua (`alpha>0.3`) hanya saat n ≤ 300; (c) cap node token mode (flag-wallet di luar top-limit digabung/hide, P2-11); (d) rendahkan reheat toggles ke 0,2.

### P2-D1 — preset "Bubblemaps raw" kini peta titik mengambang: 150-600 node degree-0, "ikatan cluster" hilang
- **File:line:** `graph-data.js:209-220` (bonds hanya dari link wallet→hub; anggota terlipat tidak punya node wallet) + preset raw (`visualizer.js:111`).
- **Bukti runtime:** raw L150/300/600 → 152/302/602 node, **1 link** (bond antar 2 MEV spesial), degree-0 = 150/300/600. Seluruh anggota cluster/bundle terlipat ke group node yang (sejak fix #1) ikut tersembunyi → tidak ada lagi yang bisa di-bond.
- **Dampak:** tampilan flagship "cuma wallet + ikatan cluster" (guide.js:66) kini menampilkan ladang gelembung tanpa ikatan — eskalasi P2-C8 (yang tadinya 27 floaters di default view; default view sendiri kini 22-160 floaters, tetap seperti Round C).
- **Saran:** di raw preset biarkan group node tetap tampil (grup = cluster bubble versi bubblemaps): raw tidak menonaktifkan "layer grup" (mis. pisahkan flag `groups` dari funders/bundles), atau saat hub hidden boncatkan special members ke group node tetangga.

### P2-D2 — sisa P2-C3: mode entity never set `foldedVol` → kartu & sub-layer $0.00 di scope entity
- **Bukti runtime:** ke-20 entity scope → `hub.foldedVol = undefined, hub.vol = 0`; kartu hub "Volume grup est. $0.00" (visualizer.js:250) dan baris sub-layer `foldedVol ?? vol` → $0.00. Tidak disentuh oleh fix #2/#3 Round C (yang hanya menyentuh network mode).
- **Saran:** `h.foldedVol = e.members.reduce((a,m)=>a+(S.statsAll.get(m)?.vol||0),0)` di mode entity (graph-data.js:68-77).

### P2-D3 — reload saat paused: label tombol stale + layout beku di posisi spawn (sisa P2-C6, tidak diperbaiki)
- `visualizer.js:64` microtask `setPaused(true)` tanpa `syncPanels()`/`drawLeft()` setelahnya; sinkronisasi label via syncPanels (fix #5) tidak menjangkau jalur ini. Sim juga tidak pernah menick (alpha di-nol-kan) → spiral phyllotaxis permanen.
- **Saran:** di dalam microtask: `g.setPaused(true); syncPanels();` (dan idealnya jangan reheat 0,9 di rebuild bila akan langsung di-pause).

### P2-D4 — `ResizeObserver` timeline tidak pernah di-disconnect (keluarga P2-C5, observer lain)
- `visualizer.js:446`: `new ResizeObserver(() => scope && drawTimeline()).observe($('#time'))` — tidak disimpan, tidak di-disconnect di cleanup mana pun (cleanup hanya `zoomTimer` → `g.destroy()`). Akumulasi observer per mount visualizer (elemen ter-observe detached → tidak aktif, tapi memori & referensi closure `scope`/`g` tertahan).
- **Saran:** simpan di variabel dan disconnect bersama `g.destroy()` / saat `!root.isConnected`.

### P2-D5 — timeline SVG hardcoded (white: hierarki terbalik; dark/space: baseline invisible)
- `visualizer.js:323-325`: baseline `#222834`, bar in-range `#1E6FF1`, bar out-of-range `#1B2A44`, tick `#667085`. Lihat TEMA AUDIT white §1. Nit `#667085` aman di semua tema.

### P2-D6 — white theme: aksen emas/perak/perunggu + hexBadge low-constraint (sisa P2-B6)
- `components.css:103-105` `.rank.is-1/2/3` tanpa override white (gold #F2C94C di putih ≈ 1,9:1); `ui.js:40` hexBadge `rgba(7,8,12,.35)` masih hardcoded. Terkena: podium leaderboard di tema white.

### P2-D7 — nit space/perf kecil (tidak digrade berat)
- Space: blur hanya di `.viz-panel`/`.node-card` → shimmer bintang di belakang `.pop`/`.viz-tip`/`.toast`/`.viz-time`/`.viz-rail`; `--text-3` space (#6C74BE) kontras ±3,4:1 untuk teks 10px.
- Perf kecil: `drawRight` memanggil `g.labelColor(n.type)` per baris (graph.js:35 `getComputedStyle` per panggilan) → ±600 getComputedStyle per keystroke di address search L600; `drawTimeline` memfilter `S.all` (290K) tiap rebuild/resize (±5 ms, ok).
- Carried nit Round C yang masih ada: `unpin` hanya membersihkan node visible; Reset masih `applyVisibility` 2×; guide.js:57 "SATU bubble sebesar total volume anggotanya" (kenyataan: dua bubble, vol anggota spesial tidak dihitung); `--blue-line` tak terpakai.

---

## VERIFIED-OK

1. **Syntax:** `node --check` lolos untuk semua file yang disentuh (visualizer, graph-data, graph, force, address, app, store, ui); template literal bersarang INDUKAN di `address.js:56` valid (`\"` legal, `join(' · ') || 'mint 0x0'` benar, `esc()` dipakai di label) — tidak ada syntax/escaping bug.
2. **Runtime API:** server naik di 8805, `/api/dataset` 200 (14,5 MB), JSON valid; **server dimatikan lagi** (port 8805 free).
3. **Edge — Freeze dua kali cepat:** toggle `setPaused(!g.paused)`; klik ke-2 = resume + reheat 0,15 (active 200 ticks) — tidak ada state macet, label & persist ikut.
4. **Edge — Reset saat paused:** `g.setPaused(false)` → reheat → rebuild → syncPanels; label kembali "Freeze", sim jalan; tidak crash.
5. **Edge — URL langsung:** `#/visualizer?wallet=0x…` dikenal → scope wallet (Burn address idx 0 = node entity, kartu INDUKAN & chips benar); address tak dikenal / `?entity=` di luar jangkauan → guard jatuh ke network, tanpa crash; hash `wallet` di-lowercase sebelum lookup (address checksummed aman).
6. **Edge — token scope 1 trader:** 43 token ber-trader-1; scope = 2 node / 1 link, 0 dangling, radius token 26 — normal.
7. **Edge — entity scope untuk bundle "semua anggota spesial":** kasus tidak ada di dataset ini (0/447 anggota bundle berlabel SPECIAL di luar SNIPER/BUNDLER_SUSPECT yang foldable); secara kode mode entity tidak pernah melipat → semua anggota digambar individual, tidak ada jalur yang rusak. Semua 20 entity scope: 0 dangling.
8. **Kartu grup/hub:** kartu grup pakai `sel.vol` (terisi benar), kartu hub pakai `sel.foldedVol` (tanpa dobel) — angka konsisten dengan sub-layer list di network mode.
9. **is-on chip "Ungroup clusters"** (visualizer.js:272) kini `st.grouped ? 'is-on' : ''` — konvensi is-on = aktif sudah benar (nit Round C tertangani).
10. **guide.js vs implementasi:** sub-layer chevron ✓ (`data-explayer` + eye per item, sinkron `st.hidden`), INDUKAN di kartu ✓ & profil ✓, FREEZE/Resume ✓ (kecuali jalur reload-paused, P2-D3), FLOW kini dijelaskan "ALL/OFF" sesuai kontrol nyata (mismatch "All/In/Out" Round C sudah diperbaiki teksnya).
11. **Tema — var lintas-tema:** 0 pemakaian `var(--…)`/`css('--…')` yang tak terdefinisi di salah satu tema; `--ent-fill/--ent-text/--viz-panel/--chip-bg/--seg-active-*` terdefinisi :root + white + space; ring seleksi/fokus memakai `c.text` yang di-refresh observer tema.
12. **Frame loop paused:** idle murni (hanya rAF kosong; draw hanya saat dirty) — klaim "hemat lag" tombol Freeze benar.

---

## PESAN FINAL

**Verdict Round D: 5 dari 7 fix Round C VALID (grup-layer, sub-layer $, KPI, themeObs, ring tema); 1 PARTIAL (freeze-label — jalur reload-paused masih bocor); 1 BROKEN (expand entity membuka entitas yang salah).** Temuan baru: **2 P1** (expand entity salah target; force sim 49-64 ms/tick → churn 13-17 s di cap 600/token mode) + **7 P2** (raw preset jadi ladang floaters, entity-scope $0.00, reload-paused stale, RO leak, timeline white, aksen white, nit space/perf). Core (dataset, scope builder, fold v2, router, tema) sehat — **belum 100% finishing: biliarkan P1-D1 (1 baris) dan P1-D2 (tuning decay/limit) dulu; sisanya polish yang aman ditunda.**
