# Round B — Audit Adversarial

Tanggal: 2026-09-16 · Scope: `Database Local only/html` (audit saja, tidak ada file proyek yang diubah).
Metode: baca line-by-line semua file; `node --check` 17/17 file JS lolos; `python -m py_compile dataset.py server.py` lolos; runtime `python server.py --port 8794` + `curl --compressed /api/dataset` (HTTP 200, 14.508.848 byte, JSON valid) lalu server dimatikan; harness Node menjalankan `store.load()` + `buildScope()`/`visibleGraph()` asli terhadap payload produksi (network limit 150, entity, token, wallet).

State DB saat audit: masih sama dengan Round A (price_points kosong → 290.680 swap terhargai via fallback snapshot, 39 outliers).

---

## VERDICT FIX ROUND A

### 1. P0-1 dataset.py `snap` tertimpa → **VALID**
- `dataset.py:89` kini `scale, snap_px, last = 1.0, tokens[i][3], rows[-1][1]`; pemakaian di `:90-92` memakai `snap_px`; `snap` (:59) tetap dict dan dipakai `:121` (`sp = snap.get(ta)`). Guard pembagian aman: `if snap_px and last` menyaring None/0 sebelum `last / snap_px`.
- Bukti runtime: `server.py --port 8794` rebuild sukses di startup, `/api/dataset` 200, `priced=290680 unpriced=39 outliers=39` — jalur fallback jalan tanpa AttributeError.

### 2. P0-2 Reset handler `draw()` → **VALID**
- `visualizer.js:357-368`: `persist(); rebuild(); applyVisibility(0.5); g.userMoved = false; g.fit(); syncPanels(); toast(...)`.
- Scope: `rebuild` (def `:67-75`) dan `applyVisibility` (def `:76-82`) keduanya const di closure `render()`, handler click juga di `render()` → tidak ada ReferenceError.
- Urutan benar: `rebuild()` me-reset `st.range` → scope penuh, set `g.fitted=false; g.userMoved=false` (:72), lalu `applyVisibility(0.9)` → `setGraph(reheat 0.9)`. `g.fit()` di `:364` efektif: bounding box dihitung dari posisi ter-preserve (map `prev` :69-71), dan karena `userMoved=false`, `frame()` (graph.js:173) terus auto-`fit()` tiap 8 frame selama sim aktif → view mengikuti layout sampai user pegang.
- Nit (bukan bug): `applyVisibility` dipanggil dua kali (0.9 di dalam rebuild, lalu 0.5 di handler) → setGraph + drawRight/drawLayers dieksekusi dua kali per klik Reset. Kerja ganda, tak terlihat user.

### 3. P1-1 `isPlain` via SPECIAL_LABELS → **PARTIAL** (mekanisme hidup, target utama meleset)
- Kode `graph-data.js:96-98` sesuai saran Round A; CLUSTER_MEMBER\*/BUNDLER_SUSPECT dianggap plain.
- Bukti runtime (scope network, limit 150): node kinds `{group:2, funder:2, wallet:599, token:17, bundle:18}`, sub `"top 150 wallets · 2 grup receh · top 17 pools"`. `drawGroup` kini terpanggil (dispatcher graph.js:252), kartu GRUP (visualizer.js:233-239), tooltip (:285-288), radius (:180) — semuanya reachable; 0 folded member punya label khusus; 0 folded member digambar individual; visibleGraph default 638 node / 621 link / **0 dangling** / 0 node tanpa `r`.
- **TAPI: fold untuk bundle mustahil terjadi secara struktural.** Dari 447 anggota bundle, **447/447 (100%) juga berlabel SNIPER** (beli di blok pertama = sniper by definition), dan SNIPER ada di SPECIAL_LABELS → `SPECIAL(i)` true → tidak pernah plain → **0 grup dari 18 bundle**, selamanya. Yang terlipat hanya cluster: 14 dari 16 anggota (12+2). Total 449 anggota entitas tetap digambar individual — tujuan de-clutter (guide.js:57) untuk bundle tidak tercapai. Saran: untuk anggota entitas, jangan ganggap SNIPER (label konsekuensi dari keanggotaan bundle) sebagai specializing; atau khusus BUNDLER_SUSPECT pakai daftar blocking yang lebih sempit (INSIDER/CT/WHALE/DEV/...).
- Cek dampak lain yang diminta: (a) `hub.vol` kini ter-akumulasi (:136-137) — efeknya lihat P1-B2 (double count di kartu); (b) `S.statsAll.get(i)?.toks` anggota terlipat tidak lagi dipakai di mode network (hanya `rankedSet` diiterasi :107) — link trade anggota terlipat memang hilang by design; konsekuensi kecil: 2/14 folded member kehilangan pool-nya dari map (token hanya diperdagangkan anggota terlipat); (c) node `group` tidak butuh `hasSwaps` (drawGroup miliknya sendiri, `visibleGraph` hanya cek hasSwaps untuk kind `wallet`); (d) `focus`/`neigh` untuk kind 'group' benar (link fund group→hub, computeNeigh generik); (e) `findIndex`-hanya-entitas-pertama (:142) saat ini harmless — dataset punya **0 wallet anggota >1 entitas**, 0 folded terhitung di >1 grup.

