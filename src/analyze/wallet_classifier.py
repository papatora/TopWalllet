"""Wallet classification system — docs/WALLET_TAXONOMY.md (14-type taxonomy).

Classifies every wallet that has SwapEvents into coexisting LABELS plus one
PRIMARY type (taxonomy priority 1→14, first match wins; e.g. a wallet can be
BUNDLER_SUSPECT + SNIPER + CLUSTER_MEMBER:cluster_f70d with primary
BUNDLER_SUSPECT). Results are persisted to the `wallet_labels` table and
exported to results/wallet_labels.json.

Signal sources (existing data only — no new network calls):
  * SwapEvent   — per-wallet buys/sells (side, block_num, tx_hash, token)
  * PricePoint  — min block per pool == pool-creation proxy (per taxonomy)
  * Pool        — token → pool mapping
  * results/funder_clusters.json + results/funding_provenance.py output
    (results/funding_forensics.json) — funding clusters + dev fingerprint
  * results/external_leaderboards.json — GMGN smart-money capture with CT
    names → interim CT_ATTRIBUTED (taxonomy #7; X-linkage is a later phase)
  * WalletScore.cluster_id — anti_gaming token-overlap clusters (cheap
    first-approximation sybil fleets)

DETECTION RULES THAT CANNOT BE COMPUTED FROM EXISTING DATA — SKIPPED, NOT
GUESSED (see taxonomy "CATATAN DETEKSI" / GMGN guide §2, §6, §7):
  * PHISHING_SUSPECT (#6) — needs the incoming-transfer spread graph (one
    sender airdropping ≥20 wallets within ≤100 blocks). Pure token transfers
    are NOT persisted as SwapEvent (enrichment drops non-pool legs), so the
    spread pattern is not computable yet; needs a transfers table first.
  * DEV (#2) mint sub-rule "received tokens from 0x0 directly" — mint /
    transfer legs are not in SwapEvent; only the first-buyer + fast-flip
    clause is implemented.
  * DEV_SERIAL_RUGGER (#1) "funder == funder of dead pools" clause — pool
    death (liquidity-pull) data is not in the DB; the alternative clause
    (first buyer ≤50 blocks of pool creation in ≥5 distinct tokens) plus the
    early-entry/fast-flip fingerprint (mirrors funding_provenance.dev_fingerprint,
    computed batched over all wallets) is used instead.
  * FRESH_GOOD / FRESH_BAD (#11/#12) — need wallet creation age and initial
    capital; wallets.first_seen is discovery time, not wallet age.
  * SMART_TRACKER (#10) — assigned only when the pipeline passes the ranked
    list (hard PnL verifier verdict == "verified"); session-only runs skip it.

Bundle detection follows GMGN guide §6/§7: on EVM L2 the practical bundle is
one smart-contract tx that buys from many wallets atomically — so one tx_hash
containing BUYs from ≥5 distinct wallets at pool creation flags every one of
those wallets BUNDLER_SUSPECT. Per the guide this is NOT always the dev
(third-party sniper bots bundle too) — cross-check funding + insiders.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from src.db.models import Pool, PricePoint, SwapEvent, WalletLabel, WalletScore

log = logging.getLogger(__name__)

# --- thresholds (docs/WALLET_TAXONOMY.md + GMGN guide §2/§6/§7) ---
SNIPER_BLOCKS = 10            # first buy ≤ N blocks after pool's first swap
BUNDLE_MIN_WALLETS = 5        # one tx with buys from ≥ N wallets = bundle
BUNDLE_WINDOW_BLOCKS = 10     # bundle tx must land at pool creation (± N blocks)
DEV_FIRST_BUY_BLOCKS = 300    # DEV: first buyer ≤ N blocks of pool creation
SERIAL_FIRST_BUY_BLOCKS = 50  # DEV_SERIAL_RUGGER alt clause window
SERIAL_MIN_TOKENS = 5         # ≥ N distinct tokens for the serial pattern
EARLY_BLOCKS = 300            # mirrors funding_provenance.EARLY_BLOCKS
FAST_FLIP_HOURS = 24          # mirrors funding_provenance.FAST_FLIP_HOURS
FAST_FLIP_RATIO = 0.95        # sold/bought ≥ ratio = fully flipped
MIN_CLUSTER_SIZE = 3          # funder shared by ≥ N wallets = funding cluster
MEV_MAX_HOLD_MINUTES = 10     # median hold ≤ N minutes ...
MEV_MIN_ROUNDTRIPS = 30       # ... across ≥ N buy→sell round trips

# evidence-independent confidence per label (heuristics, not verdicts)
CONF = {
    "DEV_SERIAL_RUGGER": 0.90,
    "DEV": 0.70,
    "BUNDLER_SUSPECT": 0.90,
    "SNIPER": 0.85,
    "INSIDER": 0.60,
    "PHISHING_SUSPECT": 0.60,   # reserved (rule skipped, see docstring)
    "CT_ATTRIBUTED": 0.60,
    "CLUSTER_MEMBER_FUNDING": 0.75,
    "CLUSTER_MEMBER_CAPTURE": 0.75,
    "CLUSTER_MEMBER_TOKENSET": 0.50,
    "AIRDROP_FARMER": 0.95,
    "SMART_TRACKER": 0.80,
    "FRESH_GOOD": 0.60,         # reserved (rule skipped)
    "FRESH_BAD": 0.60,          # reserved (rule skipped)
    "MEV_BOT": 0.85,
    "GENERALIST": 0.50,
}

# taxonomy priority 1→14 (prefix match covers CLUSTER_MEMBER:<id>)
PRIMARY_PRIORITY = (
    "DEV_SERIAL_RUGGER", "DEV", "BUNDLER_SUSPECT", "SNIPER", "INSIDER",
    "PHISHING_SUSPECT", "CT_ATTRIBUTED", "CLUSTER_MEMBER", "AIRDROP_FARMER",
    "SMART_TRACKER", "FRESH_GOOD", "FRESH_BAD", "MEV_BOT",
)


def primary_type(labels: list[str] | set[str]) -> str:
    """First label per taxonomy priority; GENERALIST when nothing matched."""
    for prio in PRIMARY_PRIORITY:
        for lbl in sorted(labels):
            if lbl == prio or lbl.startswith(prio + ":"):
                return lbl
    return "GENERALIST"


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


def _trunc_prefix(member: str) -> str:
    """funder_clusters.json stores display-truncated addresses ('0xabc…')."""
    if member.endswith("…"):
        return member[:-1]
    if member.endswith("..."):
        return member[:-3]
    return member


# ---------------- per-signal detectors (pure functions over event maps) ----

def _bundle_signal(by_wallet, token_first) -> dict[str, dict]:
    """BUNDLER_SUSPECT: one tx containing BUYs from ≥5 distinct wallets at
    pool creation (atomic multicall bundle, GMGN guide §7)."""
    buys_by_tx: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for wallet, evs in by_wallet.items():
        for e in evs:
            if e.side != "BUY" or not e.tx_hash:
                continue
            first = token_first.get(e.token_address)
            if first is None:
                continue
            if abs(e.block_num - first) <= BUNDLE_WINDOW_BLOCKS:
                buys_by_tx[(e.token_address, e.tx_hash)].setdefault(wallet, e.block_num)
    out: dict[str, dict] = {}
    for (token, tx), wallets in buys_by_tx.items():
        if len(wallets) < BUNDLE_MIN_WALLETS:
            continue
        evd = {
            "token": token,
            "tx_hash": tx,
            "block": min(wallets.values()),
            "distinct_wallets": len(wallets),
            "wallet_sample": sorted(wallets)[:10],
        }
        for wallet in wallets:
            out[wallet] = evd
    return out


def _sniper_signal(by_wallet, token_first) -> dict[str, dict]:
    """SNIPER: first BUY of a token within ≤10 blocks of the pool's first
    observed swap (pool-creation proxy, taxonomy #4)."""
    out: dict[str, dict] = {}
    for wallet, evs in by_wallet.items():
        first_buy: dict[str, object] = {}
        for e in evs:  # events arrive block-ordered
            if e.side == "BUY" and e.token_address not in first_buy:
                first_buy[e.token_address] = e
        snipes = []
        for token, e in first_buy.items():
            first = token_first.get(token)
            if first is None:
                continue
            delta = e.block_num - first
            if 0 <= delta <= SNIPER_BLOCKS:
                snipes.append({
                    "token": token,
                    "buy_block": e.block_num,
                    "pool_first_block": first,
                    "delta_blocks": delta,
                    "tx_hash": e.tx_hash,
                })
        if snipes:
            out[wallet] = {"snipe_count": len(snipes), "snipes": snipes[:10]}
    return out


def _insider_signal(by_wallet) -> dict[str, dict]:
    """INSIDER: SELLs a token the wallet never BUYed — the token must have
    arrived off-pipeline (receive-only / transfer, taxonomy #5 approximation)."""
    out: dict[str, dict] = {}
    for wallet, evs in by_wallet.items():
        bought = {e.token_address for e in evs if e.side == "BUY"}
        sells: dict[str, list[dict]] = defaultdict(list)
        for e in evs:
            if e.side == "SELL" and e.token_address not in bought:
                sells[e.token_address].append({"block": e.block_num, "tx_hash": e.tx_hash})
        if sells:
            out[wallet] = {
                "tokens": sorted(sells),
                "sell_count": sum(len(v) for v in sells.values()),
                "sample_sells": [s for t in sorted(sells) for s in sells[t][:2]][:10],
            }
    return out


def _airdrop_signal(by_wallet) -> dict[str, dict]:
    """AIRDROP_FARMER port (anti_gaming): swap history exists but zero BUYs —
    100% incoming, never bought (taxonomy #9)."""
    out: dict[str, dict] = {}
    for wallet, evs in by_wallet.items():
        if not evs or any(e.side == "BUY" for e in evs):
            continue
        out[wallet] = {
            "swaps": len(evs),
            "tokens": sorted({e.token_address for e in evs})[:10],
            "note": "100% incoming / zero BUY swaps (anti_gaming port)",
        }
    return out


def _dev_signals(by_wallet, token_first, funding):
    """DEV_SERIAL_RUGGER (#1) + DEV (#2) via first-buyer and early/fast-flip
    fingerprints (mirrors funding_provenance.dev_fingerprint, batched).

    Returns (serial_evidence, dev_evidence) — mutually exclusive per wallet.
    """
    first_buyer: dict[str, tuple[str, int]] = {}  # token -> (wallet, block)
    for wallet, evs in by_wallet.items():
        for e in evs:
            if e.side != "BUY" or e.token_address not in token_first:
                continue
            cur = first_buyer.get(e.token_address)
            if cur is None or e.block_num < cur[1]:
                first_buyer[e.token_address] = (wallet, e.block_num)

    serial: dict[str, dict] = {}
    dev: dict[str, dict] = {}
    for wallet, evs in by_wallet.items():
        by_token: dict[str, list] = defaultdict(list)
        for e in evs:
            by_token[e.token_address].append(e)
        serial_tokens: list[dict] = []
        firstbuyer_early: list[dict] = []
        early_tokens = 0
        fast_flips: list[str] = []
        for token in sorted(by_token):
            tevs = by_token[token]
            first = token_first.get(token)
            buys = [e for e in tevs if e.side == "BUY"]
            sells = [e for e in tevs if e.side == "SELL"]
            if first is None or not buys:
                continue
            fb = buys[0]  # block-ordered
            delta = fb.block_num - first
            if delta <= EARLY_BLOCKS:
                early_tokens += 1
            bought = sum(e.token_amount for e in buys)
            sold = sum(e.token_amount for e in sells)
            hold_h = None
            if sells and fb.ts:
                hold_h = (_as_utc(max(s.ts for s in sells)) - _as_utc(fb.ts)
                          ).total_seconds() / 3600
            flipped = (bought > 0 and sold / bought >= FAST_FLIP_RATIO
                       and hold_h is not None and hold_h <= FAST_FLIP_HOURS)
            if flipped:
                fast_flips.append(token)
            rec = first_buyer.get(token)
            hit = {"token": token, "buy_block": fb.block_num,
                   "pool_first_block": first, "delta_blocks": delta}
            if rec and rec[0] == wallet and delta <= SERIAL_FIRST_BUY_BLOCKS:
                serial_tokens.append(hit)
            elif rec and rec[0] == wallet and delta <= DEV_FIRST_BUY_BLOCKS:
                firstbuyer_early.append(hit)

        fp = (funding.get(wallet) or {}).get("dev_fingerprint") or {}
        early_n = max(early_tokens, int(fp.get("early_entries") or 0))
        flip_n = max(len(fast_flips), int(fp.get("fast_flips") or 0))
        if len(serial_tokens) >= SERIAL_MIN_TOKENS or (
                early_n >= SERIAL_MIN_TOKENS and flip_n >= SERIAL_MIN_TOKENS):
            serial[wallet] = {
                "first_buyer_tokens_le_50_blocks": len(serial_tokens),
                "early_entries": early_n,
                "fast_flips": flip_n,
                "sample": serial_tokens[:5] or [
                    {"token": t} for t in fast_flips[:5]],
            }
        elif 1 <= len(firstbuyer_early) <= 4 and fast_flips:
            dev[wallet] = {
                "first_buyer_tokens_le_300_blocks": len(firstbuyer_early),
                "fast_flips": len(fast_flips),
                "sample": firstbuyer_early[:4],
            }
    return serial, dev


def _mev_signal(by_wallet) -> dict[str, dict]:
    """MEV_BOT (#13): ≥30 buy→sell round trips with median hold ≤10 minutes
    (k-th BUY paired with k-th SELL per token, both block-ordered)."""
    out: dict[str, dict] = {}
    for wallet, evs in by_wallet.items():
        buys: dict[str, list] = defaultdict(list)
        sells: dict[str, list] = defaultdict(list)
        for e in evs:
            (buys if e.side == "BUY" else sells)[e.token_address].append(e)
        holds: list[float] = []
        for token, b_list in buys.items():
            for b, s in zip(b_list, sells.get(token, [])):
                if b.ts is None or s.ts is None:
                    continue
                minutes = (_as_utc(s.ts) - _as_utc(b.ts)).total_seconds() / 60
                holds.append(max(minutes, 0.0))
        if len(holds) >= MEV_MIN_ROUNDTRIPS:
            med = sorted(holds)[len(holds) // 2]
            if med <= MEV_MAX_HOLD_MINUTES:
                out[wallet] = {"round_trips": len(holds),
                               "median_hold_minutes": round(med, 2)}
    return out


def _cluster_signal(wallets, funding, clusters_file, score_cluster):
    """CLUSTER_MEMBER:<id> labels. Returns wallet → list[(label, conf, evid)].

    Three sources, all allowed to coexist:
      * funding_forensics.json  — funder shared by ≥3 tracked wallets
      * funder_clusters.json    — analyst/operator capture (members may be
        display-truncated '0xabc…' → prefix-matched against full addresses)
      * WalletScore.cluster_id  — anti_gaming token-overlap clusters
    """
    hits: dict[str, list[tuple[str, float, dict]]] = defaultdict(list)

    # 1) funding provenance: same funder → same operator (taxonomy #8)
    def _real_addr(a: str) -> bool:
        if not (a.startswith("0x") and len(a) >= 10):
            return False
        try:
            return int(a[2:10], 16) != 0  # excludes the zero address
        except ValueError:
            return False

    by_funder: dict[str, set[str]] = defaultdict(set)
    for wallet, info in funding.items():
        funder = (info.get("funder") or "").lower()
        if _real_addr(funder):
            by_funder[funder].add(wallet)
    for funder, members in by_funder.items():
        if len(members) < MIN_CLUSTER_SIZE:
            continue
        cid = "cluster_" + funder[2:6]
        evd = {"cluster_id": cid, "funder": funder, "member_count": len(members),
               "members": sorted(members)[:20],
               "source": "results/funding_forensics.json"}
        for m in members:
            hits[m].append((f"CLUSTER_MEMBER:{cid}", CONF["CLUSTER_MEMBER_FUNDING"], evd))

    # 2) analyst capture (funder_clusters.json, e.g. cluster_f70d / 26 wallets)
    if isinstance(clusters_file, dict):
        cid = clusters_file.get("cluster_id")
        funder = ((clusters_file.get("funder") or {}).get("address") or "").lower()
        members_raw = clusters_file.get("top38_members_funded_by_cluster") or []
        if cid and isinstance(cid, str):
            full = {m.lower() for m in members_raw if isinstance(m, str)}
            prefixes = []
            for m in members_raw:
                if not isinstance(m, str):
                    continue
                ml = m.lower()
                p = _trunc_prefix(ml)
                if p != ml:
                    prefixes.append(p)  # display-truncated member ('0xabc…')
            for w in wallets:
                matched = w in full or any(w.startswith(p) for p in prefixes)
                by_funder_hit = (funder and
                                 (funding.get(w) or {}).get("funder", "").lower() == funder)
                if not matched and not by_funder_hit:
                    continue
                evd = {"cluster_id": cid, "funder": funder,
                       "funded_wallets": clusters_file.get("funded_wallets"),
                       "source": "results/funder_clusters.json"}
                if not matched and by_funder_hit:
                    evd["match"] = "funder_of_record"
                elif matched and w not in full:
                    evd["match"] = "prefix (truncated capture)"
                hits[w].append((f"CLUSTER_MEMBER:{cid}",
                                CONF["CLUSTER_MEMBER_CAPTURE"], evd))

    # 3) token-overlap sybil clusters from anti_gaming (WalletScore.cluster_id)
    for w in wallets:
        cid = score_cluster.get(w)
        if cid:
            hits[w].append((f"CLUSTER_MEMBER:{cid}", CONF["CLUSTER_MEMBER_TOKENSET"],
                            {"cluster_id": cid,
                             "source": "wallet_scores.cluster_id (anti_gaming token-overlap)"}))
    return hits


def _ct_map(data) -> dict[str, dict]:
    """address → CT identity from the GMGN smart-money leaderboard capture."""
    out: dict[str, dict] = {}
    try:
        rank = data["sources"]["gmgn_smartmoney_30d"]["data"]["rank"]
    except (KeyError, TypeError):
        return out
    for entry in rank:
        if not isinstance(entry, dict):
            continue
        addr = (entry.get("address") or "").lower()
        handle = entry.get("twitter_username") or ""
        if addr.startswith("0x") and handle:
            out[addr] = {"source": "gmgn_smartmoney_30d capture",
                         "twitter_username": handle,
                         "name": entry.get("name") or ""}
    return out


async def classify_all_wallets(
    session: AsyncSession,
    ranked=None,
    results_dir: Path | str | None = None,
) -> dict:
    """Classify every wallet with SwapEvents; persist labels + export JSON.

    `ranked` (optional) is the pipeline's RankedWallet list — wallets with a
    hard-verifier "verified" verdict get SMART_TRACKER. Returns counts.
    """
    results_dir = Path(results_dir) if results_dir else settings.results_dir
    now = datetime.now(timezone.utc)

    # --- load everything in a handful of queries ---
    events = (await session.execute(
        select(SwapEvent).order_by(SwapEvent.block_num, SwapEvent.id)
    )).scalars().all()
    by_wallet: dict[str, list] = defaultdict(list)
    for e in events:
        by_wallet[e.wallet_address].append(e)

    token_pool = dict((await session.execute(
        select(Pool.token_address, Pool.address))).all())
    pool_first = {pool: block for pool, block in (await session.execute(
        select(PricePoint.pool_address, func.min(PricePoint.block_num))
        .group_by(PricePoint.pool_address))).all()}
    token_first = {tok: pool_first[pool] for tok, pool in token_pool.items()
                   if pool in pool_first}

    forensics = _load_json(results_dir / "funding_forensics.json", {})
    funding: dict[str, dict] = {}
    for row in (forensics or {}).get("wallets", []):
        if isinstance(row, dict) and row.get("wallet"):
            funding[row["wallet"].lower()] = {
                "funder": ((row.get("funding") or {}).get("funder") or ""),
                "dev_fingerprint": row.get("dev_fingerprint") or {},
            }
    clusters_file = _load_json(results_dir / "funder_clusters.json", None)
    ct_map = _ct_map(_load_json(results_dir / "external_leaderboards.json", {}))
    score_cluster = dict((await session.execute(
        select(WalletScore.wallet_address, WalletScore.cluster_id)
        .where(WalletScore.cluster_id.isnot(None)))).all())

    verified: dict[str, dict] = {}
    for entry in ranked or []:
        v = getattr(entry, "verification", None) or {}
        if v.get("verdict") == "verified":
            addr = (getattr(entry, "wallet_address", "") or "").lower()
            verified[addr] = {"composite_score": getattr(entry, "composite_score", None),
                              "rank": getattr(entry, "rank", None),
                              "verdict": "verified"}

    # --- run detectors ---
    sig_bundle = _bundle_signal(by_wallet, token_first)
    sig_sniper = _sniper_signal(by_wallet, token_first)
    sig_insider = _insider_signal(by_wallet)
    sig_airdrop = _airdrop_signal(by_wallet)
    sig_serial, sig_dev = _dev_signals(by_wallet, token_first, funding)
    sig_mev = _mev_signal(by_wallet)
    sig_cluster = _cluster_signal(set(by_wallet), funding, clusters_file, score_cluster)

    # --- assemble labels per wallet ---
    classified: dict[str, dict] = {}
    for wallet in sorted(by_wallet):
        labels: dict[str, tuple[float, dict]] = {}

        def add(label: str, evidence: dict) -> None:
            labels.setdefault(label, (CONF[label], evidence))

        if wallet in sig_serial:
            add("DEV_SERIAL_RUGGER", sig_serial[wallet])
        elif wallet in sig_dev:
            add("DEV", sig_dev[wallet])
        if wallet in sig_bundle:
            add("BUNDLER_SUSPECT", sig_bundle[wallet])
        if wallet in sig_sniper:
            add("SNIPER", sig_sniper[wallet])
        if wallet in sig_insider:
            add("INSIDER", sig_insider[wallet])
        if wallet in sig_cluster:
            for lbl, conf, evd in sig_cluster[wallet]:
                labels.setdefault(lbl, (conf, evd))
        if wallet in sig_airdrop:
            add("AIRDROP_FARMER", sig_airdrop[wallet])
        if wallet in verified:
            add("SMART_TRACKER", verified[wallet])
        if wallet in ct_map:
            add("CT_ATTRIBUTED", ct_map[wallet])
        if wallet in sig_mev:
            add("MEV_BOT", sig_mev[wallet])
        if not labels:
            add("GENERALIST", {"note": "no taxonomy signal matched; default type"})

        classified[wallet] = {
            "primary_type": primary_type(labels.keys()),
            "labels": sorted(labels),
            "evidence": {lbl: evd for lbl, (_c, evd) in sorted(labels.items())},
            "confidence": {lbl: conf for lbl, (conf, _e) in sorted(labels.items())},
        }

    # --- persist (full refresh keeps re-runs idempotent) ---
    await session.execute(delete(WalletLabel))
    for wallet, res in classified.items():
        for lbl in res["labels"]:
            session.add(WalletLabel(
                wallet_address=wallet,
                label=lbl,
                confidence=round(res["confidence"][lbl], 4),
                evidence=json.dumps(res["evidence"][lbl], default=str),
                assigned_at=now,
            ))
    await session.commit()

    # --- export ---
    summary: dict[str, int] = defaultdict(int)
    for res in classified.values():
        summary[res["primary_type"]] += 1
    n_labels = sum(len(res["labels"]) for res in classified.values())
    out = {
        "generated_at": now.isoformat(),
        "taxonomy": "docs/WALLET_TAXONOMY.md (14 types; primary = priority 1→14)",
        "summary": {"wallets_classified": len(classified),
                    "labels_assigned": n_labels,
                    "primary_types": dict(sorted(summary.items()))},
        "wallets": classified,
    }
    (results_dir / "wallet_labels.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")

    counts = dict(out["summary"])
    log.info("wallet classification done: %d wallets, %d labels, %s",
             len(classified), n_labels, counts["primary_types"])
    return counts
