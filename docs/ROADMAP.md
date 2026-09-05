# ROADMAP — the real phases (living document)

> The original phase list (1–5) was a scaffold. The REAL work is longer and
> deeper, centered on one question: **which wallets are genuinely, verifiably,
> consistently profitable — and who is behind them?** This document is the
> source of truth for scope. Update it as phases evolve.

North star: **AI + on-chain data + community attribution compresses years of
trading-forensics into weeks** — and turns unrealized PnL into realized PnL by
following verified smart money, not vibes.

---

## PHASE 2 — "Bedah Wallet" (wallet forensics) — THE CORE

### 2a. PnL Truth Engine (beyond R1–R3)
Classify every scored wallet into exactly one verdict:
- `GENUINE` — PnL survives re-derivation, fee-adjustment, and raw-flow matching
- `HALU` — inflated by data artifacts (mispriced legs, router double-counts,
  stale marks, dust-churn win-farming) — quantified: reported vs audited delta
- `TREND_RIDER` — profits fully explained by token beta (entered during a
  +230% pump with everyone else); no entry-timing skill vs token cohort
Hard outputs per wallet: fee-adjusted realized PnL, audited win rate (raw
round-trips, not classified positions), max drawdown inside positions.
Current state: R1/R2/R3 verifier exists; fee-adjustment + trend-cohort
comparison + raw-flow win-rate are the next three increments.

### 2b. Copy-trade recommendation tier
A wallet becomes `RECOMMENDED_FOR_COPYTRADE` only with: GENUINE verdict +
style stability (same style across weeks) + hold-time compatible with
copy-latency + position sizing sane (not one-coin-all-in lottery) + verified
history length. Output: tiered list (S/A/B) with per-wallet "copy profile":
typical entry→exit window, avg size, drawdown risk, token quality filter.

### 2c. Cluster attribution — "cluster ini milik siapa"
Go beyond token-set Jaccard:
- funding graph: shared funder address, nonce adjacency, bridge-in source
- counterparty graph: wash-pairs (already flagged), repeated same-block flows
- cash-out venue: which CEX deposit addresses clusters drain to (identifies
  operator geography/venue)
- known-entity matching: exchange hot wallets, market makers, known KOL wallets
Output: cluster → operator hypothesis + confidence + evidence list.

### 2d. Fresh-wallet sniper pattern
Detect the pattern: **fresh wallet, small capital, $K → $M within weeks**.
Signals: wallet age < 90d, first funding trace, early entry into tokens before
liquidity events, growth curve steepness. Purpose: find these wallets EARLY
(they are the insiders/pros) and monitor from their first trade, not after
they are famous.

### 2e. CT identity attribution — "wallet ini punya siapa"
Map wallets → X/Twitter identities:
- community tags from GMGN / fomo.family leaderboards (screenshot evidence:
  CT names + PnL + **avg entry MC** + X post links per wallet)
- time-correlation: a CT account posts about CA, an attributed wallet buys
  within minutes → identity link candidate
- user will provide X auth tokens + GitHub access at this phase
- ENS/names, public "claimed wallet" lists, Arkham-style attributes
Output: CT directory — handle, owned wallets, PnL, style, shilled tokens.

### 2f. Follow-the-CT monitor
Combine 2e with the real-time monitor: when a CT wallet POSTS or BUYS →
alert carries both context (post text + trade). Score signals:
post-only < trade-only < post+trade. Goal: copy CT entry flow with latency
budget measured (their tx block → our alert time).

### 2g. Whale Entry Map (formalized rule from user's friend)
> "Jangan entry asal-app. Lihat holdernya: whale entry di area berapa? Kalau
> area whale dekat (atau DI ATAS) area kita, apalagi dengan size jumbo, itu
> conviction hold long-term."

Implement as a first-class feature:
- per token: entry-area distribution of top holders (volume-weighted avg
  entry MC/price — we already store per-wallet per-token swap legs)
- metrics: `whale_avg_entry_mc`, `% of top-20 holders with entry_mc >= current_mc`,
  `jumbo_above_us` (whale size entered after our reference point)
- `conviction_score` for an entry decision: whales avg-entry near/above ours
  = strong; whales all below (they are up huge, we are the exit liquidity)
  = danger
- expose via API + track-by-CA output ("show me the whale entry areas")

Data required: MC history (price × supply — we have price series; add supply
snapshots), holder snapshots over time (Blockscout holders pagination or
periodic snapshots).

---

## PHASE 3 — X/Twitter integration (needs user-provided X auth + GitHub)
- ingest CT posts mentioning CAs/tickers on RH chain
- link posts ↔ wallets ↔ trades (2e/2f engines)
- alert: "CT X posted + 3 verified wallets bought in 4 min"

## PHASE 4 — Strategy acceleration engine
- backtest "what if we copied wallet X since day 1" (entry latency × fee model)
- exit-engine: per copied wallet, style-matched exit rules that convert
  unrealized → realized (trailing, partial-exit ladders by hold-history)
- A/B the friend's whale-area rule on real data: conviction-score vs outcomes

## PHASE 5 — Scale (as originally written)
VPS, 500+ tokens, multi-chain (Base/Ink same engine), Solana adapter optional.

---

## Sources directory (Robinhood Chain)
| Source | What | Status |
|---|---|---|
| DexScreener API | token/pool universe, spot prices | ✅ integrated |
| Blockscout API v2 | holders, transfers, token meta | ✅ integrated (flaky 500s — retry) |
| public RH RPC | getLogs price series | ✅ integrated (throttled) |
| Alchemy (free) | generic RPC | ✅ (getLogs capped 10 blocks) |
| robinscan.io/leaderboard | chain-native wallet leaderboard | ⬜ Phase 2e |
| GMGN robinhood | CT tags, PnL, avg entry MC | ⬜ Phase 2e (Cloudflare — no CAPTCHA bypass) |
| fomo.family | CT leaderboard (see screenshots: username, $PnL, %, avg entry MC, X links) | ⬜ Phase 2e |
| OKX Web3 robinhood | token pages | ⬜ optional |
| X/Twitter | CT attribution + posts | ⬜ Phase 3 (user provides auth) |