### 4. P1-2 INDUKAN lookup by address → **VALID** (untuk visualizer)
- `visualizer.js:248-249`: `S.origins[S.wallets[sel.ref][0]]` — `S.origins` memang di-key address lowercase (dataset.py:269-302, store.js tidak me-rekey). Runtime: **737/737 entri origins ter-hit by address**; hit index numerik 0-999 = **0** (konfirmasi bug lama).
- Guard `isW` (kind wallet/entity saja) benar: kind 'group' punya `ref` = entity index yang BUKAN index wallet — tanpa guard itu `S.wallets[sel.ref]` akan salah baca; sudah ter-short-circuit.
- Sisa (P2): `address.js` tetap tidak me-render INDUKAN padahal guide.js:69-70 menjanjikan "kartu node & halaman profil" → lihat P2-B4.

### 5. P1-3 `label_counts` + derived → **VALID**
- `dataset.py:312`: `Counter(... labels) + Counter(... derived)`. Bukti runtime (payload terserve): `label_counts` = BOT **22**, WHALE **19**, WHALE_SUS **3**, SNIPER_BOT **4** (plus INSIDER 2611, SNIPER 574, BUNDLER_SUSPECT 447, AIRDROP_FARMER 3392, PHISHING_TARGET 87, GENERALIST 28340, dst).
- Cross-check vs rows: count per index di `w[2]` = BOT(idx 1)=22, WHALE(14)=19, WHALE_SUS(15)=3, SNIPER_BOT(12)=4 — **match sempurna, 0 mismatch** untuk semua 16 label. Konsumen ikut benar: facet Labels & tab LABELS explorer (explorer.js:71,79) dan global search (app.js:88) kini menampilkan angka nyata; `S.labelIndex` dari `S.labels` (memuat derived) → filter URL/facet berfungsi.

### 6. P1-5 class `viz-tab-left/right` → **VALID**
- `visualizer.js:42-43`: `class="viz-tab viz-tab-left"` / `"viz-tab viz-tab-right"`; CSS `tokens.css:216` `.viz-tab-left{left:8px} .viz-tab-right{right:8px}` ada. Tab kini di tepi kiri/kanan sesuai desain.

### 7. drawEntity theme-aware → **VALID**
- `--ent-fill`/`--ent-text` terdefinisi di `:root` (tokens.css:30-31) dan di-override tema white (:43-44: `#FFFFFF`/`#141922`); space mewarisi :root (terang di atas gelap — konsisten dengan tema dark, kontras baik).
- `graph.js:30-31`: dibaca di constructor + di-refresh oleh MutationObserver `data-theme`; `drawEntity` (:332-334) memakai `c.ent_fill || '#F4F6FA'` / `c.ent_text || '#07080C'` — fallback aman bila var kosong.

