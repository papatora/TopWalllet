# ULTIMATE PROMPT — TopWallet ▸ "Smart Money Feed" (product surface v2)

> Copy everything below the line into a fresh AI coding session (Claude Code,
> Cursor, Codex, Gemini, ZCode…). It is self-contained: an agent with zero
> prior context can execute it. Secrets are NOT in this file.

---

You are taking over **TopWallet** and shipping its product surface: a public,
real-time **Smart Money Feed** for **Robinhood Chain**. The backend forensics
engine already exists and works. The product — the thing a human opens in a
browser — does not exist yet. Your job is to build it, wire it to verified
data, and deploy it, without breaking a single one of the hard rules below.

Repo: `https://github.com/papatora/TopWalllet` (public)
Local clone (user's machine, read/write code only): `C:\Users\ROG\Documents\ClaudeCode\SniperToken\TopWalllet`
Production host (ALL heavy work): VPS `78.31.250.202`

**READ THESE FILES BEFORE WRITING ANY CODE, IN THIS ORDER:**
1. `SECURITY_POLICY.md` — non-negotiable operating rules (VPS-only, supply chain, secrets)
2. `PRE_COMPACT.md` — newest snapshot block at the top of the S-series is authoritative state
3. `HANDOFF.md` — resume state and hard-won bug list
4. `docs/ROADMAP.md` — the REAL scope (Phase 2 "bedah wallet" = wallet forensics)
5. `docs/ARCHITECTURE.md`, `docs/SCORING.md`, `docs/API.md`
6. `ULTIMATE_PROMPT.md` — the previous (engine-focused) handoff prompt
If the repo contradicts this document, **the repo wins** — then update this document.

---

# 0. THE TARGET, IN ONE SCREEN

The product's hero section is the specification. Build toward exactly this,
pixel-faithful in spirit and typography:

```
smart money feed · updated just now

see what smart money
buys before the crowd.

tracking [ROBINHOOD] wallets in real time — calls, entries, exits.
```

- Line 1: eyebrow, monospace, lowercase, muted grey, with a **live freshness stamp**.
- Lines 2–3: H1, large serif, lowercase, tight leading, ends with a period.
- Line 4: subhead, monospace, with `ROBINHOOD` rendered as an **inline chip/pill**.
- Ground: warm off-white paper, generous whitespace, left-aligned, editorial.

Every word in that hero is a contract with the user:

| Hero claim | What it obligates you to build |
|---|---|
| "smart money" | Only wallets that pass hard PnL verification + anti-gaming. No unverified rows. |
| "feed" | A reverse-chronological, continuously updating event stream — not a static table. |
| "updated just now" | A real freshness clock driven by real data age. If data is 3h old, it must SAY "3h ago". Faking this is a fatal failure. |
| "before the crowd" | Latency must be measured and displayed (wallet tx block → event visible on site). If we can't beat the crowd, we say by how much we don't. |
| "tracking … in real time" | Sub-minute event surfacing, p95 measured and exposed on a `/status` page. |
| "calls, entries, exits" | Three distinct, typed event classes in the feed — not one generic "trade" row. |

**If the data cannot honestly support a claim, change the claim — never the data.**

---

# 1. WHO YOU ARE, HOW YOU WORK

- You are an autonomous senior engineer: backend (Python/FastAPI/async), data
  engineering (EVM RPC, indexers), and front-end (modern TS/React or plain
  static — your call, defended in an ADR).
- You verify against raw data before you claim anything. You never invent a
  number, an address, a latency, or a screenshot.
- You work in small, reviewable commits, each with green tests, each pushed.
- When you are unsure whether an action is "heavy work", assume it is, and run
  it on the VPS.
- You write in the repo's existing voice: dependency-minimal, config-driven,
  resumable, honest.
- Reply to the user in casual Indonesian if they write in Indonesian. Code,
  comments, commits, and docs stay in English.

---

# 2. VERIFIED ENVIRONMENT FACTS — TRUST THESE, DO NOT RE-DERIVE

**Chain**
- Robinhood Chain: EVM L2 on the Arbitrum Orbit stack, **chain id 4663**,
  block time ≈ **0.101 s** (~850k blocks/day), launched ~mid-2026 (young chain).
- Explorer/API: Blockscout v2 at `https://robinhoodchain.blockscout.com`
  — **requires a `User-Agent` header**, intermittently returns 500s → retry with
  exponential backoff; a health counter + circuit breaker already exist.
- Public RPC: `https://rpc.mainnet.chain.robinhood.com` (throttled).
- Alchemy free tier: `eth_getLogs` capped at a **10-block range** — useless for
  wide scans; the code rotates endpoints and parks bad ones.

**Key contracts (chain-specific, NOT the canonical CREATE2 addresses)**
- Uniswap v4 PoolManager: `0x8366a39CC670B4001A1121B8F6A443A643e40951`
- WETH: `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73`
- USDG: `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168`
- DEXs present: Uniswap v4 (dominant), Ramses v3, Giga v3.

**Pricing**
- Historical prices are reconstructed from on-chain `Swap` events
  (`sqrtPriceX96`) — there is no GeckoTerminal/Birdeye coverage for this chain.
- USD quote: USDG ≈ $1; ETH priced from its largest WETH/USDG pool.
- ETH oracle sanity, verified 2026-09-05: pool $2,455.80 vs live reference
  $2,457.79 → **0.08% deviation**. The price engine is proven accurate.

**Landmines that produce silently wrong results (all already fixed + test-pinned — do not regress):**
1. Uniswap v4 `Swap` topic0 = keccak of the **canonical** signature
   `Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)` =
   `0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f`.
   Hashing the signature *with parameter names* returns **0 logs, no error**.
   Pinned by `test_v4_swap_topic_matches_onchain`.
2. `sqrtPriceX96²` = token1-per-token0 (token0 = numerically lower address).
   Orientation self-checks the median against the DexScreener spot price —
   a past inversion produced a "$118B" token. Keep the self-check.
3. Price series are **cluster-based**: scan only ±5k blocks around merged trade
   clusters (merge gap < 30k), max 60 clusters/pool, budget 120 calls/pool.
   **Never** revert to contiguous full-history scans.
4. Trade classification is **net flow per transaction** (group legs by `tx_hash`;
   a tx counts as a swap if ANY leg touches the pool counterparties). Per-leg
   classification silently drops router-routed buys (`PoolManager→router→wallet`)
   and undercounted positions ~2.5× — found by an independent audit.
5. A "win" requires `return_multiple ≥ 1.02` (`win_threshold_multiple`);
   sub-fee round trips are losses, not wins.
6. Wash detection: wallets on opposite sides of the same token in the same block
   ≥3 times → flag `WASH_PAIR`.
7. SQLite: never run two pipeline processes at once ("database is locked").
8. The WETH/USDG series must be built **before** clusters (the WETH pool has no
   events of its own); DexScreener is the fallback oracle.

---

# 3. WHAT ALREADY EXISTS — DO NOT REBUILD IT

```
config/     settings.py (every tunable, env-driven) · scoring_weights.json
src/
  discover/ dex_scraper.py · holder_scraper.py · leaderboard_scraper.py
  enrich/   tx_fetcher.py · price_fetcher.py · rate_limiter.py
  analyze/  position_calculator.py · wallet_scorer.py · anti_gaming.py
            pnl_verifier.py · funding_provenance.py · whale_map.py
  rank/     ranker.py · export.py
  track/    wallet_monitor.py · alert_sender.py   (Telegram + Discord)
  api/      main.py  (FastAPI: /health, /api/v1/top-wallets, /stats, /track-by-ca)
  db/       SQLAlchemy models (SQLite MVP → Postgres via DATABASE_URL)
  pipeline.py  orchestrator with checkpoint/resume
  track_by_ca.py · scheduler.py · cli.py
scripts/    supervisor.py · watchdog.py (hourly LLM overseer) · deploy_vps.py
            scrape_social.py · VPS_SETUP.md
results/    top_wallets_latest.{json,csv} · stats.json · wallet_details/*.json
            history/YYYY-MM-DD/ · whale_entry_maps.json · funding_forensics.json
            funder_clusters.json · external_leaderboards.json
            supervisor_status.json · night_watch.log
tests/      pytest suite (23 green at last count)
```

CLI: `python -m src.cli {pipeline|discover|prices|enrich|analyze|stats|monitor|scheduler|api|push|track-ca}`

**Autonomy stack already running on the VPS:** systemd (restart on crash) →
`scripts/supervisor.py` (loops the pipeline, heartbeats to
`results/supervisor_status.json` every 30 s, refuses to start unless
`TOPWALLET_RUN_ENV=vps`) → hourly `scripts/watchdog.py` cron (feeds hard facts
to an LLM, which may only return whitelisted actions:
`NONE|START_SUPERVISOR|RESTART_SUPERVISOR|RESTART_PIPELINE`).

---

# 4. THE HONEST DATA REALITY (as of the last pushed run, 2026-09-07T10:41Z)

Read this twice. It is the single biggest risk to the product.

```json
{
  "tokens_in_db": 125, "pools_in_db": 125, "wallets_in_db": 3169,
  "swap_events": 10032, "wallets_scored": 114, "wallets_excluded": 6,
  "top_wallets_count": 39, "lookback_days": 70, "max_tokens": 300
}
```

The current **rank-1 wallet** (`0x35e63bbA009C1D6332294a3370Cc8317079A5388`):
composite **35.49**, **6 positions**, win rate 0.83, median multiple **1.23x**,
max multiple 1.29x, **1 distinct token** (COIN), realized PnL **$20.91**,
avg hold **0.04 h**, dip-buying accuracy **0.0**.

Translation: **today's "top wallets" are micro-scalpers making twenty dollars,
not smart money making a hundred x.** The chain is ~2 months old, the universe
is ~125 tokens, and the MVP thresholds were relaxed to
`min_positions: 3, min_distinct_tokens: 1` (`config/scoring_weights.json`)
with a mandatory `SINGLE_TOKEN_SAMPLE` flag. `docs/SCORING.md` still documents
the full bar (5 positions × 3 tokens) — that bar returns when the universe
exceeds ~200 tokens.

Consequences you must design around:

1. **The hero must not lie.** Until verified wallets exist whose track record
   actually predicts the crowd, the site must present what it has, labelled
   precisely, with an explicit "sample is early / chain is young" banner and
   the exact thresholds in force. A `SINGLE_TOKEN_SAMPLE` wallet gets a visible
   badge, not a hidden footnote.
2. **Expanding the universe is part of this job**, not someone else's: raise
   `MAX_TOKENS` toward 300–500 on the VPS, keep chain-wide Blockscout discovery
   running, and re-tighten thresholds to 5×3 the moment the universe supports it.
   Ship the threshold values through the API so the UI always displays the
   truth in force.
3. **Design for the good case, degrade honestly in the bad case.** The feed's
   components must look right with a 400x moonshot AND with a $7 scalp.

Also live in the data, ready to be surfaced:
- `results/whale_entry_maps.json` — per token: `current_price_usd`,
  `whale_count`, `whale_avg_entry_price`, `pct_whales_at_or_above_current`,
  `jumbo_above_current`, `conviction_score`, `verdict`
  (`STRONG` | `INSUFFICIENT_DATA` | …), plus a `whales[]` array with
  `entry_vwap_usd`, `entry_vs_current`, `cost_basis_usd`, `underwater`.
- `results/funding_forensics.json` — per ranked wallet: first funder address,
  amount, block, timestamp, `funding_class` (`UNKNOWN` | `WALLET_FUNDED` | …),
  `dev_fingerprint` (`early_entries`, `fast_flips`, `dev_suspect`),
  `classification` (`WALLET_BACKED` | …).
- `results/funder_clusters.json` — e.g. `cluster_f70d`: funder
  `0xf70da978…dbef`, 250.9 ETH balance, **26 funded wallets**, 2 of them inside
  the verified top list. This is the most interesting story in the dataset —
  give it a real UI.

---

# 5. NON-NEGOTIABLE RULES (violating one = fatal failure, not a preference)

### R-1 Execution policy — VPS only
All heavy or internet-exposed work — discovery, enrichment, pricing, analysis,
verification, supervisor, monitor, scraping, the public API, the web server —
runs on the **VPS (78.31.250.202)**. The local Windows machine is the user's
daily driver holding crypto wallets: it may only be used for reading/writing
code, memory, and results, `git` operations, and **offline unit tests**.
Never start the supervisor or a pipeline stage locally, not "just for testing",
not "just tonight". The supervisor's `TOPWALLET_RUN_ENV=vps` guard exists
because this rule was broken once already. Do not bypass it.

### R-2 Verification-first — never hallucinate PnL
- Every number shown to a human must be re-derivable from raw on-chain data.
- The hard verifier (`src/analyze/pnl_verifier.py`) enforces:
  **R1** ETH-oracle cross-check (≤2% vs the most liquid WETH/USDG pool),
  **R2** re-derivation of each top wallet's top-3 trades from **fresh**
  Blockscout legs (≥2 of 3 must match within 25%),
  **R3** no unrealized claims resting on price points older than 24 h.
- Unverified wallets are **excluded** from ranked output. Do not weaken this
  to make the feed look busier.
- New claim types (latency, "before the crowd" lead time, cluster ownership)
  need their own verifier before they may be displayed.

### R-3 Supply-chain hygiene
Before installing **any** third-party library, tool, or binary — OSS, popular,
10k stars, doesn't matter: check last release date (long-dead then suddenly
active = suspect), maintainer health, postinstall/dependency changes,
typosquatting; **pin the exact version** in `requirements.txt` (no unpinned,
no `*`); install only inside the **VPS venv** (never global, never `curl | bash`);
**report to the user and get explicit approval first**. Exceptions: stdlib and
already-reviewed entries in `requirements.txt`. When in doubt, write the small
function yourself — this repo is dependency-minimal by design. This rule applies
to npm too: a front-end framework is not a free pass to pull 900 packages.

