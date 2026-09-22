# 04 — NEXT STEPS (update S-40, 2026-09-18 pagi)

## SELESAI S-39/S-40 (jangan dikerjakan lagi)
- ✅ Volume sweep LIVE + filter stock tokens (config/sweep_skip_tokens.json)
- ✅ Ekstraksi harian VPS → DB lokal (94.961 wallet, MD5-verified)
- ✅ Fix jaringan: dexscreener+rpc direct (proxy CF-blocked), 403 rotate
- ✅ Launcher native WinForms (desktop/TopWalletLauncher.exe) — ganti Tauri
- ✅ Arkham: Brave+CDP login OK; harvester title-based + error-state aware;
  399/611 dicek, 20 labeled terverifikasi → known_entities.json

## ✅ ARKHAM TUNTAS (S-41, 2026-09-21 dini hari)
- 614/611 address dicek · **79 wallet BERLABEL · 81 entity di registry**
- Dataset explorer sudah di-rebuild → nama entity TAMPIL di visualizer +
  address page (Uniswap, SnuggleVaultAdminSatellite, Proxy, dll).
- **2captcha TERBUKTI jalan** (observasi user: tombol human muter sendiri
  & lolos; 1,5 jam tanpa klik manual vs dulu tiap 15-20 menit). Solver live:
  sitekey dari window._cf_chl_opt (cCKey) + inject + submit form.
- Orkestrator self-healing (backoff 5-30 menit, exit hanya setelah 5x
  hard-block tanpa progress) + cf_watch notifier.

## KONTEKS: PC user DIBIARKAN NYALA malam ini (koreksi 2026-09-21)
- **Workflow A-J jalan di PC LOKAL** — shutdown/sleep = workflow hangus.
  WAJIB: matikan sleep (Settings → Power → Never saat plugged in).
- Explorer 8787 jalan; Brave Arkham/Bubblemaps boleh di-close (session
  persist di data/arkham-profile-brave — buka lg dgn arkham_open.py).
- [VPS] jalan sendiri seperti biasa.
- User mau recall besok: arkham (done) + goal #5 bubblemaps + rescoring.

## 🚨 [VPS] DOWN (2026-09-21 pagi — user perlu cek console provider)
- SSH 78.31.250.202:22 TIMEOUT total sejak pagi (host tak merespons —
  kemungkinan hang, reboot, atau IP di-null-route provider).
- WORKFLOW A-J SUDAH JALAN 10 RONDE PENUH (A-J): 0 P0, kode explorer sehat
  (10 commit fix polish: ce0f00d..a18691d), skor tertahan 6.55 HANYA karena
  DB lokal belum punya price_points/wallet_scores (butuh ekstraksi [VPS]).
- **PUSH FALLBACK KETEMU**: lokal push via URL eksplisit
  `git push https://x-access-token:$GITHUB_TOKEN@github.com/...` TIDAK hang
  (yang hang itu credential-manager). Pakai ini selama [VPS] down.
- Saat [VPS] hidup lagi (urut): (1) cek supervisor + wallet_scores;
  (2) `git pull` di VPS (VPS ketinggalan: a18691d); (3) baru ekstraksi
  besar → rebuild → ronde audit final → konvergen.

## ❗ YANG HARUS DILAKUKAN [PC] BESOK PAGI (urut)
1. Cek [VPS]: `wallet_scores > 0`? (fix autoflush 09b7c10 baru dideploy
   dini hari — cycle analyze restart dgn kode baru; watcher lapor).
   Kalau > 0 → lanjut langkah 2. Kalau masih 0 → py-spy dump lagi.
2. **EKSTRAKSI BESAR [VPS]→[PC]**: dump_snapshot.py (SEKARANG termasuk
   4,4jt price_points — dump besar ~100MB+) → split → download MD5 →
   rebuild_local_db.py → start launcher → dataset fresh dgn price asli.
3. Audit A-J lokal (subagent adversarial) atas dataset baru (price asli!).
4. Lanjut goal #1/#5/#3/#4 (lihat bawah).

## PRIORITAS SETELAH ARKHAM TUNTAS
1. Goal #1 — re-verify cluster: Trace Address funder f70d/be41 di arkm.com
   + cross-check label entity → koreksi confidence cluster kita.
2. **Goal #5 (usulan user 2026-09-20) — RE-VERIFY CLUSTER VIA BUBBLEMAPS**:
   HASIL REKON 2026-09-21 dini hari (jangan diulang dari nol):
   - API mereka = `POST api.bubblemaps.io/relationships/subgraph?whitelist_
     token_address=<CA>&whitelist_token_chain=<slug>` → RESPONSE = JSON
     cluster utuh (nodes=holders, links) — tangkap via response listener
     Playwright saat map render di browser. TERTANGKAP sudah contohnya
     (featured solana) di results/bm_capture.json.
   - Auth = header `x-validation` (JWT HS256 yg menandatangani path+query,
     di-mint frontend) + `x-session-id` + `x-iframe-partner`. JANGAN coba
     forge token — gunakan UI/iframe mereka sbg interface (iframe src =
     `iframe.bubblemaps.io/map/<internalId>?partnerId=demo`, internalId
     BUKAN CA mentah — dapat dari queue/flow situs).
   - Homepage bubblemaps.io TIDAK punya input search visible — app UI ada
     di route lain. NEXT: screenshot homepage → temukan entry point search
     (atau klik trending lalu ganti chain/CA via UI) → capture response
     subgraph utk token RH chain → PERTANYAAN KUNCI: apakah bubblemaps
     meng-index robinhood chain sama sekali (kalau tidak, goal ini shift
     ke chain lain / nanti).
   - Etherscan label ronde-1 (614 addr, 79 named) tetap valid regardless.
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