### Follow-up P2 Round A (cek cepat)
- P2-1 **PARTIAL** — fragmen keyframes yatim sudah hilang, tapi dua `}` liar masih tertinggal di `tokens.css:206-207` (parse error yang di-recover browser; rules setelahnya tetap berlaku).
- P2-2 **FIXED** — `app.js:163` kini `if (!document.getElementById('sfcv'))` sebelum insert; index.html:17 punya canvas.
- P2-3 **FIXED** — branch `act==='freeze'` kedua hilang dari chain delegasi (kini fit/zin/zout saja); flag `opt.frozen` (graph.js:26,169) masih ada sebagai vestigial tapi tak pernah di-set UI.
- P2-4 **FIXED dengan caveats** — `visualizer.js:64` restore `saved.paused`; tapi lihat P2-B2 (layout beku di posisi spawn + label tombol stale).
- P2-5 **TIDAK DIJALANKAN** — `evidence.js:46` (duplikat `AIRDROP_FARMER`, unreachable) masih ada → P2-B7.
- P2-6 **FIXED** — `evidence.js:30` kini `(si || {}).kind`; line 41 juga guard `(s && s.spread ...)`.
- P2-7 **FIXED** — `foldedEntityOf`/`extrasByEntity` sudah tidak ada di graph-data.js.
- P2-8 **SEBAGIAN BESAR FIXED** — `.viz-rail`/`.viz-time`/`.viz-panel` kini `var(--viz-panel)` (views.css:81,123,134; var didefinisikan per tema tokens.css:26,39,55); `.fchip` + `.seg-btn.is-active` di-override per tema (tokens.css:218-220). Sisa hardcoded: `.pill` dan hexBadge → P2-B6.
- P2-9 **FIXED** — `token.js:37-40`: MINT_ALLOCATION → "alokasi mint dari 0x0", CONFIRMED_INSIDER → "transfer murni dari N pengirim", fallback `?? ''`.
- P2-10 **FIXED** — `evidence.js:25` kini `nf(d.mint?.amount || 0)` + "unit token".
- P2-11 **TETAP** (perf, terdokumentasi) — mode token tetap mengabaikan `limit` (25 node di token teratas saat ini, belum terasa).

---

## P0/P1/P2 BARU

### P0
Tidak ada. (Tidak ditemukan crash/fungsional-rusak level baru; Reset, build, dan keempat mode scope jalan normal.)

### P1-B1 — visualizer.js: **8 tombol/kontrol dirender tapi TIDAK punya handler sama sekali** (mati diam-diam)
- **File:line:** `visualizer.js:35` (`data-act="more"` — tombol primer toolbar "More info", selalu tampil), `:49` + `:103` (`data-act="unpin"` — rail "Unpin all" + chip "N pinned"; `g.unpinAll()` graph.js:91 tidak pernah dipanggil dari manapun), `:100` (`data-act="range-clear"`), `:101` (`data-act="toggle-flow"` — chip Flow, selalu tampil), `:104` (`data-act="unhide"` — chip "N hidden · show"), `:260` (`data-act="open"` — tombol Open di kartu node), `:263` (`data-act="expand"` — tombol PRIMER "+ Expand"/"+ Map entity"), `:267` (`data-act="group"` — toggle "Ungroup/Group clusters").
- **Bukti:** grep seluruh visualizer.js — satu-satunya chain aksi adalah `:408-410` (`fit|zin|zout`) plus handler bernama (resetviz/fs/hide-\\*/show-\\*/freeze/preset/eye/explayer/collapse/focus/mode/copy). Tidak ada branch untuk kedelapan act di atas; `st.grouped` hanya pernah di-set `true` (:14, :360) dan dibaca (:210, :267) — tidak pernah di-toggle.
- **Dampak:** (a) toggle "Group clusters" yang dijanjikan guide.js:64 mati — address list selalu grouped; (b) satu-satunya cara "Map entity" dari kartu hub mati (kini hanya via picker kiri); (c) setelah brush timeline, chip penghapus rentang mati (dblclick timeline masih bisa); (d) node yang di-pin tidak bisa di-unpin massal; (e) wallet ter-hide hanya bisa di-show per-item lewat eye di list/sub-layer; (f) "More info" & "Flow all/off" klik tanpa efek. `node --check` lolos karena ini bukan error sintaks — handler-nya memang tidak pernah ditulis.
- **Saran:** tambahkan branch: `group` → `st.grouped=!st.grouped; drawRight()`; `open` → `sel && openNode(sel)`; `expand` → hash ke `#/visualizer?entity=${sel.ref}` (hub) / `#/visualizer?wallet=${sel.addr}`; `unpin` → `g.unpinAll(); drawChips()`; `toggle-flow` → `st.show.flow=!st.show.flow; persist(); applyVisibility(0)`; `unhide` → `st.hidden.clear(); applyVisibility(0.3)`; `range-clear` → `st.range=null; rebuild({refit:false})`; `more` → buka panel kiri atau hapus tombol.

