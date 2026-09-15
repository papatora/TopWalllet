# Round E — Audit Adversarial FINAL (verifikasi fix Round D + functional sweep)

Tanggal: 2026-09-16 · Scope: `Database Local only/html` (audit saja — tidak ada file proyek yang diubah).
Metode: baca line-by-line seluruh file yang disentuh fix Round D; `node --check` 17/17 JS lolos + `python -m py_compile` lolos; **runtime `python server.py --port 8795`** — `/api/dataset` HTTP 200 (14.508.849 byte), `POST /api/rebuild` HTTP 200 (`{"ok":true,"built":"2026-09-15T21:24:48+00:00"}`, blok 4,98 s), 24 aset statis (HTML/CSS/JS/JSON/SVG) semuanya 200, **server dimatikan lagi setelah pengujian (port 8795 bebas)**; tiga harness Node (di `%TEMP%\rounde`, bukan di proyek) menjalankan `store.load()` + `buildScope()`/`visibleGraph()`/`ForceSim` ASLI terhadap payload produksi (payload diunduh dari server 8795), termasuk simulasi persis urutan handler `resetviz`, pola `queueMicrotask` paused-restore, dan mock `ResizeObserver` sesuai spesifikasi DOM.

State DB: 32.456 wallet (semua aktif), 290.719 swap (290.680 priced, 39 unpriced/outliers), 1.378 token, 2 cluster + 18 bundle = 20 entitas, 737 origins, 16 label. `meta.built` = waktu rebuild server (fresh); swap window 2026-06-21 → 2026-09-15. Token terbesar kini HOOD (1.313 traders, scope 718n/717l).

---

## VERDICT FIX ROUND D

### 1. `expand` kind entity → `#/visualizer?wallet=${S.wallets[g.sel.ref][0]}` → **VALID**
- `visualizer.js:433` persis saran; `ref` node entity memang index wallet (`graph-data.js:21`).
- **Bukti runtime:** wallet index 0 = `0x0000…dead` (Burn address, terdaftar di `known_entities.json`) → node `w:0` kind `entity`, `ref: 0`. Handler menghasilkan hash `#/visualizer?wallet=0x0000…dead` → guard `S.addrIndex.get(...)` resolve ke idx 0 → scope wallet terbuka (153n/156l, title `0x0000…dead`). Peta cluster be41 yang salah dari Round D tidak lagi bisa terbuka dari tombol ini.
- Catatan kecil: node entity HANYA ada di scope wallet Burn address itu sendiri (network L150: 0 node entity) → satu-satunya klik Expand kind entity saat ini adalah navigasi ke halaman yang sama (hash identik → `hashchange` tidak fire → no-op benign). Null address `0x…0000` tidak ada di wallets → tidak pernah jadi node. Tidak ada jalur rusak.

### 2. `force.js` alphaDecay 0.035 → **VALID (churn −50%), residual P1-D2 belum tuntas**
- `force.js:5` = `alphaDecay 0.035` (terverifikasi di instance nyata). **Ukur settle dari alpha=1 (mount pertama, reheat 0.9 → tetap 1.0):**
  | Skenario | ticks | frames | wall@60fps | wall riil (ms/tick terukur) |
  |---|---|---|---|---|
  | L150 (209n) baru 0.035 | **155** | 138 | **2,30 s** | ≈0,65 s (4,2 ms/tick — halus) |
  | L150 lama 0.018 | 304 | 271 | 4,52 s | ≈1,2 s |
  | L300 (359n) baru | 155 | 138 | 2,30 s | ≈1,75 s (11,3 ms/tick — border) |
  | L600 (659n) baru | 155 | 138 | 2,30 s | **≈6,2 s (39,7 ms/tick — masih patah-patah ±25fps)** |
  | L600 lama 0.018 | 304 | 271 | 4,52 s | ≈11,5 s (37,9 ms/tick) |
- Dari keadaan settle (alpha→0 lalu reheat): resume 0.15 = **102 ticks** (≈4,2 s wall @L600, sebelumnya 200 ticks ≈10 s); toggle layer 0.35 = 126 ticks (≈5,3 s @L600; 0,54 s @L150; 1,6 s @L300); preset/reset 0.5 = 136 ticks.
- **Token mode terbesar diukur ulang: HOOD 718n/717l = 7,0–7,6 ms/tick → settle 1,1–1,2 s** (Round D: 769n/64 ms/17,3 s — skenario terberat lama praktis hilang).
- Verdict: perbaikan nyata (semua reheat ±2× lebih cepat, L150 kini selalu mulus), tapi **L600 masih 40+ ms/tick** — akar O(n²) (`force.js:44-62,72-86`) tidak disentuh; churn 4–6 detik tetap ada tiap toggle/resume di cap 600.

