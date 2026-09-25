# 01 — CURRENT STATE (VPS + Pipeline) — update S-42 (2026-09-24 dini hari)

> Baca ini dulu. Setelah itu: PRE_COMPACT S-42 (paling baru) + FIXED_LEDGER +
> 04_NEXT_STEPS + playbook HANDOFF_MASTER (konvensi [VPS]/[PC] wajib).

## [VPS]
- Supervisor AKTIF dgn SEMUA fix: autoflush sync_session (fc39078),
  is_degraded (fa13afa), lock-retry per stage (e5ad5d9), /proc-scan
  (66dc995), orphan-killer. Cycle jalan — **wallet_scores masih 0**
  (analyze 3-6 jam/cycle belum tuntas; cek pertama tiap sesi:
  `python scripts/vps_query.py scores`).
- price_points [VPS]: 4,7 jt (stage prices TUNTAS).
- Dexscreener + RPC = DIRECT (proxy Webshare diblok CF permanen).
- Sweep live + stock filter (config/sweep_skip_tokens.json).
- Verifier on-chain cron 30 menit jalan.

## [PC] DATABASE LOKAL (S-42, MD5-verified)
- 94.961 wallet · 1.694 token · 442K swap · **4.707.511 price_points ASLI**
- Label presisi pasca-WF-1 (4.096 wallet relabeled): INSIDER 2.416
  (core sell-only terverifikasi), MEV_BOT 48 (be41 = ARB fleet 517/517 +
  hidden bots), f70d = BRIDGE-funded (bukan insider), SNIPER dipecah 3
  tingkat confidence, AIRDROP_FARMER 86 verified-spam.
- Explorer 8787: jalan, dataset built dgn 915 spark pool + 46 calibrated.

## [PC] ARKHAM + BUBBLEMAPS SESSION
- Brave (profile data/arkham-profile-brave): Arkham + Bubblemaps LOGIN
  HIDUP (user login 2026-09-21 malam; persist lintas shutdown).
- Buka: `python scripts/arkham_open.py brave` → 2 tab siap.
- Bubblemaps API ter-recon: POST api.bubblemaps.io/relationships/subgraph
  (response = cluster JSON utuh) — auth x-validation JWT dari frontend,
  JANGAN diforge; pakai UI/iframe sbg interface (detail 04_NEXT_STEPS).

## KONVENSI
- [VPS] = pipeline/scraping/server · [PC] = explorer/launcher/panen
  Arkham/DB lokal. WAJIB tag lokasi di tiap laporan (playbook atas).
- Push: [VPS] hidup = via VPS (bundle). [VPS] down = direct push
  `git push https://x-access-token:$GITHUB_TOKEN@github.com/...` (TIDAK
  hang — yang hang credential-manager). Terbukti S-42.


## Update 2026-09-24 16:39 UTC (S-43)
- [VPS] fix crash-loop db-locked (flock), cycle hijau; wallet_scores menunggu analyze.
- [PC] Brave CDP 9222 + sesi Arkham & Bubblemaps hidup; arkham_entities 652;
  known_entities 108; bubblemaps 12 token ter-capture (REPORT.md).


## S-45 (2026-09-25 malam)
- [VPS] fix berlapis S-44..S-45i terdeploy (ccec46f) — semua akar "LB beku"
  (enrich one-shot, flock non-FIFO, kunci per-stage, delete-transaksi,
  supervisor bunuh-diri, rps antar-proses, queue mayat). Cycle berjalan;
  pantau swap_max_ts > 2026-09-17 → jalankan night_delta.py.
- [PC] explorer mati (sengaja). Workflow "Ronde Verifikasi Swap" tersedia
  (draft .zcode/workflow-drafts/Ronde-Verifikasi-Swap.dwf.ts) — peluncur
  berulang utk pantau per ronde, auto-delta saat eligible.
