# Round A — Audit

Tanggal: 2026-09-16 · Scope: `Database Local only/html` (index.html, server.py, dataset.py, assets/js/**, assets/css/**).
Metode: `node --check` semua 17 file JS (semua lolos), `python -m py_compile dataset.py server.py` (lolos), baca line-by-line, runtime test `python server.py --port 8793` + `curl --compressed /api/dataset` (HTTP 200, 14.5 MB, JSON valid), plus harness node yang benar-benar menjalankan `store.load()` + `buildScope()` 4 mode terhadap payload asli.

Catatan state DB saat audit: tabel `price_points` KOSONG (0 baris), sehingga `series`/`spark` kosong (0 token) dan SEMUA swap (290.680) dihargai lewat jalur fallback snapshot. State ini menyembunyikan P0-1.

---

## P0 (crash/fungsional rusak)

### P0-1 — dataset.py: variabel `snap` (dict harga snapshot) tertimpa skalar di loop pool → fallback pricing baru meledak AttributeError
- **File:line:** `dataset.py:89` (penimpaan) dan `dataset.py:121-122` (pemakaian).
- **Bukti kode:**
  ```python
  # line 59: snap dibuat sebagai dict
  snap: dict[str, float] = {}
  ...
  # line 89 (di dalam for tok,(pool,dex,quote) in pool_for.items(): — scope fungsi SAMA, tidak ada block scope)
  scale, snap, last = 1.0, tokens[i][3], rows[-1][1]
  ...
  # line 120-122 (loop swaps, DIJALANKAN SETELAH loop pool selesai)
  if p is None:
      sp = snap.get(ta)   # snap sudah BUKAN dict lagi
      p = sp
  ```
- **Dampak:** Python tidak punya block scope; baris 89 me-rebind nama `snap` (yang di line 59-66 adalah peta alamat→harga snapshot) menjadi skalar float/None. Begitu ADA SATU pool saja yang punya price_points (dan ada token swap tanpa series — kondisi normal saat DB diisi ulang), fallback pricing — fitur baru yang jadi konteks perubahan — raise `AttributeError: 'float' object has no attribute 'get'` di tengah `build()`. Akibatnya `python server.py` gagal di startup (rebuild() sebelum serve) dan `POST /api/rebuild` balik 500 → seluruh app mati. Hari ini build selamat HANYA karena `price_points` kosong → loop selalu `if not rows: continue` sebelum line 89, jadi `snap` kebetulan tetap dict dan fallback jalan untuk 290.680 swap.
- **Bukti runtime:** `dataset.build()` sukses pada DB sekarang; replikasi query menunjukkan 1282 token swap tanpa series (karena semua pool tanpa points), dan `snap_scalar.get('x')` → `AttributeError`. Cukup satu pool dapat points → build crash.
- **Saran fix:** ganti nama variabel lokal di line 89, mis. `scale, snap_px, last = 1.0, tokens[i][3], rows[-1][1]` dan pakai `snap_px` di line 90-92; biarkan `snap` tetap dict. (Tambah guard `if isinstance(snap, dict)` tidak perlu kalau shadowing dihilangkan.)

### P0-2 — visualizer.js: tombol Reset baru (`data-act="resetviz"`) memanggil `draw()` yang tidak ada → ReferenceError, reset tidak selesai
- **File:line:** `assets/js/views/visualizer.js:356-366` (handler), `:148` (tombol).
- **Bukti kode:**
  ```js
  const rz = e.target.closest('[data-act="resetviz"]');
  if (rz) {
    st.show = { ...DEFAULT_SHOW }; ... st.hideLeft = false; st.hideRight = false;
    g.setPaused(false); g.userMoved = false;
    persist(); draw();            // ← line 362: `draw` TIDAK PERNAH didefinisikan/diimpor di file ini
    g.userMoved = false; g.fit();
    syncPanels();
    toast('Visualizer kembali ke default');
    return;
  }
  ```
  `grep -n "function draw\b|const draw\b|import.*draw" assets/js/views/visualizer.js` → tidak ada hasil (yang ada hanya `drawLeft/drawLayers/drawRight/drawTimeline/drawChips`; `draw` milik class GraphCanvas, bukan global). `node --check` lolos karena ini ReferenceError runtime.
- **Dampak:** klik Reset → state `st` sudah berubah + `persist()` jalan, lalu throw ReferenceError → `g.fit()`, `syncPanels()`, `toast()` tidak pernah dieksekusi dan TIDAK ADA redraw (`drawLeft/drawChips/drawRight` tidak dipanggil). UI stuck: panel/layer/lama tampil, checkbox layer tidak kembali ke default visual, toast tidak muncul. Fitur baru (Reset) rusak total.
- **Saran fix:** ganti `draw();` dengan `rebuild(); applyVisibility(0.5); drawLeft();` (atau ekstrak helper `redrawAll()` dan panggil itu), lalu `g.fit(); syncPanels(); toast(...)` seperti sekarang.

---

## P1 (salah tampil/logika)

### P1-1 — graph-data.js: fold v3 "group node" TIDAK PERNAH aktif — semua anggota entitas pasti berlabel, `isPlain` selalu false
- **File:line:** `assets/js/lib/graph-data.js:94-98` dan `:118-133`.
- **Bukti kode:**
  ```js
  const isPlain = i => !S.wallets[i][2].some(li => S.labels[li] !== 'GENERALIST');
  const SPECIAL = i => entityMember.has(i) && !isPlain(i);
  const ranked = rankedAll.filter(([i]) => !entityMember.has(i) || SPECIAL(i)).slice(0, limit);
  ...
  const plainMembers = e.members.filter(i => !rankedSet.has(i) && !SPECIAL(i));
  if (!plainMembers.length) continue;   // ← selalu continue
  ```
- **Bukti runtime (dataset asli):** `buildScope({mode:'network', limit:150})` → node kinds `{wallet:613, token:17, funder:2, bundle:18}`, **groups: 0**; dari 463 anggota entitas, **0 yang "plain"** — karena keanggotaan itu sendiri lahir dari label `CLUSTER_MEMBER:*` / `BUNDLER_SUSPECT` (dataset.py:219-228), jadi `S.wallets[i][2]` selalu memuat label ≠ GENERALIST → `SPECIAL(i)` selalu true → `plainMembers` selalu kosong. Subtitle scope pun menampilkan "0 grup receh".
- **Dampak:** seluruh fitur lipat v3 mati diam-diam: `drawGroup` (graph.js:306), kartu GRUP kind 'group' (visualizer.js:232), tooltip grup (visualizer.js:284), radius group (graph-data.js:178) — semuanya unreachable. Map tetap penuh 463 anggota individual, tujuan de-clutter tidak tercapai. Bonus: `findIndex` di line 135 hanya melihat entitas PERTAMA, jadi bila nanti grup terbentuk, anggota multi-entitas bisa tergambar individual sambil terhitung di grup entitas kedua (double count).
- **Saran fix:** definisikan ulang "plain": anggota yang label khususnya HANYA label keanggotaan itu sendiri, mis. `isPlain = i => S.wallets[i][2].every(li => S.labels[li] === 'GENERALIST' || S.labels[li].startsWith('CLUSTER_MEMBER') || S.labels[li] === 'BUNDLER_SUSPECT')`. Jangan biarkan plainMembers kosong karena label keanggotaan.

### P1-2 — visualizer.js: kartu INDUKAN membaca `S.origins[sel.ref]` (index angka) padahal payload di-key ADDRESS → tidak pernah render
- **File:line:** `assets/js/views/visualizer.js:247-248`; producer `dataset.py:269-302,317`.
- **Bukti kode:**
  ```js
  ${isW && S.origins && S.origins[sel.ref] ? (() => {   // sel.ref = INDEX wallet (angka)
      const o = S.origins[sel.ref];
  ```
  dataset.py: `origins[a] = o` — `a` = alamat `0x…` (string), dikirim apa adanya (`"origins": origins`), store.js tidak me-rekey.
- **Bukti runtime:** sampel 5000 wallet aktif → `S.origins[numericIndex]` = **0 hit**; `S.origins[S.wallets[r][0]]` = **206 hit** (737 entri origins ada di payload).
- **Dampak:** fitur headline "INDUKAN — ASAL TOKEN" (dataset.py baru menambahkan peta `origins`) tidak pernah muncul di kartu node visualizer. `address.js` juga sama sekali tidak me-render origins, padahal guide.js:69-70 menjanjikan "kartu node & halaman profil menampilkan INDUKAN". Fitur mati total di UI.
- **Saran fix:** lookup by address: `const o = S.origins[S.wallets[sel.ref]?.[0]]`; dan tambahkan blok INDUKAN yang sama di `address.js` (key `S.origins[w[0]]`).

### P1-3 — dataset.py: `meta.label_counts` tidak menghitung label turunan → facet/tab LABELS explorer tidak punya BOT/WHALE/WHALE_SUS/SNIPER_BOT, search menampilkan count "0"
- **File:line:** `dataset.py:205-206` vs `dataset.py:312`; konsumen `assets/js/views/explorer.js:70-71,79`, `assets/js/app.js:88`.
- **Bukti kode:**
  ```python
  "label_counts": Counter(l for v in W.values() for l in v["labels"]),   # line 312 — TANPA derived
  ```
  bandingkan `label_names` line 205-206 yang justru menggabungkan derived. Runtime: rows memuat BOT=22, WHALE=19, WHALE_SUS=3, SNIPER_BOT=4 wallet, tetapi `meta.label_counts` keempatnya `null`.
- **Dampak:** (a) sidebar facet "Labels" dan tab LABELS di explorer tidak menampilkan 4 label baru sama sekali (tidak bisa difilter dari UI); (b) global search (app.js:88) menampilkan `nf(S.meta.label_counts[l])` = **"0"** untuk label yang sebenarnya punya 22/19/3/4 wallet — salah tampil langsung terlihat. (Filter via URL `#/explorer?label=BOT` sendiri bekerja karena pakai `S.labelIndex`.)
- **Saran fix:** `Counter(l for v in W.values() for l in v["labels"]) + Counter(l for ls in derived.values() for l in ls)` (atau hitung dari `rows` final).

### P1-4 — hub funder/bundle: `foldedVol`/`foldedCount` tidak pernah di-set → radius hub konstan, "Volume grup est." selalu $0.00
- **File:line:** `assets/js/lib/graph-data.js:37` (hub dibuat `vol: 0`, tanpa foldedVol), `:177` (radius memakai foldedVol); `assets/js/views/visualizer.js:241-244` (kartu), `:182` (sub-layer list).
- **Bukti kode:**
  ```js
  // graph-data.js:177
  else if (n.kind === 'funder' || n.kind === 'bundle') n.r = 8 + 18 * Math.sqrt((n.foldedVol || 0) / maxVol);
  // visualizer.js:243-244
  <div class="t3">GRUP — berisi ${e.members.length} wallet${folded ? ` (${folded} terlipat)` : ''}</div>
  <div class="t3" ...>Volume grup est. <b>${usd((sel.foldedVol || 0) + (sel.vol || 0))}</b></div>
  ```
  `grep -rn "foldedVol|foldedCount"` → hanya 4 baris, SEMUanya pembacaan; tidak ada assignment di manapun.
- **Dampak:** semua hub selalu r=8 (tidak proporsional volume anggotanya — kebalikan janji "dilipat jadi SATU bubble sebesar total volume anggotanya" di guide.js:57); kartu GRUP hub menampilkan "Volume grup est. **$0.00**" walau anggotanya bernilai jutaan; daftar item sub-layer funder/bundle juga selalu $0.00. Salah tampil menyesatkan.
- **Saran fix:** saat membangun hub di `buildScope`, agregasikan `n.vol += S.statsAll.get(m)?.vol ?? 0` untuk tiap anggota (dan set `foldedCount` = jumlah anggota non-individual), atau di visualizer hitung dari `e.members` langsung.

### P1-5 — tab collapse panel (`#tabLeft`/`#tabRight`) tanpa class posisi `viz-tab-left/right` → dua tab ditumpuk di posisi statis yang sama
- **File:line:** `assets/js/views/visualizer.js:42-43`; CSS `assets/css/tokens.css:205-211`.
- **Bukti kode:**
  ```html
  <button class="viz-tab" id="tabLeft" data-act="show-left" hidden ...>
  <button class="viz-tab" id="tabRight" data-act="show-right" hidden ...>
  ```
  ```css
  .viz-tab{ position:absolute; top:118px; ... }      /* TIDAK ADA left/right default */
  .viz-tab-left{ left:8px; } .viz-tab-right{ right:8px; }   /* ada di CSS, tidak pernah dipakai */
  ```
- **Dampak:** absolute positioning tanpa `left`/`right` → kedua tab jatuh di static position masing-masing (menumpuk di bawah `.viz-rail`/setelah asides), bukan di tepi kiri/kanan seperti didesain. Saat satu panel disembunyikan, tab pembukanya muncul di tempat salah dan kedua tab saling menimpa bila keduanya hidden.
- **Saran fix:** tambahkan class: `class="viz-tab viz-tab-left"` / `class="viz-tab viz-tab-right"`.

---

## P2 (polish)

### P2-1 — tokens.css:196-202: fragmen `@keyframes` yatim (CSS rusak)
- Sisa hapus animasi komet versi CSS: blok `2% {…} 16% {…} 100% {…} }` dan `3% {…} 14% {…} 100% {…} }` berada di luar aturan manapun, dengan dua kurung tutup liar. Parser browser melewatkan (brace tiap fragmen balanced) tapi ini syntax error yang menunggu parser ketat/minifier. Fix: hapus baris 195-202.

### P2-2 — duplikat canvas `#sfcv` (index.html:17 + app.js:163)
- `#spacefx` di index.html sudah berisi `<canvas id="sfcv">`, app.js menyisipkan canvas kedua dengan id sama via `insertAdjacentHTML('afterbegin')`. `getElementById` mengambil yang pertama (yang disisipkan) → animasi jalan, tapi ada elemen duplikat-ID tak terpakai. Fix: buat kanvas di satu tempat saja (cek `if (!document.getElementById('sfcv'))` sebelum insert, atau hapus dari index.html).

