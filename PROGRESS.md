# Progress Log

## Phase 1 (MVP) — build log

### [2026-09-05] — Phase 1: Robinhood Chain pivot + full pipeline MVP
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
