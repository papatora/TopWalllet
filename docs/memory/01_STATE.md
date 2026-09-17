# 01 — CURRENT STATE (VPS + Pipeline) — update S-40 (2026-09-18)

> Baca ini dulu. Setelah itu: HANDOFF_MASTER (playbook top) + FIXED_LEDGER.md
> + docs/DIRECTIVE_VOLUME_SWEEP.md. Data verified: 2026-09-16 ~18:00 UTC.

## VPS
- Supervisor AKTIF. Enrich 94.786 wallet **100% selesai**. prices stage
  grinding (direct RPC sejak S-40; 403 di-cool+rotate, TIDAK crash lagi) —
  price_points/wallet_scores masih 0 s.d. S-40; pantau count harian.
- Jaringan: proxy Webshare DIBLOK CF — dexscreener+rpc wajib direct
  (default sejak 07da67e).
- Verifier on-chain: cron 30 menit (2.511 INSIDER proven; TRADER_COVERAGE_GAP
  868; AIRDROP_FARMER 91 per extract 2026-09-16). Defer-safe, flock.
- **VOLUME SWEEP LIVE**: cron */5, scripts/volume_sweep.py. Tag gate port
  bot.js (FIRST/DOUBLE/TROUGH/SUSTAIN, floor $100K 5m) → antrean CA →
  run_track_by_ca (resolve pool → upsert Token+Pool → discover semua wallet
  on-chain → prices → enrich → analyze → results/by_ca/<ca>.json).
  Debat A/B/C: semua P0/P1 tuntas, skor akhir 8/10 SHIP.
- GitHub push dari VPS (branch master:main). Lokal push suka hang.

## DATABASE LOKAL (snapshot S-39, MD5-verified dump)
- 94.961 wallets · 442K swaps · 1.442 tokens · 1.454 pools · 32.456 classified
- Labels: INSIDER 2.511 (proven) · TRADER_COVERAGE_GAP 868 · AIRDROP_FARMER 91
  · BUNDLER_SUSPECT 447 · SNIPER 127 · DEV 32 · dst.
- ⚠️ Explorer dataset perlu start ulang server (launcher) untuk membangun
  dataset dari DB baru — server sedang mati saat sync ini.
- Sync path baru: scripts/dump_snapshot.py (atomic, data-only) → split 6MB →
  SFTP → rebuild_local_db.py (build ke topwallet.new.db → validasi MIN_ROWS →
  baru replace; backup rolling topwallet.prev.db). Verifikasi part = MD5,
  BUKAN ukuran (part 6MB fixed-size dari dump beda bisa sama ukuran —
  pernah campur dua dump = stream korup).

## EXPLORER LOKAL
- Launcher: Desktop "TopWallet Launcher" shortcut → target\release exe
  (folder ASR-excluded). Mulai/Stop/Stop-paksa/Buka Website/Fullscreen.
- 3 tema, Guide tab, leaderboard filter tag, INDUKAN lineage, sub-layer
  per-item hide, freeze/reset, fold-to-group. Debat Round A-G 9/10.

## ATURAN CEPAT
- Push git SELALU dari VPS; lokal→VPS = bundle (lihat 09_VPS_OPS).
- Setelah ubah dataset.py → POST /api/rebuild (server cache stale trap).
- Blockscout fallback saja; Etherscan primer. SCRAPING = VPS only.
- DexScreener dari VPS kadang 403/429 intermittently (CF) — token_pairs
  strict=True melempar exception agar sweep membedakan outage vs token mati.