### P2-3 — visualizer.js:386-393 vs 410: dua mekanisme freeze, branch kedua dead code
- Handler `fz` (setPaused) di line 386-393 selalu `return` sebelum delegasi `act` di line 405 → `else if (act === 'freeze') { g.opt.frozen = ... }` (line 410) unreachable. Konsep `opt.frozen` (skip sim.tick) vs `paused` (skip frame) campur. Fix: hapus branch line 410 dan `opt.frozen`, konsisten pakai `setPaused`.

### P2-4 — visualizer.js:16: `paused` disimpan tapi tidak pernah di-restore
- `persist()` menulis `paused: g?.paused || false`, tapi tidak ada kode membaca `saved.paused` (hanya `saved.show/colorMode/limit`). Freeze hilang saat reload — simpanan sia-sia. Fix: `if (saved.paused) g.setPaused(true)` setelah GraphCanvas dibuat + sinkronkan label tombol.

### P2-5 — evidence.js:39 vs 46: handler `AIRDROP_FARMER` ganda, branch kedua unreachable
- Line 39 `else if (L === 'AIRDROP_FARMER' || L === 'PHISHING_TARGET')` sudah menangani keduanya; line 46 `else if (L === 'AIRDROP_FARMER')` tidak akan pernah jalan. Fix: hapus line 46 (atau gabungkan informasi `d.swaps` ke branch pertama bila memang diinginkan).

