# 04 — NEXT STEPS (update S-42, 2026-09-24)

## ✅ TUNTAS S-40/S-41/S-42 (jangan ulangi)
- Volume sweep + stock filter · ekstraksi besar 4,7 jt price_points
- Audit A-J + K: KONVERGEN 9.55 (0 P0/P1) — label presisi (MEV_BOT 48,
  INSIDER core 2.416, SNIPER 3-tingkat, f70d = bridge)
- Launcher native WinForms · 2captcha proven · CF self-healing
- Fix: autoflush sync_session, is_degraded, lock-retry, /proc-scan,
  dump resumable, direct-push fallback

## STATUS (2026-09-24 malam, S-43)
- ✅ crash-loop db-locked FIXED + deployed (6e7816a) — flock per-stage/per-entry,
  cycle hijau; prices stage panjang tapi sehat, analyze menyusul → wallet_scores.
- ✅ Goal #1: Arkham 38 funder → 652 entitas / known_entities 108; 294 wallet
  terbukti platform-funded (GMGN 134) — bukti aditif di tag_overrides; RELABEL
  MENUNGGU RONDE AUDIT (jangan auto).
- ✅ Goal #5: bubblemaps 12 token — 5 GHOST_SUPPLY ~90%, insider = distributor
  historis (bukan holder kini). results/bubblemaps/REPORT.md. Alat reusable:
  scripts/bubblemaps_capture.py.
- ✅ Goal #4: halaman "Cek Token" (#/lookup) LIVE di explorer :8787 — rating
  0-10 rincian, cluster, deployer/funder, sosial, ghost-check. (c4bfaf8)
- ⬜ Goal #3 DIAMOND: butuh akun X di [VPS] .env (file Downloads, JANGAN git).
- ⬜ wallet_scores terisi → ekstraksi delta → ronde audit (294 platform-funded
  + kandidat label token GHOST_SUPPLY).

## SISA HARI INI (update S-43)
1. [VPS] wallet_scores terisi setelah analyze → ekstraksi delta (fetch_dump→rebuild→explorer).
2. Ronde audit: 294 wallet platform-funded (GMGN/proxy) — putuskan relabel;
   kandidat label token GHOST_SUPPLY utk 5 token.
3. Goal #3 DIAMOND (akun X di [VPS] .env, JANGAN masuk git) + Goal #4 paste-CA.

## URUTAN HARI INI (asli)
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
