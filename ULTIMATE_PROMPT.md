# ULTIMATE PROMPT — paste this into ANY AI agent to continue TopWallet

> Usage: open this file, copy everything below the line into a new AI session
> (Claude, GPT, Gemini, ZCode, Cursor, etc.). It is self-contained. Secrets
> are NOT in this file — they live in the repo's `.env` (gitignored) and in
> the user's local credential files.

---

You are taking over **TopWallet** — a production-grade, fully automated smart-wallet
discovery and PnL-forensics engine for **Robinhood Chain** (EVM L2, Arbitrum-Orbit
stack, chain id 4663, ~0.101s blocks, launched ~mid-2026). Work autonomously,
verify everything against raw data, and never fabricate numbers.

## Mission

Build and operate an end-to-end pipeline that:
1. Scrapes the token/wallet universe of Robinhood Chain,
2. Reconstructs every wallet's full trade history with on-chain-derived prices,
3. Scores wallets by CONSISTENT dip-buying / top-selling / holding winners,
4. Ships ONLY independently verified "smart money" wallets (hard PnL verification),
5. Runs autonomously on a VPS with scheduled re-runs and auto-pushed results to GitHub.

Repo: https://github.com/papatora/TopWalllet (local clone: `C:\Users\ROG\Documents\ClaudeCode\SniperToken\TopWalllet`).
READ FIRST: `HANDOFF.md` (resume state), `docs/ROADMAP.md` (the REAL expanded scope),
`PROGRESS.md` (chronology), `docs/ARCHITECTURE.md`, `docs/SCORING.md`.

## Verified environment facts (do not re-derive, trust these)

- **Data sources**: DexScreener API (token/pool universe, chainId `robinhood`),
  Blockscout API v2 at `https://robinhoodchain.blockscout.com` (holders,
  token-filtered transfers; REQUIRE a User-Agent header; intermittently 500s — retry),
  public RPC `https://rpc.mainnet.chain.robinhood.com` for eth_getLogs.
- **Key contracts**: Uniswap v4 PoolManager `0x8366a39CC670B4001A1121B8F6A443A643e40951`
  (NOT the universal CREATE2 address), WETH `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73`,
  USDG `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168`. DEXs: Uniswap v4 (dominant),
  Ramses v3, Giga v3.
- **ETH price sanity**: on-chain WETH/USDG pool ≈ $2,455.80 vs live reference
  $2,457.79 (0.08% deviation) — the price engine is proven accurate.
- **Current DB state** (data/topwallet.db, SQLite): 62 tokens, 62 pools,
  1,675 wallets, 7,643 classified swaps, ~22.5k price points.
- A full re-enrichment run (router-hop classification fix) was interrupted at
  916/1,675 wallets. **Resume is automatic** via wallet status checkpointing:
  `python -m src.cli pipeline --stages enrich,prices,analyze`
  (Windows: `.venv/Scripts/python`). Then check `results/stats.json` —
  `top_wallets_count` must be > 0 — and run `python -m src.cli stats`.

## Hard-won engineering rules (violating these = silent wrong results)

1. Uniswap v4 Swap event topic0 = keccak256 of the CANONICAL signature
   `Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)`
   = `0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f`.
   Hashing the signature WITH parameter names/indexed returns 0 logs silently.
   (Unit test `test_v4_swap_topic_matches_onchain` pins this.)
2. `sqrtPriceX96²` = token1-per-token0 (token0 = numerically lower address).
   The code self-checks orientation against the DexScreener spot price — keep it.
3. Price series are built CLUSTER-BASED: only scan ±5k blocks around merged
   trade-event clusters (gap < 30k), max 60 clusters/pool, call budget 120/pool.
   NEVER do full-history contiguous scans — the public RPC throttles and free
   Alchemy caps eth_getLogs at a 10-block range.
4. Trade classification is NET FLOW PER TRANSACTION (group legs by tx_hash;
   tx counts as a swap if ANY leg touches the pool counterparties). Per-leg
   classification silently drops router-routed buys (`PoolManager→router→wallet`)
   — this bug was found by an independent audit and inflated win rates.
5. A "win" requires return_multiple ≥ 1.02 (`win_threshold_multiple`) —
   sub-fee trips are break-even-to-losing, not wins.
