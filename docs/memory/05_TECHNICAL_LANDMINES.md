# 05 — TECHNICAL LANDMINES (things that break SILENTLY)

> Setiap item di bawah ini PERNAH menyebabkan hasil salah tanpa error.
> Jangan ulangi. Semua sudah ada test yang mengunci.

## 1. v4 Swap topic0
```
BENAR:  0x40e9cecb… (keccak canonical tanpa nama param)
SALAH:  hash dengan nama param/indexed → 0 logs TANPA ERROR
Test:   tests/test_price_math.py::test_v4_swap_topic_matches_onchain
```

## 2. Price orientation
```
sqrtPriceX96² = token1/token0 (token0 = alamat lebih kecil)
SALAH arah = harga $118 miliar. Self-check vs DexScreener median.
Test: orientation dipilih otomatis di build_series_for_pool
```

## 3. Cluster pricing (JANGAN full scan)
```
Scan ±5k blok sekitar trade clusters (gap <30k merge).
Full-history scan = throttle + self-DoS.
Budget: 120 getLogs/pool, max 60 clusters/pool.
```

## 4. Net-flow per TX classification
```
JANGAN per-leg classification (PoolManager→router→wallet = BUY terbuang).
Group legs by tx_hash, cek APA PUN leg menyentuh pool.
Per-leg = undercount 2.5× (ditemukan oleh audit subagent).
```

## 5. Fee-aware win
```
Win = return ≥1.02x. Trip 1.001x = RUGI setelah fee 1%.
Config: scoring_weights.json → thresholds.win_threshold_multiple
```

## 6. WASH_PAIR
```
≥3 kali berlawanan sisi token sama dalam blok sama = koordinasi.
Sudah ditemukan di data nyata (2 wallet top-38).
```

## 7. SQLite lock
```
JANGAN jalankan 2 pipeline bersamaan. "database is locked" = crash.
Pipeline + API bersamaan = aman (API read-only dengan busy timeout 30s).
```

## 8. WETH series harus dibangun DULU
```
WETH/USDG pool tidak punya swap events sendiri.
Kalau tidak dibangun sebelum token loop → semua ETH-quoted pool gagal.
```

## 9. Stable coin price noise
```
USDG series kadang punya near-zero points → persentase 10^37%.
Filter: gain <100.000% dan token ≠ stable.
```

## 10. SSH rate limit
```
Jangan reconnect ke VPS terlalu cepat (10054 reset).
Tunggu 30+ detik antar koneksi. Gunakan setsid untuk detached processes.
```
