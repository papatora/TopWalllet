# Round C — Audit Adversarial

Tanggal: 2026-09-16 · Scope: `Database Local only/html` (audit saja — tidak ada file proyek yang diubah).
Metode: baca line-by-line semua file JS/Python/CSS; `node --check` 17/17 JS lolos; `python -m py_compile dataset.py server.py` lolos; runtime `python server.py --port 8799` + `curl --compressed /api/dataset` (HTTP 200, 14.508.849 byte) lalu server dimatikan; harness Node (di `%TEMP%`, bukan di proyek) menjalankan `store.load()` + `buildScope()`/`visibleGraph()` asli terhadap payload produksi pada limit 50/150/300/600 + mode token/entity/wallet.

State DB saat audit: 32.456 wallet (semua aktif), **290.719 swap** (bertambah 39 dari Round A/B), 1.378 token, 18 bundle, 2 cluster, 737 origins, 16 label, 20 entitas. `price_points` masih kosong (fallback snapshot tetap jalan).

---

## VERDICT FIX ROUND B

### 1. graph-data.js `isPlain` v2 (SPECIAL_LABELS tanpa SNIPER/BUNDLER_SUSPECT) → **VALID**
- `graph-data.js:98-100`: SPECIAL_LABELS kini hanya label identitas (INSIDER/WHALE/…/SNIPER_BOT/…); SNIPER & BUNDLER_SUSPECT & CLUSTER_MEMBER* = foldable.
- **Bukti runtime (dataset asli, mode network):**
  - limit 150 → node kinds `{group:20, funder:2, bundle:18, wallet:152, token:17}`, 192 link, **0 dangling link, 0 node tanpa `r`**, sub "top 150 wallets · **20 grup receh** · top 17 pools". Build **67 ms**.
  - limit 50/300/600 → `{group:20 …}`, 110/72/77 ms; grup selalu 20 (2 cluster + 18 bundle).
  - **461 dari 463 anggota entitas terlipat** ke 20 group node; hanya **2 anggota individual** (w:22758 & w:23656 — CLUSTER_MEMBER + **MEV_BOT**, satu-satunya label SPECIAL di anggota). 0 anggota terlipat digambar ganda.
  - Group node `ref` = entity index ✓ (`graph-data.js:124,130`); integritas `S.entities[g.ref]` + `members[0]` valid untuk 20/20 grup (konsumen handler `more`/`expand` aman).
- Round B yang menyimpulkan "fold bundle mustahil (447/447 SNIPER)" kini terlampaui: seluruh 18 bundle punya grup. Tujuan de-clutter (guide.js:57) akhirnya hidup.
- **Efek samping besar:** lihat P1-C1 — fold + `visibleGraph` yang tidak mengenal kind `group` membuat preset raw runtuh.

### 2. hub `foldedVol` single-source → **PARTIAL** (kartu benar; dua konsumen `hub.vol` lupa disapu)
- Kartu hub `visualizer.js:245` kini `usd(sel.foldedVol || 0)` ✓: bundle `b:0x2597…` menampilkan **$11.320,16** (= jumlah vol anggotanya, cocok dengan angka Round B), cluster `f:cluster_be41` **$3.337,84** — dobel hilang. Radius hub `graph-data.js:180` tetap pakai `foldedVol` ✓.
- **REGRESI — sub-layer list:** `visualizer.js:183` masih menampilkan `usd(it.vol || 0)` untuk item funder/bundle, tapi `h.vol` **tidak pernah di-assign lagi** (dibuat `vol: 0` di `graph-data.js:37`, dan baris akumulasi `h.vol += vol` dihapus — kini hanya `h.foldedVol` di :138). Harness: `hub.vol non-zero: 0` untuk semua 20 hub, sementara foldedVol-nya $3,3K–$563K → **seluruh baris sub-layer Funders/Bundle menampilkan $0.00**. (Round B mencatat list ini "benar" karena saat itu `h.vol` masih ter-akumulasi — fix Round B justru mematikannya lagi.) → P1-C2.
- **Sisa lama:** mode entity tidak pernah set `foldedVol`/`vol` hub (harness entity 0: `['f:cluster_be41', 0, 0]`) → kartu hub di scope entity tetap "Volume grup est. $0.00" (P1-B2 Round B tak tersentuh di scope ini) → P2-C3.

