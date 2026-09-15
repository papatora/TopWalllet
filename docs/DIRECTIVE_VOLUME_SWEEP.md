# DIRECTIVE — VOLUME SWEEP WALLET HARVESTER (implementasi pasca-compact)

> Konteks: user punya bot notifikasi Telegram (`C:\Users\ROG\Documents\ClaudeCode\
> VolumeNotification\bot.js`) yang polling GMGN interval 5m dan kirim alert
> ketika volume token menyentuh tier $100K lalu doubling. TopWallet TIDAK
> kirim notifikasi — kita lebih tajam: **kita panen WALLET-NYA** (top traders,
> bundler, dev, sniper early, korban rug) jadi bahan database + bahan
> verifikasi on-chain.

## KENAPA PENTING (dari observasi user, 2026-09-15)
- Hari ini saja 200+ token RH chain yang volume 5m-nya tembus tier
  ($100K / $300K / $500K / $700K) — mayoritas LIQUIDITY KECIL + VOLUME TINGGI
  DI AWAL = pola RUG. Bertahan 5-22 menit lalu rug.
- Ada juga yang tidak rug tapi volume kecil; ada token LAMA (3d/10d+) yang
  tiba-tiba pump 300K → 3M-5M lalu stay; ada juga yang rug pas pump.
- Susah cari token yang MASIH di puncak ("di tiang") dan belum dibanting —
  makanya yang dikejar BUKAN tokennya, tapi WALLET-WALLET-nya (sniper early,
  bundler, dev, akumulator) — itu aset yang hidup lebih lama dari token.

## MEKANISME TAGGING (port dari bot.js — JANGAN diubah konsepnya)
- Polling: GMGN `/v1/market/rank` interval `5m`, chain robinhood.
- TAG_FLOOR = $100,000 volume (5m).
- State per token (`chain:address`): `lastTagVol`, `troughVol`.
- Eligible re-catch:
  1. FIRST — volume ≥ floor (pertama kali)
  2. DOUBLE — volume ≥ 2× lastTagVol (step dolar mengecil relatif saat token
     membesar; makanya pakai multiplier, bukan step flat)
  3. TROUGH — volume pernah anjlok ≤ $350K lalu naik lagi ≥ floor (token lama
     yang "hidup lagi" — ini yang mencakup kasus dead token → pump 300K→3M)
  4. SUSTAIN — volume bertahan ≥ floor terus selama window tertentu
- FILTER RUG-RISK: `volume / liquidity` tinggi di AWAL (liqu kecil, vol besar)
  = pola rug. Token ini tetap DIPANEN walletnya (justru penting: sniper early
  + dev + bundler-nya = kandidat rugger serial), tapi DITANDAI rug-risk agar
  tidak masuk daftar whale/smart.

## YANG DIPANEN PER TOKEN QUALIFYING (urutan prioritas)
1. Top traders (Etherscan `token_transfers` / GMGN token_top_traders) — semua
   wallet dengan volume signifikan.
2. FIRST BUYERS ≤10 blok (sniper) dan ≤300 blok (dev).
3. Same-tx bundles (bundler).
4. Korban rug = buyer setelah puncak terakhir sebelum volume anjlok
   (LATE_CHASER) — tandai `RUG_VICTIM` (bukan untuk copytrade, tapi untuk
   memetakan rugger: wallet yang SELL tepat sebelum anjlok = RUGGER kandidat).
5. Semua wallet baru → masuk antrean ENRICH (full history) → classifier →
   verifier on-chain (reverify_tags).

## INTEGRASI PIPELINE
- File baru: `scripts/volume_sweep.py` (VPS, cron per 5-10 menit atau loop
  dalam trending_scanner).
- Reuse: `src/discover/gmgn_client.py` (rank 5m), `EtherscanV2Client
  .token_transfers()`, `src/enrich/tx_fetcher.py`, `reverify_tags.py`.
- State file: `data/volume_sweep_state.json` (lastTagVol/trough per token —
  format sama dengan bot.js supaya konsisten mental modelnya).
- Output: token qualifying → wallet → wallet_pool + langsung antrean enrich.
- Threshold & tier via config (jangan hardcode): `VOLUME_SWEEP_FLOOR=100000`,
  `VOLUME_SWEEP_DOUBLE=2.0`, `VOLUME_SWEEP_TROUGH=350000`.

## HAL YANG PERLU DITAMBAH JUGA (satu keluarga dengan sweep ini)
- RUG-EVENT DETECTOR: dev/liquidity pull dalam ≤30 menit setelah launch →
  tandai token RUGGED, wallet top SELL sebelum anjlok → RUGGER kandidat
  (sering token yang sama beda nama — serial rugger).
- OLD-TOKEN PUMP SWEEP: cek SEMUA token yang sudah ada di DB (bukan cuma
  trending baru) — volume 24h melonjak ≥10x dari baseline → queue deep scan.
- KORELASI SERIAL RUGGER: wallet dev/rugger yang muncul di ≥2 token berbeda
  → label DEV_SERIAL_RUGGER (sudah ada di taxonomy, tinggal data).

## PERINGATAN OPERASIONAL
- GMGN public key rate-limit tipis — polling 5m + budget rps 1.5-2.0, jangan
  brutál. Kalau butuh lebih, user beli GMGN plan.
- Semua scraping di VPS (ATURAN 1). Jangan jalankan lokal.
- Wallet hasil panen → enrich BERAT → pastikan jangan tabrakan dengan cycle
  utama (single pipeline process, SQLite lock).
