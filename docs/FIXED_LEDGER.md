# FIXED LEDGER — masalah yang SUDAH difix & diverifikasi (jangan di-re-open)

> Tujuan: setelah context compact, agent baru sering melakukan blind-fix —
> membuka lagi bug yang sudah fix, atau menganggap ada bug padahal bukan.
> LEDGER ini = daftar lengkap "sudah fix + diverifikasi" (dossier
> DEBATE_ROUND_A..G.md = bukti). SEBELUM memfix sesuatu, cek ledger ini.
> Update ledger SETIAP kali fix baru diverifikasi.

Legenda: ✅ FIXED+VERIFIED · ⚠️ LIMITASI DIKETAHUI (bukan bug, jangan "diperbaiki") · 🔜 DIJADWALKAN

## Explorer / Visualizer
- ✅ `css is not defined` crash visualizer — helper `css()` didefinisikan module-level di graph.js
- ✅ `groupNodes is not defined` crash — sekarang `groupOf`
- ✅ Fold bundler/cluster: anggota plain dilipat ke 1 group bubble per entitas
  (chunk 20 dihapus; 1 entitas = 1 grup), hub cube tetap, special-labeled
  (whale/insider/dll) tetap individual. isPlain v2 = SPECIAL_LABELS set tanpa
  SNIPER/BUNDLER_SUSPECT/CLUSTER_MEMBER.
- ✅ visibleGraph mengenali kind 'group' (ikut layer funders/bundles) —
  preset Bubblemaps raw tidak runtuh, 0 grup yatim.
- ✅ INDUKAN (lineage) tampil di kartu node visualizer (lookup BY ADDRESS)
  + halaman address (by address). 737 wallet berlineage.
- ✅ Reset: mengembalikan layer/warna/cap/hidden/collapse/timeline + UNPIN
  SEMUA node scope (termasuk yang hidden) + kamera fit + panel dimunculkan.
- ✅ Freeze: settle sim (alpha=0) + fit saat freeze; Resume reheat 0.15.
  Freeze/Resume hanya satu kontrol (panel kiri); rail freeze lama dihapus.
- ✅ Fullscreen toggle (data-act fs).
- ✅ Panel kiri/kanan collapsible (x = hide, chevron tab = show).
- ✅ Sub-layer chevron di LAYERS untuk DEX pools/Funders/Bundle tx — hide
  per-item (eye), vol per item.
- ✅ 8 tombol mati ter-wiring: group/ungroup, unpin, range-clear,
  toggle-flow, unhide, open, more, expand (entity → wallet scope).
- ✅ Timeline bars + teks theme-aware (var CSS, bukan hex).
- ✅ White mode: nav/panel/rail/time/fchip/pill/seg/entity semuanya var tema
  (tidak ada lagi hardcode gelap yang membuat teks tak terbaca).
- ✅ Space: 120 bintang 2 layer kelap-kelip + komet CANVAS (script user,
  fisika natural, spawn 0.9–2.7s, hanya tema space, gated MutationObserver).
- ✅ Leaderboard $0 FIXED (fallback harga snapshot; 100% swap priced) +
  filter by tag.
- ✅ Labels tab menampilkan BOT/SNIPER_BOT/WHALE/WHALE_SUS/
  PHISHING_TARGET/TRADER_COVERAGE_GAP (label_counts + derived).
- ✅ meta.label_counts + derived; labels/confidence aligned di 32.456 rows.

## Pipeline / Data
- ✅ Etherscan V2 PRIMER (api.etherscan.io/v2, chainid 4663, 2 key rotasi,
  round-robin + rotasi saat rate-limit). Blockscout = fallback legacy.
- ✅ S-39: etherscan_client.token_info eth_call retry+backoff — ReadTimeout
  dulu MEMBUNUH cycle pipeline (prices/analyze tak pernah sampai);
  supervisor restart bolak-balik. Tertutup, diverifikasi log "etherscan aktif".
- ✅ S-39: GMGN get() guarded (httpx/JSON error → error-dict, bukan raise) +
  print visibility saat non-200; pump_analyzer._retry mengenal _http_error
  dan TIDAK me-retry respons sukses (regresi Round C sudah dibetulkan).
- ✅ S-39: dataset.py: fallback pricing snapshot (P0 snap shadow FIXED —
  snap_px); label_counts + derived.
- ✅ S-39: Verifikasi on-chain INSIDER/CLUSTER: 1,646+ pair (730+ proven);
  cron 30 menit + flock + Defer anti-skip.
