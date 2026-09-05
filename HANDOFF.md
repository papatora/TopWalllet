# HANDOFF — lanjutkan TopWallet tanpa kehilangan konteks

> Dokumen ini ditulis agar sesi berikutnya bisa langsung lanjut. Baca ini
> dulu, lalu PROGRESS.md untuk kronologi lengkap, dan **docs/ROADMAP.md untuk
> scope asli yang diperluas** (Phase 2 = "bedah wallet": PnL truth engine,
> copy-trade tiers, cluster attribution, fresh-wallet sniper pattern, CT/X
> identity attribution, follow-the-CT monitor, Whale Entry Map dari rule
> teman user). Catatan catchup Bahasa Indonesia ada di vault Obsidian:
> `C:\Users\ROG\Documents\Obsidian\Sniper Token\TopWallet\`.

## 0. PERLUASAN SCOPE DARI USER (WAJIB DIBACA — ini tugas yang sebenarnya)

User menegaskan roadmap asli 1–5 terlalu pendek. Inti tambahan (detail di
docs/ROADMAP.md):
1. **Phase 2 sebenarnya = bedah wallet**: tentukan wallet mana yang PnL-nya
   BENAR-BENAR positif vs HALU, mana yang konsisten → recommended copy-trade;
   clustere dipecah untuk tahu "milik siapa".
2. **Pola fresh wallet**: modal kecil → jutaan $ dalam minggu/bulan — deteksi
   dan pantau dari awal (ini para insider/pro).
3. **CT attribution**: wallet top CT → identitas X/Twitter (user akan sediakan
   auth token X + GitHub saat masuk phase ini); pantau CT: kalau post/beli,
   kita bisa ikor. Semua on-chain, plus AI → tahun-tahun investigasi dipadatkan.
4. **Whale Entry Map (rule teman user, WAJIB diimplement + di-A/B test)**:
   "Jangan entry asal-app. Lihat holder: whale entry di area berapa? Kalau
   area whale dekat/di atas area kita, apalagi size jumbo → conviction hold
   long-term." → fitur: distribusi entry-MC top holder per token +
   `conviction_score` untuk keputusan entry.

## 1. STATUS SAAT INI (2026-09-06, di-stop karena limit usage)

- Repo lokal: `C:\Users\ROG\Documents\ClaudeCode\SniperToken\TopWalllet`
- Remote: `https://github.com/papatora/TopWalllet` (public, sudah ter-push
  beberapa commit; commit lokal terbaru `2fe0dbe` **belum di-push** — push dulu!)
- Unit tests: **19 passed**.
- DB: `data/topwallet.db` (SQLite, di-gitignore): 62 token, 62 pool,
  1.675 wallet, 7.643+ swap events, ~22.5k price points.
- **Run yang sedang berjalan saat di-stop**: `enrich,prices,analyze` dengan
  klasifikasi BARU (fix router-hop dari hasil audit). Terhenti di enrich
  ~916/1675 wallet. **Checkpoint aman** — wallet berstatus `pending` akan
  dilanjutkan otomatis.

## 2. LANGKAH PERTAMA SAAT LANJUT (copy-paste)

```bash
cd "C:\Users\ROG\Documents\ClaudeCode\SniperToken\TopWalllet"
git push https://papatora:<GITHUB_TOKEN>@github.com/papatora/TopWalllet main
# token ada di file credentials user (JANGAN commit). Atau set .env GITHUB_TOKEN.

# lanjutkan run yang terputus (resume otomatis dari wallet pending):
.venv/Scripts/python -m src.cli pipeline --stages enrich,prices,analyze > logs/resume.log 2>&1
```

Setelah selesai, cek hasil:
```bash
python -c "import json; d=json.load(open('results/stats.json')); print(d['stage_counts'], 'ranked:', d['top_wallets_count'])"
python -m src.cli stats   # tampilkan top wallet
```
Lalu `python -m src.cli push` (atau biarkan auto-push, AUTO_PUSH_RESULTS=true).

## 3. YANG SUDAH JADI (jangan kerjakan ulang)

- **Pipeline lengkap** discover → enrich → prices → analyze(+verifikasi) → export/push.
- **Chain**: Robinhood Chain (chain id 4663, EVM L2 Arbitrum-Orbit, block ~0.101s,
  umur chain ~2 bulan per 2026-09). BUKAN Solana (user koreksi).
- **Sumber data**: DexScreener (token universe, chainId `robinhood`),
  Blockscout API v2 (`robinhoodchain.blockscout.com`, wajib User-Agent header),
  public RPC `rpc.mainnet.chain.robinhood.com` untuk getLogs.
- **Kontrak kunci**: PoolManager v4 `0x8366a39CC670B4001A1121B8F6A443A643e40951`,
  WETH `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73`,
  USDG `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168`.
- **Verifikasi keras (aturan keras user)**: `src/analyze/pnl_verifier.py`
  R1 ETH-oracle (DexScreener pool WETH/USDG $29M likuiditas; terverifikasi
  $2.455,80 vs live user $2.457,79 = deviasi 0.08%), R2 re-derivasi top-3
  trade dari raw Blockscout (≥2/3 harus cocok ≤25%), R3 stale-open (<24 jam).
  Wallet tak terverifikasi TIDAK ikut daftar Top.
