# Scoring methodology

## Position definition

A **position** is one round trip of a wallet in one token, built by FIFO lot
accounting over the wallet's classified swaps:

- consecutive BUYs accumulate a volume-weighted cost basis
- a SELL realizes the proportional cost basis → **closed position**
  (return multiple = proceeds / cost of the sold slice)
- whatever remains is an **open position** valued at the token's latest known
  price → **unrealized** return

A "winning" position = return multiple > 1.0.

## Timing percentiles

For every position we look at the token's pool price series within
±`DIP_WINDOW_DAYS` (default 7) of the entry/exit block and compute the
fraction of window prices strictly below the trade price:

- `entry_pctile ≈ 0.0` → bought at the **local bottom** (dip buy)
- `exit_pctile ≈ 1.0` → sold at the **local top**

`dip_buying_accuracy` = share of entries with pctile ≤ 0.2.
`top_selling_accuracy` = share of exits with pctile ≥ 0.8.

## Wallet metrics

| Metric | Definition |
|---|---|
| win_rate | winning closed positions / closed positions |
| median_return_multiple | median multiple across closed positions |
| max_return_multiple | best closed multiple (the 100x–1000x detector) |
| total_realized_pnl_usd | Σ pnl over closed positions |
| total_unrealized_pnl_usd | Σ (current value − cost) over open positions |
| consistency_score | win_rate × (0.4 + 0.6 × min(distinct_tokens/15, 1)) |
| recent_win_rate | win rate with exponential age weighting (45-day half-life) |
| big_wins | closed positions with multiple ≥ 10x |

## Composite score (0–100)

Weights live in `config/scoring_weights.json`:

| Component | Weight | Normalization |
|---|---|---|
| win_rate | 0.22 | raw (0–1) |
| median_return | 0.18 | log10(median) / log10(20), capped at 1 |
| moonshots | 0.10 | log10(max) / log10(500), capped at 1 |
| dip_buying | 0.15 | raw (0–1) |
| top_selling | 0.10 | raw (0–1) |
| consistency | 0.15 | raw (0–1) |
| recency | 0.10 | raw (0–1) |

`composite = 100 × Σ(weightᵢ × componentᵢ) / Σ weightᵢ`

Tune the JSON without touching code; the pipeline reloads it every run.

## Trading styles

Tags from thresholds in the same JSON: `dip_buyer`, `top_seller`,
`diamond_hands` (deep unrealized winners or ≥7-day holds), `scalper`,
`multi_moonshot` (≥3 separate 10x+), `whale_size` (median position ≥ $5k).
Output joins up to 3 tags, e.g. `dip_buyer_diamond_hands_multi_moonshot`.

## Anti-gaming

| Flag | Trigger | Effect |
|---|---|---|
| LOW_DATA | <5 positions or <3 distinct tokens | **excluded** |
| AIRDROP_FARMER | zero BUY events (only receives) | **excluded** |
| MEV_BOT | median hold ≤10 min on ≥30 positions | flag |
| WASH_SUSPECT | ≥5 same-token round trips within 30 blocks | flag |
| INSIDER_SUSPECT | first buy ≤300 blocks after first observed token trade + fast dump at >20x | flag |
| UNREALISTIC_RETURNS | median >1000x on <10 closed positions | flag |
| DUST_ONLY | median position <$10 | flag |
| cluster_* | token-set Jaccard ≥0.85 with other wallets (sybil fleet) | tag |

Phase 2 roadmap: funding-graph clustering (common funder address, nonce
linkage), counterparty circular-flow detection.

## Hard PnL verification (aturan keras)

Ranked output ships ONLY wallets that survive independent re-derivation
(`VERIFY_PNL=true`, `src/analyze/pnl_verifier.py`):

- **R1 — ETH oracle cross-check**: the ETH USD price used for valuations must
  match an independent on-chain source (most liquid WETH/USDG pool via
  DexScreener) within 2%. Verified 2026-09-05: pool price $2,455.80 vs live
  reference $2,457.79 → 0.08% deviation. On mismatch, all ETH-quoted PnL is
  unverified and such wallets are dropped.
- **R2 — trade re-derivation**: each top wallet's top-3 closed trades are
  re-pulled RAW from Blockscout (fresh requests, not our DB) and the return
  multiple recomputed. ≥2 of 3 must match within 25%, else `PNL_UNVERIFIED`
  → dropped from Top-N.
- **R3 — stale-open rule**: unrealized multiples only count when the price
  point they rest on is <24h old.

Each exported wallet carries a `verification` block:
`{"verdict": "verified", "eth_oracle_ok": true, "trades_verified": "3/3", "details": []}`.

