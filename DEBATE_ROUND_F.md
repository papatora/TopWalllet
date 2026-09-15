# Round F — FINAL PRE-SHIP

Tanggal: 2026-09-16 · Scope: `Database Local only/html` (audit saja — tidak ada file proyek yang diubah).
Metode: verifikasi fix Round E dengan **runtime harness, bukan cuma baca** — `python server.py --port 8796` dijalankan lalu **dimatikan lagi (port 8796 bebas)**; payload produksi diunduh dari server ke `%TEMP%\roundf` (bukan di proyek); tiga harness Node menjalankan `store.load()` + `buildScope()`/`visibleGraph()`/`GraphCanvas`/`ForceSim` ASLI terhadap payload produksi, termasuk replikasi **baris-per-baris** handler `resetviz` (`visualizer.js:362-374`), lifecycle `window.__timeRO` 3× mount dengan mock `ResizeObserver` sesuai spesifikasi DOM, dan skenario reload-paused. Sweep D via heuristik identifier + grep per file.

State DB: 32.456 wallet (semua aktif), 290.719 swap (290.680 priced, 39 unpriced/outliers), 1.378 token, 2 cluster + 18 bundle = 20 entitas, 737 origins, 16 label. `meta.built` = 2026-09-15T21:37:39+00:00 (rebuild server Round F, fresh).

---

## VERDICT FIX ROUND E

### 1. Reset unpin iterasi `scope.nodes` (semua node, termasuk hidden) sebelum rebuild → **VALID (P1-E1 tuntas)**
- Kode: `visualizer.js:368` — `for (const n of (scope?.nodes || [])) { n.pinned = false; n.fx = n.fy = null; }` — loop sekarang menjangkau **seluruh** node scope lama (node hidden tetap ada di `scope.nodes`; `st.hidden` hanya menyaring di `visibleGraph`), dijalankan **sebelum** `rebuild()` yang menyalin `pinned/fx/fy` dari `prev` (:69-71) — urutan ini yang membuat salinan `prev` tidak lagi membawa pin lama.
- **Bukti runtime (harness mereplikasi handler persis):**
  - **Skenario A (pin → langsung Reset):** pin `w:4637` (fx 1234, fy −777) → after reset `pinned=false, fx=null, fy=null`, pinned di scope = 0, `g.pinnedCount()=0` → chip "1 pinned" tidak muncul. PASS.
  - **Skenario B (pin → hide via eye → Reset — bug P1-E1 Round E):** pre-reset terverifikasi akar masalahnya masih ada secara data (`g.pinnedCount()=0` karena node hidden, tapi `pinned=true, fx=1234` tersimpan di `scope.nodes`) → **setelah Reset: pinned=false, fx/fy=null, pinned di scope = 0, `g.pinnedCount()=0`, node kembali visible tanpa pin.** Pin tidak bangkit lagi. PASS.
  - **Skenario D (pin node GROUP → Funders OFF → Reset):** pin `g:0` → funders OFF (group hilang dari map, terverifikasi) → Reset → `pinned=false, fx=null`, pinned di scope = 0, `g.pinnedCount()=0`. PASS.
  - **Cakupan loop:** semua node scope di-pin lalu 2 node di-hide → setelah loop reset, pinned tersisa di `scope.nodes` (termasuk hidden) = **0**. PASS.
- Kontrak Reset ("kembalikan semua ke default") kini benar di semua jalur.

### 2. `ResizeObserver` — `window.__timeRO` assign dipisah dari `observe` → **VALID (P2-E1 tuntas)**
- Kode `visualizer.js:448-450`: `if (window.__timeRO) window.__timeRO.disconnect();` → `window.__timeRO = new ResizeObserver(() => scope && drawTimeline());` → `window.__timeRO.observe($('#time'));` — dua pernyataan terpisah, persis saran Round E.
- **Bukti runtime (mock RO sesuai spec — `observe()` mengembalikan `undefined`, 3× mount):** `window.__timeRO` terisi (instance RO) di **ketiga** mount (Round E: `undefined` terus-menerus, 0 disconnect); RO dibuat = 3, **disconnect = 2** — observer mount sebelumnya selalu diputus saat mount berikutnya; observer hidup tersisa = 1 (hanya milik mount aktif).
- Catatan kecil (nit, bukan kegagalan): setelah keluar dari route visualizer, RO mount terakhir tetap hidup menahan closure `scope`/`g` sampai kunjungan berikutnya memutusnya — leak kini **ter-batas 1** (sebelumnya tak terbatas), elemen ter-observe detached → callback tidak pernah fire. Memory-only, dapat diterima.