### P1-B2 — kartu hub funder/bundle: "Volume grup est." **dobel** di cluster, **$0.00** di bundle & entity scope (regresi/sisa P1-4)
- **File:line:** `graph-data.js:136-137` (`h.vol = (h.vol||0)+vol; h.foldedVol = (h.foldedVol||0)+vol`) + `visualizer.js:245` (`usd((sel.foldedVol || 0) + (sel.vol || 0))`).
- **Bukti runtime:** hub cluster `f:cluster_be41` → `vol === foldedVol === 3338` (tidak ada jalur lain yang menambah hub.vol — `addHubsFor`/`tradeLink` tidak mengakumulasi vol hub) → kartu menampilkan `3338+3338 = $6.68K` padahal volume terlipat riil $3.34K (vol semua anggota pun $4.12K — angka yang tampil bukan keduanya). Hub bundle: `foldedVol=0, foldedCount=undefined` (tidak pernah ada grup bundle, lihat Fix 3) → kartu "GRUP — berisi 45 wallet · Volume grup est. **$0.00**" padahal jumlah vol anggotanya **$11,320**. Mode entity: `foldedVol` undefined, `vol=0` → tetap $0.00 (P1-4 lama tidak tersentuh di scope ini).
- **Dampak:** angka uang menyesatkan di kartu seleksi — 2× untuk cluster, 0 untuk bundle/entity. (Radius hub :179 yang memakai `foldedVol` sendiri sudah benar; sub-layer list `:183` menampilkan `it.vol` = foldedVol juga benar.)
- **Saran:** di kartu pakai `usd(sel.foldedVol ?? sel.vol ?? 0)`; dan agregasi vol hub untuk mode entity (`e.members.reduce((a,m)=>a+(S.statsAll.get(m)?.vol||0),0)`) serta untuk hub bundle di network scope, sehingga "Volume grup est." = total vol anggota.

### P2-B1 — node `group` tidak ikut filter layer induk → grup yatim tanpa hub/edge
- **File:line:** `graph-data.js:192-201` (`visibleGraph` — `vis()` tidak punya cabang untuk `kind==='group'`; grup cluster seharusnya mengikuti `show.funders`, grup bundle mengikuti `show.bundles`).
- **Bukti runtime:** preset "Bubblemaps raw" (funders+bundles off): 2 node group tetap visible; grup `g:1` (cluster_f70d, semua 2 anggotanya terlipat, tanpa anggota spesial) → **degree 0** — bubble putus-putus melayang tanpa satu link pun. Grup `g:0` selamat (degree 2) hanya karena bond-star ke 2 anggota spesial yang digambar individual.
- **Dampak:** di preset flagship raw / saat layer Funders dimatikan, muncul node yatim yang tak terhubung apa pun — membingungkan dan kotor.
- **Saran:** di `vis()`: `if (n.kind === 'group') return n.ref != null && (S.entities[n.ref]?.kind === 'cluster' ? show.funders : show.bundles);`

