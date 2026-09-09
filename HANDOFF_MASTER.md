# TOPWALLET — COMPLETE STATE & CONTINUATION (ultra detailed)

> **BACA INI DULU SEBELUM NGAPAINTO APAPUN.** Dokumen ini berisi SEMUA yang
> perlu diketahui untuk melanjutkan proyek TopWallet. Jangan skip satu pun.

---

## 1. TARGET AKHIR (jangan lupa)

**Cari wallet-wallet DIAMOND untuk COPYTRADE AGENT** — wallet dengan PnL beneran
bukan halu, bukan dev, bukan bundler, bukan scammer. Profil yang dicari:
- Fresh wallet modal kecil → jutaan (pola insider/pro)
- CT (Crypto Twitter) wallet dengan track record terverifikasi
- Wallet yang konsisten early-buy sebelum pump, multiple token
- Wallet dengan funding bersih (bukan dari deployer/scammer)

Copytrade agent akan menggunakan list ini untuk auto-follow trading mereka.

---

## 2. STATUS SAAT INI (2026-09-08)

### VPS (78.31.250.202, root/lala123456)
- Supervisor: **ACTIVE**, cycle berjalan otomatis
- **Wallets: ~4,873+** (terus bertambah dari trending scanner per 30 menit)
- **Tokens: 447+** (Blockscout chain-wide + DexScreener trending)
- **Swap events: 65K+**
- **Pumps detected: 455** (dari pump_scan.json)
- **Classified: 11,240 wallets** dengan 12,627 labels
- **Ranked: 2 wallets** (hard filter PnL>$1 — hanya yang beneran profit)
- **GMGN trending scanner**: cron per 30 menit, active

### Website
- **CLOSED** (VPS port 8000 ditutup + GitHub Pages di-disable)
- Alasan: data belum matang + design perlu revamp total
- Spec dashboard: docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md (M0-M6)
- Bangun ulang SAAT verified wallets >50 dan universe >500 tokens

### Codebase (semua di repo, pushed)
- src/discover/gmgn_client.py — GMGN OpenAPI client (LIVE, verified)
- src/analyze/pump_analyzer.py — pump analysis + cross-analysis
- src/analyze/pump_detector.py — pump detection dari PricePoint series
- src/analyze/wallet_classifier.py — 14-type taxonomy (LIVE)
- src/analyze/funding_provenance.py — first funder tracing
- src/analyze/whale_map.py — whale entry conviction scoring
- src/analyze/pnl_verifier.py — R1/R2/R3 hard verification
- src/analyze/grouping.py — deployer registry + funding sources
- scripts/supervisor.py — overnight loop (VPS only, guard TOPWALLET_RUN_ENV)
- scripts/watchdog.py — hourly LLM check (ZAI API)
- scripts/trending_scanner.py — GMGN trending → wallet pool (cron 30min)

---

## 3. DIAMOND WALLET CANDIDATES (dari VAPE + Life K-line analysis)

**⚠️ SEMUA WALLET INI DI BSC CHAIN — cek di gmgn.ai/bsc/address/{address}**

| Wallet | PnL | Win | Entry | Status |
|---|---|---|---|---|
| 💎 `0xdc137c78c17500223031a2ca326c11062be0bad1` | +18,075% | 100% | **51 HARI** pre-pump | GOLD — akumulator sabar |
| 🟢 `0x472e619c30ea725ed9ca2f60e54a307d3044d05f` | +3,166% | 100% | 5.3 jam pre-pump | EARLY_HUNTER |
| 🟢 `0x30b6d90dc881ecc2e17080af12af0b0146888485` | +2,704% | 100% | 6.8 jam pre-pump | EARLY_HUNTER |
| 🟡 `0x43dcf4cb1c6d84e54f0b11025a8fbb845e8e212a` | +9,150% | 64% | 2.7 jam POST-pump | HIGH_FREQ (1,356 token/30d, $136K PnL 30d) |

**VERIFIKASI MANUAL USER**: 0x43dcf4cb confirmed genuine — Aug +$80.9K (20/23
hari profit, streak 13d), Sep +$55.8K (streak 7d). Tapi **unrealized -$61.7K**
(red flag — pegang kantong). Semua 4 wallet BUKAN dev (0 created tokens).

**GMGN anchors (top PnL wallets dari screenshots):**
- `0xa05ec35f7d1eba823cff2ed26aeaed419683742f` — CT: @0xyukaz — TOP WALLET
- `0x21…04b6` — +$580K/30D, win 31%, 3,385 tx
- `0xa5…282f` — +$259K/30D, win 37.4%
- `0xac…a92f` — +$258K/30D, win 46.9%
- Rell — +$221K/30D, win 39.9%
- `0x44…c40d` — +$192K/30D, win 42.6%

---

## 4. YANG HARUS DILAKUKAN SELANJUTNYA (urutan prioritas)

