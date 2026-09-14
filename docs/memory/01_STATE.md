# 01 — CURRENT STATE (VPS + Pipeline)

> Baca ini dulu. Data terakhir verified: 2026-09-14 18:20 UTC (S-35).

## VPS
- Host: `78.31.250.202` · user: `root` · password di local `.env` (VPS_PASSWORD)
- Supervisor: **ACTIVE** (systemd `topwallet-supervisor`, auto-restart)
  - Sedang stage ENRICH utk ~93K wallets (lama, berjam-jam)
  - Setelah enrich → prices (kode decimals S-34 benar, price_points 0 saat ini)
  - Setelah analyze → classifier + tag_overrides merge otomatis
- Trending scanner: cron per 30 menit (GMGN API)
- Watchdog GLM: cron per jam
- **Re-verify tags: cron per 30 menit** (`reverify_tags.py --max-calls 1500`,
  flock anti-overlap, checkpoint per 10 pair)
- GitHub PAT baru terpasang local+VPS (S-35); push HANYA dari VPS
  (local push bisa hang di git-credential-manager → pakai jalur bundle)

## DATABASE (SQLite WAL: /opt/topwallet/data/topwallet.db)
- Tokens: **1,330** · Pools: **1,342**
- Wallets: **93,459** (meledak dari 16K — trending scanner bekerja)
- Swap events: **302,541** · Price points: **0** (menunggu stage prices)

## LABELS (snapshot analyze terakhir, sebelum enrich 93K selesai)
- INSIDER 1,345 (⚠️ mayoritas curiga false positive — verifikasi on-chain
  jalan via reverify_tags; verdict: TRADER_MISREAD / CONFIRMED_INSIDER /
  MINT_ALLOCATION / AIRDROP_SPAM / UNRESOLVED)
- BUNDLER_SUSPECT 211 · SNIPER 287 · DEV 19 · CLUSTER 16 (be41, f70d)
- Hasil verification: results/tag_verification.json + tag_overrides.json

## LOKAL
- Repo: `C:\Users\ROG\Documents\ClaudeCode\SniperToken\TopWalllet`
- Branch: `main` (VPS: `master` — push `master:main`) · Tests: **87 green**
- Desktop launcher: `desktop/src-tauri/target/release/topwallet-launcher.exe`
  (start/stop server localhost 8787 — GUI-tested, jalan)
- Explorer lokal: jalankan exe → "Mulai Server" → http://127.0.0.1:8787
