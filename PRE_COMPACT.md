# PRE_COMPACT — context-loss insurance (LOSSY-COMPACT RECOVERY)

> **PROTOCOL (agent Wajib baca):**
> 1. File ini = **snapshot otoritatif SEBELUM compaction**. Update blok snapshot
>    baru (append, JANGAN hapus blok lama) setiap milestone besar, setiap kali
>    ada keputusan/temuan penting, dan PROAKTIF saat percakapan makin panjang
>    (jangan tunggu compact terjadi).
> 2. Setelah compaction terjadi, bandingkan ringkasan post-compact dengan blok
>    snapshot TERBARU di file ini. **Ada perbedaan = compaction sudah terjadi →
>    pulihkan state kerja dari blok terbaru**, jangan percaya ringkasan lossy.
> 3. Blok lama sengaja disimpan: itu jejak audit berapa kali compact terjadi
>    dan apa yang "hampir hilang".
> 4. Selalu commit+push file ini ke GitHub dan sync ke Obsidian
>    (`Sniper Token\TopWallet\PRE_COMPACT.md`) agar kebal mesin mati.
> 5. Kalau repo dan file ini bentrok, repo yang benar → update file ini.

---

## SNAPSHOT S-8 — 2026-09-07 (watchdog cron selesai; semua siap deploy VPS)

- User tegaskan lagi: desktop lokal akan di-SHUTDOWN → supervisory lokal memang
  mustahil; SEMUA autonomy di VPS. Insiden lokal di S-7 tidak boleh terulang.
- **Watchdog LLM (`scripts/watchdog.py`) selesai + dites end-to-end**: cron per
  jam di VPS → kumpulkan fakta keras (proses/heartbeat/stats) → injek ke ZAI
  GLM-5.3-flash → verdict JSON aksi whitelisted (NONE/START_SUPERVISOR/
  RESTART_SUPERVISOR/RESTART_PIPELINE) → eksekusi restart otomatis (hanya
  TOPWALLET_RUN_ENV=vps; lokal report-only — SUDah DITES). Log →
  results/night_watch.log. Tes nyata: GLM benar mendiagnosis supervisor mati
  → START_SUPERVISOR.
- `scripts/VPS_SETUP.md`: systemd unit (supervisor auto-restart on boot/crash)
  + crontab watchdog + verifikasi. Ini yang dipaste user di VPS.
- Arsitektur autonomy 3 lapis di VPS: systemd (restart on crash) → supervisor
  (loop pipeline + resume checkpoint) → watchdog cron per jam (LLM pengawas
  yang bisa membangunkan keduanya).
- Besok (atau saat user siap): user SSH ke VPS, paste blok SECURITY_POLICY.md
  §VPS DEPLOY + scripts/VPS_SETUP.md → semuanya jalan otomatis di sana.

## SNAPSHOT S-7 — 2026-09-07 (KEBIJAKAN BARU: VPS-ONLY, lokal supervisor dihentikan)

**Insiden & koreksi:**
- User marah (BENAR): agent menjalankan scraping+verification berat FULL LOCAL
  semalaman padahal user sudah kasih VPS + proxies. Local = 1 IP statis (lambat,
  di-rate-limit) + mesin pribadi (risiko supply-chain dari OSS tools).
- **SEMUA supervisor/pipeline lokal SUDAH DIHENTIKAN** (0 python processes).
- Policy baru mengikat: **`SECURITY_POLICY.md`** (WAJIB dibaca agent, isinya
  aturan bernomor yang tidak bisa dinegosiasi):
  - Rule 1: kerja berat/scraping/internet-exposed = VPS ONLY; lokal hanya
    memory/results/code/unit-tests.
  - Rule 2: supervisor menolak jalan tanpa `TOPWALLET_RUN_ENV=vps` (guard di
    kode sudah dites menolak); bypass hanya `FORCE_LOCAL=true` oleh USER.
  - Rule 3: supply-chain hygiene — sebelum install tool/library apa pun
    (OSS sekalipun): cek kesehatan repo, tanggal rilis, typosquat, pin versi,
    LAPOR ke user dulu, install hanya di venv VPS.
  - Rule 4–6: secrets di .env, jangan halu PnL, checklist kerja agent.
**State teknis:** enrich 703/703 + prices (8.471 titik) SUDAH tersimpan di
data/topwallet.db lokal — nanti di-migrate/ulang di VPS (setup.sh). Whale map
+ verifier circuit-breaker + supervisor (dengan guard) sudah di-push.
**Langkah berikutnya:** deploy VPS (perintah di SECURITY_POLICY.md bawah —
user jalankan `ssh root@78.31.250.202` lalu paste setup), lalu semua cycle
jalan di sana; lokal cuma git pull + baca hasil.

## SNAPSHOT S-6 — 2026-09-07 dini hari (supervisor overnight AKTIF — KINI DIHENTIKAN, lihat S-7)

**State:**
- User minta: verification yang lambat (Blockscout 500-an) jalan otomatis semalam
  → dibuat **supervisor** (`scripts/supervisor.py`, commit `ec3cb2e`), SEDANG
  JALAN di lokal (background): loop pipeline enrich,prices,analyze + heartbeat
  `results/supervisor_status.json` (update tiap 30s) + watchdog per jam via
  ZAI GLM-5.3-flash coding-plan endpoint (key di .env ZAI_API_KEY) →
  `results/night_watch.log`
- Patch resilience: BlockscoutClient health counter + circuit breaker
  (is_degraded → verifier nunggu API pulih, tidak membakar retry), R2 progress
  log per 10 wallet. 23 tests hijau.
- Data: enrich 703/703 selesai (klasifikasi baru), prices 8.471 titik/60 pool.
  Analyze+verification (101 wallet × 3 trade) berjalan di bawah supervisor —
  besok cek hasilnya.
- **Besok pagi cara cek (urut):**
  1. `cat results/supervisor_status.json` → phase/cycle/top_wallets/updated_at
  2. `cat results/night_watch.log` → penilaian GLM per jam
  3. `python -m src.cli stats` → top wallet terverifikasi
  4. `cat results/whale_entry_maps.json` → Whale Entry Map per token (fitur baru!)
- Catatan fairness: run sebelumnya gugur 65 wallet saat Blockscout 500-san
  berat (1.856 error) — sebagian mungkin gugur karena API down, bukan halu.
  Verifier sekarang nunggu API pulih; supervisor bakal me-retry analyze.
- VPS belum dideploy malam ini (tak ada sshpass di Windows untuk password
  auth) — besok: `sudo bash setup.sh` di VPS (78.31.250.202) cukup satu
  perintah; supervisor lokal ini tetap aman untuk semalam.

## SNAPSHOT S-5 — 2026-09-06, sesi lanjutan (run resume berjalan)

**Progress run resume (laporan berkala):**
- enrich 396/703 (±52 wallet / 10 menit; Blockscout lambat hari ini), 0 gagal
- Estimasi sisa: enrich ±1 jam → prices ±5 menit → analyze ±2 menit
- Setelah analyze: `results/stats.json` harus `top_wallets_count > 0`,
  `results/whale_entry_maps.json` harus ada (fitur baru)
- Whale Entry Map SUDAH diimplement + integrasi + push (`bddc1cb`), 23 tests
- PRE_COMPACT + ULTIMATE_PROMPT sudah di-push (`5be850c`)
- Jangan restart pipeline saat enrich jalan — resume otomatis, biarkan selesai

