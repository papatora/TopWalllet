# 04 — NEXT STEPS (update S-40, 2026-09-18 pagi)

## SELESAI S-39/S-40 (jangan dikerjakan lagi)
- ✅ Volume sweep LIVE + filter stock tokens (config/sweep_skip_tokens.json)
- ✅ Ekstraksi harian VPS → DB lokal (94.961 wallet, MD5-verified)
- ✅ Fix jaringan: dexscreener+rpc direct (proxy CF-blocked), 403 rotate
- ✅ Launcher native WinForms (desktop/TopWalletLauncher.exe) — ganti Tauri
- ✅ Arkham: Brave+CDP login OK; harvester title-based + error-state aware;
  399/611 dicek, 20 labeled terverifikasi → known_entities.json

## LANJUTAN ARKHAM (tinggal dijalankan)
1. `python scripts/arkham_open.py brave` → pastikan sesi login hidup
   (profile data/arkham-profile-brave persist; login sekali cukup).
2. Jalankan orchestrator (bg): `python scripts/arkham_orchestrator.py`
   → recheck 379 unlabeled + sisa queue sampai 611 tuntas.
3. Klik CF checkbox di Brave kalau muncul (solver 2captcha belum berfungsi —
   sitekey ada di dalam iframe challenges.cloudflare.com; fix: ekstrak dari
   page.frames lalu order TurnstileTaskProxyless pertama).
4. Selesai → merge otomatis → POST /api/rebuild → nama entity tampil.

## PRIORITAS SETELAH ARKHAM TUNTAS
1. Goal #1 — re-verify cluster: Trace Address funder f70d/be41 di arkm.com
   + cross-check label entity → koreksi confidence cluster kita.
2. **Goal #5 (usulan user 2026-09-20) — RE-VERIFY CLUSTER VIA BUBBLEMAPS**:
   setelah labeling by Robinscan/Etherscan, cross-validate deteksi cluster
   pakai bubblemaps.io (pendekatan berbeda; Etherscan = RAW + NOISE — tx
   count & kompresi timestamp bisa bikin salah label). Bubblemaps diyakini
   lebih akurat utk struktur cluster. Implementasi: kirim address cluster
   kita → bandingkan anggota cluster bubblemaps vs milik kita → catat
   selisih → koreksi confidence/label. Jalankan SETELAH goal #1.
3. Goal #3 — DIAMOND hunt: atribusi CT via GROK (akun X user; file
   kredensial di Downloads, JANGAN masuk git; simpan ke VPS .env; tool
   referensi github.com/DezXBT/AgentX). Label baru: DIAMOND (trading asli,
   PnL tinggi, tanpa indikasi insider/airdrop/phishing; pola beli-bawah-
   pump; sniper-bot dengan PnL konsisten boleh dipertimbangkan).
4. Goal #4 — app paste-CA: paste CA/link GMGN/DexScreener → rating 0-10,
   cluster, deployer, funding, sosial, ada di DB kita atau tidak.

## BERJALAN OTOMATIS (pantau saja)
- VPS: prices→analyze grinding (price_points masih 0 — kalau berhari-hari
  tetap 0, grep Traceback supervisor_pipeline.log).
- Sweep: poll 5m (stock ter-skip; track-ca jalan kalau pipeline idle).

## MENUNGGU KEPUTUSAN USER
- Naming final label (DEV_ALLOC/dll) — proposal lama masih menunggu OK.
- Website publik — data matang dulu.