### LANGKAH 1 — GMGN API deep-check GOLD wallets
```
Untuk masing-masing 4 diamond wallet di atas:
  1. GET /v1/user/wallet_activity → semua tx history
  2. GET /v1/user/created_tokens → cek apakah dev
  3. GET /v1/user/wallet_stats → win rate + PnL 30d/7d/1d
  4. GET /v1/user/wallet_profits → breakdown per token
  5. GET /v1/user/wallet_activity → cari token lain yang mereka early-buy
```
Output: profil lengkap per wallet + daftar token yang mereka beli early.

### LANGKAH 2 — Expand ke RH chain via GMGN trending
```
Gunakan GMGN /v1/market/rank?chain=robinhood&interval=5m untuk:
  1. Temukan token yang SEDANG pump di RH chain
  2. Extract top traders dari token tersebut
  3. Cross-reference dengan wallet yang sudah ada di DB
  4. Wallet baru dengan tag smart_degen = kandidat diamond
```

### LANGKAH 3 — Funding provenance untuk diamond wallets
```
Untuk setiap diamond wallet:
  1. Trace ETH funding: dari mana modal pertama?
  2. Apakah dari CEX (binance hot wallet)? Dari wallet lain? Dari bridge?
  3. Kalau dari wallet lain → apakah wallet itu juga di DB kita?
  4. Build funding graph: funder → funded wallets → trades
```

### LANGKAH 4 — Copytrade tier assignment
```
Setelah deep-check:
  - Tier S: GENUINE + multi-token + win ≥70% + PnL ≥$1K + bukan dev/bundler
  - Tier A: GENUINE + single-token tapi konsisten + bukan insider
  - Tier B: GENUINE tapi sample kecil atau 1 token
  - REJECT: HALU, TREND_RIDER, DEV, BUNDLER, INSIDER
```

---

## 5. KEY TECHNICAL DETAILS (jangan diulang, sudah diperbaiki + test-pinned)

1. v4 Swap topic0 = `0x40e9cecb…` (canonical, bukan dengan nama param)
2. sqrtPriceX96² = token1/token0; orientation self-check vs DexScreener
3. Cluster-based pricing (±5k blok, bukan full scan)
4. Net-flow per tx (router hops = 1 event)
5. Win ≥1.02x (fee-aware)
6. WASH_PAIR detection (same-block counterparty)
7. SQLite: jangan 2 proses bersamaan
8. Blockscout: wajib User-Agent, retry on 500
9. GMGN OpenAPI: X-APIKEY + timestamp + client_id (±5s window)
10. Hard filter: PnL>$1, win≥1.02x, bukan dev/bundler/insider

---

## 6. GMGN OPENAPI REFERENCE

```
Base: https://openapi.gmgn.ai
Auth: X-APIKEY header (test key: gmgn_solbscbaseethmonadtron)
Params: timestamp (unix sec) + client_id (UUID)

Chains: sol, bsc, base, eth, robinhood, arc, stable
Tags: smart_degen, renowned, fresh_wallet, sniper, rat_trader, bundler, dev

Endpoints:
  GET  /v1/market/rank              trending by volume/swaps/mc
  GET  /v1/token/info               price, volume, MC, dev
  GET  /v1/token/security           honeypot, bundler, insider, rug
  GET  /v1/market/token_top_holders  top 100 + PnL + tags
  GET  /v1/market/token_top_traders  top traders + profit + tags
  GET  /v1/market/token_kline       OHLCV 30s-1d
  POST /v1/market/token_signal      price spike, smart buy, bundler dump
  GET  /v1/user/wallet_stats        win rate, PnL, token count
  POST /v1/user/wallet_profits      1d/7d/30d breakdown
  GET  /v1/user/wallet_activity     full tx ledger
  GET  /v1/user/created_tokens      tokens deployed by wallet
```

Client sudah ada: `src/discover/gmgn_client.py` (GmgnClient class)

---

## 7. FILE PENTING

| File | Isi |
|---|---|
| PRE_COMPACT.md | snapshot chain (S-1 sampai S-32) |
| SECURITY_POLICY.md | aturan operasional (VPS only, supply chain) |
| docs/ROADMAP.md | scope lengkap (2a-2g, 3, 4, 5) |
| docs/WALLET_TAXONOMY.md | 14 tipe wallet + deteksi |
| docs/DIRECTIVE_PUMP_ANALYZER_SCANNER.md | GMGN API directive |
| docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md | product spec (M0-M6) |
| src/discover/gmgn_client.py | GMGN API client |
| src/analyze/wallet_classifier.py | 14-type classifier |
| src/analyze/pnl_verifier.py | R1/R2/R3 hard verifier |
| results/wallet_labels.json | labels per wallet |
| results/pump_scan.json | 455 pumps |
| results/gold_wallet_deepcheck.json | deep-check 4 diamond |
| results/funder_clusters.json | cluster f70d + lainnya |

---

## 8. OBSIDIAN SYNC

Semua dokumen penting ada di: `C:\Users\ROG\Documents\Obsidian\Sniper Token\TopWallet\`
- Catchup & Handoff.md
- PRE_COMPACT.md
- WALLET_TAXONOMY.md
- SECURITY_POLICY.md
- ROADMAP.md
- ULTIMATE_PROMPT_SMART_MONEY_FEED.md
- GMGN_PANDUAN_LENGKAP.md
- funding_sources.md
- deployer_registry.md