- **Hasil pertama**: 101 wallet lolos bar konsistensi → 36 terverifikasi ikut
  daftar (65 gugur verification). Dominasi mikro-scalper CYBR (win 77–100%,
  1.03–1.34x per trip, PnL $7–76) — JUJUR, bukan whale 100x. Lihat
  results/top_wallets_latest.json.
- **Audit subagent** (agent selesai): metode verifikasi user minta. Hasil:
  - multiple trade AKURAT (1.2067x vs klaim 1.21; harga valid 0.4% vs DexScreener);
  - DITEMUKAN BUG: buy via router (`PoolManager→router→wallet`) terbuang karena
    cek `touched_pool` per-leg → posisi undercount ~2.5x, win rate menyesatkan;
  - fee diabaikan (trip 1.001x = rugi setelah fee);
  - 2 wallet saling jual-beli di blok sama/berdekatan ≥4x (pola wash).
  **SEMUA SUDAH DIFIX + di-commit `2fe0dbe`**:
  - `touched_pool` kini level TRANSAKSI (leg mana pun menyentuh pool);
  - `win_threshold_multiple: 1.02` di scoring_weights.json (sub-fee bukan win);
  - flag `WASH_PAIR` untuk pasangan yang ≥3x berlawanan di token+blok sama;
  - re-enrich penuh 1.675 wallet dijalankan (inilah run yang di-stop).

## 4. LARANGAN/PREFERENCES USER (patuhi!)

- JANGAN halu soal PnL — semua angka harus bisa dibuktikan dari data mentah.
- Jangan pakai 2captcha/fingerprint-spoofing untuk menembus Cloudflare
  (GMGN terblokir Cloudflare untuk plain HTTP — modulnya graceful-fail).
- Akun temp-mail/wallet kosong TIDAK dibutuhkan (semua data publik).
- Proxy: Webshare file + DataImpulse tersedia di folder Downloads Telegram
  Desktop (format ip:port:user:pass) — opsional via PROXY_URLS_FILE.
- Kalibrasi bar konsistensi: MVP preset = 3 posisi × ≥1 token
  (scoring_weights.json `thresholds`) + flag `SINGLE_TOKEN_SAMPLE`.
  Target penuh (5 posisi × 3 token) aktifkan lagi saat universe >200 token.
- Alchemy keys user = FREE TIER → getLogs dibatasi 10 blok/request. Untuk
  scale-up di VPS: upgrade SATU key ke PAYG atau pakai public RPC + kesabaran.

## 5. BUG/KEUNGGULANAN TEKNIS YANG SUDAH DIKUNCI TEST

- v4 Swap topic0 = keccak canonical `Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)`
  = `0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f`
  (hash dengan nama param = 0 log! test_price_math mengunci ini).
- sqrtPriceX96² = token1/token0 (token0 = alamat lebih kecil). Orientasi
  sekarang self-check median vs harga spot DexScreener (pernah kebalik → $118B).
- Harga cluster-based: hanya pindai ±5k blok di sekitar klaster event
  (gap<30k di-merge), max 60 klaster/pool, budget 120 call/pool — JANGAN
  kembali ke full-history scan (public RPC throttling).
- ETH quote: series pool WETH/USDG dibangun DULU sebelum klaster
  (pool WETH tidak punya event sendiri); fallback oracle DexScreener.
- Blockscout kadang 500 pada endpoint token-filtered → retry 5x backoff;
  kalau massive-500, tunggu beberapa menit.
- SQLite: jangan jalankan 2 pipeline bersamaan ("database is locked").

## 6. ROADMAP (Phase 2+, urutan disarankan)

1. Selesaikan run auditfix (langkah §2) → push hasil verified baru.
2. Audit ulang pasca-fix dengan 1 subagent (wallet #1–3 lama + beberapa baru)
   untuk membuktikan undercount hilang (jumlah posisi ≈ round-trip raw).
3. VPS deploy: `sudo bash setup.sh` di VPS user (creds ada di file user),
   MAX_TOKENS=300–500, ENRICH_CONCURRENCY=6 — di sana jalankan penuh.
4. Sumber tambahan: robinscan.io/leaderboard (chain-native!), GMGN robinhood
   (ENABLE_GMGN, butuh solusi Cloudflare — jangan 2captcha), fomo.family,
   OKX Web3. Semua optional; pipeline on-chain sudah richer dari leaderboard.
5. Funding-graph sybil clustering (funder sama + nonce), fee-aware PnL
   (parse receipt gas), dashboard UI.

## 7. FILE PENTING

- `config/settings.py` + `.env` (lokal, ada Alchemy keys + GITHUB_TOKEN — jangan commit)
- `config/scoring_weights.json` — semua bobot & threshold (win_threshold_multiple!)
- `src/pipeline.py` — orkestrator (stage_prices cluster logic di sini)
- `src/analyze/pnl_verifier.py` — aturan keras R1/R2/R3
- `results/top_wallets_latest.json` + `results/stats.json`
- `logs/topwallet.log` — JSON structured log (cari "msg": "..." saat debug)