### P2-B2 — Freeze→Resume tidak pernah melanjutkan simulasi; reload saat paused membekukan layout di posisi spawn + label tombol stale
- **File:line:** `graph.js:151-159` (`setPaused(true)` memaksa `alpha=0`; `setPaused(false)` tidak restore `alphaTarget`/reheat) + `visualizer.js:64` (`if (saved.paused) queueMicrotask(() => g.setPaused(true))` setelah `rebuild()` sinkron di `:424`).
- **Bukti:** `sim.active = alpha>0.004 || alphaTarget>0` — setelah resume keduanya 0 → `frame()` tidak pernah tick → layout statis permanen (hanya flow dots jalan), padahal toast mengatakan "Animasi jalan lagi". Saat reload dengan `paused=true`: `rebuild()` → `setGraph(reheat 0.9)` → microtask `setPaused(true)` → alpha di-zero → node permanen di formasi phyllotaxis awal (tidak pernah di-layout); tombol Freeze terlanjur dirender "Freeze" (drawLeft jalan sebelum microtask) padahal state paused.
- **Dampak:** UX menyesatkan (Resume tidak resume; reload-paused memperlihatkan spiral node tak tersusun). Tidak crash.
- **Saran:** di `setPaused(false)` lakukan `this.sim.reheat(0.3)` bila layout belum settle (atau simpan flag pernah-settle); di restore path, render ulang `drawLeft()` setelah microtask.

### P2-B3 — `GraphCanvas.destroy()` tidak memutus MutationObserver tema → leak per mount visualizer
- **File:line:** `graph.js:31` (observer dibuat per instance, observe `document.documentElement`) vs `graph.js:44` (`destroy()` hanya cancel raf + disconnect ResizeObserver).
- **Dampak:** setiap pindah route kelir-masuk visualizer menambah satu observer abadi yang menahan referensi instance lama dan membaca getComputedStyle saat ganti tema. Kecil tapi menumpuk di sesi panjang.
- **Saran:** simpan observer di `this.mo`, disconnect di `destroy()`.

### P2-B4 — halaman profil address tidak menampilkan INDUKAN (janji guide) — sisa P1-2
- **File:line:** `address.js` (seluruh file — tidak ada referensi `S.origins`); janji di `guide.js:69-70` "kartu node & halaman profil menampilkan INDUKAN".
- **Dampak:** fitur headline hanya hidup di kartu visualizer; halaman profil (tempat paling alami untuk "di-induki siapa") tetap kosong. 737 wallet punya data origins.
- **Saran:** blok sama seperti visualizer.js:248-258 dengan key `S.origins[w[0]]` di panel Overview/atas evidence.

### P2-B5 — `tokens.css:206-207`: dua `}` liar di top level (sisa P2-1)
- Dua closing brace tanpa pembuka setelah keyframes. Browser me-recover (aturan `.viz-panel.is-hidden` dslm tetap berlaku) tapi ini CSS rusak bagi parser ketat/minifier. Hapus kedua baris.

### P2-B6 — sisa warna gelap hardcoded di tema white: `.pill` dan `hexBadge`
- **File:line:** `components.css:152` `.pill{...background:rgba(7,8,12,.35)}` dan `ui.js:40` `hexBadge` `fill="rgba(7,8,12,.35)"` — keduanya tanpa override tema.
- **Dampak:** di tema white, pill leaderboard (podium foot) dan hexagon rank jadi kotak gelap di atas panel putih (ikon `--text-2` gelap di atas gelap → kontras buruk).
- **Saran:** pindah ke var (mis. `--chip-bg` yang sudah theme-aware) atau override `[data-theme="white"]`.

### P2-B7 — `evidence.js:46`: duplikat branch `AIRDROP_FARMER` masih ada (P2-5 tidak dijalankan)
- Line 39-45 (`L === 'AIRDROP_FARMER' || L === 'PHISHING_TARGET'`) sudah menangani keduanya — dan isinya **benar untuk keduanya**: guard null-sender ada (`(s && s.spread ...)` :41), tampilkan pola mass-spread + tokens + penjelasan "target/korban". Line 46 (`else if (L === 'AIRDROP_FARMER')` dengan `row('Swaps', d.swaps)`) tetap unreachable dead code. Hapus line 46 (atau merge info `d.swaps` ke branch pertama bila diinginkan).

---

