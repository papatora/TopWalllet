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

## SNAPSHOT S-6 — 2026-09-07 dini hari (supervisor overnight AKTIF)

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