### 3. Delapan handler ter-wiring → **VALID** (semua hidup; satu celah kecil baru)
- Semua ada di chain `visualizer.js:411-428`: `group` (:411 `st.grouped=!st.grouped; drawRight()`), `unpin` (:412), `range-clear` (:413), `toggle-flow` (:414), `unhide` (:415), `open` (:416), `more` (:417-422), `expand` (:423-428).
- **Urutan/tabrakan:** aman. Branch bernama (eye → explayer → resetviz → fs → hide-\*/show-\* → collapse → focus → freeze → preset → mode → copy) semuanya `return` dan tidak ada satu pun elemen yang membawa dua atribusi aksi sekaligus (dicek satu per satu: chip `data-preset` tidak punya `data-act`; tombol Hide di kartu node pakai `data-eye` dan tertangani lebih dulu dengan deselect yang benar; `data-copy`/`data-mode`/`data-layer`/`#limit` tidak menabrak).
- **`more` untuk kind 'group' tidak crash** — VERIFIKASI: `graph-data.js:130` memang `ref: ei` (entity index), dan harness membuktikan `S.entities[g.ref].members[0]` valid 20/20 (badRef 0, badMore 0). Catatan kecil: `members[0]` itu anggota PERTAMA entitas, yang bisa jadi justru anggota spesial yang tidak ikut grup — tetap navigasi yang masuk akal, bukan crash.
- **Celah:** `expand` tidak punya cabang untuk kind **'entity'** (node wallet terdaftar di known_entities.json) → tombol "+ Expand" mati untuk node itu. Dulu dormant; kini **live**, karena `data/known_entities.json` berisi 2 entri (Null address & Burn address, type CONTRACT) dan harness menemukan node kind `entity` di scope wallet → P2-C4.

### 4. INDUKAN di address.js → **VALID**
- `address.js:56` (panel Overview): guard `(S.origins && S.origins[w[0]]) ? IIFE : ''`. Escaping `\"` di dalam nested template adalah escape legal (menghasilkan `"`); `node --check` lolos dan pola yang sama sudah dipakai di banyak tempat lain.
- Runtime: 737/737 entri origins ter-hit by address; 0 hit by index (bug lama tetap mati); **31.719 wallet tanpa origins → blok kosong, tanpa crash** (jalur false-string). Origin kind MINT (`senders: []`) → `join(' · ')` = '' → fallback teks "mint 0x0" tampil benar.
- Janji guide.js:69-70 "kartu node & halaman profil" kini benar-benar terpenuhi (kartu: visualizer.js:248-258; profil: address.js:56).

### 5. evidence.js (duplikat AIRDROP dihapus, guard null) → **VALID**
- Duplikat `AIRDROP_FARMER` (Round A P2-5 / Round B P2-B7) sudah hilang; chain kini SNIPER → BUNDLER_SUSPECT → DEV → INSIDER(3 kind) → `AIRDROP_FARMER || PHISHING_TARGET` (:39-45, guard `(s && s.spread …)` :41) → CT_ATTRIBUTED → CLUSTER_MEMBER\* → MEV_BOT → SMART_TRACKER → fallback — semua branch lain utuh.
- Guard `(si || {}).kind` di :30 ada. Bukti payload: 704 CONFIRMED_INSIDER (semua `senders`, 0 sender null), 17 MINT_ALLOCATION (semua `mint`), **2.749 INSIDER legacy tanpa `kind` — seluruhnya punya `sell_count`** (min 1) → jatuh ke else-branch yang benar di evidence.js:35-36 maupun token.js:39; tidak ada jalur yang menghasilkan "undefined".