## VERIFIED-OK

1. **Syntax:** `node --check` 17/17 JS lolos; `python -m py_compile dataset.py server.py` lolos.
2. **Runtime API:** server naik di 8794, rebuild startup sukses, `GET /api/dataset` HTTP 200 (gzip, 14.5 MB), JSON valid, semua field lengkap (`wallets 32456, active 32456, tokens 1378, bundles 18, clusters 2, origins 737`).
3. **meta.label_counts kini berisi derived** dan identik dengan rows (BOT 22 / WHALE 19 / WHALE_SUS 3 / SNIPER_BOT 4; 0 mismatch di semua label) — facet explorer, tab LABELS, global search, dan dropdown tag leaderboard (TAG_OPTIONS dari `S.labels`) semuanya kini konsisten; filter `#/explorer?label=BOT` via `S.labelIndex` bekerja.
4. **Derived labels dataset.py benar secara arah & aman dari div/0:** median gap dihitung dari `sorted(tss)` (gap `b>=a` selalu true setelah sort), `median([])` di-guard `if gaps else 10**9`; kalibrasi `last/snap_px` di-guard `if snap_px and last`; `net = sell(+) − buy(−)` hanya atas swap priced — konvensi sama dengan `stats.net` (sampel WHALE: stats.net = $167,996, positif = net seller, sesuai deskripsi guide). Sampel BOT: 1071 swap, median gap 1s, 43 token — threshold masuk akal.
5. **buildScope 4 mode** (harness, payload asli): network `{group2, funder2, wallet599, token17, bundle18}`; entity/token/wallet sukses (25/24 dan 153/156 node/link); 0 node tanpa `r`; visibleGraph default 0 dangling link; semua kind punya renderer termasuk `group → drawGroup` (graph.js:252, :306-316; label `×N` fallback `members ? length : foldedCount || '?'` aman).
6. **Fold aman di dataset ini:** 0 folded member berlabel khusus; 0 folded member digambar individual; 0 wallet anggota >1 entitas (findIndex-first :142 harmless saat ini; tetap direkomendasikan pakai `S.memberOf` bila data berubah).
7. **Thread-safety rebuild (hunt f):** `dataset.build()` jalan di luar lock (GET tetap dilayani gz lama), swap `_cache["gz"]+_cache["built"]` atomik di bawah `_lock` (server.py:33-35) — tidak ada state terkoyak; dua POST /api/rebuild bersamaan hanya boros (build ganda, last-wins), tidak korup.
8. **P2-2/P2-6/P2-7/P2-9/P2-10 Round A terkonfirmasi fixed** (lihat follow-up di atas); `#sfcv` unik, guard null `si`, `foldedEntityOf` hilang, kartu Flagged INSIDER 3-kind, mint dalam "unit token".
9. **Tema/CSS (hunt h):** `--chip-bg` terdefinisi di :root/white/space (tokens.css:27,40,56) + override `.fchip` per tema; `--ent-fill/--ent-text` :root+white; `.viz-panel.is-hidden` (tokens.css:209) dan `.al-row.is-hidden` (views.css:106) ada; `.viz-tab-left/right` ada dan terpakai.
10. **Comet/spacefx (hunt i):** guard `if (!getElementById('sfcv'))` mencegah duplikat; `resize()` berbasis innerWidth/innerHeight aman dijalankan saat `#spacefx` masih `display:none` (canvas ber-dimensi, sync() me-resize ulang saat tema space aktif); raf dibatalkan + canvas dibersihkan saat keluar tema space; observer/resize-listener berumur halaman (diterima untuk SPA ini).
11. **Sisa interaksi visualizer yang benar:** eye per node/sub-layer (st.hidden ∪ applyVisibility), collapse cluster (`data-collapse`), focus dari address list, timeline brush + dblclick reset, limit dropdown, dropdown warna via `dd:change`, presets arkham/raw (raw kini meninggalkan 2 grup — lihat P2-B1), persistence `tw.viz.v12` termasuk paused.
12. **Server dimatikan** setelah pengujian (port 8794 tidak meninggalkan proses).