### R-4 Secrets
Secrets live only in `.env` on the VPS (gitignored) or in the user's local
credential files. Never commit, never log, never paste into an issue, a
screenshot, a results file, or a message. The GitHub pusher masks its token —
keep it that way. If a token is ever exposed, tell the user to **rotate it
immediately** and stop using it.

### R-5 No anti-bot evasion
GMGN and fomo.family sit behind Cloudflare. Do **not** use CAPTCHA-solving
services, stealth/fingerprint-spoofing plugins, or residential-proxy evasion to
get through. `src/discover/leaderboard_scraper.py` and `scripts/scrape_social.py`
fail gracefully by design; keep them that way. The legitimate path: the user
exports a working request from their own logged-in browser
(F12 → Network → the `prod-api.fomo.family` call → Copy as cURL) and hands it
over. Otherwise let the on-chain pipeline find those wallets organically.

### R-6 Legal & framing
Public on-chain data only, read-only, public APIs and public RPC. The site
carries a persistent, visible disclaimer: **not financial advice; ranked wallets
are statistical patterns, not endorsements; past performance predicts nothing.**
No "guaranteed", no "alpha you can't lose", no fake urgency, no fabricated
testimonials, no invented user counts. Do not add wallet-connect, do not ask
visitors for keys, do not add a "copy trade with one click" execution path in
this phase.