### Follow-up P2 Round B (cek cepat)
- **P2-B1 (grup tak ikut filter layer) — TIDAK DIJALANKAN, kini kritis** → naik grade jadi P1-C1.
- **P2-B2 (freeze/resume) — PARTIAL**: `graph.js:158` kini `setPaused(false) → sim.reheat(0.15)` → Resume benar-benar menghidupkan sim lagi (alpha 0.15 > alphaMin, `frame()` tick). Sisa: reload saat `paused=true` masih membekukan layout di posisi spawn phyllotaxis (microtask `setPaused(true)` meng-nol-kan alpha setelah `rebuild()` sinkron) dan label tombol yang dirender sebelum microtask tetap "Freeze" → P2-C6.
- **P2-B3 (themeObs leak) — FIX-nya ILUSI**: `graph.js:31` menuliskan `this.themeObs = new MutationObserver(cb).observe(...)` — `observe()` mengembalikan `undefined`, jadi `this.themeObs` = undefined dan `destroy()` (:44) `this.themeObs?.disconnect()` = no-op yang tidak error. Observer tetap bocor per mount → P2-C5.
- **P2-B4 (INDUKAN profil) — FIXED** (lihat verdict 4).
- **P2-B5 (dua `}` liar tokens.css) — FIXED**: cek keseimbangan brace skripted: 4 file CSS final depth 0, tanpa depth negatif.
- **P2-B6 (.pill/hexBadge) — SEBAGIAN**: `.pill` (components.css:152) kini `var(--chip-bg, …)` dan `--chip-bg` terdefinisi di 3 tema ✓; **hexBadge (ui.js:40) masih `fill="rgba(7,8,12,.35)"`** tanpa override tema ✗.
- **P2-B7 (duplikat AIRDROP) — FIXED** (lihat verdict 5).

---

## P0/P1/P2 BARU

### P0
Tidak ada. Tidak ditemukan crash baru; kelima jalur fix Round B bekerja pada payload asli.

### P1-C1 — `visibleGraph` tidak mengenal kind 'group' + bond-collapse mengabaikan grup → **preset "Bubblemaps raw" runtuh total** (eskalasi P2-B1, material lebih parah setelah fold v2)
- **File:line:** `graph-data.js:194-201` (`vis()` tanpa cabang `kind==='group'`) dan `:206-216` (bonds hanya dibangun dari link fund/bundle yang `l.s`-nya node wallet; link `group→hub` di-skip dari mekanisme collapse).
- **Bukti runtime (limit 150, dataset asli):**
  - Preset raw (funders+bundles+dex+tradeEdges OFF): **172 node / 2 link** — **168 node degree-0**, termasuk **20 group node yatim** (`g:1`…`g:19`) dan ±148 wallet individu melayang tanpa satu garis pun. 2 link yang tersisa cuma bond antara 2 wallet MEV_BOT spesial.
  - Sebelum fold v2 (Round B), raw masih "memegang" cluster karena semua anggota individual → bond-star per hub terbentuk. Kini anggota terlipat jadi group node, group terhubung ke hub dengan link `fund` yang mati saat hub disembunyikan, dan bond map hanya menerima 1 "anggota" (group itu sendiri) → tidak ada bond dibuat.
  - Skenario lain: **Funders OFF** (bundle ON) → g:1 (cluster_f70d) degree 0 yatim; g:0 bertahan (deg 2) hanya karena bond ke 2 anggota spesial.
- **Dampak:** preset flagship yang dijanjikan guide.js:66 ("cuma wallet + ikatan cluster") menampilkan ladang gelembung tak terhubung; toggle layer Funders/Bundles meninggalkan grup yatim. Ini tampilan pertama yang dilihat user yang memilih "Bubblemaps raw".
- **Saran:** (a) di `vis()`: `if (n.kind==='group') return n.ref!=null && (S.entities[n.ref]?.kind==='cluster' ? show.funders : show.bundles);` (b) perlakukan link `group→hub` sebagai collapsible: saat hub hidden, boncatkan group node ke anggota spesial lain di hub yang sama (atau jadikan group mewakili seluruh anggota terlipat + bond ke spesial).