6. Wash detection: wallets on opposite sides of the same token in the same
   block ≥3 times get flag `WASH_PAIR`.
7. SQLite: never run two pipeline processes concurrently ("database is locked").
8. Blockscout 500s and RPC 429s: retry with exponential backoff; the client
   already rotates endpoints and parks bad ones for log queries.

## Verification-first rules (user mandate — "aturan keras")

- Never report PnL that isn't re-derivable from raw data. The strict verifier
  (`src/analyze/pnl_verifier.py`) enforces: R1 ETH-oracle cross-check (≤2% vs
  most-liquid WETH/USDG pool), R2 re-derivation of each top wallet's top-3
  trades from FRESH Blockscout legs (≥2/3 must match within 25%), R3 no
  unrealized claims on stale (>24h) price points. Unverified wallets are
  EXCLUDED from the ranked list — do not weaken this.
- An independent subagent audit confirmed best-trade multiples accurate to
  ~0.4% but exposed a position undercount (now fixed). Keep auditing: spawn
  independent agents that re-derive wallets from raw explorer/RPC data without
  trusting the local DB, and compare.
- Honest labeling: current MVP bar is 3 positions × ≥1 token (young chain,
  small sample) with a mandatory `SINGLE_TOKEN_SAMPLE` flag. The full bar
  (5 positions × 3 tokens) returns when the universe exceeds ~200 tokens.

## User constraints & preferences

- Secrets live ONLY in `.env` (gitignored) — GitHub token, RPC endpoints.
  Never hardcode or commit them.
- Do NOT use CAPTCHA-solving services or fingerprint spoofing to bypass
  Cloudflare (GMGN is blocked for plain HTTP clients — the module
  `src/discover/leaderboard_scraper.py` fails gracefully by design).
- All tunables live in `config/settings.py` + `.env` +
  `config/scoring_weights.json` — re-tune without code changes.
- The user's long-term vision (see docs/ROADMAP.md §2): PnL truth engine
  (GENUINE / HALU / TREND_RIDER classification), copy-trade tier lists,
  cluster attribution ("who owns this cluster"), fresh-wallet sniper pattern
  ($K → $M in weeks, detected early), CT (Crypto Twitter) identity attribution
  (wallet → X handle; the user will supply X auth tokens at that phase),
  follow-the-CT alerts, and the **Whale Entry Map**: per token, compute top
  holders' volume-weighted entry MC; if whales' average entry is near/above the
  user's entry (especially jumbo size) that is long-term conviction —
  formalize as `whale_avg_entry_mc`, `% holders entry_mc >= current_mc`,
  `conviction_score`, and A/B test it on real data.
- Results, PROGRESS.md, and stats are auto-pushed to GitHub after each run
  (`AUTO_PUSH_RESULTS=true`, pusher masks the token).

## Immediate work queue (in order)

1. Resume the interrupted run (command above). If `top_wallets_count == 0`,
   debug via `logs/topwallet.log` (JSON structured logs — grep `"msg":`)
   and `logs/*.log`.
2. Re-audit with one independent subagent: re-derive 2–3 ranked wallets from
   raw Blockscout token-filtered transfers + on-chain Swap logs and confirm
   the router-hop undercount is gone (positions ≈ raw round-trips).
3. Implement the Whale Entry Map (docs/ROADMAP.md §2g) — data already exists
   (per-wallet per-token swap legs); add supply snapshots for MC.
4. Scale on VPS (user has one; `sudo bash setup.sh`): MAX_TOKENS=300–500.
5. Then Phase 2e: robinscan.io/leaderboard + fomo.family CT→wallet scraping,
   then X/Twitter integration when the user provides auth tokens.
6. Keep pushing every milestone to GitHub and updating PROGRESS.md.

## Definition of done for any change

Unit tests green (`pytest -q`, currently 19 passing) → pipeline stage re-run
successfully on real data → numbers cross-checked against an independent
source → PROGRESS.md updated → committed and pushed to GitHub.

---

*Chain of custody: this prompt was generated at the end of the session that
built Phase 1 MVP + hard verification + audit-driven fixes (commits through
`b27f265`). If repo state disagrees with this file, trust the repo and update
this prompt.*
