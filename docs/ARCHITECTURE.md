# Architecture

## Pipeline stages

```
Stage 1 DISCOVER
  DexScreener (token-boosts/profiles/search on chainId=robinhood)
    → candidate tokens → /tokens/v1/{chain}/{addrs} batch (30/call)
    → filter liquidity ≥ MIN_LIQUIDITY_USD, volume24h ≥ MIN_VOLUME_24H_USD
    → Token + main Pool (pairAddress = v4 poolId | v3 pool contract)
  Blockscout per token
    → /tokens/{ca}/holders        (top HOLDERS_PER_TOKEN, EOAs only)
    → /tokens/{ca}/transfers      (recent traders, EOAs only)
    → Wallet rows (status=pending) + WalletTokenInterest edges
    → dedupe + MAX_WALLETS cap (kept by cross-token activity count)

Stage 2a PRICES
  head block via eth_blockNumber; empirical block time (head vs head-1M)
  per pool: eth_getLogs Swap events
    v4: address=PoolManager(0x8366a3…), topics=[v4Swap, poolId]
    v3: address=pool, topics=[v3Swap]
  adaptive window halving on provider range errors
  sqrtPriceX96 → raw price → token0/token1 ordering → USD via quote
    (USDG=$1; ETH via its largest USDG pool)
  persisted as PricePoint (+ BlockTimestamp cache)

Stage 2b ENRICH  (checkpoint/resume: wallets.status)
  per wallet (concurrency ENRICH_CONCURRENCY):
    Blockscout /addresses/{wallet}/token-transfers (ENRICH_MAX_PAGES)
    classify: wallet→pool = SELL, pool→wallet = BUY (counterparty =
      token's pools + v4 PoolManager singleton)
    quote infra (USDG/WETH) ignored; plain transfers ignored
  price attach from PricePoint series; USD = amount × price
  persisted as SwapEvent (unique per wallet+tx+token+side)

Stage 3 ANALYZE
  per (wallet, token): FIFO position builder → CalcPosition
    closed: return_multiple, pnl, hold_hours
    open:   valued at latest price (unrealized)
  timing percentiles vs local ±DIP_WINDOW_DAYS price window
  wallet metrics (win rate, median/max multiple, PnL, consistency…)
  anti-gaming filters → excludes + risk flags
  sybil clustering: token-set Jaccard ≥ 0.85 → union-find clusters

Stage 4 RANK/EXPORT
  composite score (config/scoring_weights.json weights)
  → results/top_wallets_latest.{json,csv}, wallet_details/, history/
  → results/stats.json, PROGRESS.md append
  → optional auto-push to GitHub

Stage 5 TRACK (always-on services)
  monitor: polls top wallets' newest transfers → new-token entries → alerts
  scheduler: full pipeline re-run on PIPELINE_CRON (default weekly)
```

## Why Blockscout + raw JSON-RPC?

- Robinhood Chain has no Birdeye/GeckoTerminal coverage.
- Blockscout gives indexed, paginated holders + transfer history for free —
  far cheaper than scanning logs for wallet activity.
- But historical *prices* need on-chain data: Swap events carry `sqrtPriceX96`
  at every swap, giving an exact per-block price series from the same pools
  users traded on. That is also what powers dip/top percentile scoring.
- Raw JSON-RPC over httpx keeps the dependency footprint tiny (no web3.py)
  and works with any EVM RPC (Alchemy/QuickNode/public).

## Resumability & rate limits

| Mechanism | Where |
|---|---|
| Wallet enrichment checkpoint | `wallets.status` column |
| Discovery idempotence | upserts on natural keys (addresses/poolIds) |
| getLogs range limits | adaptive window halving (`get_logs_adaptive`) |
| RPC failover | rotating endpoints with 429 cooldowns |
| Blockscout/DexScreener backoff | exponential on 429/5xx |
| Price re-runs | PricePoint unique per (pool, block) |

## Scaling notes (Phase 5)

- The enrich stage is embarrassingly parallel: shard `wallets` by hash across
  `--scale worker=N` containers (each with its own DB row claims).
- Price series: build once, then incrementally extend from `last block seen`.
- Postgres (compose default) takes over from SQLite seamlessly via DATABASE_URL.
