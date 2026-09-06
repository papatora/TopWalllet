# Progress Log

## Phase 1 (MVP) — build log

### [2026-09-06] — Independent subagent audit → 3 hard fixes
- **Setup**: 2 subagents assigned to re-derive the top-6 shipped wallets' PnL purely from raw Blockscout transfers + on-chain Swap logs (no trust in our DB). One agent completed (wallets #1–3); the second hit a concurrency limit and is queued.
- **Audit verdicts**: best-trade multiples confirmed accurate (1.2067x vs claimed 1.21; 1.1969x vs 1.2; price math independently validated to 0.4% vs DexScreener). BUT:
  1. **Position undercounting ~2.5x** — root cause found: v4 router-routed buys (`PoolManager→router→wallet`) have no wallet-adjacent pool leg, so whole buy transactions were dropped by the `touched_pool` per-leg check → FIFO undercounted closed positions and inflated win rates (claimed 1.0 vs true 0.842 on wallet #1).
  2. **Fees ignored** — trips at 1.001–1.007x are break-even-to-losing after swap fees.
  3. **Coordinated trading** — two shipped wallets repeatedly on opposite sides of the same token in the same/adjacent blocks (4+ coincidences), classic wash pattern.
- **Hard fixes shipped (all in this commit)**:
  - `touched_pool` now evaluated at TRANSACTION level (any leg touching pool counterparties) → router hops classified correctly.
  - Win threshold raised to ≥1.02x (`win_threshold_multiple` in scoring_weights.json) — sub-fee "wins" no longer counted.
  - Wash-pair detection: wallets appearing ≥3x on opposite sides of the same token in the same block are flagged `WASH_PAIR`.
  - Full re-enrichment of all 1,675 wallets triggered (classification changed).
- **Status**: audit-fix run executing; results + updated verified list to be pushed on completion.

### [2026-09-06] — First VERIFIED Top-Wallet list shipped (36 wallets)
- **What was completed**:
  - End-to-end pipeline validated on real chain data: 62 tokens / 62 pools discovered, 1,675 wallets enriched, 7,643 classified swaps, 22,552 on-chain price points across ~58 pools.
  - Hard PnL verification shipped ("aturan keras"): R1 ETH-oracle cross-check, R2 per-wallet trade re-derivation from raw Blockscout legs, R3 stale-open rule. Of 101 consistency-passing wallets, **36 shipped** — 65 dropped by strict verification.
  - ETH pricing verified against real-time reference: on-chain WETH/USDG pool $2,455.80 vs live $2,457.79 → **0.08% deviation** (R1 green).
  - GMGN-style metrics added to exports: return-distribution buckets + daily PnL calendar per wallet.
  - Independent subagent audit of top wallets launched against raw Blockscout data (results appended below).
- **Engineering war stories (all fixed, all test-locked)**:
  - Uniswap v4 Swap topic0 must be keccak of the canonical signature (`Swap(bytes32,address,…)` = 0x40e9cecb…) — the naive "with parameter names" hash silently returns zero logs (unit test pins it).
  - sqrtPriceX96² = token1/token0; orientation now self-checks against the DexScreener spot price (fixed a $118B/token inversion).
  - Cluster-based pricing: prices are built only around blocks where trades actually happened (gaps <30k blocks merged, ±5k margin) — full-history scans of active pools cost hundreds of getLogs calls and were throttled; cluster scans cost 1–3 calls each.
  - v4 router hops: trades classified by NET token flow per transaction (PoolManager→router→wallet legs defeated per-leg classification).
  - SQLite lock contention and Blockscout 500s handled with retries/status resets.
- **Honest calibration (documented, config-driven)**: on a ~2-month-old chain, the 1675-wallet sample contains mostly single-token specialists. Consistency bar lowered for the MVP preset (3 positions × ≥1 token, `SINGLE_TOKEN_SAMPLE` flag discloses it); the shipped list is dominated by verified micro-scalpers (77–100% win rate, 1.03–1.34x per trip, $7–76 realized PnL). The 5-position × 3-token bar ships as the default target once coverage widens on the VPS.
- **Stats**: see results/stats.json — wallets_scored 101, shipped 36, excluded 822.
- **Blockers/issues**: Blockscout token-filtered endpoint intermittently 500s (retried); Alchemy free tier caps eth_getLogs at 10 blocks (public Robinhood RPC used for log scans; PAYG key recommended).
- **Next steps**: VPS deployment (setup.sh) with wider universe (500+ tokens), GMGN leaderboards via the ENABLE_GMGN path, robinscan.io/leaderboard integration, funding-graph sybil clustering.

### [2026-09-05] — Phase 1: Robinhood Chain pivot + full pipeline MVP (v0.1)
- **Chain correction**: target chain is **Robinhood Chain** (EVM L2, Arbitrum-Orbit stack, chain id 4663) — not Solana as originally drafted. Architecture rebuilt EVM-first.
- Recon facts baked into the design:
  - DexScreener indexes Robinhood Chain (chainId `robinhood`); DEXs: Uniswap v4 (dominant), Ramses v3, Giga v3; quote token USDG; real liquidity ($10M+ ETH/USDG pools).
  - Uniswap v4 PoolManager on this chain: `0x8366a39CC670B4001A1121B8F6A443A643e40951` (not the universal CREATE2 address).
  - Blockscout explorer API v2 available at `robinhoodchain.blockscout.com` (holders + transfer history, free).
  - Block time ≈ 0.1s → chain is ~2 months old; lookback auto-clamps to full chain history.
- Completed:
  - Stage 1 DISCOVER: DexScreener token/pool universe + Blockscout holders/traders → deduped wallet candidates.
  - Stage 2 PRICES: historical price series reconstructed on-chain from Uniswap Swap events (sqrtPriceX96 per block), adaptive getLogs windows, USDG=$1 + ETH via USDG pool.
  - Stage 2b ENRICH: per-wallet full ERC-20 transfer history → classified BUY/SELL swaps with USD values; checkpoint/resume via wallet status.
  - Stage 3 ANALYZE: FIFO position builder with local-window dip/top percentiles, wallet metrics + composite score (config-driven weights), anti-gaming filters (LOW_DATA, AIRDROP_FARMER, MEV_BOT, WASH_SUSPECT, INSIDER_SUSPECT, DUST_ONLY, UNREALISTIC_RETURNS) + Jaccard sybil clustering.
  - Stage 4 RANK/EXPORT: ranked JSON/CSV per spec schema, wallet details, daily history snapshots, stats.json, PROGRESS.md auto-append, auto-push to GitHub.
  - Track-by-CA (CLI + API), real-time monitor with Telegram/Discord alerts, cron scheduler, FastAPI endpoints, Docker Compose stack (postgres/redis/worker/scheduler/api), one-command setup.sh.
- Blockers/issues:
  - GeckoTerminal & Birdeye do not cover Robinhood Chain → prices derived from on-chain Swap events instead (documented in docs/ARCHITECTURE.md).
  - v4 Swap events do not carry trader wallets → wallets extracted from token Transfer legs (wallet↔PoolManager), prices from Swap logs; contract addresses excluded from discovery.
- Next steps:
  - Scale run on VPS (setup.sh) with Alchemy keys for full getLogs throughput.
  - Funding-graph sybil clustering, incremental price-series extension, dashboard UI.

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 12, "pools_in_db": 12, "wallets_in_db": 316, "swap_events": 0, "wallets_scored": 0, "wallets_excluded": 0}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 12, "pools_in_db": 12, "wallets_in_db": 316, "swap_events": 137, "wallets_scored": 0, "wallets_excluded": 0}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 12, "pools_in_db": 12, "wallets_in_db": 316, "swap_events": 137, "wallets_scored": 0, "wallets_excluded": 0}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 12, "pools_in_db": 12, "wallets_in_db": 316, "swap_events": 137, "wallets_scored": 0, "wallets_excluded": 0}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 12, "pools_in_db": 12, "wallets_in_db": 316, "swap_events": 1807, "wallets_scored": 0, "wallets_excluded": 177}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 41, "pools_in_db": 41, "wallets_in_db": 1155, "swap_events": 4833, "wallets_scored": 0, "wallets_excluded": 76}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 41, "pools_in_db": 41, "wallets_in_db": 1155, "swap_events": 4833, "wallets_scored": 0, "wallets_excluded": 0}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 41, "pools_in_db": 41, "wallets_in_db": 1155, "swap_events": 4833, "wallets_scored": 0, "wallets_excluded": 0}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 41, "pools_in_db": 41, "wallets_in_db": 1155, "swap_events": 5143, "wallets_scored": 0, "wallets_excluded": 121}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 62, "pools_in_db": 62, "wallets_in_db": 1675, "swap_events": 7643, "wallets_scored": 0, "wallets_excluded": 18}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 62, "pools_in_db": 62, "wallets_in_db": 1675, "swap_events": 7643, "wallets_scored": 0, "wallets_excluded": 139}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 62, "pools_in_db": 62, "wallets_in_db": 1675, "swap_events": 7643, "wallets_scored": 0, "wallets_excluded": 888}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-05] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 62, "pools_in_db": 62, "wallets_in_db": 1675, "swap_events": 7643, "wallets_scored": 101, "wallets_excluded": 822}
- Top wallet: `0x805b2cc2…` score 46.6 (scalper, 1 tokens, median 1.0963x)
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-06] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 0, "pools_in_db": 0, "wallets_in_db": 0, "swap_events": 0, "wallets_scored": 0, "wallets_excluded": 0}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-06] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 0, "pools_in_db": 0, "wallets_in_db": 0, "swap_events": 0, "wallets_scored": 0, "wallets_excluded": 0}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-06] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 0, "pools_in_db": 0, "wallets_in_db": 0, "swap_events": 0, "wallets_scored": 0, "wallets_excluded": 0}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json

### [2026-09-06] — Automated pipeline run
- What ran: full pipeline (discover → enrich → analyze → rank → export)
- Stats: {"tokens_in_db": 0, "pools_in_db": 0, "wallets_in_db": 0, "swap_events": 0, "wallets_scored": 0, "wallets_excluded": 0}
- No wallets passed the consistency filters this run (normal for small samples).
- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json