### 3. Reset unpin `for (const n of g.nodes) { n.pinned=false; n.fx=n.fy=null; }` → **BROKEN — dugaan terkonfirmasi sebagian (bug hidup di jalur node tersembunyi)**
- Mekanika: `visibleGraph` mengembalikan **objek node yang sama** dengan `scope.nodes` (harness: `every(n => scope.nodes.includes(n))` = true) → unpin loop di `g.nodes` MEMANG membersihkan pin semua node yang saat itu terlihat, dan salinan `prev` di `rebuild()` (:69-71) ikut terbersih. **Skenario A (pin → langsung Reset): pinned di peta baru = 0 → bersih ✓.**
- **TAPI** handler resetMembersihkan `st.hidden` (:365) **setelah** node sudah tidak ada di `g.nodes`, dan unpin loop (:368) hanya menjangkau node visible → pin yang tersimpan di `scope.nodes` untuk node tersembunyi SELAMAT, lalu **direstore oleh `Object.assign(n, {x,y,fx,fy,pinned})` di rebuild (:71)**:
  - **Skenario B — pin → Hide (eye) → Reset:** `pinned di scope.nodes = 1` (tidak tersentuh unpin loop) → AFTER RESET: **1 node pinned kembali, `w:4637` terkunci di (1234,−777)** persis posisi lama; chip "1 pinned" langsung muncul setelah Reset.
  - **Skenario D — pin node GROUP → layer Funders OFF → Reset:** `g:0` kembali **pinned di (999,−999)**.
- Dampak: Reset menjanjikan "kembalikan semua ke default" tapi pin lama (beserta bekuan posisi `fx/fy`) bangkit lagi untuk setiap node yang tidak sedang tergambar saat Reset — termasuk node yang barusan di-unhide oleh reset itu sendiri. **P1-E1** (detail di BUG BARU). Fix 1 baris: unpin loop harus iterasi `scope.nodes` (bukan `g.nodes`), atau buang `pinned/fx/fy` dari salinan `prev` di jalur reset.

### 4. Hub card volume dari `e.members.reduce` + `S.statsAll` → **VALID (kartu), sisa list masih $0.00**
- `visualizer.js:250`: kartu funder/bundle kini `usd(e.members.reduce((s,m)=>s+(S.statsAll.get(m)?.vol||0),0))` — tidak lagi bergantung `sel.foldedVol`. `S.statsAll` ada di payload runtime (Map 32.456 entri, dibangun `store.js:54`).
- **Bukti runtime entity scope (20/20 tanpa crash):** `hub.foldedVol = undefined, hub.vol = 0` di mode entity, tapi kartu menghitung: Cluster be41 **$4.120**, Cluster f70d **$16.084**, Bundle 0x2597… **$11.320**, Bundle 0x8ea1… **$351.096** — masuk akal (cocok dengan angka foldedVol Round C/D + volume anggota spesial).
- Konsistensi network: 20/20 hub, **0 pelanggaran** `card ≥ foldedVol` (identik kecuali cluster be41: card 4.120 vs foldedVol 3.338 — selisih = volume 2 anggota spesial yang digambar individual; semantik "volume seluruh anggota" masuk akal).
- **Sisa (P2-E2):** baris sub-layer (`visualizer.js:188`, `foldedVol ?? vol ?? 0`) di mode entity **tetap $0.00** — setengah P2-D2 tidak tersentuh. Card juga memakai volume **all-time** (abaikan range timeline) — konsisten dengan `group.vol` yang juga all-time, tapi tidak konsisten dengan vol wallet di kartu yang sama saat range aktif.

### 5. Raw preset funders/bundles tetap ON → **VALID**
- `PRESETS.raw` (`visualizer.js:111`) kini hanya mematikan `dex/tradeEdges/icons/labels/flow/etype_*`; funders+bundles+labelOnly tetap on.
- **Bukti runtime (dataset asli):** raw L150/300/600 → kinds `{group:20, funder:2, bundle:18, wallet:152/302/602}`, **group-orphan = 0, hub-orphan = 0, dangling = 0** di semua limit. Grup yatim `g:1…g:19` Round C dan "ladang murni mengambang" Round D tidak ada lagi: 20 struktur bintang cluster (grup+hub+2 anggota spesial) selalu tergambar dengan link fund.
- Sisa kosmetik: wallet individual tetap degree-0 (150/300/600) karena pool/edge sengaja dimatikan di raw — "ikatan cluster" penuh ala bubblemaps tetap tidak terbentuk untuk top-wallet (P2-D1 lama, kini by-design sebagian).