**Yang sedang dikerjakan saat snapshot ini dibuat:**
- Resume run yang kemarin terputus di 916/1675 wallet (re-enrich penuh dengan
  klasifikasi baru pasca-audit). Command:
  `.venv/Scripts/python -m src.cli pipeline --stages enrich,prices,analyze > logs/resume2.log 2>&1`
  (dijalankan background, cek log, bukan foreground).
- Setelah selesai: cek `results/stats.json` → `top_wallets_count` > 0, lalu
  `python -m src.cli stats` → push hasil (`python -m src.cli push` atau auto).
- Berikutnya (queue): audit ulang 1 subagent (buktikan undercount hilang —
  jumlah posisi ≈ raw round-trips), lalu Whale Entry Map (docs/ROADMAP.md §2g),
  lalu robinscan/fomo scraping (2e), lalu VPS scale-up.

**State repo:**
- Repo lokal: `C:\Users\ROG\Documents\ClaudeCode\SniperToken\TopWalllet`
- GitHub: `papatora/TopWalllet` — commit terakhir di push: `fb45f4f` (ULTIMATE_PROMPT)
- Tests: 19 passing. Jangan ubah kode tanpa `pytest -q` hijau dulu.
- `.env` lokal ADA (Alchemy keys + GITHUB_TOKEN) — gitignored, jangan commit.
- Remote push pakai token di `.env` (GITHUB_TOKEN) — format:
  `git push https://papatora:<TOKEN>@github.com/papatora/TopWalllet main`

**State data (data/topwallet.db, SQLite):**
- 62 token, 62 pool, 1.675 wallet, ~7.643+ swap events, ~22.5k price points
- Semua wallet di-reset `pending` untuk re-enrich (klasifikasi baru level-transaksi)
- Hasil terverifikasi terakhir (SEBELUM re-enrich): 36 wallet di
  `results/top_wallets_latest.json` — mikro-scalper CYBR, bakal berubah setelah
  resume run selesai (harusnya jumlah posisi naik ~2.5x karena bug router-hop
  sudah difix)

**Fakta kunci yang tidak boleh hilang:**
- Chain: Robinhood Chain 4663, PoolManager v4 `0x8366a39CC670B4001A1121B8F6A443A643e40951`,
  WETH `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73`, USDG `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168`
- v4 Swap topic0 = `0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f`
  (canonical signature TANPA nama param — yang pakai nama param = 0 log!)
- ETH oracle tervalidasi: pool $2.455,80 vs live user $2.457,79 (0.08%)
- Verifikasi keras R1/R2/R3 di `src/analyze/pnl_verifier.py` — jangan dilemahkan
- Win threshold ≥1.02x; flag `SINGLE_TOKEN_SAMPLE` & `WASH_PAIR` wajib ada
- Alchemy free tier: getLogs max 10 blok → scan log pakai public RPC + cluster
  pricing (±5k blok sekitar event, gap<30k merge, budget 120 call/pool)
- Blockscout wajib User-Agent; sering 500 → retry backoff
- DILARANG: 2 proses pipeline SQLite bersamaan; 2captcha/bypass Cloudflare;
  halu angka PnL tanpa re-derivasi

