# FIXED LEDGER — masalah yang SUDAH difix & diverifikasi (jangan di-re-open)

> Tujuan: setelah context compact, agent baru sering melakukan blind-fix —
> membuka lagi bug yang sudah fix, atau menganggap ada bug padahal bukan.
> LEDGER ini = daftar lengkap "sudah fix + diverifikasi" (dossier
> DEBATE_ROUND_A..G.md = bukti). SEBELUM memfix sesuatu, cek ledger ini.
> Update ledger SETIAP kali fix baru diverifikasi.

Legenda: ✅ FIXED+VERIFIED · ⚠️ LIMITASI DIKETAHUI (bukan bug, jangan "diperbaiki") · 🔜 DIJADWALKAN

## Explorer / Visualizer
- ✅ `css is not defined` crash visualizer — helper `css()` didefinisikan module-level di graph.js
- ✅ `groupNodes is not defined` crash — sekarang `groupOf`
- ✅ Fold bundler/cluster: anggota plain dilipat ke 1 group bubble per entitas
  (chunk 20 dihapus; 1 entitas = 1 grup), hub cube tetap, special-labeled
  (whale/insider/dll) tetap individual. isPlain v2 = SPECIAL_LABELS set tanpa
  SNIPER/BUNDLER_SUSPECT/CLUSTER_MEMBER.
- ✅ visibleGraph mengenali kind 'group' (ikut layer funders/bundles) —
  preset Bubblemaps raw tidak runtuh, 0 grup yatim.
- ✅ INDUKAN (lineage) tampil di kartu node visualizer (lookup BY ADDRESS)
  + halaman address (by address). 737 wallet berlineage.
- ✅ Reset: mengembalikan layer/warna/cap/hidden/collapse/timeline + UNPIN
  SEMUA node scope (termasuk yang hidden) + kamera fit + panel dimunculkan.
- ✅ Freeze: settle sim (alpha=0) + fit saat freeze; Resume reheat 0.15.
  Freeze/Resume hanya satu kontrol (panel kiri); rail freeze lama dihapus.
- ✅ Fullscreen toggle (data-act fs).
- ✅ Panel kiri/kanan collapsible (x = hide, chevron tab = show).
- ✅ Sub-layer chevron di LAYERS untuk DEX pools/Funders/Bundle tx — hide
  per-item (eye), vol per item.
- ✅ 8 tombol mati ter-wiring: group/ungroup, unpin, range-clear,
  toggle-flow, unhide, open, more, expand (entity → wallet scope).
- ✅ Timeline bars + teks theme-aware (var CSS, bukan hex).
- ✅ White mode: nav/panel/rail/time/fchip/pill/seg/entity semuanya var tema
  (tidak ada lagi hardcode gelap yang membuat teks tak terbaca).
- ✅ Space: 120 bintang 2 layer kelap-kelip + komet CANVAS (script user,
  fisika natural, spawn 0.9–2.7s, hanya tema space, gated MutationObserver).
- ✅ Leaderboard $0 FIXED (fallback harga snapshot; 100% swap priced) +
  filter by tag.
- ✅ Labels tab menampilkan BOT/SNIPER_BOT/WHALE/WHALE_SUS/
  PHISHING_TARGET/TRADER_COVERAGE_GAP (label_counts + derived).
- ✅ meta.label_counts + derived; labels/confidence aligned di 32.456 rows.

## Pipeline / Data
- ✅ Etherscan V2 PRIMER (api.etherscan.io/v2, chainid 4663, 2 key rotasi,
  round-robin + rotasi saat rate-limit). Blockscout = fallback legacy.
- ✅ dataset.py: fallback pricing snapshot (P0 snap shadow FIXED — snap_px);
  label_counts + derived.
- ✅ Verifikasi on-chain INSIDER/CLUSTER: 1,646 pair (730 proven, 806
  dibantalkan, 90 airdrop spam); cron 30 menit + flock + Defer anti-skip.
- ✅ extract_wallets.py: CSV 94K + labels regen dari DB + summary.
- ✅ rebuild_local_db.py: dump selektif VPS → DB lokal (backup otomatis).

## Launcher Desktop
- ✅ Tauri exe jalan; deteksi Python + folder server; Mulai/Stop/Buka.
- ✅ Stop sekarang SEKALIGUS paksa-matikan proses APAPUN yang memegang port
  8787 (netstat → taskkill), jadi server eksternal yatim pun bisa distop
  dari tombol.
- ⚠️ Defender ASR memblokir exe yang disalin ke Desktop (prevalence) —
  SOLUSI: folder `desktop\src-tauri\target\release` masuk ASR exclusion;
  Desktop pakai SHORTCUT (.lnk) ke exe di folder itu. Jangan salin exe-nya
  langsung ke Desktop lagi.

## ⚠️ LIMITASI DIKETAHUI (bukan bug — JANGAN "diperbaiki")
- Wallet cap 600: churn reheat ±7 detik (sim O(n²)) — pakai FREEZE; decay
  sudah 0.035 (2× lebih cepat dari semula).
- Raw preset: wallet top individual degree-0 (pool/edge sengaja off) — by design.
- USD = ESTIMASI harga snapshot sampai VPS selesai prices+analyze.
- Sub-layer list mode entity masih all-time vol (minor).
- `paused` sengaja tidak di-restore saat reload (mulai selalu unfrozen).

## 🔜 DIJADWALKAN (belum diimplementasi — jangan anggap sudah ada)
- VOLUME SWEEP WALLET HARVESTER — spec: docs/DIRECTIVE_VOLUME_SWEEP.md
  (floor $100K 5m + DOUBLE/TROUGH/SUSTAIN, panen wallet, filter rug-risk).
- Rug-event detector (liquidity pull ≤30 menit) + old-token pump sweep +
  serial rugger correlation.
- Arkham flow: chromium temp + user login manual + harvest tag CEX.
- Re-enrich TRADER_COVERAGE_GAP (772) + 772-an wallet coverage gap.
- Sub-layer entity-mode vol range-aware (minor).
