# 01 — CURRENT STATE (VPS + Pipeline) — update S-38 (2026-09-16)

> Baca ini dulu. Setelah itu: HANDOFF_MASTER (playbook top) + FIXED_LEDGER.md
> + docs/DIRECTIVE_VOLUME_SWEEP.md. Data verified: 2026-09-16.

## VPS
- Supervisor AKTIF: enrich 94K wallets (Etherscan V2 primer, 2 key rotasi).
  Setelah enrich → prices → analyze OTOMATIS (PnL terverifikasi masuk).
- Verifier on-chain: cron 30 menit (1,646 pair done: 730 proven, 806
  overturned, 90 airdrop spam). Defer-safe, flock, checkpoint.
- GitHub push dari VPS (branch master:main). Lokal push suka hang.

## DATABASE LOKAL (snapshot S-38)
- 94,786 wallets · 365K swaps · 1,378 tokens · 32,456 classified
- 100% swaps priced (est. fallback snapshot) — PnL verified menyusul
- Labels: INSIDER 2,611 (proven) · TRADER_COVERAGE_GAP 772 · AIRDROP_FARMER
  87 · BUNDLER 447 · SNIPER 127 · DEV 32 · BOT 22 · WHALE 19 · SNIPER_BOT 4
  · WHALE_SUS 3 · dst.

## EXPLORER LOKAL (semua fitur verified Round A-G)
- Launcher: Desktop "TopWallet Launcher" shortcut → targetelease exe
  (folder ASR-excluded). Mulai/Stop/Stop-paksa/Buka Website/Fullscreen.
- 3 tema (badge chain klik), Guide tab, leaderboard filter tag,
  INDUKAN lineage, sub-layer per-item hide, freeze/reset, fold-to-group.
- Kunci: Etherscan 2 key di .env lokal+VPS. GMGN key. 2chapta key (VPS .env).

## ATURAN CEPAT
- Push git SELALU dari VPS; lokal→VPS = bundle (lihat 09_VPS_OPS).
- Setelah ubah dataset.py → POST /api/rebuild (server cache stale trap).
- Jangan bunuh server 8787 user tanpa cek — sekarang launcher yang kelola.
- Blockscout fallback saja; Etherscan primer. SCRAPING = VPS only.