### P1-C2 — sub-layer list funder/bundle: semua $0.00 (regresi akibat fix #2 Round B)
- **File:line:** `visualizer.js:183` (`usd(it.vol || 0)`) vs `graph-data.js:37,138` (`vol: 0` dibuat, `h.vol` tidak pernah ditambah; hanya `h.foldedVol`).
- **Bukti runtime:** ke-20 hub di scope network punya `vol === 0` sementara foldedVol riil $3.338–$563.237 (contoh `b:0xbcb5…` foldedVol $563.237 → list menampilkan **$0.00**).
- **Dampak:** panel Tampilan → chevron Funders/Bundle menampilkan daftar item dengan kolom volume kosong semua; satu-satunya tempat `hub.vol` masih dikonsumsi — lapangan `vol` pada hub kini dead field.
- **Saran:** ganti ke `usd((it.foldedVol || 0) + (it.vol || 0))`, atau agregasi `h.vol` lagi di buildScope dan pakai itu konsisten (jangan dua-duanya).

### P2-C3 — kartu hub scope entity tetap $0.00 + KPI "Trace overview" tidak menghitung volume terlipat (konsistensi angka)
- `buildScope` mode `entity` (graph-data.js:68-77) tidak pernah set `foldedVol`/`vol` hub → kartu "GRUP — berisi 14 wallet · Volume grup est. **$0.00**" walau anggota punya volume (sisa P1-B2 Round B, tidak tersentuh fix #2).
- KPI kiri: `drawLeft` (visualizer.js:114-115) menjumlah `vol` hanya dari node wallet/entity → di network limit 150: **$91,05J terhitung vs $4,69J volume grup TIDAK terhitung** (~5% undercount); KPI "Wallets" menampilkan 152 padahal peta mewakili 152 + 461 anggota terlipat. Perubahan ini by-design fold, tapi angka ringkasan berubah diam-diam begitu grup terbentuk.
- **Saran:** entity-mode: `h.foldedVol = e.members.reduce((a,m)=>a+(S.statsAll.get(m)?.vol||0),0)`; trace overview tambahkan `group.vol` (dan sebut "wallet individual" pada KPI Wallets, atau +folded).

### P2-C4 — tombol "+ Expand" mati untuk node kind 'entity' (kini live)
- `visualizer.js:423-428`: cabang `expand` hanya `wallet`/`token`/`funder|bundle|group`. Kind `entity` (wallet yang address-nya terdaftar di `data/known_entities.json` — file kini berisi 2 entri CONTRACT: `0x0000…0000`, `0x0000…dead`) tidak punya cabang → klik tanpa efek, tanpa feedback. `more`/`open`/tooltip sudah menangani kind itu dengan benar (ref = wallet index).
- **Saran:** tambah `else if (g.sel.kind === 'entity') location.hash = walletHref(g.sel.ref);` (atau sembunyikan tombol Expand untuk kind ini).

### P2-C5 — "fix" MutationObserver tema adalah dead code; leak P2-B3 masih ada
- `graph.js:31`: `this.themeObs = new MutationObserver(...).observe(...)` — `observe()` mengembalikan `undefined` → `this.themeObs` selalu undefined; `destroy()` :44 `this.themeObs?.disconnect()` = no-op senyap. Observer abadi per mount visualizer tetap ada (menahan instance lama + baca getComputedStyle saat ganti tema).
- **Saran:** `this.themeObs = new MutationObserver(cb); this.themeObs.observe(...)`.

### P2-C6 — reload saat paused masih membekukan layout di posisi spawn + label tombol stale
- `visualizer.js:64` `queueMicrotask(() => g.setPaused(true))` berjalan setelah `rebuild()` (:442) yang reheat 0.9 → microtask men-nol-kan alpha sebelum satu tick pun → node permanen dalam formasi phyllotaxis; `drawLeft()` (:148) sudah dirender dengan `g.paused=false` → tombol terbaca "Freeze" padahal state paused. (Resume-click sendiri kini benar — verdict P2-B2 partial di atas.)
- **Saran:** setelah microtask, render ulang `drawLeft()`; idealnya tunda reheat bila `saved.paused` (bangun sim hanya saat resume pertama).

### P2-C7 — tema white: ring seleksi/hover/focus node putih-di-atas-terang
- `graph.js:257` ring seleksi `'#FFFFFF'`, hover `'rgba(255,255,255,.5)'`; `graph.js:280` ring fokus `'#FFFFFF'`. Stage white theme = `--bg-sunk #ECEEF2` (terang) → **indikator node terpilih/disentuh nyaris tak terlihat** (fill node sendiri semi-transparan, ring putih lenyap di background). Round A/B hanya menangani drawEntity/drawHub; ring-interaksi ini terlewat.
- **Saran:** pakai `c.text`/`c.blue` per tema (sudah ada di `this.c`), bukan putih hardcoded.

### P2-C8 — default view: ±27 bubble top-wallet tanpa satu edge pun
- Harness (default show, limit 150/300/600): 27/86/160 node degree-0 — wallet top yang pool-nya gugur dari POOL_CAP 20 + filter `tokCount>=2` (graph-data.js:116-118) tidak punya trade link. Sudah ada sebelum fold v2, tapi kini proporsional lebih menonjol (461 wallet lain lenyap ke 20 grup, sementara floaters tetap).
- **Saran (opsional):** beri edge tipis ke pool terbaik wallet di luar top-20, atau tahan wallet tanpa-edge dari gambar (masih tampil di address list).

### Nit (tidak digrade)
- Toggle "Ungroup/Group clusters" (visualizer.js:267): label berubah benar, tapi `is-on` dipasang saat **tidak** dikelompokkan (`${st.grouped ? '' : 'is-on'}`) — terbalik dari konvensi chip preset (is-on = keadaan aktif).
- `unpin` (:412) hanya membersihkan pin node yang visible; node hidden yang pernah di-pin menyimpan `fx/fy` dan kembali ter-pin saat di-show.
- Tombol primer "More info" tanpa seleksi = klik tanpa efek/feedback.
- guide.js:47 "klik FLOW untuk ganti All/In/Out" — kontrol nyata hanya all/off (tidak ada tri-state In/Out).
- guide.js:57 "dilipat jadi SATU bubble sebesar total volume anggotanya" — kini realitasnya dua bubble (grup putus-putus + hub), ukuran hanya dari volume anggota **terlipat** (vol anggota spesial tidak masuk). Cukup dekat, tapi tidak persis.
- Hardcoded warna non-tema yang tersisa (kosmetik): timeline SVG `#222834/#1E6FF1/#1B2A44/#667085` (visualizer.js:318-320 — bar out-of-range #1B2A44 gelap di panel putih), scrollbar `#232A37` (base.css:19), `.al-cluster` tint `rgba(255,255,255,.015)` (views.css:114 — tak terlihat di kedua tema), hexBadge (P2-B6 sisa, ui.js:40). `--blue-line` didefinisikan tapi tak pernah dipakai.
- Reset masih memanggil `applyVisibility` dua kali (di dalam `rebuild` + di handler :363) — kerja ganda, tak terlihat user (nit Round B, tetap).

---

## VERIFIED-OK

1. **Syntax:** `node --check` 17/17 JS lolos (termasuk template literal bersarang `\"` di address.js:56 dan nested ternary INSIDER di token.js:37-40); `python -m py_compile dataset.py server.py` lolos; keseimbangan brace 4/4 file CSS bersih (P2-B5 confirmed fixed).
2. **Runtime API:** server naik di 8799, rebuild startup sukses, `GET /api/dataset` HTTP 200 (gzip, 14,5 MB, 290.719 swap), JSON valid; server dimatikan setelah pengujian.
3. **buildScope 4 mode** (harness, payload asli): network limit 50/150/300/600 sukses (0 dangling link, 0 node tanpa `r`); token (769 node — tetap abaikan `limit`, P2-11 lama); entity 0 (15 node/39 link); wallet 0 (196 node/201 link, memuat satu node kind `entity` — bukti known_entities kini terpakai). `visibleGraph` default konsisten (0 dangling).
4. **Hunt (b) sub-layer hide:** eye per-item di sub-layer memakai id node yang sama dengan `st.hidden`; `vis()` cek `hidden` lebih dulu (graph-data.js:195) → pool/hub hilang dari peta, chip "N hidden · show" muncul, `unhide` membersihkan semua. Sinkron dengan applyVisibility.
5. **Hunt (c) fold vs trade edges:** **0 anggota terlipat yang memperdagangkan pool top-17 yang dipertahankan** — tidak ada edge yang hilang dari peta (pool yang hanya diperdagangkan anggota terlipat memang tidak pernah masuk kandidat keepToks karena dihitung dari `rankedSet` saja). Scope volume menyusut diam-diam → dicatat sebagai P2-C3, bukan kehilangan edge.
6. **Hunt (d) guide vs implementasi:** INDUKAN kartu ✓ & profil ✓; FREEZE/Resume ✓ (resume kini benar); Group/UNGROUP ✓; sub-layer ✓; RESET ada di UI (tidak dijanjikan/dokumentasikan di guide — hanya nit). Mismatch teks: "All/In/Out" dan "SATU bubble" (lihat Nit).
7. **Hunt (e) konsistensi search:** recount label per-row vs `meta.label_counts` = **0 mismatch bolak-balik untuk 16 label**; facet explorer, tab LABELS, dan global search (app.js:88) konsisten dengan `S.labelIndex` (keduanya berasal dari sumber yang sama, derived termasuk).
8. **Hunt (f) kinerja:** buildScope network = 110/67/72/77 ms untuk limit 50/150/300/600 (satu pass `rankedAll` atas 290K swap + `statsAll` pre-computed); force sim O(n²) pada 659 node visible @limit 600 masih ringan; **bundle 100+ wallet = 1 group node + 1 hub** (fold bekerja seperti diharapkan). Mode token (768 node) tetap skenario terberat — P2-11 lama, terdokumentasi.
9. **Hunt (g) store.js:** `S.addrIndex` (Map addr→idx, address lowercase dari dataset) dipakai benar di address.js:10 dan visualizer.js:28; per-wallet swap list terurut ts (query `order by ts`) → `stats().first/last` dan "Active since" benar; 0 wallet anggota >1 entitas (`findIndex`-first graph-data.js:143 tetap harmless).
10. **Hunt (h) sisa hardcoded gelap:** `rgba(16,19,26/#07080C/#0A0C11` di CSS kini hanya sebagai **nilai :root/fallback** yang benar (tokens.css:4,26,31; fallback `var(--viz-panel,…)` di views.css). Sisa hardcoded fungsional: hexBadge + timeline SVG + scrollbar + `.al-cluster` (daftar di Nit) — tidak ada yang membuat komponen utama tak terbaca selain P2-C7 (ring interaksi).
11. **Hunt (i) CSS var lintas-tema:** audit skripted semua `var(--…)`/`css('--…')` di 4 CSS + 17 JS vs definisi per blok tema: **0 variabel dipakai-tapi-tak-terdefinisi** di salah satu tema (`--c/--h/--min/--n` = vars scoped komponen; `--stars-a/b` terdefinisi di blok `#spacefx` tema space; key dinamis `--c-<label>` semuanya terdefinisi di :root). Override white/space tidak mereferensikan var yang tidak ada.
12. **Data pendukung lain:** INSIDER evidence 3 bentuk (2749 legacy + 704 CONFIRMED + 17 MINT) semua punya jalur renderer yang benar (evidence.js + token.js); 0 sender null; origins 737/737 by-address; swaps sorted; `label_counts` = rows.