- ✅ S-39: VOLUME SWEEP WALLET HARVESTER LIVE — scripts/volume_sweep.py
  (cron */5): tag gate port bot.js (FIRST/DOUBLE/TROUGH/SUSTAIN, floor $100K
  5m, trough guard "genuine drop ≤0.7× anchor", rug-risk vol/liq ≥15) →
  antrean CA → run_track_by_ca (resolve pool DexScreener → upsert Token+Pool
  → discover SEMUA wallet on-chain → prices → enrich → analyze →
  results/by_ca/<ca>.json). Diverifikasi debat A/B/C (subagent adversarial):
  P0 stage_enrich_for tidak pernah ada → enrich_wallets + PIN regresi
  test_track_ca_binding.py; analyze_wallets tak lagi wipe global
  wallet_scores/export (do_export/do_push/persist_replace=False);
  trough bleed ≤1 fire; budget queue per-attempt; drop terpisah
  exception(6x)/None(3x); DexScreener strict (outage ≠ token mati);
  track-ca DEFER saat supervisor pipeline jalan (rebutan RPC).
- ✅ S-39: sync path VPS→lokal — scripts/dump_snapshot.py (atomik tmp+rename,
  read-snapshot BEGIN, DATA-ONLY statement-level) + rebuild_local_db.py
  (build ke topwallet.new.db → validasi MIN_ROWS → replace; backup rolling
  .prev.db). Verifikasi part pakai MD5 (ukuran bisa sama antar dump!).