### 6. `ResizeObserver` → `window.__timeRO` → **BROKEN — fix mati (pola self-defeating yang sama dengan P2-C5)**
- `visualizer.js:448-449`: `window.__timeRO = new ResizeObserver(() => scope && drawTimeline()).observe($('#time'))` — **`observe()` mengembalikan `undefined`** (spec DOM), jadi `window.__timeRO` selalu `undefined` → guard `if (window.__timeRO) window.__timeRO.disconnect()` **tidak pernah jalan**.
- **Bukti runtime (mock RO sesuai spec, 3× mount visualizer bolak-balik):** observer dibuat = **3**, disconnect dipanggil = **0**, `window.__timeRO = undefined` sepanjang waktu. Akumulasi observer + closure `scope`/`g` per mount **tetap terjadi persis seperti P2-D4**; tidak ada perbaikan.
- Fix benar 2 baris: `window.__timeRO = new ResizeObserver(...); window.__timeRO.observe($('#time'));`

### 7. Paused restore `queueMicrotask(() => { g.setPaused(true); syncPanels(); })` → **VALID untuk label; layout beku tetap (setengah P2-D3)**
- **Bukti runtime (pola persis `visualizer.js:64` + `drawLeft:153` + `syncPanels:90-92`):** tepat setelah render sinkron tombol terbaca **"Freeze"** (stale); setelah microtask jalan → **"Resume"**, `paused=true`, `alpha=0` — label kini konsisten, dan semua `drawLeft` berikutnya konsisten "Resume". `setPaused(true)` juga memanggil `fit()` (userMoved=false) → view ter-fit rapi.
- Residual: alpha di-nol-kan sebelum tick pertama dan sim tidak pernah active → **layout reload-saat-paused tetap permanen di formasi seed phyllotaxis** (posisi tidak tersimpan di localStorage) sampai user klik Resume. Setengah kedua P2-D3 sengaja tidak dikerjakan — masih P2.

---

## BUG BARU

### P0
Tidak ada. Tidak ada crash di semua mode/limit/preset/harness; API + rebuild + seluruh aset statis sehat.

### P1-E1 — Reset tidak membersihkan pin node yang tersembunyi saat Reset (pin & posisi beku bangkit kembali) — *verdict fix D #3*
- **File:line:** `visualizer.js:368` (unpin loop hanya `g.nodes`) × `visualizer.js:69-71` (`rebuild` meng-copy `pinned/fx/fy` dari `prev` = `scope.nodes` lama yang memuat node tersembunyi).
- **Bukti runtime:** Skenario B (pin → eye-hide → Reset): 1 node kembali pinned `(1234,−777)` + chip "1 pinned" setelah Reset. Skenario D (pin group → funders OFF → Reset): `g:0` kembali pinned `(999,−999)`. Skenario A (pin visible → Reset): bersih — membuktikan akarnya adalah jangkauan loop, bukan salinan `prev` untuk node visible.
- **Dampak:** keadaan "beku di posisi lama" muncul kembali setelah Reset untuk node yang di-hide/disembunyikan layer — kontrak Reset ("kembali ke default") patah diam-diam.
- **Saran:** di handler reset, ganti loop ke `scope.nodes` (semua node scope lama), ATAU pada jalur reset lewatkan `pinned/fx/fy` saat menyalin `prev` (mis. `rebuild({ dropPins: true })`).

