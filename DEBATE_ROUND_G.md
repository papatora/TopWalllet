# Round G — Verifikasi Konvergensi (FINAL)

Tanggal: 2026-09-16 · Scope: `Database Local only/html` (audit saja — tidak ada file proyek yang diubah).
Metode: verifikasi fix pasca-Round F di kode baris-per-baris; `node --check` 17/17 JS + `python -m py_compile` OK (Python 3.14.4); **runtime `python server.py --port 8797`** — `/api/dataset` HTTP 200 (14.508.849 B gzip, JSON valid), `POST /api/rebuild` HTTP 200 (`{"ok":true,"built":"2026-09-15T22:09:23+00:00"}`), 25/25 aset statis 200, **server dimatikan lagi (port 8797 bebas, diverifikasi)**; harness Node di `%TEMP%\roundg` menjalankan `store.load()` + `buildScope()`/`visibleGraph()`/`ForceSim` ASLI terhadap payload produksi (4 mode × 3 preset); **uji render empiris headless Edge** — (1) halaman uji var() SVG, (2) screenshot aplikasi live `#/visualizer` + crop strip timeline.

State DB: 32.456 wallet, 290.719 swap, 1.378 token, 2 cluster + 18 bundle = 20 entitas, 737 origins, 16 label. `meta.built` = rebuild Round G (fresh).

---

## TUGAS 1 — VERDICT FIX TERAKHIR (pasca-Round F): **7/7 VALID**