- ✅ S-39: extract_wallets.py: CSV 94,961 + labels regen dari DB.
- ✅ S-39: trending_scanner save_pool atomik + load tahan file korup.
- ✅ S-39: supervisor kill_orphan_pipelines() — systemctl restart TIDAK
  membunuh child pipeline lama → 3 writer bersamaan → sqlite "database is
  locked" crash. Sekarang tiap cycle bunuh `src.cli pipeline` yatim dulu
  (scan /proc). LOCK lain: engine connect timeout 30s sudah ada; 2 pipeline
  manual JANGAN dijalankan bareng (landmine #7 tetap berlaku).

## Launcher Desktop
- ✅ Tauri exe jalan; deteksi Python + folder server; Mulai/Stop/Buka.
- ✅ Stop sekarang SEKALIGUS paksa-matikan proses APAPUN yang memegang port
  8787 (netstat → taskkill), jadi server eksternal yatim pun bisa distop
  dari tombol.
- ⚠️ Defender ASR memblokir exe yang disalin ke Desktop (prevalence) —
  SOLUSI: folder `desktop\src-tauri\target\release` masuk ASR exclusion;
  Desktop pakai SHORTCUT (.lnk) ke exe di folder itu. Jangan salin exe-nya
  langsung ke Desktop lagi.

- ✅ S-40: launcher native WinForms (tools/launcher/launcher.cs →
  desktop/TopWalletLauncher.exe via csc.exe bawaan Windows) menggantikan
  Tauri yang not-responding 100%. Electron di-park (binary download diblok
  jaringan user). Shortcut Desktop menunjuk exe baru.
- ✅ S-40: dexscreener + rpc direct-by-default (proxy Webshare diblok CF
  permanen — penjelasan semua 403); rpc 403 cool+rotate, bukan crash.
- ✅ S-40: arkham harvester deteksi "Something went wrong" (error app
  Arkham ≠ unlabeled) + retry + stop-safe 8x beruntun.
- ✅ S-40: skip stock tokens via config/sweep_skip_tokens.json.
- ✅ S-40: explorer server mati saat user tes Stop-paksa = FITUR bekerja,
  bukan bug. Restart cukup dari launcher (Mulai) atau hidden-start.

- ✅ S-42: **AsyncSession.autoflush assignment itu SHADOW ATTR** — fix S-41
  pertama tidak pernah aktif. Yang benar `session.sync_session.autoflush =
  False` (fc39078). Pasang di run() level (semua stage) + analyze_wallets.
- ✅ S-42: is_degraded property di EtherscanV2Client (pnl_verifier
  AttributeError mematikan track-ca 4 hari — fa13afa).
- ✅ S-42: pipeline lock-retry per stage (e5ad5d9) + pipeline_busy via
  /proc scan (bukan file status yang stale).
- ✅ S-42: fetch_dump v2 resilient (koneksi fresh per langkah, resumable
  manifest data/fetch_manifest.json, MD5 per part).
- ✅ S-42: label presisi pasca-verifikasi — 4.096 wallet relabeled via
  tag_overrides (INSIDER core 2.416 presisi, SNIPER 3-tingkat, MEV_BOT 48,
  f70d = bridge-funded).

## ⚠️ LIMITASI DIKETAHUI (bukan bug — JANGAN "diperbaiki")
- Wallet cap 600: churn reheat ±7 detik (sim O(n²)) — pakai FREEZE; decay
  sudah 0.035 (2× lebih cepat dari semula).
- Raw preset: wallet top individual degree-0 (pool/edge sengaja off) — by design.
- USD = ESTIMASI harga snapshot sampai VPS selesai prices+analyze.
- Sub-layer list mode entity masih all-time vol (minor).
- `paused` sengaja tidak di-restore saat reload (mulai selalu unfrozen).
- S-39: satu track-ca bisa jalan 5-15 menit (discovery+prices+enrich) — cron
  */5 berikutnya skip via flock; itu normal, bukan macet.
- S-39: error transien track-ca (RPC 429, DexScreener 403 intermittently,
  SSL blip) normal di log — queue me-retry (6x exception/3x None) lalu drop.
- S-39: stock tokens RH chain (NVDA/GOOGL/SPY/PONS dkk.) ikut dipanen sweep
  kalau volume 5m-nya tembus floor — sengaja (wallet RH chain sah), menunggu
  keputusan user kalau mau difilter.
- S-39: track_by_ca menutup client di jalur sukses & None-return; jalur
  exception mid-run meninggalkan client terbuka sampai proses cron selesai
  (P3, OS membereskan).
- S-39: race wallet_pool.json scanner-vs-sweep = last-writer-wins antar
  penulis atomik (report-only, self-healing saat token re-fire).
- S-39: stock tokens RH chain DI-SKIP dari volume sweep (keputusan user
  2026-09-17: "nyepam terus"). Daftar = config/sweep_skip_tokens.json
  (addresses lowercase + symbols exact-match, seed 8 token teramati + ticker
  besar). Edit file di VPS untuk ubah; fallback embedded kalau file hilang.
  Hati-hati symbol ambigu: HOOD = token degen TheGreenHood, BUKAN stock —
  sengaja tidak masuk daftar symbol.
- S-39: **proxy Webshare (PROXY_URLS_FILE, 1 proxy) flaky** — DexScreener
  (dan sebagian traffic lain) lewat proxy → intermittent `403 SITE_PERMANENTLY_
  BLOCKED` + `SSL WRONG_VERSION_NUMBER`. curl direct SELALU berhasil; ini
  infrastruktur proxy, bukan kode. Queue sweep me-retry (6x/30 menit) dan
  token re-fire via sustain/double — biarkan; kalau mau tuntas: perbarui
  daftar proxy Webshare atau tambah proxy kedua di PROXY_URLS_FILE.
- S-42: wallet_scores [VPS] masih 0 — analyze durasi panjang, BUKAN bug
  (semua fix sudah ter-deploy). Cek harian; kalau stuck → py-spy dump.
- S-42: **cf_solver BELUM berfungsi** — selalu gagal "sitekey tidak
  ketemu": sitekey Turnstile ada DI DALAM iframe challenges.cloudflare.com,
  ekstraksi harus dari page.frames (besok). Klik manual CF sesekali masih
  diperlukan sampai fix.
- S-40: SNIPERS/BUNDLERS "—" di token top-traders = data sah (cuma 90
  token rug kecil yang punya sniper berlabel; 0 di token blue-chip).
  Lihat scope "Flagged" di halaman Tokens.
- S-39: `database is locked` lama di log = era 3-writer (sudah lewat);
  era sekarang single-writer + orphan-killer. Kalau muncul LAGI berarti
  ada proses asing yang menulis DB — cek dulu `ps -eo pid,cmd | grep python`.

## 🔜 DIJADWALKAN (belum diimplementasi — jangan anggap sudah ada)
- Rug-event detector (liquidity pull ≤30 menit) + old-token pump sweep +
  serial rugger correlation (sebagian bahan sudah mengalir via by_ca/).
- Arkham flow: chromium temp + user login manual + harvest tag CEX.
- Re-enrich TRADER_COVERAGE_GAP (868) + coverage gap.
- Sub-layer entity-mode vol range-aware (minor).
- Pump-scan kalau dipakai lagi: _retry sudah benar; honeypot "silent clean"
  saat GMGN error sudah terselesaikan lewat _http_error handling.

## S-43 (2026-09-24) — crash-loop database-locked + panen Arkham/Bubblemaps
- **ROOT CAUSE crash-loop cycle 152-166**: volume_sweep gate `/proc`
  dicek sekali per batch → sweep menulis berjam-jam bareng cycle → SQLite
  single-writer jebol. Fix: `src/utils/db_write_lock.py` (flock; pipeline
  per-stage + yield 90s, track-ca per entry), busy_timeout 30→120,
  retry 3→5x. Deploy 6e7816a; tes 21 lulus; cycle hijau.
- **trending_scanner**: tags list→set (crash 30 menitan).
- **Arkham 38 funder**: 652 entitas total (known_entities 108). Funder
  besar: 0x6505=**GMGN** (134 wallet), proxy-fleet 119, PonsV2BondingCurve
  13 → 294 wallet terbukti platform-funded; bukti aditif di tag_overrides
  (`arkham_entity`), label menunggu ronde audit.
- **Bubblemaps (Goal #5)**: rute resmi `v2.bubblemaps.io/map?address=<ca>&chain=robinhood`;
  capture `relationships/subgraph` + `token-top-holders` via sesi UI.
  12 token: 5 = GHOST_SUPPLY ~90% satu kantong; wallet INSIDER = distributor
  historis (hampir nol masih hold). `results/bubblemaps/REPORT.md`.

- **Goal #4 paste-CA**: halaman `#/lookup` explorer (c4bfaf8). Rating 0-10
  dengan rincian komponen terlihat; deployer via Etherscan V2 (getcontractcreation),
  sosial via DexScreener, ghost-supply dari capture Goal #5. Catatan: SSL
  Python sistem expired → `_get` fallback certifi→default→unverified (endpoint
  publik baca-saja). Key Etherscan kedua (JMTC…) INVALID — hanya key pertama
  yang dipakai rotasi.

## S-44 (2026-09-25) — akar LB/dashboard statis: enrich one-shot
- **GEJALA**: LB & dashboard explorer tidak bergerak. BUKAN karena noise
  filter — **[VPS] berhenti mengindeks swap sejak 2026-09-16**
  (swap_max_ts mentok, wallets_last24h=0, wallets mentok 94.961).
- **AKAR**: universe trader RH chain terbatas (~95k alamat); enrich
  one-shot (hanya pilih pending/in_progress); setelah backlog habis,
  swap TIDAK pernah di-scan ulang walau discover menemukan token baru
  (trader-nya semua wallet lama). analyze checkpoint mentok 11 Sep.
- **FIX (c5794c4)**: stage_enrich menambah kohor refresh — wallet
  'enriched' dengan enriched_at kadaluarsa (>ENRICH_REFRESH_HOURS=24),
  urut last_active terbaru, limit ENRICH_REFRESH_LIMIT=400/cycle;
  re-scan idempoten (delete+reinsert per wallet, kolom enriched_at sudah
  ada sejak lama).
- **Goal #3 X**: Xlogin (zip user) → /opt/xlogin VPS (luar repo);
  10 akun "extra" (ada auth_token, cross-valid dgn cookies b64) →
  **10/10 LOGIN SUCCESS** (Chromium render home timeline). Sesi utama
  (LevonneBickel) → X_USERNAME/X_AUTH_TOKEN/X_CT0 di [VPS] .env.
  Akun file TIDAK pernah masuk git. verify_credentials v1.1 = retired
  (404) — liveness dibuktikan lewat render browser.

## Debat Audit P1-P3 (malam 2026-09-25, run dwfrun-6e9f5114)
- Hasil: TIDAK ADA YANG DIAPPLY (P1 skor 2, P2 skor 6, P3 skor 7 — semua
  <8). Detail lengkap: results/audit_p123_verdicts.json + artifact
  "laporan-audit-malam". Ditunda untuk audit manusia — sesuai desain.
- PELAJARAN (ditemukan hakim via pengukuran mandiri):
  1. usd_value NULL di SEMUA 442.345 baris swap → guard USD apa pun yang
     baca kolom itu VAKUM; USD nyata hanya dari engine dataset.py
     (rescale 30x + snapshot fallback + filter outlier).
  2. audit_queries p3 last-sender-wins → 6/294 salah kategori
     (multi-entity sender); 0xdb5af497… MINT_ALLOCATION 0,95.
  3. 561 (pp-only) vs 1.038 (engine) wallet >$10k = perbedaan metodologi,
     bukan fabrikasi; 92,9% notional dust ada di 625 wallet >$10k.
  4. Preseden penting (P1): 688 TCG-primary = INSIDER yang DIBATALKAN
     karena terbukti benar membeli (Swap log) — promosi facet buta bisa
     membalik vonis on-chain.