### P2-6 — evidence.js:29-30: `si.kind` tanpa guard null (producer-nya saja yang defensif)
- `Object.entries(d.senders || {}).map(([sa, si]) => ... si.kind ...)` — dataset.py:281 melakukan `si = si or {}` yang menandakan si bisa null di sumber. Data saat ini aman (0 dari 762 entri null), tapi satu entri null di wallet_labels.json berikutnya = TypeError saat render halaman address. Fix: `const s = si || {}` lalu pakai `s.kind`.

### P2-7 — graph-data.js:146-151: `foldedEntityOf()` dead code yang referensi `extrasByEntity` (tidak pernah didefinisikan)
- Fungsi lokal di mode network tidak pernah dipanggil; bila suatu saat dipanggil → `ReferenceError: extrasByEntity is not defined`. Fix: hapus fungsi (versi hidupnya adalah `groupOf`), atau definisikan mapnya.

### P2-8 — hardcoded warna gelap yang rusak di tema white
- `views.css:81` `.viz-rail` dan `views.css:134` `.viz-time` background `rgba(16,19,26,.96)` — di tema white jadi kotak gelap besar di atas stage putih (ikon rail pakai `--text-2` gelap → hampir tak terbaca). Juga `components.css:85` `.fchip` background `rgba(7,8,12,.6)`, `components.css:55` `.seg-btn.is-active` `#F4F6FA/#07080C`, dan `graph.js:332-334` `drawEntity` fill `#F4F6FA` + text `#07080C` (entitas nyaris tak terlihat di tema white; `drawToken` fill `hsl(h 36% 19%)` gelap memang tetap kontras tapi inkonsisten dengan panel terang). Fix: pindahkan ke var tema (`--viz-panel`, `--panel-2`, dst.) atau tambah override `[data-theme="white"]`.

