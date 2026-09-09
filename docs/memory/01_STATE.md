# 01 — CURRENT STATE (VPS + Pipeline)

> Baca ini dulu. Data terakhir verified: 2026-09-09 08:03 UTC.

## VPS
- Host: `78.31.250.202` · user: `root` · password di file creds user
- Supervisor: **ACTIVE** (systemd `topwallet-supervisor`, auto-restart)
- API: **STOPPED** (disabled per user — buka saat data matang)
- Trending scanner: **cron per 30 menit** (GMGN API)
- Watchdog GLM: **cron per jam** (auto-restart kalau mati)
- Pipeline: **cycle per jam** (discover→enrich→prices→analyze→export→push)

## DATABASE (SQLite: /opt/topwallet/data/topwallet.db)
- Tokens: **447+**
- Wallets: **16,259+**
- Swap events: **65,412+**
- Wallet labels: **12,627 assigned** (1,310 classified)
- Deployer registry: **1,489 entries** (19 devs, 1,185 insiders, 285 snipers)

## RANKED LIST
- 2 wallets lolos SEMUA filter (PnL>$1 + verifier R1-R3 + anti-gaming)
- 23 trash sudah dibuang (PnL negatif tapi composite score tinggi)
- **Ini kualitas, bukan kekurangan** — filter keras mencegah halu

## LOKAL
- Repo: `C:\Users\ROG\Documents\ClaudeCode\SniperToken\TopWalllet`
- Branch: `main` · Tests: **79 green** · Last push: `96699d4`
- Obsidian: `C:\Users\ROG\Documents\Obsidian\Sniper Token\TopWallet\`

## SUMMARY STATS JSON
```json
{
  "tokens_in_db": 447, "pools_in_db": 449, "wallets_in_db": 16259,
  "swap_events": 65412, "wallets_scored": 476, "wallets_excluded": 166,
  "top_wallets_count": 2, "wallets_classified": 11240, "labels_assigned": 12627
}
```
