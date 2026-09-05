# TopWallet

**Fully automated smart-wallet discovery & tracking engine — built for Robinhood Chain (EVM L2, chain id 4663).**

TopWallet scrapes hundreds of thousands of wallet addresses across the chain's DEX universe, reconstructs every wallet's full trade history with on-chain-derived prices, and ranks wallets by a single thesis: **consistently buy local dips, sell local tops (or hold deep winners), across MANY tokens.**

```
┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────┐
│  DISCOVER   │ → │    PRICES    │ → │    ENRICH    │ → │    ANALYZE    │ → │ RANK/EXPORT  │
│ DexScreener │   │ on-chain     │   │ full wallet  │   │ positions,    │   │ top wallets  │
│ Blockscout  │   │ Swap-event   │   │ histories    │   │ scoring,      │   │ JSON/CSV/    │
│ holders+trd │   │ price series │   │ (Blockscout) │   │ anti-gaming   │   │ GitHub push  │
└─────────────┘   └──────────────┘   └──────────────┘   └───────────────┘   └──────────────┘
                                        └──── TRACK: real-time monitor + alerts + track-by-CA ────┘
```

## Quick start

### Local (no Docker, no paid keys)
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt          # Linux
cp .env.example .env          # optional: add Alchemy keys for speed
python -m src.cli pipeline --max-tokens 50 --enrich-limit 100
```
Results land in `results/top_wallets_latest.json` (+ CSV, stats, history).

### VPS (Ubuntu 22.04+), fully autonomous
```bash
sudo bash setup.sh            # installs docker, clones, builds, runs, schedules
```
That starts: postgres + redis + weekly scheduler + FastAPI API. First pipeline
runs immediately; results are pushed to this repo automatically after every run.

## How it works (chain reality, not hand-waving)

Robinhood Chain is a ~2-month-old Arbitrum-Orbit L2 (block time ≈ 0.1 s,
~850k blocks/day). There is no GeckoTerminal/Birdeye coverage for it, so
TopWallet derives everything from three free sources:

| Data | Source | Notes |
|---|---|---|
| Token universe, liquidity, volume, pools | [DexScreener API](https://docs.dexscreener.com/) (free) | chainId `robinhood`, Uniswap v4 / Ramses v3 / Giga v3 |
| Wallet discovery (top holders + traders) | [Blockscout API v2](https://robinhoodchain.blockscout.com) (free) | contract addresses (pools/routers) excluded automatically |
| Per-wallet full trade history | Blockscout `addresses/{wallet}/token-transfers` | paginated, checkpointed per wallet |
| Historical prices | on-chain Swap events (`sqrtPriceX96`) via `eth_getLogs` | v4: PoolManager singleton + poolId topic; v3: pool contract |
| USD quotes | USDG ≈ $1; ETH priced via its largest USDG pool | no external price API needed |

Optional keys (in `.env`): **Alchemy** RPC endpoints for fast `getLogs`
(recommended), Telegram/Discord for alerts, GitHub token for auto-push.

## The scoring thesis

A wallet is ranked by **consistency**, not one lucky 1000x (see
[docs/SCORING.md](docs/SCORING.md) for the full formula):

- **win rate** across all positions (share of profitable round trips)
- **median return multiple** (log-normalized; median 20x = full marks)
- **moonshots** — max multiple (1,000x patterns surface here)
- **dip-buying accuracy** — share of buys in the bottom 20% of the local price window
- **top-selling accuracy** — share of sells in the top 20%
- **consistency** — win rate × token breadth
- **recency** — exponentially decayed recent win rate (45-day half-life)

Hard excludes: <5 positions, <3 distinct tokens, pure airdrop farmers.
Flags (not excludes): MEV bots, wash round-trips, insider patterns, sybil
clusters, dust-only wallets — see [docs/SCORING.md](docs/SCORING.md).

## Track-by-CA

"Show me which smart wallets bought token X, ranked by their overall track record":
```bash
python -m src.cli track-ca --ca 0x90A71817bdA6DAC8c3A28bBfd877b02D667ae2f9
# API: GET /api/v1/track-by-ca?ca=0x...
```
Pulls every wallet that ever touched the token, scores their **global**
history with the same engine, and ranks them.

## Repo layout

```
config/     settings.py (all tunables) + scoring_weights.json (formula weights)
src/
  discover/ dex_scraper.py · holder_scraper.py · leaderboard_scraper.py
  enrich/   tx_fetcher.py · price_fetcher.py · rate_limiter.py
  analyze/  position_calculator.py · wallet_scorer.py · anti_gaming.py
  rank/     ranker.py · export.py
  track/    wallet_monitor.py · alert_sender.py
  api/      FastAPI app (top-wallets, stats, track-by-ca)
  db/       SQLAlchemy models (SQLite MVP → PostgreSQL in compose)
  pipeline.py  orchestrator with checkpoint/resume
results/    auto-updated: top_wallets_latest.json/csv, stats.json, history/
tests/      unit tests (scoring, positions, anti-gaming, price math)
```

## Operations

| Task | Command |
|---|---|
| Full pipeline | `python -m src.cli pipeline` |
| One stage | `python -m src.cli discover` (also `prices`, `enrich`, `analyze`) |
| Stats + top list | `python -m src.cli stats` |
| Real-time monitor | `python -m src.cli monitor` |
| Weekly scheduler | `python -m src.cli scheduler` |
| Push results to GitHub | `python -m src.cli push` |
| Tests | `pytest -q` |

Resumability: wallet enrichment state lives in the DB (`pending → enriched →
skipped/failed`), so an interrupted run continues where it stopped. All
rate limits, thresholds and weights are env/JSON config — no code changes.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the deep dive.

## Honest limitations (v0.1)

- **Chain age**: Robinhood Chain launched ~mid-2026; the "6–12 month"
  lookback clamps to the chain's full history (the pipeline computes the
  window from live block data).
- **USD accuracy**: prices are reconstructed from pool swap events; trades
  outside the built price window are skipped rather than mis-valued.
- **Contract wallets**: smart-contract wallets (Safes) are excluded from
  discovery to keep infrastructure addresses out; a Phase 2 tx-sender
  resolution will bring them back.
- **Clustering** is token-set Jaccard today; funding-graph clustering
  (common funder / nonce linkage) is Phase 2.

## Roadmap

- [x] **Phase 1 (MVP)** — discovery + enrichment + scoring + exports
- [x] **Phase 2** — Docker/Postgres stack, anti-gaming filters, this repo layout
- [x] **Phase 3** — real-time monitor, Telegram/Discord alerts, track-by-CA
- [ ] **Phase 4** — dashboard UI, funding-graph sybil clustering
- [ ] **Phase 5** — 500k+ wallet scale-out, additional EVM chains (Base/Ink via same engine), optional Solana adapter

## Disclaimer

On-chain data is public; this tool only reads public APIs and public RPC.
Nothing here is financial advice — ranked wallets are statistical patterns,
not endorsements.
