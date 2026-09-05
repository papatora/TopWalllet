"""Stage 4 — Ranking: composite score ordering + trading-style assignment."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.analyze.position_calculator import CalcPosition
from src.analyze.wallet_scorer import WalletMetrics, trading_style
from src.utils.logger import jlog

log = logging.getLogger(__name__)


@dataclass
class RankedWallet:
    rank: int
    wallet_address: str
    composite_score: float
    metrics: WalletMetrics
    positions: list[CalcPosition]
    trading_style: str
    risk_flags: list[str]
    cluster_id: str | None
    verification: dict | None = None  # set by the hard PnL verifier


def rank_wallets(
    scored: list[tuple[str, WalletMetrics, list[CalcPosition], float, list[str], str | None]],
    weights_cfg: dict,
) -> list[RankedWallet]:
    """`scored` items: (wallet, metrics, positions, composite, risk_flags, cluster_id).

    Wallets carrying hard-exclusion flags (LOW_DATA / AIRDROP_FARMER etc.)
    must already be filtered out by the caller.
    """
    ordered = sorted(scored, key=lambda t: t[3], reverse=True)
    ranked: list[RankedWallet] = []
    for i, (wallet, metrics, positions, score, flags, cluster_id) in enumerate(ordered, start=1):
        ranked.append(RankedWallet(
            rank=i,
            wallet_address=wallet,
            composite_score=score,
            metrics=metrics,
            positions=positions,
            trading_style=trading_style(metrics, weights_cfg),
            risk_flags=flags,
            cluster_id=cluster_id,
        ))
    jlog(log, logging.INFO, "ranking done", wallets=len(ranked),
         top_score=ranked[0].composite_score if ranked else None)
    return ranked