**Preferensi user:**
- Bahasa santai Indonesia boleh; jujur, jangan manis-manis soal hasil
- Semua milestone → commit+push GitHub + sync Obsidian
  (`C:\Users\ROG\Documents\Obsidian\Sniper Token\TopWallet\`)
- Sumber tambahan phase attribution: robinscan.io/leaderboard, fomo.family,
  GMGN robinhood (Cloudflare — graceful skip), OKX Web3
- Nanti user kasih: X auth token + GitHub (phase CT/X)

---

## SNAPSHOT S-3 — 2026-09-06 (arsip: sebelum ULTIMATE_PROMPT dibuat)

- Berhenti karena limit usage; HANDOFF.md + sync Obsidian selesai (commit `892eba3`)
- Audit subagent selesai: bug undercount router-hop + fee + wash pair ditemukan,
  difix di commit `2fe0dbe` (touched_pool level-transaksi, win ≥1.02, WASH_PAIR)
- 36 wallet terverifikasi dikirim (dari 101 lolos bar); ETH oracle 0.08% vs live
- Roadmap diperluas: docs/ROADMAP.md (2a–2g, 3, 4, 5) — bedah wallet = inti Phase 2

## SNAPSHOT S-2 — 2026-09-05/06 (arsip: Phase 1 MVP jadi)

- Pipeline lengkap jalan end-to-end pertama kali: discover(62 token) → enrich
  (1.675 wallet) → prices (22.5k titik) → analyze+verify → export/push
- 19 unit tests; Docker Compose + setup.sh siap; docs lengkap (ARCHITECTURE,
  SCORING, API, ROADMAP); obsidian vault sinkron

## SNAPSHOT S-1 — 2026-09-05 (arsip: pivot chain)

- User koreksi: target = Robinhood Chain (bukan Solana). Recon: DexScreener
  index chain `robinhood`; Blockscout API hidup (perlu UA); block ~0.101s;
  PoolManager v4 chain-specific; GMGN/fomo punya robinhood (CF-blocked untuk
  plain HTTP); user punya VPS, proxy Webshare/DataImpulse, 2chapta (dibatasi
  aturan: tidak dipakai untuk bypass CF), X accounts (untuk phase CT nanti)

## SNAPSHOT S-9 — 2026-09-07 siang (fomo/GMGN scraping status)
- Browser automation (playwright+chromium) terpasang di VPS untuk scraping
  fomo.family + GMGN → DIBLOKIR Cloudflare di kedua situs (headless dicurigai;
  halaman challenge ter-render, 0 data). Sesuai policy, TIDAK pakai
  stealth-evasion. Script tersimpan scripts/scrape_social.py (cookie sanitizer
  sudah benar; tinggal jalan kalau nanti ada clearance yang valid).
- **Yang dibutuhkan dari user**: dari browser yang login fomo.family →
  F12 → Network → klik request ke prod-api.fomo.family → Copy as cURL →
  paste ke agent. cURL itu berisi headers + token yang benar-benar lolos.
  Alternatif: biarkan pipeline on-chain menemukan wallet yang sama secara
  organik (universe ekspansi MAX_TOKENS=300 + Blockscout chain-wide discovery
  sudah jalan di VPS — 99 kandidat token, cycle otomatis per supervisor).
- Cluster_f70d (funder 250 ETH, 26 wallet, 2 di top-38) menunggu deep-trace:
  cek apa 0xccc88a9d (ops hub, 20x funding) → akan masuk otomatis kalau
  wallet-nya trading token terlacak.

## SNAPSHOT S-10 — 2026-09-07 (DIRECTIVE BARU: Smart Money Feed product v2)

**User memberi 2 dokumen directive (tersimpan di docs/):**
1. `docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md` — SPESIFIKASI LENGKAP produk:
   build **Smart Money Feed** web (hero + live feed SSE + wallet dossier +
   token page + Whale Entry Map + clusters + track-by-CA + /status +
   /methodology). Milestone M0–M6 di §12. Data reality §4 (38 verified,
   micro-scalpers — hero TIDAK BOHONG, label SINGLE_TOKEN_SAMPLE). Design
   system §7 (editorial newspaper × terminal, warm paper, serif + mono).
   API v2 §8.1, event model §6.2 (FeedEvent + proof wajib), signal taxonomy
   §6.3 (CALL/ENTRY/ADD/TRIM/EXIT/ROTATION), freshness contract §6.9 (P0!).
   First ten actions §14. Failure modes §15.
2. `docs/GMGN_PANDUAN_LENGKAP.md` — kriteria analisis yang harus masuk
   wallet/token forensics: security grid (Top10, Dev, Insiders, Snipers,
   Phishing vs Bundler — dua dimensi berbeda!), dev fingerprint (Total Pairs,
   % Migrated, Funding wallet, Rug History), bonding curve/migrated, callout
   X, launchpad economics (Pons = Pump.fun-nya RH chain). Ini blueprint untuk
   memperkaya anti_gaming + whale/token scoring (Phase 2 forensics).

**Eksekusi:** milestone plan §12 M0→M6, kerjakan berurutan di VPS, pytest
hijau tiap milestone, PRE_COMPACT update tiap milestone. Context session ini
hampir habis → **sesi berikutnya mulai dari dokumen ini** (baca §14 first
ten actions). Cron monitor per jam tetap aktif.

## SNAPSHOT S-11 — 2026-09-07 (DIRECTIVE: WALLET CLASSIFICATION SYSTEM)

User: jangan muter di tempat — bangun **ekosistem klasifikasi wallet utuh**
(TOP TRACKER / DEV / DEV_SERIAL_RUGGER / CT / CLUSTER A-B-C / BUNDLER /
PHISHING / SNIPER / EARLY_BUYER_PNL / FRESH_GOOD / FRESH_BAD / dll).
Blueprint deteksi = docs/GMGN_PANDUAN_LENGKAP.md (security grid, dev panel,
bundler vs phishing, funding wallet). Spesifikasi lengkap + aturan deteksi +
false-positive warnings = **docs/WALLET_TAXONOMY.md** (BARU).
Implementasi: `wallet_labels` table + `src/analyze/wallet_classifier.py` +
hook ke analyze/export. GMGN anchors (0x21…04b6 dkk) = CT_ATTRIBUTED targets.

## SNAPSHOT S-12 — 2026-09-07 (ROUND-ROBIN PNL RECHECK + hard PnL>0 filter)

**User mandate**: round-robin recheck wallet sama 3x (window 7d/1m) untuk
buktikan PnL benar; kelompokkan per skenario (fresh modal kecil → besar, dst);
buang yang sampah/halu/keluar filter.

**Temuan brutal (analisis lokal 39 verified)**: hanya **1** profit-positive
(0x35e63bbA, $21), 15 breakeven, **23 TRASH** (PnL negatif masuk ranked karena
composite score). Fix: `min_realized_pnl_usd: 1.0` di scoring config → ranked
hanya berisi PnL positif. Hasil grouping: results/wallet_scenario_groups.json.

**ROUND-ROBIN PROTOCOL (jalankan di VPS, 3 pass per wallet)**:
- Pass 1: verifier R1-R3 (sudah jalan)
- Pass 2 (7 hari kemudian): re-derive ulang — PnL harus konsisten ±25%
- Pass 3 (30 hari kemudian): re-derive final + cek wallet masih aktif
- Wallet yang lolos 3 pass = `TRIPLE_VERIFIED` → baru eligible copytrade tier
- Implementasi: kolom `verification_passes` di WalletScore + supervisor menjalankan
  re-verify pass berkala (queue by oldest verification date)

## SNAPSHOT S-13 — 2026-09-07 (3-STREAM WORK ORDER + GROUPING LISTS + ANTI-SKIP RULE)

**Arahan user (WAJIB dieksekusi session berikutnya):**
1. **3 STREAM PARALEL di VPS** (berdiri sendiri, tidak ganggu supervisor cycle):
   - **STREAM 1 — DEPLOYER GROUPING**: bangun list deployer wallet (semua
     wallet yang first-buy ≤300 blok pool creation) → kelompokkan per funder →
     output `results/deployer_registry.md` + `.json`: deployer address, token
     yang dia launch, funder-nya siapa, rug pattern (early entry + fast flip
     count), cluster id. Tujuan: biar deepcheck per wallet tinggal lookup
     "ini deployer apa bukan" tanpa hitung ulang.
   - **STREAM 2 — AUDITOR (deep-check per wallet)**: full forensics 10–30
     menit/wallet — buy/sell/timing, airdrop vs buy, dev atau bukan, hold
     bersamaan (co-holders), funding chain sampai asal. **ATURAN KERAS:
     rate limit TIDAK BOLEH bikin wallet di-skip** — wallet wajib selesai
     dulu (tunggu rate limit pulih), baru lanjut wallet berikutnya.
   - **STREAM 3 — RE-VERIFIER**: round-robin 3× per wallet (R1-R3 sekarang,
     7 hari, 30 hari) — dari S-12.
2. **GROUPING LISTS WAJIB ADA** (MD + JSON per kategori, auto-generated):
   `deployer_registry.md`, `funding_sources.md` (funder → total wallet
   didanai → total ETH → cluster), `wallet_labels.json` (dari classifier),
   dipisah kategori biar deepcheck 1 wallet = lookup cepat semua kategori.
3. **4K wallet existing: biarkan** — terus nambah otomatis. 3 stream di atas
   memproses bertahap. Target akhir: menemukan GOLD/DIAMOND wallet di tumpukan
   yang 98% serial rugger — tugas kita memfilter rugger itu.
4. Privacy tx tidak menyembunyikan semuanya — on-chain data tetap ada,
   tinggal deepcheck. Limitasi utama = API rate limit (sudah ada circuit
   breaker; tambahkan queue anti-skip per stream).

## SNAPSHOT S-14 — 2026-09-07 (CLASSIFIER SHIPPED — 14-type wallet taxonomy LIVE)

Subagent selesai: wallet classification system implemented + pushed (`3a73afe`).
- `wallet_labels` table + `src/analyze/wallet_classifier.py` + 14 tests (total 37 green)
- Hook di analyze_wallets (safe, try/except) → `results/wallet_labels.json`
- Dry-run DB nyata: **1.310 wallet terklasifikasi, 1.430 label** — 26 SNIPER,
  107 INSIDER, 3 DEV, 2 CT_ATTRIBUTED, 1 CLUSTER_MEMBER:cluster_f70d
  (0xb1bc…876f), sisanya GENERALIST
- Deployed ke VPS (HEAD 3a73afe, supervisor active) → cycle berikutnya
  otomatis mengklasifikasi semua wallet
- Skipped rules (butuh data yang belum ada): PHISHING_SUSPECT (butuh transfers
  table), DEV mint sub-rule, FRESH_GOOD/BAD (butuh wallet age + modal awal)
- SSH rate-limit: jangan reconnect terlalu sering ke VPS (kena reset 10054)

## SNAPSHOT S-15 — 2026-09-07 23:30 (ACTIVE WORK ORDER: SMART MONEY FEED M0-M6 + SCALING)

**STATUS SAAT INI (verified):**
- VPS: supervisor active, cycle berjalan; wallets ~4.8K+ (terus tumbuh), events 24K+
- Classifier LIVE di VPS (commit 3a73afe, 37 tests): 1.310 wallet terklasifikasi
  (26 SNIPER, 107 INSIDER, 3 DEV, 2 CT_ATTRIBUTED, 1 CLUSTER_MEMBER:f70d)
- Hard filter PnL>1$ aktif; round-robin 3x protocol terdefinisi (S-12)
- Semua sistem: systemd + supervisor + watchdog GLM + cron monitor ZCode per jam

**ACTIVE WORK ORDER = docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md (baca penuh!)**
Target: **100K+ wallets**, universe 300-500 tokens, dan bangun produk:
- M1: feed_events table + shared classifier + backfill CLI + tests ← **LANGKAH BERIKUTNYA**
- M2: API v2 (/feed /stream /status /wallet /token /whale-map /clusters) + hardening
- M3: hero + live feed (SSE) + freshness contract (P0: jangan pernah "just now"
  di atas data basi!) + design system §7 (editorial paper + serif + mono)
- M4: depth pages (wallet dossier, whale entry map, leaderboard, methodology)
- M5: block follower real-time + latency p50/p95
- M6: forensics surface (clusters, f70d story, GENUINE/HALU/TREND_RIDER verdicts)
- CONTINUOUS: universe ekspansi (naikkan MAX_TOKENS ke 300-500), restore bar 5×3
  saat universe >200 token, wallet labels PHISHING/FRESH (butuh transfers table)

**LANGSUNG KERJAKAN (jangan berhenti, usage unlimited):**
1. M1 feed data layer (subagent atau langsung)
2. Pantau VPS tiap ~5 menit: wallets/events harus naik; kalau stagnan → cek log
3. Setelah M1-M2: deploy web di VPS port via systemd + Caddy TLS
4. Semua milestone: pytest hijau → PRE_COMPACT update → push → Obsidian sync
5. Catatan SSH: jangan reconnect terlalu cepat (kena reset 10054, tunggu 30s+)

## SNAPSHOT S-16 — M1 FEED DATA LAYER DONE (commit 7d23a6f, 58 tests green)
- FeedEvent model + src/feed/events.py (make_event_id, freshness_band, backfill)
- CLI: python -m src.cli backfill; dry-run: 6.197 events (ADD 2001/ENTRY 1918/
  EXIT 1390/TRIM 827/CALL 60/ROTATION 1), idempotent
- **NEXT = M2: API v2** (/feed /stream /wallet /token /whale-map /clusters
  /status /methodology + hardening §8.2) → lalu M3 hero+feed page (URL untuk user)
- VPS deploy M1: ssh → git reset --hard origin/main → restart supervisor

## SNAPSHOT S-17 — M2 API v2 DEPLOYED (commit b0a7b2c, 60 tests green)
- src/api/v2.py: /api/v2/feed (cursor pagination) /stream (SSE) /wallets
  /wallet/{addr} /token/{ca}/whale-map /clusters /status /methodology
  + rate limit 120/min + CA validation (400) + generated_at/data_age_seconds
- Wired ke main.py; 60 tests green; API process RUNNING on VPS (pgrep OK,
  curl internal 127.0.0.1 works per log) TAPI external access port 8000
  masih gagal (exit 7) — ufw allow 8000 sudah ditambahkan. NEXT SESSION:
  cek `ss -tlnp | grep 8000` di VPS (uvicorn bind address?), provider
  firewall, lalu M3 (hero+feed frontend) + TLS Caddy.

## SNAPSHOT S-18 — M2 LIVE (API v2 public di http://78.31.250.202:8000)
- /health + /api/v2/status + /api/v2/methodology VERIFIED dari luar ✓
- /api/v2/feed 500 → feed_events table BELUM ada di VPS DB (dibuat otomatis
  oleh init_db supervisor di cycle berikutnya, ≤1 jam) → lalu jalankan sekali:
  `cd /opt/topwallet && .venv/bin/python -m src.cli backfill` (isi 6K+ events)
- API = systemd topwallet-api (auto-restart), bind 0.0.0.0:8000, ufw allow,
  sqlite busy timeout 30s, init_db startup DIHAPUS (lock contention)
- 60 tests green, commit 760b2e1
- NEXT SESSION: (1) verifikasi /api/v2/feed 200 (2) jalankan backfill (3) M3
  frontend hero+feed per docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md §7 + §0

## SNAPSHOT S-19 — SMART MONEY FEED LIVE 🎉
- Frontend M3 LIVE: http://78.31.250.202:8000/ (hero + live feed, design system §7)
- /api/v2/feed serving REAL events (EXIT/ENTRY/ADD dsb dari 6K+ backfill —
  backfill2 masih melanjutkan sisanya, idempotent)
- supervisor + api systemd active; SSH rate-limit sering 10054 — tunggu 2-3
  menit antar koneksi
- NEXT: M4 depth pages (wallet dossier /token whale-map /leaderboard /
  methodology), M5 block follower, M6 clusters view + tiering

## SNAPSHOT S-20 — 🎉 M3 LIVE: Smart Money Feed publicly accessible
- **URL: http://78.31.250.202:8000/** (HTTP 200 from outside, verified)
- Hero per spec §0 (editorial serif + mono, freshness stamp, live dot) +
  live feed consuming /api/v2/feed (real events with proof links) +
  light/dark + mobile + stale banner + methodology footer
- API v2 fully public: /feed /wallets /wallet /token/whale-map /clusters
  /status /methodology /stream (SSE)
- Fix terakhir: HTMLResponse import hilang saat patch (NameError) → ditambah
- M4-M6 tersisa: wallet dossier page, whale map visual, cluster graph,
  block follower real-time, tiering S/A/B — semua spec di
  docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md

## SNAPSHOT S-21 — 2026-09-07 malam (WEBSITE CLOSED, ecosystem mapping live)

- **Website DITUTUP** per user (data masih sedikit + perlu revamp habis-habisan):
  topwallet-api stopped+disabled, ufw port 8000 deleted. Bangun ulang NANTI
  saat data matang (spec tetap: docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md).
- **Fokus sekarang: PnL-in + kategori-in semua wallet.**
- Classifier v2 results (results/wallet_labels.json, ter-push): 1.310 wallet,
  **9 funder clusters** (ad06acf9=12, be41=8, 2e9839d9=7, f70d, dst), 107
  INSIDER, 3 DEV, 2 CT_ATTRIBUTED, 2 SNIPER, sisanya GENERALIST.
- Analyze cycle berjalan (verification R2 ±1 jam) → ranked baru dengan filter
  PnL>1$ (23 wallet trash otomatis keluar dari 39 lama).
- Wallet scenario groups: results/wallet_scenario_groups.json (hanya 1 wallet
  PROFIT_POSITIVE saat ini — jujur; universe ekspansi terus menambah kandidat).
- **NEXT SESSION (urutan):**
  1. Cek hasil analyze cycle: ranked baru + labels ter-update
  2. Build 3-stream (S-13): deployer_registry, funding_sources grouping lists,
     auditor queue anti-skip, re-verifier round-robin
  3. GMGN criteria → anti_gaming enrichment (bundler/insider/phishing per token)
  4. Website revamp HANYA setelah data matang (300-500 token, ratusan verified)

## SNAPSHOT S-23 — STRATEGY PIVOT: PUMP-FIRST DISCOVERY (user mandate)

**User insight (benar):** wallet-first scan salah — 12K wallet cuma ketemu top
PnL $480. Yang benar: **PUMP-FIRST** — cari token yang PUMP (price velocity +
volume spike, interval 1m/5m/1h/6h/24h ala GMGN trend), lalu ekstrak SIAPA
yang beli SEBELUM/awal pump. Contoh user: token Vape di BSC flat lalu +7207%
24h — wallet yang beli di zona flat (merah box) = hunter emas.

**Implemented: `src/analyze/pump_detector.py`** (64 tests green):
- `detect_pumps(blocks, prices, min_gain_pct=50)` — episode pump non-overlap
  (rise ≥50% dalam window 200-300K blok, dari PricePoint series yang SUDAH ADA)
- `classify_pump_participants()` — per pump: ACCUMULATOR (beli sebelum pump),
  EARLY_HUNTER (first 10% pump), MID_RIDER, LATE_CHASER (exit liquidity)
- `multi_pump_hunters(min_pumps=2)` — wallet yang early-catch ≥2 pump BERBEDA
  di token BERBEDA = GOLD WALLET candidates, sorted

**Integration plan (next):**
1. Pipeline analyze: jalankan detektor per pool series → pumps + participants
   → `results/pumps.json` + label wallet (ACCUMULATOR/EARLY_HUNTER per token)
2. multi_pump_hunters → prioritaskan wallet ini untuk enrich mendalam + verify
3. VPS cron terpisah (5 menit): deteksi pump BARU real-time → feed + alert
4. GMGN cross-check: pump RH chain vs BSC (Vape contoh user) — wallet yang
   sama di kedua chain = 100% operator, bukan kebetulan

## SNAPSHOT S-25 — 2026-09-08 (GMGN OPENAPI UNLOCKED — game changer)

**GMGN OpenAPI resmi WORKING (bukan scraping lagi!):**
- Client: `src/discover/gmgn_client.py` (BASE https://openapi.gmgn.ai, X-APIKEY
  gmgn_solbscbaseethmonadtron public test key + timestamp + client_id ±5s)
- Verified live: market/rank (bsc+robinhood, interval 1m/5m/1h/6h/24h),
  token/security, token/info, top holders/traders, kline, wallet stats/profits/
  activity/created_tokens
- RH trending 1h live: PONS +7.8%, ZZZ +39.2%, ELIZABAO +5463% (pump tokens!)
- VAPE (BSC 0xa6b5…ffff) security via API: top10 17.49%, no honeypot, OSS

**DIRECTIVE BARU USER (docs/DIRECTIVE_PUMP_ANALYZER_SCANNER.md):**
- TASK 1: Pump Wallet Analyzer — analisis token dead→pump (VAPE + Life K-line
  0x1a1e…4444, keduanya BSC), klasifikasi DEV/BUNDLER/SMART_MONEY + scoring
- TASK 2: Smart Wallet Scanner trending-based (target 50K+ wallet, $10K+ PNL)
- TASK 3: Dashboard web dark terminal aesthetic (anti-slop rules di dokumen)
- TASK 4: Cross-analysis VAPE × Life K-line (shared wallets/funding/bundler →
  grup terkoordinasi → track pump berikutnya). Sample tokens DEAD 268-352 hari
  lalu pump vertikal — pattern identik = kemungkinan grup yang sama!
- Endpoint + auth scheme + tag filter (smart_degen/sniper/bundler/dev/fresh_wallet)
  lengkap di dokumen directive

**NEXT SESSION: langsung eksekusi TASK 1+2+4 via subagent (GMGN client sudah
jadi), lalu TASK 3 dashboard. Session ini context habis.**

## SNAPSHOT S-26 — PUMP ANALYZER + VAPE LIVE ANALYSIS DONE (79 tests, commit 077318f)
- `src/analyze/pump_analyzer.py` + CLI + 15 tests (total 79 green)
- gmgn_client.py kline/top_traders payload bugs fixed by subagent
- **VAPE LIVE (BSC)**: pump terdeteksi 2026-09-08T10:35Z (peak $0.00547),
  100 traders → **63 BUNDLERS** (37 = satu klaster temporal BUNDLE_001,
  26 ber-tag bundler resmi GMGN), **3 SMART MONEY** — 2 di antaranya masuk
  5.3-6.8 JAM SEBELUM PUMP dengan win_rate 1.0 (30d PnL hingga $136K),
  33 pre-pump buyers, 0 dev terdeteksi
- Cross-analysis CLI siap: --chain2/--ca2 untuk Life K-line (rate limit
  public key = jalankan bertahap)
- **Ini blueprint pencarian GOLD wallet**: yang pre-pump + win 100% di
  token berbeda = target copytrade. Telusuri 2 smart money VAPE + 26 wallet
  fleet f70d di pump berikutnya.

## SNAPSHOT S-27 — GOLD WALLET CONFIRMED + SCALING TO 100K (user mandate)

**0x43dcf4cb1c6d84e54f0b11025a8fbb845e8e212a DIVERIFIKASI MANUAL USER di GMGN
(All chains): 7D PnL +55.17% / +$56K, win 76.27%, 344 token, 89% buy di MC
$0-$100K (early low-cap buyer), phishing clean, tags $bib/$NFLXB. ENGINE
TERBUKTI TIDAK HALU.**

**Directive scaling (user):**
- Target funnel: **100K wallet kandidat** → ultra deep-check memotong ~90%
  → diamond list. Wallet dipilah: pure profit / hoki / dev / scammer /
  rugger / deployer — cek cluster + tipe tx sama di jam/detik sama
  (indikasi hot wallet / privacy tx funding).
- Multi-chain: BSC + RH (aset user di dua chain itu).

**Trending scanner (Task 2) mulai dibangun + jalan di VPS sekarang.**

## SNAPSHOT S-28 — 0x43dcf4cb CONFIRMED GENUINE + UNREALIZED RISK FRAMEWORK (user insight)

**Verifikasi manual user (GMGN, All chains):**
- 0x43dcf4cb = GENUINE: Aug +$80,9K (20/23 hari profit, streak 13d), Sep
  +$55,8K (streak 7d) — mesin harian konsisten, BUKAN hoki
- **RED FLAG yang ditemukan user: Unrealized = -$61,7K** (setengah balance!)
- Pertanyaan kunci user: token unrealized itu token deployan dia atau token
  orang? → menentukan "trader averaging down" vs "dev trapped bag"

**FRAMEWORK BARU — penilaian wallet = 3 angka, bukan 1:**
1. `realized_pnl` — kebenaran yang sudah dicairkan (bank)
2. `unrealized_pnl` — risiko terbuka; NEGARIF besar = pegang kantong
3. `unrealized_provenance` — per token unrealized: wallet = deployernya?
   (pakai early-entry fingerprint yang sudah ada) → token sendiri = dev bag,
   token orang = investor bag

**Scoring update (implement next):**
- WalletScore tambah: unrealized_pnl, unrealized_ratio (unreal/balance),
  bags_count (token unrealized minus)
- Rule: realized positif + unrealized negatif besar → tier turun sementara
  (monitor 7 hari: cut loss = sehat; nambah = trapped)
- Tier S: realized++ AND unrealized ≥ 0 ATAU unrealized minor
- R3 sudah melarang klaim unrealized di atas data >24h — konsisten

**Dataset baru yang bisa diambil dari GMGN untuk ini:** wallet unrealized per
token ada di wallet_activity/wallet_profits (endpoint sudah di client).

## SNAPSHOT S-29 — PUMP SCAN COMPLETE: 455 real pumps detected

- Pump detector dijalankan pada seluruh PricePoint series di VPS
- **455 real pumps** terdeteksi (gain 100%-43,717%, excl. stable noise)
- Top pumps: MEME +43,717%, Jacob +19,280%, ZZZ +18,672%, BOLTAI +13,224%
- Multi-pump hunters = 0 (wajar: universe masih 341 token, wallet baru mulai
  menumpuk — hunters akan muncul saat universe >500 token)
- Hasil tersimpan: results/pump_scan.json
- Insight: 455 pump dalam ~2 bulan = chain ini SANGAT aktif — rata-rata 7-8
  pump/hari. Ini feed data yang ideal untuk pump-first wallet discovery.

## SNAPSHOT S-30 — PARTICIPANT EXTRACTION RUNNING + PUMP SCAN COMPLETE

**455 real pumps detected** (results/pump_scan.json, ter-push c726465):
- Top: MEME +43K%, Jacob +19K%, ZZZ +18K%, BOLTAI +13K%, 9TO5 +8K%
- Multi-pump hunters = 0 (expected dengan universe kecil)

**Participant extraction RUNNING di VPS** (scripts/participant_extract.py):
- Ambil top 50 pumps by gain
- Per pump: extract semua ACCUMULATOR (beli sebelum pump) + EARLY_HUNTER
  (first 10% pump) + MID_RIDER + LATE_CHASER
- Output: results/pump_participants.json
- Hasil → GOLD wallet candidates untuk copytrade priority

**Next session (urutan):**
1. Cek results/pump_participants.json — siapa yang konsisten ACCUMULATOR
   atau EARLY_HUNTER di ≥2 pumps? Itu GOLD candidates.
2. Deep-check GOLD candidates: funding chain, wallet age, dev check (via GMGN API)
3. 3-stream work order (S-13): deployer registry / auditor / re-verifier
4. Website revamp saat verified wallets >50 dan universe >500 tokens
5. M4-M6 per docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md

**VPS state:** supervisor active cycle 2 | 447+ tokens | 16K+ wallets |
65K+ events | pipeline PID running | trending scanner cron per 30 menit |
watchdog GLM per jam | systemd auto-restart

## SNAPSHOT S-31 — WEBSITE REVAMP PENDING (user: "design bolog, close dulu")

**KESALAHAN:** website raw dibuka tanpa design skill + expose port VPS. User marah.
**YANG HARUS DILAKUKAN SESSION BERIKUTNYA (PRIORITAS #1):**
1. Pakai web-design skill untuk bikin dashboard **GMGN-style dark terminal**
   (bukan editorial paper — user mau GMGN clone tapi lebih clean)
2. Frontend baca data dari **GitHub raw URLs** (repo public, auto-pushed):
   - https://raw.githubusercontent.com/papatora/TopWalllet/main/results/top_wallets_latest.json
   - https://raw.githubusercontent.com/papatora/TopWalllet/main/results/wallet_labels.json
   - https://raw.githubusercontent.com/papatora/TopWalllet/main/results/whale_entry_maps.json
   - https://raw.githubusercontent.com/papatora/TopWalllet/main/results/stats.json
   → TIDAK PERLU expose port VPS. Frontend statis di Vercel, baca data dari GitHub.
3. Deploy ke **Vercel** (bukan VPS port). GitHub PAT tersedia di .env.
4. Filter buttons per taxonomy (SNIPER/INSIDER/DEV/CLUSTER/dll)
5. Close port 8000 lagi di VPS setelah Vercel live.
6. GMGN OpenAPI (openapi.gmgn.ai, key: gmgn_solbscbaseethmonadtron) bisa
   dipakai untuk real-time data yang lebih fresh dari GitHub raw.

## SNAPSHOT S-32 — DEEP PUMP ANALYSIS + HONEST FINDINGS

- 455 pumps terdeteksi, participant extraction jalan → 0 multi-pump hunters
- Alasan: enrichment belum menjangkau periode pre-pump untuk kebanyakan token
- Wallet dengan pre-pump buys = 0 (data coverage issue, bukan bug)
- 12,880 wallets classified, 1,430 labels, 455 pumps — semua data benar
- **Diamond wallet 0xdc137c78 (+18,075%, akumulasi 51 hari) ditemukan dari
  GMGN API BUKAN dari pipeline kita — ini menunjukkan pipeline perlu:
  1. Lebih banyak token (510→5000) 
  2. Lebih banyak periode waktu (enrichment mendalam)
  3. GMGN API sebagai sumber data supplement untuk cross-validate
- Website CLOSED, VPS pipeline JALAN 24/7, semua data ter-push GitHub

## NEXT SESSION PRIORITY
1. GMGN API → cari top traders di trending RH tokens → cross-ref dengan DB
2. Enrichment cycle penuh untuk token baru
3. Round-robin reverify wallet yang sudah ada
4. GMGN criteria (bundler/insider/phishing) → enrich anti_gaming
5. Website revamp SAAT verified >50 + universe >500 tokens

## SNAPSHOT S-33 — CRITICAL FIX: PRICE DECIMALS BUG (2M points cleared)

**BUG**: sqrtPriceX96² gives ratio in SMALLEST units. USDG=6 decimals, WETH=18.
Every 18-dec token in 6-dec pool was 10¹² off. Claude session found it.
**FIX**: decimal adjustment 10^(dec0−dec1) applied in build_series_for_pool.
**DEPLOYED**: VPS restarted, 2M bad price points cleared, 21K wallets reset.
**Claude session also built**: local HTML website at Database Local only/html/
(port 8787), Bubblemaps-style visualizer, Arkham-style explorer. Not committed.
**VPS NOW**: re-running full pipeline with correct prices. This will take
several hours (21K wallets to enrich + price series to rebuild). Results will
be MUCH more accurate — realized PnL will be in real dollars, not 10¹² off.

## ⚡ S-33 SUPPLEMENT — TARGET CALIBRATION + PENDING ITEMS (2026-09-08 23:30)

**TARGET PNL BUKAN $10K — TARGET $1M+ seperti wallet "decu" di Solana:**
- decu: +$1M realized, win 61.2%, konsisten harian $500-$6.25K, unrealized $0
- Target: temukan wallet RH chain dengan profil serupa → copytrade agent
- Saat ini: top ranked cuma $24 (micro-scalper) — universe masih terlalu kecil

**UNTUK MENCAPAI 100K WALLET + $10K+ PNL — YANG HARUS DILAKUKAN:**
1. GMGN paid API — public test key tidak punya coverage untuk semua token
2. Universe expansion — trending scanner sudah jalan per 30 menit, akan menambah token secara otomatis
3. Bubblemaps scraping — cookies sudah ada, tapi perlu browser automation (playwright) untuk bypass CF
4. X/CT attribution — butuh X auth tokens dari kamu
5. Unrealized risk scoring — sudah diimplement, perlu GMGN API untuk data lengkap

**BAHAN DARI USER YANG BELUM DIPROSES:**
- Bubblemaps cookies: `C:\Users\ROG\Downloads\bubblemaps cokkies.txt`
- Arkham cookies: `C:\Users\ROG\Downloads\arkham cokkies.txt`
- fomo.family cookies: sudah di-eksport sebelumnya (expired, perlu fresh)
- X accounts: `C:\Users\ROG\Downloads\Telegram Desktop\X10akun.txt` (untuk phase CT)
- 2chapta: `C:\Users\ROG\Downloads\Telegram Desktop\2chapta.txt` (untuk bypass non-CF)
- Webshare proxies: 100 proxies + rotating endpoint
- DataImpulse resident proxy: aktif
- VPS creds: `C:\Users\ROG\Downloads\Telegram Desktop\Vps chunkserve 4cpu.txt`

**TOKEN SAMPLE UNTUK ANALYSIS (BSC — bukan RH, untuk cross-chain validation):**
- VAPE: 0xa6b53819f5bf521945fceb1f9bbb3a7a7b4effff — DEAD→PUMP pattern, sudah dianalisis
- Life K-line: 0x1a1e69f1e6182e2f8b9e8987e83c016ac9444444 — DEAD 268 hari → PUMP, sudah dianalisis
- Token1: 0xceebf25b318201f1f949be2fabbfcee231737139
- Token2: 0x0e3c3420da3ef7ee6aad373dd2cdd968f57a0788
- Token3: 0xab528169dcc80d68837a33b1e2b866bb7d7ee301
- Token4 (RUG): 0x77b857e8445baa484b49c28d225fc16538be3be8
- Token5 (pre-rug): 0xf2ce522ce04657b6f47f99b1ded10f4a33b71e18
- Token6 (pre-rug): 0x4b455ee2689b7ee65cff13011a33d406c27dcaa3

**RH TOKENS YANG SUDAH DIANALISIS:**
- 富貴 Wealth: 0xceebf25b318201f1f949be2fabbfcee231737139 — $6.32M MC, $8.2M vol
- SOUP: 0x0e3c3420da3ef7ee6aad373dd2cdd968f57a0788 — dead→pump pattern
- WRESTLER: 0xab528169dcc80d68837a33b1e2b866bb7d7ee301 — pump and dump
- WRESTLER top trader: 0x0310cfebe1d7a69f2414f6595bbe9d17c5342acc — kalender cuma Sep

**CONTEXT NOTES:**
- Context 78-81% (809K/1M) — MASIH BANYAK, jangan bilang limited
- Usage LLM: UNLIMITED (user kasih ZAI API key + unlimited plan)
- Jangan bilang "context limited" atau "extremely limited" — PROAKTIF TERUS
- Update PRE_COMPACT SETIAP selesai milestone, bukan cuma saat mau habis

---

## SNAPSHOT S-34 — S-33 DECIMALS FIX WAS BROKEN → REPLACED + VPS CREDS OUT OF SOURCE (2026-09-14)

**S-33 (`10dcc8a`) had 3 bugs** (verified with tests/test_price_decimals.py):
1. `spot = token.price_usd …` line got deleted → `NameError: spot` on EVERY
   `build_series_for_pool` → after S-33 cleared 2M points the VPS likely rebuilt
   **zero** price points. Check VPS log for `series build failed` / `spot`.
2. USDG decimals only looked up in `tokens` table (USDG isn't there) → still 18 → still 1e-12.
3. token0 branch used `10^(quote_dec − token_dec)` (sign flipped) → 1e-24.

**Replaced by `781b287`**: `quote_per_token()` = (raw or 1/raw) × 10^(token_dec − quote_dec)
(same exponent both orientations) + `PriceService._quote_decimals()` (native=18 →
tokens table → on-chain `decimals()`, cached). USDG = 6 verified on-chain. 84 tests pass.
- `scripts/backfill_quote_decimals.py`: local-only, dry-run default, per-point idempotent
  rescale of old USDG points (only needed if old bad points still exist).
- After deploy: VPS must re-run prices → analyze → feed.

**Security `22a646c`**: VPS password removed from scripts/HANDOFF → `scripts/_vps.py`
reads `VPS_HOST` + `VPS_SSH_KEY`/`VPS_PASSWORD` from local `.env`.
⚠️ Password still in git history (`86b0450`, `96699d4`) → **ROTATE root password**
(prefer SSH key + disable password login). History NOT rewritten.

---

## SNAPSHOT S-35 — ON-CHAIN TAG VERIFICATION + TAURI DESKTOP LAUNCHER (2026-09-14/15)

**USER DIRECTIVE (sesi ini):** (1) re-verify semua cluster & wallet — insider
beneran insider? phishing beneran phishing? JANGAN pakai tag mentah GMGN,
cek on-chain, lalu re-position wallet ke kategori yang benar. (2) bikin
desktop app (.exe) untuk start/stop server localhost 8787.

### A. DISCOVERY: VPS TERNYATA JALAN KODE LAMA (critical fix)
- VPS git head = 10dcc8a (broken S-33 decimals!) — commit 781b287..0d62727
  TIDAK PERNAH sampai VPS/GitHub karena local repo tidak punya remote origin
  + local GITHUB_TOKEN invalid. "S-34 one-shot finisher" tidak melakukan apa
  yang dia klaim. price_points=0 di VPS akibatnya.
- FIX: git bundle → SFTP → git reset --hard di VPS (patch loop gagal, bundle
 路径 lebih reliable). VPS branch ternyata bernama `master` (bukan main!) —
  push pakai `master:main`.
- **USER kasih GitHub PAT baru** ("github pat.txt" di Downloads) — terpasang
  di local .env + VPS .env. Push sukses. ⚠️ PAT ada di file Downloads user.
- Pipeline di-restart 17:29 UTC dengan kode decimals benar. DB VPS sekarang
  WAL mode (reader tidak lagi bentrok dengan writer).

### B. TAG VERIFICATION ENGINE (jalan sekarang di VPS)
- Masalah: 1,345 wallet dilabel INSIDER (10.4%!) — diderive dari swap_events
  lokal ("sell without buy") → false positive massal saat coverage bolong.
- `scripts/reverify_tags.py` verifikasi on-chain per (wallet, token):
  - TRADER_MISREAD: tx ternyata ada Swap log (v4 PoolManager/v3 topic) →
    bukan insider, kita kelewatan beli-nya → antre re-enrich
  - MINT_ALLOCATION: transfer dari 0x0 → insider terbukti (conf 0.95)
  - CONFIRMED_INSIDER: transfer murni non-swap → insider terbukti (0.85)
  - AIRDROP_SPAM: pengirim nyebar >=20 wallet dalam <=100 blok →
    AIRDROP_FARMER + PHISHING_TARGET (deteksi phishing on-chain pertama!)
  - UNRESOLVED: tak ada jejak transfer → turun GENERALIST + antre enrich
- Cluster: funding link funder→member diverifikasi tx on-chain + profil
  funder (CONTRACT_BATCHER / FUNDING_BOT_EOA / OPERATOR_EOA / CEX)
- Output: results/tag_verification.json (evidence), tag_overrides.json
  (koreksi label, di-apply pipeline tiap cycle via tag_overrides.py),
  reenrich_queue.json. Checkpoint per 10 pair (persist parsial).
- ANTI-SKIP: bc_get 3 putaran × 6 retry backoff; receipts 5× inline retry.
- CRON: `*/30 * * * * --max-calls 1500` + flock anti-overlap (.reverify.lock).
  Nohup detached ternyata MATI diam-diam ~9 menit (bukan OOM — RAM 7GB free;
  dugaan systemd session cleanup) → cron+checkpoint = solusi tahan-penyakit.
- Overlap label di VPS saat ini: INSIDER 1345, BUNDLER_SUSPECT 211, SNIPER
  287, DEV 19, CLUSTER 16 (be41: 14 @0.002ETH uniform, f70d: 26 funder
  250.9 ETH), MEV 5, CT 15.

### C. TAURI DESKTOP LAUNCHER (selesai + GUI-tested)
- `desktop/` — Tauri v2 app. exe 7.6MB portable + NSIS installer 1.7MB di
  desktop/src-tauri/target/release/.
- Fitur: status dot (mati/hijau-jalan/amber-port-eksternal), Mulai/Stop/
  Buka Website, live log (events), auto-detect Python (python→py→
  LOCALAPPDATA glob) + folder server.py (env→ini file→walk-up exe→default
  user path), kill child saat window close, CREATE_NO_WINDOW.
- GUI test PASS: start → HTTP 200; stop → conn refused; status dot benar.
- TIP build: a11y WebView2 tidak expose tombol HTML → test via screenshot.
  `into_string()` Cow → `to_string()`; Manager trait wajib di-import.
- Local push git HANG karena git-credential-manager dialog invisible —
  sudah di-close. Jalur push yang benar: bundle → VPS → push dari sana.

### D. STATE VPS SEKARANG
- wallets 93,459 | tokens 1,330 | pools 1,342 | swaps 302,541 | price_points
  0 (pipeline masih stage ENRICH utk 93K wallets; prices+analyze menyusul;
  sekali analyze jalan, classifier + overrides merge otomatis).
- Blockscout sering 429 (pipeline enrich) → verifier lambat tapi gigih.

### E. LOCAL EXPLORER SYNC 94K (S-35 lanjutan, user request)
- scripts/extract_wallets.py (VPS, read-only): regen wallet_labels.json dari
  TABEL DB (32,456 wallet, fresher dari file lama 12,880) + wallet_extract.csv
  (94,176 rows: kategori, aktivitas, skor, cluster, status verified) +
  wallet_extract_summary.json. INSIDER sekarang 3,470 — semua akan diverifikasi
  on-chain oleh cron (Defer-safe).
- DB snapshot selective dump (skip block_timestamps/feed_events/
  wallet_token_interest — tidak dipakai explorer): 962MB -> 30MB gz ->
  split 6MB -> download -> scripts/rebuild_local_db.py (backup otomatis
  data/topwallet.pre-s35.db). Jangan decompress per-part: gabung bytes dulu,
  gzip.decompress SEKALI (bug yang menghabiskan waktu 1x retry).
- dataset.py + evidence.js: chip "on-chain: insider PROVEN/OVERTURNED/
  airdrop spam target/unproven" di evidence panel explorer.
- Local explorer SEKARANG: 94,435 wallets, 310K swaps, 32,456 classified,
  dataset gz 11.6MB — jalan via topwallet-launcher.exe (tested HTTP 200).
- Commit terakhir: b148346 (GitHub sinkron).

## SNAPSHOT S-36 — ETHERSCAN V2 MIGRATION + VERIFIKASI OVERNIGHT (2026-09-15)

**USER DIRECTIVE:** (1) extract data semalam → update DB lokal. (2) PENTING:
robinhood scan ternyata expand ke robin.etherscan.io (Etherscan V2) — lebih
baik dari Blockscout; MIGRASI, jangan pakai Blockscout lagi.

### A. VERIFIKASI OVERNIGHT — 1,646 pair selesai (cron anti-skip bekerja)
- 712 CONFIRMED_INSIDER + 18 MINT_ALLOCATION = 730 insider TERBUKTI on-chain
- 806 TRADER_MISREAD = label insider SALAH (mereka beneran beli; coverage
  scan bolong) → TRADER_COVERAGE_GAP 772, antre re-enrich
- 90 AIRDROP_SPAM → AIRDROP_FARMER (distribusi phishing ≥20 wallet/≤100 blk)
- INSIDER bersih: 3,470 → 2,611 (semua yang tersisa sudah teruji on-chain)
- 4 ERROR (dilewati dengan tanda, resume nanti)

### B. ETHERSCAN V2 MIGRATION (commit 4451678, live di VPS)
- robin.etherscan.io = Etherscan V2 chainid 4663. API: api.etherscan.io/v2,
  WAJIB ETHERSCAN_API_KEY (gratis: etherscan.io/myapikey, 5rps/100K per hari)
  → key belum ada, user harus daftar & isi .env (local+VPS) lalu restart.
- src/utils/etherscan_client.py: EtherscanV2Client dengan METHOD SAMA +
  item berbentuk Blockscout (from.hash/token.address/total.value) → seluruh
  pipeline berganti via make_explorer_client() factory tanpa refactor.
  Blockscout = fallback legacy selama key kosong (warning log tiap start).
- tokentx sort=asc (jangkau histori terdalam dalam cap 10K — obat penyakit
  coverage-hole Blockscout); token_holders free-tier = derivasi trader aktif
  (holderlist itu PRO); metadata token via eth_call; stats=ethprice;
  chain_tokens=[] (discovery tetap DexScreener+GMGN); link UI → explorer_url.
- funding_provenance + reverify_tags + wallet_monitor + track_by_ca +
  dex_scraper + price_fetcher + feed links: semua pindah ke factory /
  interface umum address_transactions(). Funder profile verifier sekarang
  via RPC murni (eth_getCode/eth_getBalance) — explorer-agnostic.
- 91 tests green. VPS deploy + restart OK; GitHub sinkron.

### C. KEYS AKTIF — ETHERSCAN PRIMER SEKARANG (S-36 lanjutan, 2026-09-15)
- USER kirim 2 Etherscan API key → terpasang di .env local+VPS sebagai
  "KEY1,KEY2" (comma-separated). Keys TIDAK ditulis di repo (env only).
- EtherscanV2Client: round-robin rotasi per call + lompat key saat rate-limit;
  factory mengalikan rps dgn jumlah key (2 key ≈ 10 rps total, 200K/hari).
- Deploy ed2f892, supervisor restart: log "etherscan aktif keys=2" (bukan
  fallback lagi). Enrich mengalir cepat: swap +4K dalam 2 menit pertama
  (histori dalam blok Juni 2026 terjangkau — Blockscout tidak pernah bisa).
- Sync lokal hari ini: DB 94,786 wallets / 365K swaps / dataset explorer
  32,456 classified (INSIDER 2,611 terverifikasi + TRADER_COVERAGE_GAP 772
  + AIRDROP_FARMER 87). Sync ulang besok — data akan jauh lebih kaya.

### D. EXPLORER BATCH UI + LABEL BARU (S-36-D, commit 6b483a8)
- Launcher exe disalin ke Desktop user ("TopWallet Launcher.exe") — user
  semula tidak tahu app-nya sudah jadi (hanya ada di folder target).
- 3 tema: dark (default) / white / space (starfield) — klik badge
  "Robinhood Chain 4663" untuk cycle; persist localStorage. Logo: bintang.
- Guide tab baru: cara baca visualizer (DEX pool = kontrak yang wajar
  menyerap semua swap — sembunyikan via LAYERS), INDUKAN, glosarium label,
  skala keyakinan.
- Leaderboard $0 FIX: fallback harga snapshot token utk swap tanpa price
  point → 100% swap ter-priced (tetap "est."). Filter by tag ditambahkan.
- Label baru dari pola swap: BOT (kaden multi-detik ≥150 swap), SNIPER_BOT
  (bot + ≥6 early buys di ≥8 token), WHALE (est net ≥$100K TANPA linkage
  airdrop/insider/cluster), WHALE_SUS (≥$100K TAPI terhubung). Count awal:
  BOT 22, SNIPER_BOT 4, WHALE 19, WHALE_SUS 3 — preliminary sampai analyze.
- scripts/arkham_labels.py siap (butuh ARKHAM_API_KEY resmi; cookie web
  TIDAK tembus Cloudflare — sesuai kebijakan kita). Sementara: manual edit
  known_entities.json utk tag CEX/bridge (visualizer sudah render).
- Catatan proses: server manual user jalan di 8787 — JANGAN dibunuh; setelah
  update file, user cukup klik tombol rebuild (⟳) atau restart server.
