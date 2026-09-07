"""Feed event derivation + persistence (docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md §6.2/§6.3/§8.3-5).

Derives `feed_events` rows from data already in the DB (SwapEvents priced via
PricePoint series) — no network calls. This is the backfill path; the live
block follower (M5) must reuse these same typing rules, not a second set.

Determinism / idempotency contract
----------------------------------
* SwapEvent has no on-chain log index, so the id's `idx` is a CONTENT-based
  per-tx combo index: the lexicographic position of the swap's
  (wallet, token, side) tuple among the distinct tuples of that tx (unique per
  tx by uq_swap). Same tx content → same id, regardless of row ids or insert
  order — a replayed range adds zero duplicates.
* Positions and the CALL check ("no tracked wallet held the token before") are
  replayed over the FULL swap history; only events inside
  [start_block, end_block] are emitted.
* ROTATION is typed ON the ENTRY leg (a first buy that redeploys capital
  exited within the previous ROTATION_WINDOW_BLOCKS from a different token),
  so every event still anchors 1:1 to one SwapEvent — no synthetic ids. A
  genuine CALL outranks the rotation pattern; the payload's context.rotation
  cites the exit event.

Honesty rules (§6.2): unknown fields stay null — no zero-filling, no guessed
market caps, no token age (tokens.first_seen is discovery time, not creation).
Tiers (S/A/B, §6.4) stay null until the M6 tiering ships. A swap without a
known tx_hash has no proof → no row. Sells with no tracked position (airdrop
dumps) are not typable per §6.3 → no event.

Confidence (§6.4) is a documented rule sum, each term citing its reason:
verified verdict +0.40, CALL +0.15, first touch +0.10, ≥3 other tracked
wallets in the token over the previous 24h +0.20, whale map verdict STRONG
+0.15 (capped at 1.0). No reasons → score stays null.
"""
from __future__ import annotations

import bisect
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from src.db.models import FeedEvent, Pool, PricePoint, SwapEvent, Token, WalletScore

log = logging.getLogger(__name__)

# --- typing thresholds (§6.3) ---
ADD_MIN_INCREASE = 0.25        # buy that grows the position ≥25% = ADD
TRIM_MIN_FRACTION = 0.20       # sell 20–80% of the position = TRIM
EXIT_MIN_FRACTION = 0.80       # sell ≥80% of the position = EXIT
ROTATION_WINDOW_BLOCKS = 2400  # ENTRY within N blocks after an EXIT (≈10 min at 0.25 s/block)
EPS = 1e-12                    # position noise floor

DERIVATION = ("backfill v1: net-flow-per-tx swaps (swap_events) priced from "
              "price_points series; types per §6.3; id idx = per-tx "
              "(wallet,token,side) combo index")

# freshness bands (§6.9) in seconds
JUST_NOW_S = 60
MINUTES_S = 900        # 15 min
HOURS_S = 7200         # 2 h
STALE_TODAY_S = 86400  # 24 h


def freshness_band(age_seconds: float) -> str:
    """§6.9 freshness band for a data age in seconds."""
    if age_seconds < JUST_NOW_S:
        return "just_now"
    if age_seconds < MINUTES_S:
        return "minutes"
    if age_seconds < HOURS_S:
        return "hours"
    if age_seconds < STALE_TODAY_S:
        return "stale_today"
    return "stale"


def make_event_id(block: int, tx_hash: str, idx: int) -> str:
    """Deterministic §6.2 id: evt_{chain_id}_{block}_{tx_hash}_{idx}."""
    return f"evt_{settings.chain_id}_{int(block)}_{(tx_hash or '').lower()}_{int(idx)}"


def _as_utc(ts):
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _load_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _price_at(series_by_token: dict, token: str, block: int) -> float | None:
    """Nearest PricePoint at or before `block` for the token's pool series."""
    bp = series_by_token.get(token)
    if not bp:
        return None
    blocks, prices = bp
    i = bisect.bisect_right(blocks, block) - 1
    return prices[i] if i >= 0 else None


