# 04 — NEXT STEPS (exact task list, priority order)

> Kerjakan BERURUTAN. Jangan skip. Setiap selesai → update PRE_COMPACT + push.

## TASK 1 — GMGN deep-check 4 diamond wallets (BSC)
```
Untuk masing-masing wallet di 02_DIAMOND_WALLETS.md:
  GmgnClient.wallet_activity(chain, wallet, limit=200)
  GmgnClient.wallet_profits(chain, wallet, '30d')
  GmgnClient.created_tokens(chain, wallet)

Output per wallet:
  - Token lain yang mereka early-buy (selain VAPE/LifeK)
  - Funding chain (dari mana modal pertama)
  - Apakah masih aktif hari ini
  - Pattern: akumulator / hunter / high-frequency

Yang paling penting: 0xdc137c78 (💎 +18,075% akumulasi 51 hari)
```

## TASK 2 — Trending scanner → wallet expansion (SUDAH CRON per 30 min)
```
Scanner otomatis tarik wallet dari GMGN trending (bsc + robinhood).
Pastikan trending_scanner.py jalan dan wallet_pool.json bertambah.
Target: 100K+ wallet kandidat sebelum deep-check massal.
```

## TASK 3 — Cross-analysis pump tokens
```
Untuk 455 pump yang terdeteksi:
  1. Jalankan classifier per pump (bukan cuma VAPE)
  2. Cari wallet yang muncul di ≥2 pump berbeda (GOLD hunters)
  3. Cari cluster yang sama di ≥2 pump (koordinasi)
  4. Flag dev yang launch multiple token (created_tokens)
```

## TASK 4 — Deployer registry enrichment
```
Untuk 19 DEV yang terdeteksi:
  1. GMGN created_tokens → berapa token yang mereka deploy
  2. Apakah ada rug pattern (migrated 0%, rug history)
  3. Funding wallet mereka → hubungkan ke cluster
Output: results/deployer_registry.md (sudah ada skeleton)
```

## TASK 5 — Re-verifier round-robin
```
Setiap 7 hari: re-verify top-N wallets
Setiap 30 hari: re-verify semua
Pass 2/3 mismatch → flag HALU, hapus dari ranked
```

## TASK 6 — Website revamp (SETELAH data matang)
```
Trigger: verified wallets >50 AND universe >500 tokens
Design: dark terminal GMGN-style (bukan editorial paper)
Deploy: Vercel (static, baca dari GitHub raw URLs)
Filter: per taxonomy labels (SNIPER/DEV/CLUSTER/FRESH dll)
```