### P2-9 — token.js:37: kartu Flagged menampilkan "undefined sells without a buy" untuk INSIDER kind baru
- INSIDER evidence kind `MINT_ALLOCATION` (17) dan `CONFIRMED_INSIDER` (704) tidak punya `sell_count` (diverifikasi: 721/721 tanpa field) → tabel "Flagged wallets" halaman token me-render `undefined sells without a buy`. Fix: branch khusus kind (mint → "alokasi mint dari 0x0"; confirmed → "transfer murni dari N pengirim"), fallback `?? ''`.

### P2-10 — evidence.js:25: jumlah mint token ditampilkan dengan `usd()` (label "$" menyesatkan)
- `row('Jumlah', usd(d.mint?.amount || 0))` — `mint.amount` adalah JUMLAH TOKEN (bukan USD) tapi diformat `$1.23K`. Fix: format angka polos + simbol token, atau beri keterangan "unit token".

### P2-11 — buildScope mode token mengabaikan `limit` (perf)
- `graph-data.js:55-65` membuat node untuk SEMUA wallet di `tokAgg` (runtime: token teratas → 1314 node, 1313 link). Sim O(n²) (force.js:44-62 ×2 pass) pada scope ini berat di mesin lemah. Fix: batasi trader (mis. top `limit` by vol, sisanya digabung), atau setidaknya dokumentasikan.

