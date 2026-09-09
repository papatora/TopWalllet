# 08 — PUMP-FIRST PLAYBOOK (strategy pivot: cari wallet via pump, bukan random)

## KONSEP
```
LAMA (SALAH): scan wallet random → 12K wallet → top PnL $480 ← buang waktu
BARU (BENAR): cari token yang PUMP → siapa yang beli SEBELUM/awal pump?
              → wallet yang konsisten early-catch ≥2 pump di token berbeda
              = GOLD WALLET untuk copytrade
```

## IMPLEMENTASI
```
src/analyze/pump_detector.py — sudah jadi, 4 tests green
  detect_pumps(blocks, prices, min_gain_pct=100) → Pump objects
  classify_pump_participants(pump, buys, sells) → per-wallet category
  multi_pump_hunters(parts_by_pump, min_pumps=2) → GOLD list

Category per wallet per pump:
  ACCUMULATOR  — beli sebelum pump start (paling emas)
  EARLY_HUNTER — masuk first 10% of pump rise
  MID_RIDER    — tengah pump
  LATE_CHASER  — masuk last 25% (exit liquidity)

GOLD = wallet yang ACCUMULATOR atau EARLY_HUNTER di ≥2 pump BERBEDA
```

## DATA YANG SUDAH ADA
```
455 pumps terdeteksi (results/pump_scan.json):
  MEME +43K% | Jacob +19K% | ZZZ +18K% | BOLTAI +13K% | dst
  Top pump: VAPE-adjacent tokens, RH chain native tokens

Multi-pump hunters: 0 (dari 16K wallet)
→ WALBAR: universe masih 341 token. Wallet baru masuk tiap cycle.
→ Saat 500+ token + enrichment tuntas, hunters akan muncul.
```

## PLAYBOOK: finding the next diamond
```
1. Pump terdeteksi di token X (gain ≥100% dalam window)
2. Extract participants: siapa ACCUMULATOR, siapa EARLY_HUNTER
3. Cross-check: apakah wallet yang sama muncul di pump lain?
   → YA = ini systematic hunter (bukan hoki), prioritaskan
   → TIDAK = kemungkinan insider/dev satu token saja
4. Check funding provenance: modal dari mana?
   → CEX withdrawal = retail, private wallet = operator
5. Check unrealized: apakah masih hold atau sudah dump?
   → Hold + unrealized positif = conviction, pantau
6. Cross-check X/CT: apakah wallet ada tag CT di GMGN?
   → Ya = tambah ke CT attribution, pantau callout berikutnya
```