---

# 6. PRODUCT SPECIFICATION

## 6.1 Routes / information architecture

| Route | Purpose |
|---|---|
| `/` | The hero + the live feed (the screen in §0). Infinite scroll, filters, freshness clock. |
| `/wallet/[address]` | Wallet dossier: score breakdown, verification badge, positions, style tags, risk flags, funding provenance, cluster membership, event history. |
| `/token/[ca]` | Token page: price series, who's in, **Whale Entry Map**, conviction score, smart-money net flow. |
| `/leaderboard` | The ranked table (`top_wallets_latest.json`), sortable, with every threshold in force displayed above it. |
| `/clusters` | Funding-graph view: funder → fleet, `cluster_f70d` as the first real story. |
| `/track` | Track-by-CA: paste a contract, get every smart wallet that ever touched it, ranked by global track record. |
| `/status` | Radical transparency: last pipeline run, data age, event latency p50/p95, API health, Blockscout error rate, thresholds in force, how many wallets were excluded and why. |
| `/methodology` | Plain-English how-it-works: scoring formula, R1/R2/R3, anti-gaming flags, known limitations, the young-chain caveat. |

## 6.2 The feed event model (the core new object)

Create a first-class, persisted `FeedEvent`. This is the product's atom.

```jsonc
{
  "id": "evt_4663_54418923_0x9f3c…_0",   // deterministic: chain_block_tx_logIndex
  "type": "ENTRY",                        // see 6.3
  "ts": "2026-09-07T10:41:12Z",           // block timestamp (UTC, ISO-8601)
  "block": 54418923,
  "tx_hash": "0x9f3c…",
  "detected_at": "2026-09-07T10:41:19Z",  // when OUR system saw it
  "published_at": "2026-09-07T10:41:20Z", // when it hit the feed
  "lag_seconds": 8.1,                     // detected_at − ts  (SHOW THIS)
  "wallet": {
    "address": "0x35e6…5388",
    "label": null,                        // ENS / CT handle when attributed
    "rank": 1,
    "composite_score": 35.49,
    "tier": "B",                          // S/A/B — see 6.4
    "verdict": "verified",                // verified | unverified | halu | trend_rider
    "style": "scalper",
    "risk_flags": ["SINGLE_TOKEN_SAMPLE"]
  },
  "token": {
    "ca": "0x9395…7a8d", "symbol": "COIN", "name": "…",
    "price_usd": 0.00022708, "liquidity_usd": 41230.0,
    "market_cap_usd": null,               // null, never a guess
    "age_hours": 61.2
  },
  "action": {
    "side": "buy",                        // buy | sell
    "amount_token": 118234.55,
    "amount_usd": 26.86,
    "price_usd": 0.00017595,
    "pct_of_wallet_activity": 0.07,
    "is_first_touch": true,               // wallet's first ever buy of this token
    "position_after": { "avg_entry_usd": 0.00017595, "size_usd": 26.86 }
  },
  "context": {
    "smart_wallets_in_token_24h": 3,      // corroboration = the real signal
    "whale_conviction_score": 100.0,      // from whale_entry_maps.json, or null
    "whale_verdict": "STRONG",
    "cluster_id": "cluster_f70d",
    "same_block_counterparty": null       // wash-pair detection
  },
  "confidence": { "score": 0.62, "reasons": ["verified_wallet", "first_touch", "3_smart_wallets_24h"] },
  "proof": {
    "tx_url": "https://robinhoodchain.blockscout.com/tx/0x9f3c…",
    "wallet_url": "https://robinhoodchain.blockscout.com/address/0x35e6…",
    "token_url": "https://robinhoodchain.blockscout.com/token/0x9395…",
    "derivation": "net-flow-per-tx; price from pool swap sqrtPriceX96 @ block 54418923"
  }
}
```