---

## VERIFIED-OK

1. **Syntax:** `node --check` 17/17 file JS lolos; `python -m py_compile dataset.py server.py` lolos.
2. **Runtime API:** server naik di port 8793, `GET /api/dataset` HTTP 200 (gzip), JSON valid; field `wallets/swaps/ev/origins/labels/types/tokens/spark/bundles/clusters/known/meta` lengkap (server.py:54-64 gzip path benar).
3. **labels vs confidence ALIGNED:** seluruh 32.456 rows punya `len(row[2]) == len(row[3])` (labels turunan diberi confidence 0.8 di dataset.py:244-246 — tidak ada index mismatch). `Math.max(...w[3])` di explorer aman (max(0,...)), confidence min 0.
4. **Derived labels masuk payload:** BOT/WHALE/WHALE_SUS/SNIPER_BOT ada di `S.labels` dan terpasang di rows (22/19/3/4 wallet); `ui.js:21-24` sudah punya warna+desc (`--c-bot/--c-whale/--c-whalesus/--c-phishing/--c-gap` terdefinisi di tokens.css:16); graph.js:34 `labelColor` menangani semua label baru; evidence page menampilkan chip + conf 0.80 untuk label tanpa evidence (evidence.js:18) tanpa crash.
5. **Fallback pricing (saat ini):** dengan price_points kosong, 290.680 swap terhargai via snapshot, 39 unpriced/outliers; struktur baris swap `[tokIdx, ts, side, usd, tx]` konsisten dengan store.js:24 dan charts.bucketDays (indeks 2/3/4 benar di semua pemanggil).
6. **origins payload:** 737 entri, struktur `{kind,label,senders[],tokens[],cluster?}` benar; senders berisi `{addr,kind,spread}`; token di `origins` memang alamat mentah (tapi juga belum ada konsumen yang salah baca selain P1-2). `ev.INSIDER.tokens` sudah dikonversi ke token-index oleh dataset.py:236-237 (tokFlags keys = number, terverifikasi).
7. **INSIDER evidence kind baru:** MINT_ALLOCATION (17, semua punya `mint.amount`+`mint.blocks`) dan CONFIRMED_INSIDER (704, semua punya `senders`, 0 entri sender null) → renderer baru evidence.js:23-33 jalan tanpa crash pada payload saat ini.
8. **buildScope 4 mode** (harness node + dataset asli): network/token/entity/wallet semuanya sukses; 0 node tanpa radius (semua kind punya `n.r` — group juga, via graph-data.js:178); 0 dangling link (semua `l.s`/`l.t` ada di nodes); `visibleGraph` menghasilkan graph konsisten (0 dangling, bond-star hanya antar node visible).
9. **graph.js:** `readTheme()` + MutationObserver `data-theme` benar; `css()` module-level (line 11) tidak tertabr `css` lokal constructor (line 29, hanya untuk labelColor); `setPaused(true)` men-settle sim (alphaTarget=0, alpha=0) dan fit bila user belum interaksi; frame() saat paused tetap menggambar saat `dirty` (drag/hover/pan masih responsif); semua kind punya renderer (`wallet→drawBubble`, `token→drawToken`, `entity→drawEntity`, `group→drawGroup`, sisanya `drawHub`); `singleCluster` di-set visualizer.js:78 sehingga guard mega-cluster (graph.js:192) berfungsi; `maxVol` link-width (graph.js:50) aman.
10. **Force sim & interaksi saat paused:** `sim.active` false ketika alpha=0 (getter force.js:26) — tidak ada tick liar setelah resume settle; collision relaxation tidak menimpa pinned (`fx!=null` → bobot 0, force.js:81).
11. **Panel collapse:** handler `hide-left/hide-right/show-left/show-right` (visualizer.js:374-381) + `syncPanels()` (toggle `is-hidden`, show/hide tab) benar; CSS `.viz-panel.is-hidden{display:none}` ada (tokens.css:204). (Bug posisi tab = P1-5, terpisah.)
12. **Sub-layer chevron & eye per item:** `data-explayer` (visualizer.js:354-355) dan `data-eye` (line 352-353) ter-delegasi benar; eye di sub-layer memakai id node yang sama dengan `st.hidden` → sinkron dengan applyVisibility.
13. **Persistence:** `localStorage tw.viz.v12` menyimpan show/colorMode/limit; PRESETS arkham/raw reset penuh; dropdown warna via event `dd:change` (app.js:45-54) sampai ke root visualizer (line 431).
14. **Tema & spacefx:** `#themeBtn` ada (index.html:35), cycler dark→white→space + persist `tw-theme`; komet hanya jalan di tema space (MutationObserver → sync(), raf di-cancel saat keluar tema); `--stars-a/--stars-b` + `::before/::after` terdefinisi (P2-1 hanya soal fragmen yatim setelahnya); semua CSS var yang dipakai renderer (`--c-*`, `--text*`, `--panel`, `--bg-sunk`, `--green/--red/--blue-hi`, `--line-strong`) terdefinisi di ketiga tema.
15. **Sprite icons:** semua nama ikon yang dipakai JS (`bolt,clock,refresh,grid,x,eye,coin,graph,wallet,cluster,bundle,code,tx,star,list,arrow-out,arrow-in,at,search,copy,external,trophy,gift,bot,filter,info,lock,logo,chevron-*,user,dot`) ada di sprite.svg.
16. **Views lain:** dashboard/leaderboard/explorer/tokens/token/address tidak ada ReferenceError pada jalur utama; `bucketDays` indeks kolom benar di 4 pemanggil; pager/thead/dropdown konsisten; `spark` kosong (price_points kosong) ditangani anggun (sparkline → '—', token page auto-fallback ke chart Flow via token.js:19).
17. **server.py:** hanya bind 127.0.0.1; /api/rebuild menangani error (500 + pesan) tanpa merusak cache lama; gzip cache thread-safe (lock); `.js`→`text/javascript` map benar.