async def build_ranked_lookup(session: AsyncSession, results_dir: Path | str | None = None) -> dict:
    """Wallet → payload wallet-block (rank/score/verdict/style/flags/cluster)
    from wallet_scores + results/top_wallets_latest.json. Anything not in the
    data stays null — never guessed."""
    results_dir = Path(results_dir) if results_dir else settings.results_dir

    def blank() -> dict:
        return {"label": None, "rank": None, "composite_score": None, "tier": None,
                "verdict": None, "style": None, "risk_flags": None, "cluster_id": None}

    lookup: dict[str, dict] = {}
    for row in (await session.execute(select(WalletScore))).scalars().all():
        try:
            flags = json.loads(row.risk_flags) if row.risk_flags else []
        except ValueError:
            flags = None
        lookup[row.wallet_address] = blank() | {
            "composite_score": row.composite_score,
            "style": row.trading_style or None,
            "risk_flags": flags,
            "cluster_id": row.cluster_id,
        }
    latest = _load_json(results_dir / "top_wallets_latest.json", {}) or {}
    for entry in latest.get("wallets", []):
        addr = (entry.get("wallet_address") or "").lower()
        if not addr.startswith("0x"):
            continue
        info = lookup.setdefault(addr, blank())
        info["rank"] = entry.get("rank")
        if entry.get("composite_score") is not None:
            info["composite_score"] = entry["composite_score"]
        verdict = (entry.get("verification") or {}).get("verdict")
        if verdict and verdict != "not_checked":
            info["verdict"] = verdict  # verified | unverified (§6.4)
        info["style"] = entry.get("trading_style") or info["style"]
        if isinstance(entry.get("risk_flags"), list):
            info["risk_flags"] = entry["risk_flags"]
    return lookup


