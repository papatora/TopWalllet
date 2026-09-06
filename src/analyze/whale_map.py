"""Whale Entry Map — the "conviction" rule, formalized.

User's friend's rule (translated): before entering a token, look at WHERE the
whales entered. If whales' average entry area is near or ABOVE your entry —
especially with jumbo size — they are underwater and holding: strong
long-term conviction, you are early-ish alongside them. If every whale is
far below your entry, they are up huge and you are likely their exit
liquidity.

V1 data model: "whales" = the largest BUY entrants among enriched wallets
(top-20 by cost basis). True holder balances over time arrive with snapshot
ingestion (Phase 2), at which point this module gains a `holders=` source
without changing its interface.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Entrant:
    wallet: str
    vwap_entry_price: float   # volume-weighted avg buy price (USD)
    cost_basis_usd: float     # total bought (USD)


@dataclass
class WhaleEntryMap:
    token: str
    current_price_usd: float
    whale_count: int
    whale_avg_entry_price: float        # size-weighted
    pct_whales_at_or_above_current: float  # 0..1
    jumbo_above_current: int            # whales ≥2x median size AND entry ≥ current
    conviction_score: float             # 0..100
    verdict: str                        # STRONG / MIXED / DANGER / INSUFFICIENT_DATA
    whales: list[dict] = field(default_factory=list)


def compute_whale_entry_map(
    token: str,
    entrants: list[Entrant],
    current_price_usd: float | None,
    top_n: int = 20,
    jumbo_multiplier: float = 2.0,
) -> WhaleEntryMap | None:
    if not entrants or not current_price_usd or current_price_usd <= 0:
        return None

    # whales = biggest cost basis
    ranked = sorted(entrants, key=lambda e: e.cost_basis_usd, reverse=True)[:top_n]
    if not ranked:
        return None

    total_cost = sum(e.cost_basis_usd for e in ranked)
    avg_entry = sum(e.vwap_entry_price * e.cost_basis_usd for e in ranked) / total_cost
    sizes = sorted(e.cost_basis_usd for e in ranked)
    median_size = sizes[len(sizes) // 2]
    jumbo_floor = median_size * jumbo_multiplier

    above = [e for e in ranked if e.vwap_entry_price >= current_price_usd]
    pct_above = len(above) / len(ranked)
    jumbo_above = sum(
        1 for e in above if e.cost_basis_usd >= jumbo_floor
    )

    # conviction: whales underwater (entry ≥ current) is the core signal,
    # a SINGLE jumbo underwater whale already maxes the jumbo component —
    # per the rule, one jumbo above your entry "means something"
    conviction = 100.0 * (
        0.7 * pct_above + 0.3 * min(jumbo_above / 1, 1.0)
    )

    if len(ranked) < 5:
        verdict = "INSUFFICIENT_DATA"
    elif conviction >= 60:
        verdict = "STRONG"
    elif conviction >= 30:
        verdict = "MIXED"
    else:
        verdict = "DANGER"

    return WhaleEntryMap(
        token=token,
        current_price_usd=current_price_usd,
        whale_count=len(ranked),
        whale_avg_entry_price=avg_entry,
        pct_whales_at_or_above_current=round(pct_above, 4),
        jumbo_above_current=jumbo_above,
        conviction_score=round(conviction, 2),
        verdict=verdict,
        whales=[
            {
                "wallet": e.wallet,
                "entry_vwap_usd": round(e.vwap_entry_price, 10),
                "entry_vs_current": round(e.vwap_entry_price / current_price_usd, 4),
                "cost_basis_usd": round(e.cost_basis_usd, 2),
                "underwater": e.vwap_entry_price >= current_price_usd,
            }
            for e in ranked
        ],
    )
