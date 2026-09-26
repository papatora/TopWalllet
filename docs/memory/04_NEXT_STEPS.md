# 04 — NEXT STEPS (update 2026-09-26 siang, pasca-PEMULIHAN)

## STATUS: PEMULIHAN TUNTAS ✅
- swap_max_ts **2026-09-26 10:10** (dari beku 16 Sep) — pipeline [VPS] hidup.
- Delta ke [PC] tuntas: wallets 96.716 · swaps 457.915 · price_points 5,13 jt.
- wallet_scores=0 (analyze [VPS] belum tuntas — cek harian; masuk di delta
  berikutnya).

## SISA PEKERJAAN
1. [VPS] tunggu stage analyze selesai → wallet_scores terisi → delta ulang
   → LB/dashboard penuh (skor wallet muncul).
2. Ronde audit P2/P3 versi MODIFY hakim (menunggu keputusan user):
   - P2: GENERALIST 1-2 swap → DUST, gate union dataset.py >$10k (cap 1.039).
   - P3: 133 wallet GMGN+Pons INSIDER→GENERALIST (exclude list ketat).
3. Goal #3 DIAMOND: modul atribusi X (10 akun hidup, sesi di .env [VPS];
   GraphQL via cookies, bukan API v1.1).
4. Goal #4: halaman Cek Token (#/lookup) sudah live — pakai data baru
   otomatis setelah explorer dijalankan.

- [VPS] semua fix S-44..S-45g terdeploy (35d2c55). Supervisor crash-retry
  loop berjalan; cycle pertama pasca-fix sedang mencoba lolos discover→
  enrich. SSH sempat kebanjiran sesi (EOFError) — cooldown dulu sebelum
  cek lagi, jangan spam koneksi.
- [PC] explorer 8787 MATI (sengaja, permintaan user). Data lokal masih
  snapshot 24 Sep — delta ekstraksi MENUNGGU swap fresh (swap_max_ts >
  2026-09-17).
- Audit P1-P3: 3/3 REJECT (skor 2/6/7) — menunggu keputusan manusia.
  results/audit_p123_verdicts.json + laporan-audit-malam.

## TUGAS BERIKUTNYA (urut)
1. SSH ke VPS (tunggu pulih): cek `swap_max_ts` > 2026-09-17?
   `grep -ac Traceback logs/supervisor_pipeline.log` (baseline 3884/3887).
2. Kalau fresh → `python scripts/night_delta.py` (dump→fetch→rebuild,
   resumable; manifest sudah ada fingerprint fix) → explorer rebuild.
3. Ronde verifikasi berulang pakai workflow "Ronde Verifikasi Swap"
   (draft: .zcode/workflow-drafts/Ronde-Verifikasi-Swap.dwf.ts) — auto
   jalankan delta saat eligible.
4. RONDE AUDIT P1-P3: pakai versi MODIFY hakim (P2: gate union >$10k
   cap 1.039 wallet; P3: tepat 133 wallet GMGN+Pons) — menunggu OK user.
5. Goal #3 DIAMOND: akun X siap (10/10 hidup, sesi di .env VPS) — bangun
   modul atribusi (GraphQL x.com via cookies; BUKAN API v1.1).

## JANGAN
- Jangan paksa delta manual sebelum fresh (validasi pasti gagal di max_ts).
- Jangan nyalakan explorer tanpa permintaan.
- Jangan spam koneksi SSH (rate limit).