async def backfill(
    session: AsyncSession,
    ranked_lookup: dict | None = None,
    start_block: int | None = None,
    end_block: int | None = None,
    results_dir: Path | str | None = None,
) -> int:
    """Derive FeedEvents from SwapEvents + PricePoints; persist; return count.

    Idempotent: events whose deterministic id already exists are skipped, so
    replaying a range (or re-running after new wallets were enriched) only
    adds genuinely new rows. `ranked_lookup` (see build_ranked_lookup) fills
    the payload wallet block; missing wallets stay null.
    """
    ranked_lookup = ranked_lookup or {}
    results_dir = Path(results_dir) if results_dir else settings.results_dir
    now = datetime.now(timezone.utc)
    whale_maps = (_load_json(results_dir / "whale_entry_maps.json", {}) or {}).get("maps", {})

    # --- load everything in a handful of queries (FULL history: positions and
    # the CALL check must be seeded from each wallet's first swap) ---
    swaps = (await session.execute(
        select(SwapEvent).order_by(SwapEvent.block_num, SwapEvent.tx_hash)
    )).scalars().all()
    tokens = {t.address: t for t in (await session.execute(select(Token))).scalars().all()}
    pools = (await session.execute(select(Pool))).scalars().all()

    # deepest pool per token (same preference as pipeline.stage_prices)
    pool_by_token: dict[str, str] = {}
    for p in sorted(pools, key=lambda p: p.liquidity_usd or 0, reverse=True):
        pool_by_token.setdefault(p.token_address, p.address)
    pts_by_pool: dict[str, list] = defaultdict(list)
    for pt in (await session.execute(
            select(PricePoint).order_by(PricePoint.block_num))).scalars().all():
        pts_by_pool[pt.pool_address].append(pt)
    series_by_token: dict[str, tuple[list[int], list[float]]] = {}
    for tok, pool in pool_by_token.items():
        pts = pts_by_pool.get(pool) or []
        if pts:
            series_by_token[tok] = ([q.block_num for q in pts], [q.price_usd for q in pts])

    # --- precomputed indexes over the full history ---
    combos: dict[str, set] = defaultdict(set)              # tx → {(wallet, token, side)}
    token_first_block: dict[str, int] = {}                 # token → first activity block
    token_swaps_ts: dict[str, list] = defaultdict(list)    # token → sorted (iso ts, wallet)
    block_sides: dict[tuple, dict] = defaultdict(dict)     # (token, block) → {wallet: side}
    for s in swaps:
        combos[s.tx_hash].add((s.wallet_address, s.token_address, s.side))
        cur = token_first_block.get(s.token_address)
        token_first_block[s.token_address] = min(cur, s.block_num) if cur is not None else s.block_num
        ts_utc = _as_utc(s.ts)
        if ts_utc is not None:
            token_swaps_ts[s.token_address].append((ts_utc.isoformat(), s.wallet_address))
        block_sides[(s.token_address, s.block_num)][s.wallet_address] = s.side
    for lst in token_swaps_ts.values():
        lst.sort()
    combo_idx = {tx: {c: i for i, c in enumerate(sorted(cs))} for tx, cs in combos.items()}

    def smart_wallets_24h(token: str, ts_utc: datetime, self_wallet: str) -> int:
        """Distinct OTHER tracked wallets that swapped the token in the
        previous 24h (corroboration, §6.2 context). Timestamps are stored as
        UTC ISO strings (_as_utc), so lexicographic order == time order."""
        lst = token_swaps_ts.get(token) or []
        lo = bisect.bisect_left(lst, ((ts_utc - timedelta(hours=24)).isoformat(), ""))
        hi = bisect.bisect_right(lst, (ts_utc.isoformat(), "\uffff"))
        return len({w for _t, w in lst[lo:hi]} - {self_wallet})

    def same_block_counterparty(token: str, block: int, side: str, self_wallet: str) -> str | None:
        """Another tracked wallet on the opposite side in the same block
        (wash-pair hint, §6.2 context) — factual, not a verdict."""
        sides = block_sides.get((token, block)) or {}
        opp = "SELL" if side == "BUY" else "BUY"
        for w in sorted(sides):
            if w != self_wallet and sides[w] == opp:
                return w
        return None

    def _id_for(s: SwapEvent) -> str:
        idx = combo_idx[s.tx_hash][(s.wallet_address, s.token_address, s.side)]
        return make_event_id(s.block_num, s.tx_hash, idx)

    # --- pass 1: position replay per (wallet, token); type every swap ---
    by_wallet_token: dict[tuple, list] = defaultdict(list)
    for s in swaps:
        by_wallet_token[(s.wallet_address, s.token_address)].append(s)

    events: list[dict] = []
    exits_by_wallet: dict[str, list[dict]] = defaultdict(list)
    for (wallet, token), evs in sorted(by_wallet_token.items()):
        units = 0.0
        cost_usd = 0.0
        cost_known = True  # any unpriced buy makes avg_entry unknowable
        for s in sorted(evs, key=lambda e: (e.block_num, e.tx_hash)):
            amount = s.token_amount
            if amount <= 0:
                continue
            price = s.price_usd if s.price_usd else _price_at(series_by_token, token, s.block_num)
            first_touch = False
            if s.side == "BUY":
                first_touch = units <= EPS
                if first_touch:
                    # CALL: no tracked wallet (incl. self — it's the first
                    # touch) showed ANY activity on the token before this block
                    etype = ("CALL" if token_first_block.get(token, s.block_num) >= s.block_num
                             else "ENTRY")
                elif amount / units >= ADD_MIN_INCREASE:
                    etype = "ADD"
                else:
                    etype = None  # dust top-up: below §6.3 thresholds
                units += amount
                if price is None:
                    cost_known = False
                else:
                    cost_usd += amount * price
                if etype is None:
                    continue
                pos_after = {
                    "avg_entry_usd": (cost_usd / units) if (cost_known and units > EPS) else None,
                    "size_usd": units * price if price is not None else None,
                }
            else:  # SELL
                if units <= EPS:
                    continue  # no tracked position (airdump/receiver) → not typable
                frac = amount / units
                if frac >= EXIT_MIN_FRACTION:
                    etype = "EXIT"
                elif frac >= TRIM_MIN_FRACTION:
                    etype = "TRIM"
                else:
                    etype = None  # dust trim: below §6.3 thresholds
                cost_usd *= max(1.0 - frac, 0.0)
                units = max(units - amount, 0.0)
                if etype is None:
                    continue
                pos_after = {
                    "avg_entry_usd": (cost_usd / units) if (cost_known and units > EPS) else None,
                    "size_usd": units * price if price is not None else None,
                }
            events.append({
                "swap": s, "type": etype, "price": price,
                "is_first_touch": first_touch,
                "position_after": pos_after, "id": _id_for(s),
            })
            if etype == "EXIT":
                exits_by_wallet[wallet].append(
                    {"token": token, "block": s.block_num, "tx_hash": s.tx_hash, "id": _id_for(s)})

    # --- pass 2: ROTATION — a first buy redeploing capital from a recent exit
    # (same wallet, different token, within ROTATION_WINDOW_BLOCKS). Typed on
    # the ENTRY leg; a genuine CALL outranks it. ---
    for ev in events:
        s = ev["swap"]
        if s.side != "BUY" or not ev["is_first_touch"] or ev["type"] == "CALL":
            continue
        candidates = [x for x in exits_by_wallet.get(s.wallet_address, [])
                      if x["token"] != s.token_address
                      and 0 <= s.block_num - x["block"] <= ROTATION_WINDOW_BLOCKS]
        if not candidates:
            continue
        x = max(candidates, key=lambda x: x["block"])  # most recent exit
        ev["type"] = "ROTATION"
        ev["rotation"] = {
            "from_token": x["token"], "exit_event_id": x["id"],
            "exit_block": x["block"], "exit_tx_hash": x["tx_hash"],
            "blocks_after_exit": s.block_num - x["block"],
        }

    # --- pass 3: build payloads and persist (skip existing ids; the block
    # window applies to EMISSION only, never to the replay above) ---
    stmt = select(FeedEvent.id)
    if start_block is not None:
        stmt = stmt.where(FeedEvent.block >= start_block)
    if end_block is not None:
        stmt = stmt.where(FeedEvent.block <= end_block)
    existing: set[str] = set((await session.execute(stmt)).scalars())

    persisted = 0
    for ev in sorted(events, key=lambda e: e["id"]):
        s = ev["swap"]
        if start_block is not None and s.block_num < start_block:
            continue
        if end_block is not None and s.block_num > end_block:
            continue
        if not s.tx_hash or _as_utc(s.ts) is None:
            continue  # §6.2: no proof / no block timestamp → no row
        if ev["id"] in existing:
            continue
        existing.add(ev["id"])

        ts_utc = _as_utc(s.ts)
        lag = (now - ts_utc).total_seconds()
        ranked = ranked_lookup.get(s.wallet_address) or {}
        tok = tokens.get(s.token_address)
        w24 = smart_wallets_24h(s.token_address, ts_utc, s.wallet_address)
        wmap = whale_maps.get(s.token_address) or {}

        # confidence (§6.4): documented rule sum — every term cites its reason
        reasons: list[str] = []
        score = 0.0
        if ranked.get("verdict") == "verified":
            score += 0.40
            reasons.append("verified_wallet")
        if ev["type"] == "CALL":
            score += 0.15
            reasons.append("first_call")
        if ev["is_first_touch"]:
            score += 0.10
            reasons.append("first_touch")
        if w24 >= 3:
            score += 0.20
            reasons.append("corroborated_by_3+_smart_wallets_24h")
        if (wmap.get("verdict") or "").upper() == "STRONG":
            score += 0.15
            reasons.append("whale_map_strong")

        payload = {
            "id": ev["id"],
            "type": ev["type"],
            "ts": ts_utc.isoformat(),
            "block": s.block_num,
            "tx_hash": s.tx_hash,
            "detected_at": now.isoformat(),
            "published_at": now.isoformat(),
            "lag_seconds": round(lag, 3),
            "wallet": {
                "address": s.wallet_address,
                "label": ranked.get("label"),
                "rank": ranked.get("rank"),
                "composite_score": ranked.get("composite_score"),
                "tier": ranked.get("tier"),  # null until M6 tiering ships
                "verdict": ranked.get("verdict"),
                "style": ranked.get("style"),
                "risk_flags": ranked.get("risk_flags"),
            },
            "token": {
                "ca": s.token_address,
                "symbol": (tok.symbol or None) if tok else None,
                "name": (tok.name or None) if tok else None,
                "price_usd": tok.price_usd if tok else None,
                "liquidity_usd": tok.liquidity_usd if tok else None,
                "market_cap_usd": None,  # not in the DB — null, never a guess
                "age_hours": None,       # first_seen is discovery time, not age
            },
            "action": {
                "side": s.side.lower(),
                "amount_token": s.token_amount,
                "amount_usd": s.token_amount * ev["price"] if ev["price"] is not None else None,
                "price_usd": ev["price"],
                "pct_of_wallet_activity": None,  # not derivable from swap history
                "is_first_touch": ev["is_first_touch"],
                "position_after": ev["position_after"],
            },
            "context": {
                "smart_wallets_in_token_24h": w24,
                "whale_conviction_score": wmap.get("conviction_score"),
                "whale_verdict": wmap.get("verdict"),
                "cluster_id": ranked.get("cluster_id"),
                "same_block_counterparty": same_block_counterparty(
                    s.token_address, s.block_num, s.side, s.wallet_address),
            },
            "confidence": {"score": round(min(score, 1.0), 2) if reasons else None,
                           "reasons": reasons},
            "proof": {
                "tx_url": f"{settings.blockscout_url}/tx/{s.tx_hash}",
                "wallet_url": f"{settings.blockscout_url}/address/{s.wallet_address}",
                "token_url": f"{settings.blockscout_url}/token/{s.token_address}",
                "derivation": DERIVATION,
            },
        }
        if "rotation" in ev:
            payload["context"]["rotation"] = ev["rotation"]

        session.add(FeedEvent(
            id=ev["id"], type=ev["type"],
            wallet_address=s.wallet_address, token_address=s.token_address,
            ts=s.ts, block=s.block_num, tx_hash=s.tx_hash,
            detected_at=now, published_at=now, lag_seconds=round(lag, 3),
            payload=json.dumps(payload, default=str),
        ))
        persisted += 1

    await session.commit()
    log.info("feed backfill done: %d events persisted (%d swaps scanned, "
             "block range %s..%s)", persisted, len(swaps), start_block, end_block)
    return persisted
