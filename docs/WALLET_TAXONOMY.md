# WALLET TAXONOMY — unified wallet classification system (Phase 2 core)

> Semua wallet di DB `wallets` table WAJIB punya `wallet_type` primer + labels
> dengan evidence. Blueprint deteksi: docs/GMGN_PANDUAN_LENGKAP.md (baca §2, §3,
> §6, §7). Implementasi: `src/analyze/wallet_classifier.py` → tabel `wallet_labels`.

## PRIMARY TYPES (satu per wallet, urutan prioritas deteksi)

| # | Type | Deteksi (dari data yang SUDAH ada di DB) |
|---|---|---|
| 1 | `DEV_SERIAL_RUGGER` | early_entries ≥5 token + fast_flips ≥5 + funder sama dengan funder pool yang mati; ATAU wallet = first buyer dalam ≤50 blok dari pool creation di ≥5 token berbeda |
| 2 | `DEV` | first buyer ≤300 blok dari pool creation di 1–4 token + flip cepat; ATAU menerima token dari address 0x0 (mint) langsung |
| 3 | `BUNDLER_SUSPECT` | ikut beli token yang sama di tx_hash yang SAMA dengan ≥5 wallet lain, pada blok pertama pool (bundle = atomic banyak wallet 1 tx — GMGN guide §7) |
| 4 | `SNIPER` | first buy ≤10 blok dari pool's first observed swap (first-70 buyers pattern) |
| 5 | `INSIDER` | memegang token tanpa pernah BUY setelah pool open (receive-only dari funder yang sama dengan dev) |
| 6 | `PHISHING_SUSPECT` | menerima token via airdrop (incoming tanpa exchange leg) dari funder yang menyebar ke ≥20 wallet dalam ≤100 blok (spread pattern, GMGN guide §6) |
| 7 | `CT_ATTRIBUTED` | linked ke akun X terverifikasi (phase X nanti; sementara: ada di GMGN/fomo leaderboard capture dengan nama CT) |
| 8 | `CLUSTER_MEMBER:<id>` | funding provenance → funder sama dengan ≥3 wallet lain (contoh live: `cluster_f70d` = funder 0xf70d…dbef, 26 wallet, 250.9 ETH) |
| 9 | `AIRDROP_FARMER` | 100% incoming tanpa satu pun swap (sudah ada di anti_gaming) |
| 10 | `SMART_TRACKER` | lolos verifier R1–R3 + bar konsistensi → masuk ranked (tier S/A/B per ROADMAP §2b) |
| 11 | `FRESH_GOOD` | wallet age <30 hari + modal awal <$1K + PnL terverifikasi >10x modal + naik tier |
| 12 | `FRESH_BAD` | wallet age <30 hari + PnL konsisten negatif |
| 13 | `MEV_BOT` | median hold ≤10 menit, ≥30 round trips (sudah ada) |
| 14 | `GENERALIST` | tidak masuk kategori di atas |

## EVIDENCE & CONFIDENCE

Setiap label menyimpan: `evidence` (JSON: blok, tx, funder, token terkait),
`confidence` (0–1), `assigned_at`. Label BUKAN verdict — `SMART_TRACKER` tetap
wajib lolos verifier keras (R1–R3) sebelum masuk list copytrade.

## IMPLEMENTASI (urutan)

1. Tabel `wallet_labels` (wallet, label, confidence, evidence JSON, assigned_at)
2. `src/analyze/wallet_classifier.py`: kumpulkan sinyal dari SwapEvent + PricePoint
   + funding provenance + bundle detection (group tx_hash per pool creation)
3. Hook ke pipeline analyze: assign labels setelah scoring, sebelum export
4. Export: `results/wallet_labels.json` + kolom `wallet_type` di top_wallets JSON
5. GMGN guide §3: funder-of-dev tracking (funding wallet → dev → rug history)

## CATATAN DETEKSI (dari GMGN guide — false positive warnings)

- BUNDLER ≠ selalu dev: sniper bot pihak ketiga juga terhitung → selalu silang
  dengan funding graph (wallet bundler yang di-fund ALAMAT SAMA = satu operator)
- PHISHING % tinggi di token = holders number tidak valid, bukan pasti rug
- INSIDER: yang dicek = funder-nya sama dengan funder dev ATAU tidak pernah
  beli tapi pegang (receive-only)
- Semua label single-metrik dilarang jadi dasar vonis final — minimal 3 sinyal
  (konsentrasi supply + validitas holder + rekam jejak dev)