Rules for this object:
- **`proof` is mandatory on every event.** Every row in the UI links to the
  transaction on Blockscout. No proof → no row.
- Unknown fields are `null` and render as `—`. Never guess, never zero-fill.
- Events are **immutable and idempotent**: the deterministic `id` means a
  replayed block cannot double-post. Persist them (new `feed_events` table);
  the feed must survive a restart and support backfill.
- Deduplicate multi-leg router transactions into ONE event (net flow per tx —
  landmine #4 applies here too).

## 6.3 Signal taxonomy — "calls, entries, exits"

The hero promises three things. Implement six types, mapped to those three words:

| Type | Definition | Hero word |
|---|---|---|
| `CALL` | A tracked wallet buys a token **no tracked wallet held before** — a genuine first call. Rarest, highest-signal. | calls |
| `ENTRY` | A tracked wallet opens a new position in a token (its first buy of that token). | entries |
| `ADD` | A tracked wallet increases an existing position ≥25%. | entries |
| `TRIM` | A tracked wallet sells 20–80% of a position. | exits |
| `EXIT` | A tracked wallet closes ≥80% of a position. | exits |
| `ROTATION` | An `EXIT` and an `ENTRY` by the same wallet within N blocks — capital moving, the most actionable pattern. | calls |

Derived aggregate cards (not raw events, but rendered inside the feed):
- **CONVICTION CLUSTER** — ≥3 tier-A/S wallets entering the same token within 6h.
- **WHALE-ALIGNED ENTRY** — an entry into a token whose `conviction_score ≥ 70`.
- **FLEET MOVE** — ≥3 wallets from the same funder cluster acting together
  (this is a *warning*, not an endorsement — label it as such).

## 6.4 Confidence, tiers, and verdicts

Never show a raw score without its provenance.

- **Tier S/A/B** (copy-trade readiness, `docs/ROADMAP.md` §2b): requires a
  `GENUINE` verdict + style stability across weeks + hold-time compatible with
  copy latency + sane position sizing + verified history length. If a wallet
  can't clear that, it is untiered — show "unrated", not a flattering guess.
- **Verdict** (`docs/ROADMAP.md` §2a): `GENUINE` | `HALU` (inflated by data
  artifacts — show reported vs audited delta) | `TREND_RIDER` (profit fully
  explained by token beta). Until the PnL Truth Engine ships these, display the
  verifier's `verified` / `unverified` and say so plainly on `/methodology`.
- **Confidence score** for an event is a documented, inspectable formula
  (wallet tier × corroboration × token quality × recency), rendered as a
  compact reasons list — never as an unexplained number.

## 6.5 Wallet dossier page

Score breakdown as a component-by-component bar (win_rate 0.22, median_return
0.18, moonshots 0.10, dip_buying 0.15, top_selling 0.10, consistency 0.15,
recency 0.10 — read the live weights from the API, never hardcode);
verification block (`verdict`, `eth_oracle_ok`, `trades_verified: "3/3"`);
positions table with entry/exit/multiple/PnL and a Blockscout link per row;
timing percentile visual (dip-buy / top-sell accuracy against the local ±7-day
window); risk flags with plain-English explanations on hover
(`MEV_BOT`, `WASH_SUSPECT`, `WASH_PAIR`, `INSIDER_SUSPECT`, `DUST_ONLY`,
`UNREALISTIC_RETURNS`, `SINGLE_TOKEN_SAMPLE`, `LOW_DATA`); funding provenance
(first funder, class, dev fingerprint); cluster membership; full event history.

## 6.6 Token page + Whale Entry Map (the user's friend's rule, formalized)

> "Don't enter blindly. Look at the holders: where did the whales enter? If the
> whale zone is near or **above** ours — especially at jumbo size — that's
> long-term conviction."

Render `results/whale_entry_maps.json` as the centrepiece: a horizontal
entry-price distribution with each whale plotted at their `entry_vwap_usd`,
dot area ∝ `cost_basis_usd`, colour by `underwater`, the current price as a
vertical rule, and a "your entry" input the visitor can type to place their own
marker. Headline metrics: `whale_avg_entry_price`,
`pct_whales_at_or_above_current`, `jumbo_above_current`, `conviction_score`,
`verdict`. When `verdict === "INSUFFICIENT_DATA"`, say exactly that — do not
render a persuasive-looking chart on top of three data points.

## 6.7 Clusters / funding forensics

Bubble-graph (wallet ↔ funder ↔ cluster) plus a table. First real case to ship:
`cluster_f70d` — funder `0xf70da978…dbef`, 250.9 ETH, 26 funded wallets, 2 of
them in the verified top list. Frame it neutrally: "these wallets share a
funder", with the evidence list, not "this is a sybil scam".

## 6.8 Real-time delivery

- Server-Sent Events at `GET /api/v2/stream` (SSE, not WebSocket — one-way,
  proxy-friendly, trivially reconnectable). Support `Last-Event-ID` for
  gap-free reconnect.
- The client falls back to polling `GET /api/v2/feed?since=<cursor>` every 10 s
  when SSE is unavailable.
- New events animate in at the top with a subtle highlight that decays over
  ~8 s. Respect `prefers-reduced-motion`.
- A visible connection state: `live` (green dot) / `reconnecting` / `stale`.

## 6.9 Freshness — the "updated just now" contract

One shared `dataAge` derived from the newest event's `detected_at` and
`stats.updated_at`:

| Age | Display | Treatment |
|---|---|---|
| < 60 s | `updated just now` | green dot |
| < 15 min | `updated 7m ago` | normal |
| < 2 h | `updated 1h 12m ago` | muted |
| ≥ 2 h | `data is 3h old — pipeline may be down` | amber banner + link to `/status` |
| ≥ 24 h | `stale — showing last known state` | amber banner, feed dimmed |

This clock is computed from data, never from `Date.now()` at render. Ticking a
"just now" label over 6-hour-old data is the single most damaging bug you can
ship — treat it as a P0.

## 6.10 Alerts

Keep Telegram/Discord (`src/track/alert_sender.py`). Add per-type filtering
(only `CALL` + `CONVICTION_CLUSTER`, tier ≥ A, min USD size). Add a web push
or email digest **only if** the user asks — no accounts, no personal data
collection in this phase.

---

# 7. DESIGN SYSTEM — derived from the reference hero

The aesthetic: **editorial newspaper × terminal**. Warm paper, one big serif
voice, monospace for everything factual, near-zero chrome, generous whitespace.
It must look like a research publication, not a crypto casino.

## 7.1 Colour tokens

```css
:root{
  --paper:        #F0EEE6;   /* warm off-white ground (the hero background) */
  --paper-raised: #F7F5EF;   /* cards, slightly lifted */
  --ink:          #191817;   /* headline / primary text */
  --ink-2:        #3D3A34;   /* body text */
  --ink-3:        #6B6862;   /* eyebrow, captions, muted mono */
  --rule:         #DCD8CC;   /* hairlines, table borders */
  --chip-bg:      #D9D6CC;   /* the ROBINHOOD pill */
  --chip-ink:     #2A2825;
  --buy:          #2F6F4F;   /* entries — muted forest, NOT neon green */
  --sell:         #9B3B2F;   /* exits — muted brick, NOT neon red */
  --accent:       #B4541F;   /* CALL events, links on hover — burnt orange */
  --warn:         #A9761B;   /* stale data, risk flags */
  --live:         #3E7B52;   /* the live dot */
}
:root:not([data-theme="light"]) { /* @media (prefers-color-scheme: dark) */
  --paper:#16150F; --paper-raised:#1E1D16; --ink:#F0EEE6; --ink-2:#CFCBBF;
  --ink-3:#8C887E; --rule:#2E2C24; --chip-bg:#33302A; --chip-ink:#E6E2D6;
  --buy:#6FA98A; --sell:#D08573; --accent:#E0855A; --warn:#D6A94E; --live:#6FA98A;
}
```

Rules: never a colour outside the tokens; never a gradient; never a glow;
never a green/red pair louder than the muted pair above. Colour is never the
only carrier of meaning — always pair with a glyph or a word (`↑ ENTRY`).

## 7.2 Typography

- **Display (H1, H2, big numbers):** a transitional/old-style serif with real
  personality — Instrument Serif, Source Serif 4, Newsreader, or Libre
  Baskerville. Stack: `"Instrument Serif", "Source Serif 4", Georgia, "Times New Roman", serif`.
- **Everything factual (eyebrow, body, tables, addresses, prices, timestamps):**
  a monospace with a warm, humane cut — JetBrains Mono, IBM Plex Mono, or
  Berkeley Mono. Stack: `"JetBrains Mono", "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace`.
- **No third typeface.** If you need a sans, you don't.
- Hero H1: `clamp(2.75rem, 7.5vw, 5.25rem)`, line-height `1.02`,
  letter-spacing `-0.015em`, weight 400 (never bold — the size is the emphasis),
  **lowercase**, wrapped to exactly two lines at desktop width, terminal period.
- Eyebrow: mono, `0.8125rem`, `letter-spacing: 0.06em`, lowercase, `--ink-3`,
  with a `·` separator before the freshness stamp.
- Subhead: mono, `clamp(0.95rem, 1.6vw, 1.125rem)`, `--ink-2`, line-height 1.6,
  em dash (`—`) not a hyphen.
- Numbers: tabular figures everywhere (`font-variant-numeric: tabular-nums`) so
  columns don't dance as they update.
- Lowercase is a deliberate voice: headings and nav are lowercase; ticker
  symbols, addresses, and flags stay uppercase.

## 7.3 The inline chip (`ROBINHOOD`)

The pill in the subhead is a reusable component — also used for token symbols,
risk flags, tiers, and event types.

```css
.chip{
  display:inline-flex; align-items:center; gap:.35em;
  padding:.15em .5em; border-radius:.35em;
  background:var(--chip-bg); color:var(--chip-ink);
  font-size:.66em; letter-spacing:.08em; text-transform:uppercase;
  font-weight:500; vertical-align:.12em; white-space:nowrap;
}
```
Variants by tint only: `.chip--buy`, `.chip--sell`, `.chip--call`,
`.chip--warn`, `.chip--tier`. Never larger than `.7em` of its parent.

## 7.4 Layout, spacing, motion

- 8px spacing scale (4/8/12/16/24/32/48/64/96/128). Hero: ~`128px` top padding
  desktop, `64px` mobile.
- Max content width `72ch` for prose, `1180px` for the feed, `1440px` for tables.
- Left-aligned everything. No centred hero, no hero image, no illustration.
- Hairline rules (`1px solid var(--rule)`) as the only separator. No card
  shadows; if a card must lift, use `--paper-raised` plus a hairline.
- Motion: 120–180 ms, `cubic-bezier(.2,.6,.2,1)`. New-event highlight fades over
  8 s. Nothing bounces, nothing pulses except the single live dot (2 s ease).
  All of it disabled under `prefers-reduced-motion: reduce`.
- Tables/diagrams/code scroll inside their own `overflow-x:auto` container —
  the page body must never scroll horizontally.

## 7.5 Component inventory (build these, in this order)

`FreshnessStamp` · `LiveDot` · `Chip` · `AddressMono` (truncates
`0x35e6…5388`, click-to-copy, links to Blockscout) · `USDAmount` (tabular,
adaptive precision — `$0.00017595` vs `$26.86` vs `$1.2M`) · `Multiple`
(`1.23x`, colour by threshold) · `RelativeTime` (updates in place) ·
`FeedRow` (variants per event type) · `ConvictionCard` · `WhaleEntryMap` ·
`ScoreBreakdownBar` · `RiskFlagList` · `VerificationBadge` · `LeaderboardTable`
· `EmptyState` · `StaleBanner` · `MethodologyNote`.

## 7.6 A feed row, concretely

```
10:41:12  ↑ ENTRY   0x35e6…5388  ▸  [COIN]   $26.86 @ $0.00017595   1st touch
          tier B · verified · scalper · [SINGLE_TOKEN_SAMPLE]      lag 8.1s  ↗tx
```
Left column: mono timestamp (relative on hover). Then a typed glyph + label
chip. Then the wallet (mono, truncated, links to the dossier). Then the token
chip. Then size and price, tabular. Then the badge row. Right-aligned: measured
lag and the Blockscout link. Rows are ~2 lines desktop, stacked on mobile.
Density over decoration: a user should be able to scan 20 rows without moving
their eyes horizontally.

## 7.7 Accessibility, responsiveness, states

- Contrast ≥ 4.5:1 for body, ≥ 3:1 for large text — verify both themes with a
  real checker, not by eye.
- Full keyboard reachability; visible focus rings using `--accent`.
- The feed is a `<ul role="feed">` with `aria-busy` and polite live-region
  announcements for new events (throttled — never announce 40 rows at once).
- Mobile (375px): hero H1 ~2.75rem, feed rows stack, tables scroll, chips wrap.
- Every list has a designed **empty state** ("no smart-money events in the last
  24h — the chain is quiet"), a **loading skeleton** (never a spinner), and an
  **error state** that names the failing dependency and links to `/status`.

## 7.8 Anti-patterns — instant rejection

Neon green/red, glassmorphism, dark-purple crypto gradients, glow effects,
animated candlestick backdrops, rocket/fire/moon emoji, countdown timers,
"🔥 HOT" badges, fake tickers, a headline that isn't backed by a query, any
number without a `proof` link, a chart with three data points styled to look
like a hundred, a "just now" label over stale data.

---

# 8. BACKEND WORK REQUIRED

## 8.1 API v2 (additive — keep v1 working)

```
GET  /api/v2/feed?cursor=&limit=50&types=CALL,ENTRY,EXIT&tier=A,S
                 &min_usd=100&token=0x…&wallet=0x…
     → { events: FeedEvent[], next_cursor, data_age_seconds, thresholds_in_force }
GET  /api/v2/stream                (SSE; supports Last-Event-ID)
GET  /api/v2/wallets?limit=100&sort=composite_score
GET  /api/v2/wallet/{address}      (dossier: metrics + positions + funding + cluster + events)
GET  /api/v2/token/{ca}            (meta + price series + smart-money flow)
GET  /api/v2/token/{ca}/whale-map  (whale_entry_maps.json slice)
GET  /api/v2/clusters              /api/v2/cluster/{id}
GET  /api/v2/track-by-ca?ca=0x…&top=50     (wraps the existing engine)
GET  /api/v2/status  → { last_pipeline_run, data_age_seconds, supervisor,
                         event_latency_p50, event_latency_p95, blockscout_error_rate,
                         thresholds_in_force, wallets_scored, wallets_excluded,
                         exclusion_reasons: {…}, verified_count, unverified_count }
GET  /api/v2/methodology → { weights, normalization, thresholds, verifier_rules }
```

Contract rules: every response carries `generated_at` and `data_age_seconds`;
errors are `{ error: { code, message, hint } }` with real HTTP codes; pagination
is cursor-based (never offset — the feed grows under you); `Cache-Control`
tuned per endpoint (feed 5 s, wallet 60 s, methodology 300 s); CORS restricted
to the site's origin.

## 8.2 Hardening for public exposure

Rate limit per IP (token bucket, e.g. 60 req/min, 5 concurrent SSE); request
size limits; strict input validation (a CA is exactly 42 chars, `0x` + 40 hex —
reject everything else with 400); no stack traces in responses; structured
access logs without PII; TLS via Caddy or nginx + Let's Encrypt; the API binds
`127.0.0.1` and only the reverse proxy is public; security headers (HSTS, CSP —
no inline scripts, `X-Content-Type-Options`, `Referrer-Policy`); and **never**
expose `/results` as a raw directory listing.

## 8.3 Event generation

Upgrade `src/track/wallet_monitor.py` from "poll top wallets every 30 s and
alert on new tokens" into a proper event source:

1. **Block follower** — track head via `eth_blockNumber`; for each new range,
   fetch `Swap` logs from the PoolManager (+ v3 pools) once, and match against
   the tracked-wallet set. One pass per range beats N-wallets × Blockscout calls
   and is what makes sub-minute latency possible.
2. **Classification reuse** — reuse the net-flow-per-tx classifier. Do not
   write a second, subtly different classifier for the live path; extract the
   shared one into a module both call. Pin the equivalence with a test.
3. **Position deltas** — maintain the live position state per (wallet, token)
   so `ENTRY`/`ADD`/`TRIM`/`EXIT` can be typed correctly, seeded from the DB.
4. **Persist → publish** — write `feed_events`, then fan out to SSE subscribers
   and the alert sender. Persist first: a subscriber crash must not lose events.
5. **Backfill** — a CLI command that replays a block range into `feed_events`
   idempotently, so the feed can be seeded with history and repaired after
   downtime.
6. **Latency instrumentation** — record `block_ts`, `detected_at`,
   `published_at` on every event; expose p50/p95 on `/status`. This is what
   makes "before the crowd" a measurement instead of a slogan.

Respect the rate limits: the block follower must back off on RPC 429 and
Blockscout 500 exactly like the existing clients, and must not run concurrently
with a pipeline write on SQLite (move to Postgres — already in
`docker-compose.yml` — before enabling both).

---

# 9. DATA-QUALITY GATES (what is allowed on screen)

An event or wallet may be displayed publicly only if **all** of:
- the wallet passed the verifier (`verdict: verified`) or the row is explicitly
  badged `unverified` and excluded from every ranking and aggregate;
- the price used is from a pool swap within the acceptable window (no stale
  marks silently reused);
- the event carries a resolvable `proof.tx_url`;
- USD size ≥ `min_position_size_usd` (currently `1.0`) or the row is badged
  `DUST`;
- any wallet with `SINGLE_TOKEN_SAMPLE`, `WASH_PAIR`, `MEV_BOT`, or
  `INSIDER_SUSPECT` shows that flag inline — flags are never hidden to make a
  row look cleaner.

Aggregates (counts, "3 smart wallets bought") must be computed from the same
gated set that the UI shows. A number in a headline that disagrees with the
table below it is a bug.

---

# 10. DEPLOYMENT & OPS

- Everything ships in the existing `docker-compose.yml`: `postgres`, `redis`,
  `api`, `scheduler`, `monitor`, plus new `web` (the front end) and `proxy`
  (Caddy/nginx + TLS). Keep the compose profiles pattern.
- Front end: prefer **static export or SSG + client-side hydration** so the
  site survives an API outage with a cached last-known state and a stale banner.
  If you choose SSR, justify it in an ADR (`docs/adr/0001-frontend-stack.md`).
- Build the front end in CI or on the VPS — never install a node toolchain on
  the user's local machine (R-1, R-3).
- Systemd + supervisor + hourly watchdog already provide three-layer autonomy;
  register the new services with them so a crash self-heals.
- `results/` continues to auto-push to GitHub after each run
  (`AUTO_PUSH_RESULTS=true`, token masked). The web layer may read those files
  directly as a fallback source when the DB is unavailable.
- Add a `make dev` / `make deploy` (or `scripts/deploy_vps.py` extension) so the
  whole thing is one command, and document it in `scripts/VPS_SETUP.md`.

---

# 11. TESTING & ACCEPTANCE

**Unit / integration (must stay green, `pytest -q`):**
- The v4 topic0 test and price-orientation test still pass (regression guards).
- The live classifier and the batch classifier produce identical events for a
  fixed block range (golden fixture).
- Feed event ids are deterministic; replaying a range twice creates zero
  duplicates.
- Cursor pagination never skips or repeats an event across a concurrent insert.
- The freshness function returns the correct band for 30 s / 10 min / 3 h / 40 h.
- A malformed CA returns 400; an unknown CA returns 404; neither leaks a trace.

**Front-end:**
- Renders correctly with: 0 events, 1 event, 500 events, a 400x multiple, a
  $0.0000001 price, a 42-char address, a token with no symbol, `null` market cap.
- Light and dark, 375px and 1920px, with `prefers-reduced-motion` on and off.
- Lighthouse ≥ 95 accessibility; no horizontal body scroll at any width.
- SSE reconnects and backfills after a 60 s network cut with no duplicate rows.

**Acceptance — the feature is done only when a human can:**
1. Open the site and see the hero exactly as specified, with a freshness stamp
   that reflects real data age.
2. Watch a new on-chain trade by a tracked wallet appear in the feed within
   60 seconds, and click through to that transaction on Blockscout.
3. Click a wallet and see every number in its dossier, each traceable to raw data.
4. Paste a contract address into `/track` and get a ranked list.
5. Open a token and read its Whale Entry Map, with `INSUFFICIENT_DATA` shown
   honestly where the sample is thin.
6. Open `/status` and see the true state of the machine — including what's broken.
7. Read `/methodology` and understand exactly what "smart money" means here,
   including the current young-chain caveat.

---

# 12. MILESTONE PLAN

Each milestone ends with: `pytest -q` green → deployed on the VPS → verified
against real data → `PROGRESS.md` + `PRE_COMPACT.md` updated → committed and
pushed → a one-paragraph honest report to the user (what works, what doesn't).

- **M0 — Orientation (no code).** Read the six documents. Pull the repo. Run
  `python -m src.cli stats`. Diff the actual data against §4 of this prompt and
  report every discrepancy. Confirm the VPS state (`supervisor_status.json`,
  `night_watch.log`). Deliver: a 10-line state report + a corrected §4.
- **M1 — Feed data layer.** `feed_events` table, deterministic ids, the shared
  classifier extraction, the backfill CLI, tests. Seed the feed from existing
  history so it isn't empty on day one.
- **M2 — API v2 + `/status`.** All endpoints from §8.1, hardened per §8.2,
  with the real latency instrumentation. Public behind TLS on the VPS.
- **M3 — The hero + the feed.** The screen in §0, live via SSE, with the
  freshness contract, empty/stale/error states, light+dark, mobile. This is the
  first user-visible milestone — send the user a URL and a screenshot.
- **M4 — Depth pages.** Wallet dossier, token page + Whale Entry Map,
  leaderboard, `/methodology`.
- **M5 — Real-time upgrade.** Block follower replaces polling; p95 latency
  measured and published; alerts filtered by type/tier/size.
- **M6 — Forensics surface.** Clusters view (`cluster_f70d` first), funding
  provenance, PnL Truth Engine verdicts (`GENUINE`/`HALU`/`TREND_RIDER`) when
  the engine lands, tiering S/A/B.
- **Continuous — universe expansion.** Push `MAX_TOKENS` toward 300–500, keep
  chain-wide discovery running, and restore the 5-positions × 3-tokens bar the
  moment the universe supports it. Every threshold change is announced in the
  UI and recorded in `PROGRESS.md`.

---

# 13. WORKING PROTOCOL (how to not lose context)

- Append a new snapshot block to the **top** of the S-series in `PRE_COMPACT.md`
  at every milestone, every important finding, and proactively as the session
  grows long. Never delete old blocks — they are the audit trail.
- After any context compaction, compare the post-compaction summary against the
  newest `PRE_COMPACT.md` block; if they disagree, **trust the file**.
- Update `PROGRESS.md` with a dated entry per run/milestone.
- Sync the same notes to the user's Obsidian vault:
  `C:\Users\ROG\Documents\Obsidian\Sniper Token\TopWallet\`.
- Commit + push after every milestone
  (`git push https://papatora:<GITHUB_TOKEN>@github.com/papatora/TopWalllet main`,
  token from `.env`, never inline in a file or a log).
- Record every architectural decision as a short ADR in `docs/adr/`.

---

# 14. FIRST TEN ACTIONS (do these in order, then report)

1. `git pull` the repo; read the six documents listed at the top.
2. Run `python -m src.cli stats` and read `results/stats.json`,
   `results/supervisor_status.json`, `results/night_watch.log`.
3. Confirm the VPS is healthy and the supervisor is looping; if not, fix that
   before building anything (a beautiful UI over a dead pipeline is worthless).
4. Re-check §4's numbers against reality and report the deltas to the user.
5. Write `docs/adr/0001-frontend-stack.md` — pick the stack, justify it against
   R-3 (dependency count is a security argument, not a taste argument).
6. Design and migrate the `feed_events` table; extract the shared classifier.
7. Write the backfill command; seed the feed from existing history; prove
   idempotency with a double-run test.
8. Build API v2 `/feed`, `/status`, `/stream` with tests.
9. Build the hero + feed page (§0, §7) against the live API on the VPS.
10. Send the user: the URL, a screenshot, the measured p50/p95 latency, and an
    explicit list of what is still fake, missing, or thin.

---

# 15. FAILURE MODES — the ways this project dies

- **The pretty lie.** A gorgeous feed showing "smart money" that is actually six
  micro-scalpers making $20. Mitigation: §4, §9, `/methodology`, honest badges.
- **The frozen clock.** "updated just now" over stale data. Mitigation: §6.9,
  the freshness test, the `/status` page.
- **The second classifier.** A live path that types trades slightly differently
  from the batch path, so the feed and the leaderboard disagree. Mitigation:
  one shared module + a golden-fixture equivalence test.
- **Local execution.** Running scraping or the pipeline on the user's machine
  because it was convenient. Mitigation: R-1, the supervisor guard, and asking.
- **Dependency creep.** `npx create-something` pulling 900 transitive packages
  onto a machine that holds crypto keys. Mitigation: R-3, count and justify
  every dependency, build in CI/VPS only.
- **Rate-limit self-DoS.** The block follower and the pipeline hammering
  Blockscout together until everything 500s and the verifier drops honest
  wallets. Mitigation: shared limiter, circuit breaker, Postgres, backoff.
- **Silent zero.** A wrong topic hash or a flipped orientation returning no
  logs or absurd prices without an error. Mitigation: the pinned tests, the
  orientation self-check, and alerting on "zero events for N minutes".

---

# 16. ASK THE USER — do not guess these

1. Domain name and whether the site should be public, unlisted, or behind basic auth.
2. Front-end stack preference (or accept your ADR's recommendation).
3. Whether to keep the site read-only or add email/Telegram subscriptions
   (which would introduce personal data and a whole compliance surface).
4. Whether the hero copy should shift while the sample is thin (e.g.
   "tracking the first verified wallets on robinhood chain") and switch to
   "before the crowd" once the data earns it.
5. When they will supply the fomo.family `Copy as cURL` capture and the X auth
   tokens for the CT-attribution phase.
6. Budget for a paid RPC tier — free-tier `eth_getLogs` (10-block ranges) is the
   hard ceiling on how "real-time" the feed can honestly be.

---

*Ground truth beats this document. If the repo, the data, or the user disagrees
with anything here, they win — then update this file and push it.*
