# 03 — DETECTION RULES (all signals + false positives)

> Blueprint: docs/GMGN_PANDUAN_LENGKAP.md. Implementasi: src/analyze/wallet_classifier.py

## 14 WALLET TYPES (priority order, first match = primary)

| # | Type | Detection | False Positive Warning |
|---|---|---|---|
| 1 | DEV_SERIAL_RUGGER | early_entries≥5 + fast_flips≥5 di token berbeda | Bisa jadi trader yang cuma suka memecoin baru |
| 2 | DEV | first_buy ≤300 blok pool creation + flip cepat | Trader luck ≠ dev |
| 3 | BUNDLER_SUSPECT | ikut beli di tx_hash yang SAMA dengan ≥5 wallet, di blok pertama pool | Sniper bot pihak ketiga juga terhitung |
| 4 | SNIPER | first_buy ≤10 blok dari pool's first observed swap | Bukan semua sniper jelek |
| 5 | INSIDER | ada SELL tapi zero BUY di token yang sama (terima via transfer) | Bisa jadi airdrop legit |
| 6 | PHISHING_SUSPECT | menerima token dari funder yang menyebar ke ≥20 wallet dalam ≤100 blok | Perlu transfer-spread graph (belum implement) |
| 7 | CT_ATTRIBUTED | ada di GMGN/fomo leaderboard dengan nama CT | Attribution bisa salah |
| 8 | CLUSTER_MEMBER:{id} | funder sama dengan ≥3 wallet lain | Shared CEX withdrawal bisa false positive |
| 9 | AIRDROP_FARMER | 100% incoming, zero swap | |
| 10 | SMART_TRACKER | lolos verifier R1-R3 | |
| 11 | FRESH_GOOD | age <30 hari + PnL terverifikasi >10x modal | |
| 12 | FRESH_BAD | age <30 hari + PnL konsisten negatif | |
| 13 | MEV_BOT | median hold ≤10 min, ≥30 round trips | |
| 14 | GENERALIST | fallback | |

## DETECTION LANDMINES (sudah diperbaiki + test-pinned)

### 1. Router-hop classification
**JANGAN** klasifikasi per-leg. Klasifikasi **per-transaksi**: group legs by
tx_hash, cek APA PUN leg yang menyentuh pool counterparties. Router hops
(PoolManager→router→wallet) membuat per-leg check membuang BUY legs →
undercount ~2.5×.

### 2. Fee-aware win threshold
Win = return_multiple ≥ **1.02**. Trip 1.001–1.017x itu breakeven/rugi setelah
fee 1%. Kalau dihitung menang = win rate inflated.

### 3. Bundle detection
≥5 wallet di sisi BERLAWANAN (satu BUY satu SELL) token sama dalam blok sama
≥3 kali = `WASH_PAIR`. Satu tx dengan ≥5 BUY dari wallet berbeda di blok
pertama pool = `BUNDLER_SUSPECT`.

### 4. Cluster detection
Funder yang sama mendanai ≥3 wallet → `CLUSTER_MEMBER:{id}`.
**Contoh live**: cluster_f70d = funder 0xf70d…(250.9 ETH) → 26 wallet.

### 5. Pump detection
Scan ±5k blok sekitar trade clusters (gap <30k blok di-merge, margin 5k).
JANGAN full-history scan. Budget 120 getLogs calls/pool. USDG/WETH series
HARUS dibangun dulu ( mereka tidak punya swap events sendiri).

---

## GMGN SECURITY PANEL MAPPING (untuk memperkaya analysis)

| GMGN Label | Deteksi On-Chain | Status |
|---|---|---|
| Top 10 >30% | Perlu holder snapshot | ⬜ Phase 2 |
| DEV % | created_tokens via GMGN API | ✅ via GmgnClient |
| Snipers x/70 | first BUY ≤10 blok pool | ✅ via classifier |
| Insiders | SELL tanpa BUY (received via transfer) | ✅ via classifier |
| Phishing | funder spread pattern ≥20 wallets | ⬜ perlu transfers table |
| Bundler % | multi-buy same tx at pool creation | ✅ via classifier |
| Rug History | creator's token performance | ⬜ via GMGN /created_tokens |
| Funding wallet | first ETH incoming source | ✅ via funding_provenance |
| Dev's Best ATH | max pool price × supply | ⬜ perlu supply data |
| Callout/X | GMGN callout API | ⬜ via GmgnClient (belum) |
