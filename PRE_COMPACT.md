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
