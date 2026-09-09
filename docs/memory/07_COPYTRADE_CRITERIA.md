# 07 — COPYTRADE CRITERIA (what makes a wallet tier-worthy)

## TIER SYSTEM

### TIER S (copytrade priority)
```
✓ Verified: R1-R3 passed + manual spot-check
✓ Multi-token: ≥5 distinct tokens traded profitably
✓ Win rate: ≥70% (fee-adjusted, ≥1.02x threshold)
✓ PnL: realized ≥$1,000 in tracking period
✓ Style stability: same style across weeks (not flip-flopping)
✓ Hold time: compatible with copy latency (>1 hour avg)
✓ Position sizing: not all-in on single trade
✓ NOT: dev, bundler, insider, MEV, phishing suspect
✓ Unrealized: healthy (not deep negative bags)
```

### TIER A
```
✓ Verified R1-R3
✓ Win rate ≥60%
✓ PnL positive (any amount — chain is young)
✓ At least 3 positions
⚠️ May have SINGLE_TOKEN_SAMPLE flag (acceptable if pattern is clear)
```

### TIER B
```
✓ Verified R1-R3
✓ Positive PnL
⚠️ Small sample (<3 positions) or 1-2 tokens
⚠️ Monitor: could be luck, needs more data
```

### UNTIERED / REJECT
```
✗ Verification failed (any of R1/R2/R3)
✗ DEV, BUNDLER_SUSPECT, INSIDER, MEV_BOT, PHISHING_SUSPECT
✗ Unrealized deeply negative (holding bags)
✗ TREND_RIDER (profit fully explained by market beta)
```

## SCENARIO CLASSIFICATION (untuk setiap wallet, jawab 3 pertanyaan)

### Q1: Apakah PnL-nya beneran?
- Verifier R1-R3 pass? (oracle + re-derivation + stale check)
- Raw flow match? (jumlah posisi ≈ round trips dari raw transfers)
- Fee-adjusted? (win ≥1.02x, bukan 1.001x)

### Q2: Apakah PnL-nya dari SKILL atau dari hal lain?
- SKILL: dip_buying accuracy tinggi + multiple tokens + konsisten
- HALU: inflated by mispriced legs, stale marks, or data artifacts
- TREND_RIDER: profit fully explained by market beta (token naik karena pasar)
- DEV: first-buy ≈ pool creation di banyak token (insider allocation)
- BUNDLER: bagian dari grup terkoordinasi

### Q3: Apakah konsisten?
- Win rate ≥60% di ≥5 posisi? (buat chain muda: ≥3 posisi dulu)
- Active di >1 bulan?
- Style stabil (bukan ganti-ganti strategi)?
- Unrealized sehat (tidak pegang kantong minus besar)?

## SCENARIO EXAMPLES (dari data nyata)

### ✅ GOOD: 0xdc137c78 (Life K-line diamond)
```
+18,075% PnL, win 100%, akumulasi 51 hari sebelum pump
NOT dev (0 created tokens), NOT bundler, funding bersih
→ TIER: A (sample masih 1 token, tapi pattern sangat jelas)
```

### ⚠️ WATCH: 0x43dcf4cb (high-frequency machine)
```
+$136K/30d, 1,356 tokens, win 64%, scalper
REAL profit tapi unrealized -$61.7K (pegang kantong)
→ TIER: B (profit real tapi butuh pantau unrealized risk)
→ upgrade ke A kalau unrealized sehat di pass berikutnya
```

### ❌ REJECT: 0x805B2cC2 (dulu)
```
Win rate claimed 100% tapi audit raw flows = 84%
3 losing round trips disembunyikan oleh undercount bug
→ Sudah dibenahi: sekarang classified dengan benar
```