### P2-E1 — "Fix" RO timeline dead code; leak P2-D4 tetap utuh — *verdict fix D #6*
- `visualizer.js:449`: penugasan `window.__timeRO = new ResizeObserver(...).observe(...)` menyimpan `undefined`; guard disconnect di :448 tak pernah true. Bukti harness: 3 mount → 0 disconnect. Pola kegagalan identik dengan themeObs Round C (P2-C5 → fix Round D #6 untuk observer itu VALID, tapi pola yang sama dikopi ulang di sini dan mati).
- Dampak memory-only (elemen ter-observe detached); tetap layak diperbaiki karena 2 baris.

### P2-E2 — sisa P2-D2: sub-layer Funders/Bundle di mode entity masih $0.00
- `visualizer.js:188` memakai `it.foldedVol ?? it.vol ?? 0`; mode entity (`graph-data.js:68-77`) tidak pernah set keduanya (harness: `foldedVol=undefined, vol=0` → `$0.00`). Kartunya sudah benar (fix #4) — tinggal list ini. Fix sama seperti saran Round D: set `h.foldedVol` di mode entity, atau pakai formula card di list.

### P2-E3 (nit keluarga) — kartu hub/grup memakai volume all-time
- Kartu (`visualizer.js:250`) dan `group.vol`/`foldedVol` (`graph-data.js:128,138`) semuanya dari `S.statsAll` (all-time): saat user memasang range timeline, KPI/wallet in-range tapi kartu grup & sub-layer tetap all-time — beda angka berdampingan di panel yang sama. Pre-existing, tidak lebih buruk dari Round D; dicatat agar tidak dianggap regresi fix #4.

### Carried dari Round D (tidak disentuh fix D, diperiksa masih ada — tidak di-rehash)
- P2-D3 (layout reload-paused di formasi spawn) — setengah tersisa, lihat verdict #7.
- P2-D5 timeline hardcoded (`#222834/#1E6FF1/#1B2A44` masih di `visualizer.js:323-324`), P2-D6 hexBadge `rgba(7,8,12,.35)` (`ui.js:40`) + aksen emas white, P2-D7 nit space (`--text-3 #6C74BE`) — semua masih persis seperti Round D.

---

## VERIFIED-OK

1. **Syntax:** `node --check` 17/17 JS lolos; `python -m py_compile dataset.py server.py` lolos; semua view module + app.js ter-import bersih sebagai ESM di Node (stub `Path2D`/DOM; satu-satunya kegagalan import awal adalah ketiadaan global browser di Node, bukan kode).
2. **Runtime API:** server 8795 — rebuild startup sukses; `GET /api/dataset` 200 (gzip, 14.508.849 B, JSON valid); `POST /api/rebuild` 200 dalam 4,98 s dan payload pasca-rebuild valid; 24/24 aset statis 200; **server dimatikan, port bebas**.
3. **Meta dataset masuk akal:** `swaps_total` 290.719 = jumlah baris `swaps` persis; `priced 290.680 + unpriced 39` cocok; window swap 2026-06-21→2026-09-15; `label_counts` 16 label; 20 entitas (2 cluster + 18 bundle), 0 member index invalid, 0 wallet anggota >1 entitas; swaps per-wallet terurut ts, 0 field null; origins 737/737 by-address.
4. **Sweep buildScope semua mode (payload asli):** network L50/150/300/600 = 72-78 ms → visible 105-659n, **0 dangling link, 0 node tanpa `r`** di semua limit; mode token (HOOD, 718n/717l) 13 ms; 20/20 entity scope OK (0 dangling); wallet mode 1-5 ms; range filter (⅓–⅔ window) 49 ms — builder sehat di seluruh matriks.
5. **visibleGraph = identitas objek** dengan `scope.nodes` — dasar yang membuat fix #3 bekerja untuk node visible (dan memperjelas akar P1-E1).
6. **Expand/Open/More untuk semua kind konsisten:** wallet/entity → profil, token → halaman token, funder/bundle/group → entity scope; kind entity kini benar (verdict #1) dan URL tak dikenal (`?wallet=0x…0000`) tetap jatuh aman ke network scope tanpa crash.
7. **Freeze/Resume & Reset-saat-paused:** resume reheat 0.15 menghidupkan sim (102 ticks @L600); label tombol kini benar di semua jalur termasuk reload-paused (verdict #7).
8. **Preset Arkham/raw:** keduanya menghasilkan peta tanpa orphan/dangling (raw: verdict #5; Arkham = default all-on, 0 dangling di L50-600).
9. **Perf token mode:** skenario terberat lama (17,3 s) tidak ada lagi — HOOD 718n settle 1,1-1,2 s dengan decay baru.

---

## SKOR SIAP-SHIP: **7 / 10**

**Alasan:** Core sudah layak — dataset & API solid, keempat mode scope bersih (0 dangling/crash di seluruh matriks limit), P1 Round D #1 (expand entity) tuntas 1-baris dan benar, P1 #2 (perf) dipangkas ±50% dan skenario token terburuk lenyap, raw preset sudah structural-sound, paused-label benar. Yang menahan 3 poin: **(1) P1-E1** — fix Reset-unpin bocor untuk node tersembunyi (pin & posisi beku bangkit lagi; 1 baris: iterasi `scope.nodes` / buang pin dari salinan `prev`); **(2) fix RO adalah dead code** (P2-E1 — `observe()` mengembalikan undefined, leak tetap; 2 baris); **(3) P1-D2 belum tuntas di L600** (40+ ms/tick → churn 4–6 s tiap reheat; butuh decay adaptif/limitasi node) + setengah P2 kosmetik carried. Dua perbaikan pertama total < 5 baris kode — setelah itu aplikasi pantas 8,5–9.

**Pesan final: 2 dari 7 fix Round D gagal jalan (reset-unpin = P1 baru; RO = dead code), 4 valid, 1 setengah. Perbaiki P1-E1 + P2-E1 (total <5 baris), lalu ship.**