### 3. Paused tidak di-restore saat reload → **VALID (P2-D3 sisa tuntas)**
- Kode: `visualizer.js:64` kini hanya komentar (`// paused sengaja tidak di-restore — mulai unfrozen agar layout settle dulu`); grep seluruh file: **0** referensi `saved.paused`, **0** `queueMicrotask`, `setPaused` hanya dipanggil di handler Reset (`:367`, `false`) dan Freeze (`:396`, toggle). `persist()` (:16) masih MENULIS key `paused` ke localStorage — vestigial tapi harmless (tidak pernah dibaca).
- **Bukti runtime:** dengan `saved.paused=true` disimulasikan, mount penuh (GraphCanvas baru + buildScope + setGraph reheat 0.9) → `g.paused = false`, `sim.active = true` → sim tick dan layout settle; label tombol "Freeze" konsisten dengan state (tidak ada lagi jalur render-stale "Resume"). Dua sisa P2-D3 lama (label stale + layout beku di formasi phyllotaxis saat reload-paused) lenyap bersama fitur restore-nya.

---

## PRE-SHIP SWEEP (A–G)

### A. Server & API — **PASS**
- `python server.py --port 8796` naik; `GET /api/dataset` → **HTTP 200**, 14.508.848 byte (gzip), JSON valid.
- `POST /api/rebuild` → **HTTP 200** dalam 5,07 s: `{"ok": true, "built": "2026-09-15T21:37:39+00:00"}`; `GET /api/dataset` pasca-rebuild → 200 kembali (cache gz segar ter-serve).
- **24/24 aset statis HTTP 200** (index.html, 4 CSS, 17 JS, sprite.svg, known_entities.json).
- Server **dimatikan lagi** setelah pengujian — port 8796 bebas (diverifikasi: koneksi gagal).

### B. Syntax — **PASS**
- `node --check` **17/17** file JS lolos (app, 8 lib, 8 views).
- `python -m py_compile server.py dataset.py` → OK (Python 3.14.4).

### C. Datapath lengkap — **PASS**
Harness menjalankan `store.load()` (fetch stub → payload produksi 290.719 swap, `S.statsAll` 32.456 entri) lalu matriks penuh:
- **buildScope network × limit 50/150/300/600:** 105/209/359/659 node, 82/192/304/542 link — **0 dangling link, 0 node tanpa `r`** di semua limit. Sub-scope: "top N wallets · 20 grup receh · top 13–17 pools".
- **visibleGraph × 3 preset** (default / arkham / raw) di tiap limit: **0 dangling, 0 node tanpa `r`** di semua kombinasi. default ≡ arkham (semua layer on). Raw (dex/tradeEdges/icons/labels/flow/etype_* off; funders+bundles tetap on): 20 grup + 2 funder + 18 bundle tetap tergambar, **0 grup yatim** — struktur bintang cluster selalu terhubung (P2-D1 sisa: wallet individual degree-0 150/300/600 di raw, by-design karena pool/edge sengaja mati).
- **Group nodes mengikuti layer:** funders OFF → grup cluster 0, grup bundle 18, hub funder 0, orphan 0; bundles OFF → grup cluster 2, grup bundle 0, orphan 0. Persis semantik `visibleGraph` (`graph-data.js:199-202`).
- **Mode lain:** token HOOD L150 = 718n/717l, **L600 = 954n/953l** (0 dangling/0 no-r; catatan: cap L600 di mode token memberi scope lebih besar dari limitnya karena flag-wallet di luar slice); **20/20 entity scope** 0 dangling 0 no-r; wallet mode (top vol) 22n/21l bersih; hidden-3-node → 206n visible 0 dangling; range filter ⅓–⅔ window → 211n/166l 0 dangling (build 50 ms).

