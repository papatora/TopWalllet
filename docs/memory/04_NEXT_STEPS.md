# 04 — NEXT STEPS (update S-39, 2026-09-16)

## SELESAI S-39 (jangan dikerjakan lagi)
- ✅ VOLUME SWEEP WALLET HARVESTER — LIVE di VPS (cron */5). Debat A/B/C
  tuntas. Spec: docs/DIRECTIVE_VOLUME_SWEEP.md; kode: scripts/volume_sweep.py
  + jalur panen via src/track_by_ca.py (run_track_by_ca).
- ✅ Ekstraksi data VPS → DB lokal (94.961 wallet, MD5-verified).
- ✅ Fix bloker pipeline: etherscan token_info retry (ReadTimeout tidak lagi
  bunuh cycle → prices/analyze lanjot).

## PRIORITAS 1 — PANTAU VPS (pasif)
- price_points & wallet_scores terisi setelah cycle prices+analyze sukses
  (cek: select count(*) — masih 0 saat S-39 ditulis; kalau masih 0 berhari-hari,
  baru debugging: grep Traceback supervisor_pipeline.log).
- results/by_ca/<ca>.json muncul per token terpanen; queue di
  data/volume_sweep_state.json (caQueue). Error transien (RPC 429, DexScreener
  403/SSL) normal — queue retry; drop di 6x exception / 3x None.

## PRIORITAS 2 — ARKHAM FLOW (butuh USER login dulu)
Chromium temp dibuka → USER login Arkham manual → computer-use/python browse
wallet → harvest wallet bertag CEX → known_entities.json → visualizer.
LEGAL (akun sendiri). Lemot tak apa.

## PRIORITAS 3 — RUG-EVENT DETECTOR + OLD-TOKEN PUMP SWEEP
Sweep volume 24h semua token dikenal (dead token revive), deteksi
liquidity-pull ≤30 menit → RUGGED + RUGGER kandidat (top sell sebelum dump).
Satu keluarga dengan volume sweep — sebagian data sudah mengalir lewat
results/by_ca/ + wallet_pool.json.

## MENUNGGU KEPUTUSAN USER
- Naming final: DEV_ALLOC/CLUSTER_ALLOC/TRANSFER_IN/AIRDROP_DUST/DUST_FARMER
- Website publik (Vercel) — data matang dulu
- Stock tokens (NVDA/GOOGL/SPY di RH chain) ikut dipanen sweep — khusukkan
  filter atau biarkan? (sekarang: biarkan, mereka wallet RH chain sah)