### a. Timeline pakai token tema — **VALID, terbukti di runtime render**
- `visualizer.js:323-325`: baseline `style="stroke:var(--line)"`; bar in-range `fill="var(--blue)"`, out-of-range `fill="var(--line-strong)"`; tick text `style="fill:var(--text-3)"` — **0 hex tersisa** (hanya rect seleksi `rgba(30,111,241,.16)` yang tint biru netral, aman di 3 tema).
- **Catatan penting yang diselesaikan Round G:** bar memakai `fill="var(…)"` sebagai **atribut presentasi SVG** (bukan `style=`) — pola yang secara historis tidak didukung sebagian browser. **Uji empiris headless Edge** (halaman uji + screenshot app live): atribut-var dirender **identik** dengan style-var dan kontrol hex; screenshot `#/visualizer` live menunjukkan seluruh bar biru, baseline terlihat, tick redup. Bukan bug di browser target (Chromium/Edge modern; Firefox juga lama mendukung). Terverifikasi juga hierarki white: bar out-of-range kini abu terang (#C7CEDA via `--line-strong`) < biru in-range — P2-D5 tuntas benar.

### b. components.css `.seg-btn.is-active` / `.pill` / `.fchip` — **VALID**
- `components.css:55,58,60`: `background:var(--seg-active-bg,var(--panel-3)); color:var(--seg-active-text,var(--text))` (3 varian seg). `.pill` (:155) `background:var(--chip-bg,rgba(7,8,12,.35))`. `.fchip` (:85) `background:var(--chip-bg,rgba(7,8,12,.6))`. Bonus: override podium white `.rank.is-1/2/3` (:106-108, emas/perak/perunggu gelap) — sisa P2-D6 aksep aksen juga tuntas.

### c. tokens.css overrides white/space — **VALID dan konsisten**
- `:root` (:27-31) + `[data-theme="white"]` (:40-44): `--chip-bg`, `--seg-active-bg/text`, `--ent-fill/#FFFFFF`, `--ent-text/#141922`. `[data-theme="space"]` (:57): `--chip-bg`; seg-active/ent mewarisi `:root` yang me-resolve benar (space gelap → ent putih terang, konsisten dark). Plus `[data-theme="white"/"space"] .fchip` dan `[data-theme="white"] .seg-btn.is-active` (:217-219). 0 var dipakai tanpa definisi di ketiga tema.

### d. ui.js hexBadge — **VALID**
- `ui.js:40`: `style="fill:var(--chip-bg,rgba(7,8,12,.35))"` — memakai **bentuk `style=`** (bukan atribut), jadi var() dijamin bekerja; stroke tetap per-jabatan. Podium white kini chip terang + teks gelap.

### e. graph.js — **VALID (semua 4 sub-item)**
- `drawEntity` (:334,336) `c.ent_fill || '#F4F6FA'` / `c.ent_text || '#07080C'`; `this.c` diisi `--ent-fill/--ent-text` di constructor (:30) dan di-refresh observer (:31).
- Ring seleksi `this.c.text` (:257), ring fokus `this.c.text` (:280).
- `themeObs` disimpan lalu observe dipisah dua pernyataan (:31-32); `destroy()` disconnect (:44).
- `setPaused(false)` → `sim.reheat(0.15)` (:158).

### f. visualizer.js — **VALID (semua 4 sub-item)**
- `expand` kind entity → `#/visualizer?wallet=${S.wallets[g.sel.ref][0]}` (:433) — ref entity memang index wallet (harness: `S.addrIndex.get(S.wallets[ref][0]) === ref` untuk semua node entity).
- Reset unpin iterasi `(scope?.nodes || [])` **sebelum** rebuild (:368) — replikasi harness pin(2)→hide(1)→reset: pre-reset pin tersimpan di scope (benar-benar kondisi lama), post-reset **0 pinned** di seluruh `scope.nodes`.
- `PRESETS.raw` (:111) tidak menyentuh `funders`/`bundles` — harness: raw L50–600 selalu {group:20, funder:2, bundle:18} + 0 group-orphan + 0 dangling.
- Paused restore **dihapus** (:64 hanya komentar; grep `saved.paused` = 0; `setPaused` hanya di reset `false` dan toggle Freeze). `persist()` masih MENULIS key `paused` — vestigial, harmless.

### g. token.js + evidence.js — **VALID**
- `token.js:37-40`: INSIDER 3-cabang — `MINT_ALLOCATION` → "alokasi mint dari 0x0", `CONFIRMED_INSIDER` → "transfer murni dari N pengirim", legacy → "N sells without a buy" (payload: 704 CONFIRMED / 17 MINT / 2.749 legacy semuanya punya jalur).
- `evidence.js:23-37`: mint `nf(d.mint?.amount || 0)` + **"unit token"** (:25); guard `(si || {}).kind` (:30) dan `(s && s.spread…)` (:41); **0 duplikat AIRDROP_FARMER** (satu cabang `AIRDROP_FARMER || PHISHING_TARGET` :39-45).

---

## TUGAS 2 — RUNTIME & KONVERGENSI

### Runtime — PASS semua
1. `node --check` 17/17 JS; `python -m py_compile server.py dataset.py` OK.
2. Server 8797: `/api/dataset` 200 (14.5 MB), `/api/rebuild` 200, 25/25 aset statis 200; server dimatikan, port bebas.
3. **Harness buildScope (payload produksi 290.719 swap) — ALL CHECKS PASS:**
   - network L50/150/300/600 × preset {default, raw, funders-off}: 0 dangling, 0 node tanpa `r`, 0 group-orphan di **semua** kombinasi; raw selalu memuat 20 grup + 2 funder + 18 bundle (struktur bintang tak pernah runtuh).
   - token mode (terbesar 718n/717l, tengah, terkecil 2n/1l) × 3 preset: bersih.
   - entity 20/20: 0 dangling; formula kartu `members.reduce` finite untuk semua.
   - wallet mode (top-vol + 1-swap): bersih; range ⅓–⅔ window: 211n/166l bersih.
   - ForceSim L150: settle 138 ticks, 0 NaN; resume 0.15 settle.
   - Semantik handler `expand`/`more` direplikasi untuk SEMUA node kind di scope L150 × 3 preset: 0 referensi invalid.
4. **Smoke test browser sungguhan (headless Edge):** aplikasi boot penuh di `#/visualizer` — nav, panel kiri (Trace overview $95.74M / 152 wallets / 17 tokens), graf terlayout, address list, chips, timeline — semuanya tergambar benar (screenshot diperiksa visual).
5. Konsistensi data ulang-cepat: label/conf length mismatch **0**; `label_counts` vs rows roundtrip **0 mismatch** (16 label); `w[4]` (CT name) selalu string → jalur `.toLowerCase()` di app.js/explorer.js aman; 0 wallet dengan confidences kosong → `Math.max(...w[3])` tidak pernah `-Infinity` di data ini.

### Hunt bug BARU (belum pernah disebut A–F) — hasil jujur

### P0 — TIDAK ADA. P1 — TIDAK ADA.

Hal-hal "mencurigakan" yang diperiksa dan **terbukti bukan bug**:
- `fill="var(…)"` atribut presentasi SVG (visualizer.js:324) — **terbukti bekerja** di browser target via uji render empiris (bukan asumsi spesifikasi). Lihat verdict 1a.
- `charts.js` `mount()` ResizeObserver per-draw — siklus el↔RO↔closure tidak di-root (berbeda dari `window.__timeRO`) → ter-koleksi GC, bukan leak.
- Route regex `/token|/address` — punya flag `i`, jadi URL checksummed (EIP-55) tetap match; view me-lowercase sebelum lookup.
- `TRADER_COLS` key `w` ganda (Trader & W/L) — sort "W / L" memakai `s.w` (jumlah menang), masuk akal, bukan crash.
- `groupOf.has('g:' + findIndex-first)` (graph-data.js:143) — harmless di dataset ini (0 wallet anggota >1 entitas), carried.

P2 kosmetik BARU (semua trivial, non-blocking, tidak ada yang fungsional):
1. **`is-off` kelas mati** — `address.js:92` memancarkan `class="fchip is-off"` tapi tidak ada rule CSS `.is-off` di 4 file CSS. State toggle tetap terlihat (warna `--c` berubah ke `--text-3` + ikon X hilang), jadi hanya kelas tak terpakai. 1 baris hapus atau tambah rule.
2. **Dashboard "Largest swaps" sort 290K baris per mount** — `dashboard.js:17` `S.all.filter(...).sort(...)` satu-shot per kunjungan dashboard (puluhan ms, sekali per navigasi). Micro-perf, tidak terasa di pemakaian normal.
3. **Caret search explorer lompat ke akhir** — `explorer.js:132` (dan pola serupa `visualizer.js:443`) me-restore fokus tapi menaruh kursor di akhir input setelah redraw; mengedit kata di tengah query menggeser karet. Micro-UX, pre-existing sejak awal namun memang belum pernah dicatat A–F.

### Carried dari A–F (tidak memburuk, tidak di-rehash detail)
- **P1-D2 (setengah, perf-only):** force O(n²) — L600 (659n) ±7,5 s churn per reheat; token besar L600 ≈ 9 s (angka Round F; kode `force.js` tak berubah sejak). Limitasi diketahui, bukan blocker.
- **P2-E2:** sub-layer Funders/Bundle di **mode entity** masih $0.00 (`visualizer.js:188`, hub entity tak punya `foldedVol`/`vol` — direkonfirmasi harness: `foldedVol=undefined, vol=0`; kartunya benar). 1 baris fix.
- **P2-E3:** kartu hub/grup memakai vol all-time, tidak mengikuti range timeline.
- Teks Guide: "SATU bubble" (:57) dan raw "cuma wallet + ikatan cluster" (:66) tidak persis; KPI "Wallets" tidak menghitung anggota terlipat.
- Nit tema micro: scrollbar `#232A37` (base.css:19), dot-grid & `.al-cluster` tint putih invisible di white, highlight chart `#fff .04` invisible di white, tanpa blur di `.pop/.viz-tip/.toast` di space, `--text-3` space kontras ~3,4:1.
- `unpinAll()` (graph.js:91) dead method; Reset memanggil `applyVisibility` 2×; `persist()` menulis key `paused` vestigial.

**KONVERGEN — tidak ada P0/P1 baru.** Semua temuan baru Round G adalah P2 kosmetik (3 item trivial di atas). Setelah pencarian menyeluruh (baca ulang 17 JS + 4 CSS + server.py + dataset.py + index.html, harness datapath penuh, smoke test browser, dan pengujian render empiris atas satu-satunya mekanisme baru yang berisiko), tidak ada cacat fungsional yang belum tercatat A–F.

---

## TUGAS 3 — SKOR SIAP-SHIP: **9 / 10**

**Alasan:** Seluruh 7 fix terakhir terverifikasi valid — bukan cuma baca kode, tapi sebagian dibuktikan di runtime render sungguhan (timeline tema tergambar benar di screenshot aplikasi live; var()-di-atribut SVG yang menjadi satu-satunya risiko mekanis baru terbukti bekerja). Runtime bersih menyeluruh: syntax 17/17 + py_compile, API + rebuild + 25 aset 200, harness 4 mode × 3 preset 0 dangling/0 no-r/0 orphan, semantik semua handler tervalidasi terhadap payload asli, dan aplikasi boot penuh di browser tanpa regresi. Yang memotong 1 poin hanyalah warisan terdokumentasi yang tidak memburuk: perf L600 (7–9 s churn, perf-only), sub-layer entity $0.00 (1 baris), beberapa teks Guide, dan nit kosmetik tema — semuanya P2 yang bisa dipoles menyusul tanpa risiko.

### Sisa yang TIDAK bisa diperbaiki di sisi explorer (butuh data VPS / keputusan user):
1. **`price_points` kosong → semua USD lewat fallback harga snapshot** (dan sparkline hanya untuk pool terkalibrasi + catatan "rescaled") — butuh backfill `price_points` di pipeline VPS.
2. **39 swap unpriced/outlier** — keputusan threshold outlier/backfill harga; explorer hanya bisa menampilkan "unpriced".
3. **TRADER_COVERAGE_GAP (wallet insider yang terbukti benar membeli)** — butuh re-enrichment/scan ulang di VPS; label & deskripsinya sudah benar di sisi explorer.
4. **`known_entities.json` hanya berisi 2 entri kontrak (Null & Burn), tanpa CEX Robinhood Chain** — butuh data address CEX/bridge riil; UI sudah jujur ("No CEX address is registered…").
5. **P1-D2 perf L600 (O(n²) force sim)** — teknisnya bisa di sisi explorer, tapi butuh keputusan desain (Barnes-Hut/decay adaptif/cap node vs kesederhanaan kode); opsi mitigasi saat ini = default cap 150 (sudah default).
6. **Keputusan produk untuk sisa polish P2** (sub-layer entity $0.00, teks Guide "SATU bubble"/"raw", KPI folded, nit tema micro) — murni prioritasi, bukan hambatan teknis.

---

## PESAN FINAL

**SKOR 9/10 — KONVERGEN.** Tidak ada P0/P1 baru; 3 P2 kosmetik baru semuanya trivial (kelas mati, micro-perf dashboard, caret search). Semua fix terakhir valid dan terbukti sampai ke render. Aman di-ship sekarang; sisa 1 poin adalah polish terdokumentasi + hal yang memang harus dielesaikan di VPS (price_points, re-enrichment, known_entities) atau lewat keputusan user (perf L600).