### D. Variabel/func dipakai-tapi-tak-didefinisikan — **PASS**
- Heuristik identifier per 17 file + grep targeted: tidak ada satu pun dari daftar brief yang "use w/o def": `css` (graph.js:11 module + :29 lokal), `rgba` (graph.js:13), `SPECIAL` (graph-data.js:100), `SPECIAL_LABELS` (:98), `groupOf` (:122) — semuanya terdefinisi di scope pemakaiannya. `foldedEntityOf` / `extrasByEntity` / `groupNodes` → **0 hasil grep** (P2-7 lama tetap mati total).
- Sisa "suspect" heuristik semuanya false positive (nama method shorthand class, kata Indonesia di komentar/template, `var(--…)` di string, param destructured). Temuan kecil satu-satunya: `GraphCanvas.unpinAll()` (graph.js:91) **dead method** — tidak pernah dipanggil (handler rail unpin reimplement inline di `visualizer.js:419`). Harmless.

### E. Konsistensi Guide vs implementasi — **PASS (semua fitur yang dijanjikan punya handler)**
- FREEZE/Resume → handler `data-act="freeze"` (`visualizer.js:394-401`) + sinkron label via `syncPanels` (:90-92). ✓
- RESET → `resetviz` (:362-374), runtime PASS (fix #1). ✓ (dicatat: RESET tidak diteks di Guide — hanya dokumentasi, bukan fungsional.)
- Sub-layer (chevron + eye per-item) → `data-explayer`/:360 + `data-eye`/:358, sinkron `st.hidden` & `applyVisibility` (runtime PASS di Sweep C). ✓
- INDUKAN → kartu node (`visualizer.js:253-263`, key address `S.origins[S.wallets[sel.ref][0]]`) + halaman profil (`address.js:56`, guard + fallback "mint 0x0"). ✓
- Group bubble → renderer `drawGroup` (graph.js:308-318), kartu GRUP dengan daftar anggota (`visualizer.js:238-244`), tooltip (:290-293), radius (`graph-data.js:181`). ✓
- Tema → cycler dark→white→space + persist `tw-theme` (app.js:141-151), tombol `#themeBtn` ada (index.html:35); observer tema canvas ter-disconnect di `destroy()` (graph.js:31-32,44). ✓
- Filter tag leaderboard → `TAG_OPTIONS` dari `S.labels` termasuk derived (leaderboard.js:6), dropdown `tag` (:68), filter `matchTag` (:32-35) + `traderRows` (:26), handler `dd:change` (:119). ✓
- Fullscreen → handler `fs` (:376-380, requestFullscreen/exitFullscreen). ✓
- Sisa mismatch teks (carried, kosmetik): guide.js:57 "dilipat jadi SATU bubble" (kenyataan 2 elemen: grup + hub; vol hanya anggota terlipat) dan guide.js:66 + toast raw (:402) "cuma wallet + ikatan cluster / only" padahal funders+bundles sengaja tetap ON agar struktur tak runtuh (desain Round D yang validated). Tidak ada fitur yang dijanjikan tanpa implementasi.

### F. dataset.py — **PASS**
- `py_compile` OK (Sweep B) dan `dataset.build()` dipanggil langsung: **sukses**; wallets 32.456, swaps 290.719 (priced 290.680 / unpriced 39 / outliers 39), tokens 1.378, bundles 18, clusters 2, origins 737.
- `meta.label_counts` berisi derived: **BOT 22, WHALE 19, WHALE_SUS 3, SNIPER_BOT 4** — semuanya > 0 dan cocok dengan state Round B/E.

### G. Estimasi P0/P1 tersisa — **TIDAK ADA P0/P1 FUNGSIONAL**
- 0 crash di seluruh matriks (4 mode × limit × 3 preset + toggle layer + hidden + range + 3 skenario reset + reload); API & rebuild sehat.
- Satu-satunya warisan ber-grade di atas P2 adalah **setengah P1-D2 (perf)**: `force.js` tidak disentuh lagi (alphaDecay 0.035, O(n²)) — ukuran ulang Round F: **L600 (659n) = 49,1 ms/tick, settle ±153 ticks ≈ 7,5 s churn** per full reheat; skenario terberat baru: token HOOD di L600 (954n) ≈ 9 s. Default (L150, 209n) tetap mulus. Ini degradasi performa di cap tinggi, bukan kegagalan fungsional — layak dicatat sebagai limitasi yang diketahui, bukan blocker ship (saran jangka: decay adaptif untuk n>400 atau cap node token mode).

---

## SISA MASALAH

### P0
Tidak ada.

### P1
Tidak ada yang fungsional. Carried: **P1-D2 (setengah, perf-only)** — L600/token-besar masih 40–50 ms/tick → churn 7–9 s per reheat (bukti di G). Default view sehat; opsi mitigasi UI ada (cap 150). Tidak blocker.

### P2 (carried, tidak memburuk — bukan regresi)
1. **P2-E2** — sub-layer list di **mode entity** tetap $0.00: `visualizer.js:188` (`it.foldedVol ?? it.vol ?? 0`), hub entity tidak punya keduanya (harness: `foldedVol=undefined, vol=0`) sementara kartunya benar via formula anggota ($4.120 untuk Cluster be41). 1 baris: pakai formula card di list.
2. **P2-D5** — timeline SVG hardcoded `#222834/#1E6FF1/#1B2A44/#667085` (`visualizer.js:323-325`): di tema white bar out-of-range lebih menonjol dari in-range; baseline nyaris invisible di dark/space.
3. **P2-D6** — `hexBadge` `rgba(7,8,12,.35)` (ui.js:40) + `.pill` fallback gelap (components.css:152) tanpa override white → podium leaderboard white kontras rendah.
4. **P2-D7 (nit)** — `--text-3` space `#6C74BE` (tokens.css:61) kontras ±3,4:1 untuk teks micro 10px; RO leak kini ter-batas 1 (memory-only, callback tak pernah fire di elemen detached); `unpinAll()` dead method; Reset masih memanggil `applyVisibility` dua kali (0.9 di dalam rebuild + 0.5 di handler); mismatch teks Guide "SATU bubble" dan "raw: only".
5. **P2-D1 (sisa, by-design sebagian)** — preset raw: wallet individual tetap degree-0 (pool/edge mati sengaja); "ikatan cluster" penuh ala bubblemaps untuk top-wallet belum terbentuk.

---

## SKOR SIAP-SHIP: **8.5 / 10**

**Alasan:** Ketiga fix Round E terverifikasi jalan di runtime (bukan cuma baca): Reset-unpin kini menjangkau semua node termasuk hidden di ketiga skenario adversarial (pin→reset, pin→hide→reset, pin-group→layer-off→reset) dengan chip PINNED benar hilang; `window.__timeRO` benar-benar terisi dan observer antar-mount ter-disconnect; paused tidak lagi di-restore dan tidak ada jalur sisa. Pre-ship sweep bersih: API + rebuild + 24 aset sehat, 17/17 JS + py_compile lolos, datapath 4 mode × limit × 3 preset 0 dangling / 0 node tanpa `r` / grup mengikuti layer, 0 identifier undefined, semua fitur Guide punya handler, `label_counts` derived lengkap. Yang menahan 1,5 poin hanyalah warisan yang sudah terdokumentasi dan tidak memburuk: churn force-sim 7–9 s di cap 600/token besar (perf-only), sub-layer entity $0.00, dan beberapa kosmetik tema/teks.

**Pesan final: SKOR 8,5/10 — BOLEH DINYATAKAN FINISHING.** Semua P0/P1 fungsional lintas Round A–F telah tuntas dan terverifikasi runtime; sisa temuan adalah P2 polish (sub-layer entity 1 baris, timeline/hexBadge tema, teks Guide) dan satu limitasi perf yang diketahui di cap tinggi — aman untuk di-ship sekarang, polish bisa menyusul tanpa risiko.
