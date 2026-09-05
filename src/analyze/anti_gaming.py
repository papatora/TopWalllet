"""Stage 3c — Anti-gaming filters.

Excludes and flags wallets that are likely gaming the metrics:
  * LOW_DATA            — fewer than N positions / distinct tokens (hard exclude)
  * AIRDROP_FARMER      — only ever received tokens, never bought (hard exclude)
  * MEV_BOT             — many round-trips with machine-gun hold times
  * WASH_SUSPECT        — repeated buy+sell round trips inside a few blocks
  * INSIDER_SUSPECT     — bought within minutes of the token's first observed
                          trade, then dumped most of the position quickly
  * UNREALISTIC_RETURNS — median multiple so extreme it smells fake on small samples
  * DUST_ONLY           — median position too small to be meaningful

Plus wallet clustering (token-set similarity via Jaccard + union-find) to tag
probable sybil fleets operated by one entity. Clusters are tagged, not
excluded — a shared nonce-funding graph is Phase 2's job; token-overlap is a
cheap first approximation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.analyze.position_calculator import CalcPosition, PricedEvent
from src.analyze.wallet_scorer import WalletMetrics


@dataclass
class FilterResult:
    flags: list[str] = field(default_factory=list)
    excluded: bool = False
    cluster_id: str | None = None


def apply_filters(
    metrics: WalletMetrics | None,
    positions: list[CalcPosition],
    events: list[PricedEvent],
    weights_cfg: dict,
    first_token_trade_block: dict[str, int] | None = None,
) -> FilterResult:
    """`first_token_trade_block` maps token → earliest block seen in the token's
    price series (proxy for pool creation), enabling the insider heuristic."""
    cfg = weights_cfg.get("thresholds", {})
    result = FilterResult()

    if metrics is None:
        result.flags.append("LOW_DATA")
        result.excluded = True
        return result

    buys = [e for e in events if e.side == "BUY"]
    if metrics.total_positions > 0 and not buys:
        result.flags.append("AIRDROP_FARMER")
        result.excluded = True
        return result

    closed = [p for p in positions if p.status == "closed" and p.hold_hours is not None]
    if closed:
        holds = sorted(p.hold_hours for p in closed)
        median_hold = holds[len(holds) // 2]
        if median_hold <= (10 / 60) and len(closed) >= 30:
            result.flags.append("MEV_BOT")
        if median_hold <= 6 and metrics.median_position_size_usd < 20 and len(closed) >= 30:
            result.flags.append("DUST_ONLY")

        # wash heuristic: ≥5 buy→sell round trips on one token within 30 blocks each
        by_token_roundtrips: dict[str, int] = {}
        for p in closed:
            if p.exit_block and p.entry_block and (p.exit_block - p.entry_block) <= 30:
                by_token_roundtrips[p.token] = by_token_roundtrips.get(p.token, 0) + 1
        if by_token_roundtrips and max(by_token_roundtrips.values()) >= 5:
            result.flags.append("WASH_SUSPECT")

    if metrics.median_return_multiple > 1000 and metrics.closed_positions < 10:
        result.flags.append("UNREALISTIC_RETURNS")

    if metrics.median_position_size_usd < 10:
        result.flags.append("DUST_ONLY")

    # transparency: single-token wallets are specialists with a narrow sample,
    # not multi-token consistent traders — always disclosed, never hidden
    if metrics.distinct_tokens == 1:
        result.flags.append("SINGLE_TOKEN_SAMPLE")

    # insider: first buy of a token within 300 blocks of first observed trade,
    # and >80% of that position sold within a day of entry.
    if first_token_trade_block:
        early_buys = {}
        for p in positions:
            first = first_token_trade_block.get(p.token)
            if first and p.entry_block - first <= 300:
                early_buys[p.token] = p
        for token, pos in early_buys.items():
            sold = [
                q for q in positions
                if q.token == token and q.status == "closed" and q.entry_block == pos.entry_block
            ]
            if sold:
                avg_hold = sum(q.hold_hours or 0 for q in sold) / len(sold)
                if avg_hold <= 24 and pos.return_multiple and pos.return_multiple > 20:
                    result.flags.append("INSIDER_SUSPECT")
                    break

    return result


# ---------------- clustering ----------------

def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / len(a | b)


def cluster_wallets(
    wallet_tokens: dict[str, set[str]],
    similarity: float = 0.85,
) -> dict[str, str]:
    """Greedy union-find clustering on token-set similarity.

    Returns wallet → cluster_id ('' when the wallet is in a cluster of one).
    """
    wallets = list(wallet_tokens.keys())
    parent = {w: w for w in wallets}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, w1 in enumerate(wallets):
        for w2 in wallets[i + 1:]:
            if _jaccard(wallet_tokens[w1], wallet_tokens[w2]) >= similarity:
                union(w1, w2)

    groups: dict[str, list[str]] = {}
    for w in wallets:
        groups.setdefault(find(w), []).append(w)

    out: dict[str, str] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        cid = "cluster_" + find(members[0])[2:10]
        for m in members:
            out[m] = cid
    return out
