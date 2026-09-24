# 04 — NEXT STEPS (update S-44, 2026-09-25)

## SEDANG BERJALAN (S-44)
1. [VPS] cycle dgn kode refresh jalan (deploy 17:11 UTC). TUNGGU log
   "enrich refresh cohort refreshed=400" lalu swap_max_ts maju ke >16 Sep.
2. Setelah 1-2 cycle: DELTA EKSTRAKSI (fetch_dump → rebuild_local_db →
   explorer /api/rebuild) → LB/dashboard PC benar-benar bergerak.
3. Ronde audit (butuh keputusan user):
   - P1: promosikan facet→primary (SNIPER 573 label vs 127 primary;
     AIRDROP FARMER 3.125 vs 86) → GENERALIST 28.610 turun ~3.5k.
   - P2: GENERALIST dgn 1-2 swap (9.356 wallet, 32%) → bucket DUST/NOISE
     baru → GENERALIST tersisa ~15k trader aktif sejati.
   - P3: 294 wallet platform-funded (GMGN/proxy) — relabel pakai bukti
     arkham_entity di tag_overrides.

## Goal #3 X — READY
- 10/10 akun hidup (xlogin di /opt/xlogin VPS, cookies.txt 600).
- Sesi utama sudah di .env VPS: X_USERNAME/X_AUTH_TOKEN/X_CT0.
- Lanjut: modul atribusi DIAMOND pakai cookies itu (GraphQL x.com via
  browser-context; jangan API v1.1 — retired 404). File kredensial
  JANGAN masuk git.

## URUTAN LAMA
 (asli)
1. **[VPS]** `python scripts/vps_query.py scores` — kalau >0: ekstraksi
   delta (fetch_dump.py → rebuild → explorer). Kalau masih 0 berhari-hari:
   py-spy dump + grep Traceback (semua fix sudah ter-deploy fc39078).
2. **[PC] Arkham harvest lanjutan** (sesi login hidup di Brave profile):
   Goal #1 — Trace Address funder cluster via arkm.com UI, kumpulkan
   entity label → perkaya known_entities.json + tag_overrides.
3. **[PC] Goal #5 Bubblemaps** — sesi login hidup: buka bubble token RH
   chain via UI, capture response api.bubblemaps.io (listener Playwright),
   bandingkan cluster vs milik kita (detail recon di bawah).
4. **[VPS] Goal #3 DIAMOND** — setup akun X (file kredensial di Downloads,
   JANGAN masuk git) + Grok/X attribution → label DIAMOND.
5. **[PC] Goal #4** — app paste-CA (rating/cluster/deployer/funding).

## KONTEKS AKHIR MALAM (2026-09-24 dini hari)
- [VPS] cycle jalan semua fix; wallet_scores masih 0 (analyze belum tuntas
  — bukan bug, murni durasi; kalau stuck py-spy dump).
- [PC] explorer 8787 HIDUP dgn dataset 4,7 jt price_points + label
  presisi. Brave Arkham/Bubblemaps session login masih valid.
- Semua pushed s.d. commit terakhir (cek git log -1).
