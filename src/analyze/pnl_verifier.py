"""Hard PnL verification ("aturan keras") — every Top-N wallet must survive
independent re-derivation before it ships in the ranked list.

Rules (strict mode, config-driven):
  R1 ETH oracle cross-check — the ETH price used for USD valuations must match
     an independent source (DexScreener's most liquid WETH/USDG pool, i.e.
     on-chain derived, no CoinGecko trust) within ETH_ORACLE_TOLERANCE (2%).
     On failure every ETH-quoted PnL is UNVERIFIED and such wallets are
     dropped from Top-N.
  R2 Trade re-derivation — for each top wallet, its top-3 closed trades are
     re-pulled RAW from Blockscout (fresh request, not our DB) and the return
     multiple recomputed from the price series. At least 2 of 3 must match the
     stored multiple within TRADE_MATCH_TOLERANCE (25%). Otherwise the wallet
     is flagged PNL_UNVERIFIED and dropped from Top-N.
  R3 Stale-open rule — unrealized (open-position) multiples may only count
     when the price series point used is < STALE_OPEN_HOURS (24h) old.

This exists because a FIFO reconstruction can silently produce inflated PnL
from mispriced legs (wrong token ordering, stale series, router hops). The
verifier trusts nothing it didn't re-derive.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from config.settings import settings
from src.utils.logger import jlog

log = logging.getLogger(__name__)

WETH_ORACLE_URL = "https://api.dexscreener.com/tokens/v1/{chain}/"


@dataclass
class VerificationResult:
    wallet: str
    eth_oracle_ok: bool = True
    trades_checked: int = 0
    trades_verified: int = 0
    verdict: str = "unverified"          # verified | unverified
    details: list[str] = field(default_factory=list)


async def eth_oracle_usd(chain: str | None = None) -> float | None:
    """Independent ETH price: most liquid WETH pool on DexScreener (on-chain)."""
    url = WETH_ORACLE_URL.format(chain=chain or settings.chain)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url + settings.weth_address)
            resp.raise_for_status()
            pairs = resp.json()
            best = max(
                pairs,
                key=lambda p: ((p.get("liquidity") or {}).get("usd") or 0),
            )
            return float(best["priceUsd"])
    except Exception as e:
        jlog(log, logging.WARNING, "eth oracle fetch failed", error=str(e)[:140])
        return None


async def verify_top_wallets(
    ranked,
    price_lookup,            # PriceService (async price_at + series freshness)
    rederive_trade,          # async fn(wallet, tx_hash, token) -> float | None (recomputed multiple)
) -> dict[str, VerificationResult]:
    """Apply R1–R3 to the ranked list (in place: sets entry.verification fields).

    `rederive_trade` is injected by the pipeline (it owns the Blockscout client
    and decimals) so this module stays data-source agnostic.
    """
    results: dict[str, VerificationResult] = {}

    # R1: ETH oracle cross-check
    oracle = await eth_oracle_usd()
    pipeline_eth = None
    try:
        pipeline_eth = await price_lookup.eth_price_at(10 ** 12)  # latest known
    except Exception:
        pipeline_eth = None
    eth_ok = bool(oracle and pipeline_eth and abs(pipeline_eth - oracle) / oracle <= 0.02)
    if not eth_ok:
        jlog(log, logging.WARNING, "R1 ETH oracle mismatch",
             oracle=oracle, pipeline=pipeline_eth)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(
        hours=float(settings.stale_open_hours)
    )

    def _aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    for entry in ranked[: settings.verify_top_n]:
        res = VerificationResult(wallet=entry.wallet_address, eth_oracle_ok=eth_ok)

        # R3: stale open positions must not claim unrealized profits
        open_stale = False
        for p in entry.positions:
            if p.status == "open" and p.return_multiple and p.return_multiple > 1:
                pt = price_lookup.last_point_ts(p.token)
                if pt is None or _aware(pt) < stale_cutoff:
                    open_stale = True
        if open_stale:
            res.details.append("R3 stale open-position price")

        # R2: re-derive the top-3 closed trades from raw source data
        closed = sorted(
            [p for p in entry.positions if p.status == "closed" and p.return_multiple],
            key=lambda p: p.return_multiple or 0, reverse=True,
        )[:3]
        for p in closed:
            res.trades_checked += 1
            try:
                recomputed = await rederive_trade(entry.wallet_address, p)
            except Exception as e:
                res.details.append(f"R2 rederive error {str(e)[:80]}")
                continue
            if recomputed is None:
                res.details.append("R2 rederive returned no data")
                continue
            stored = p.return_multiple or 0
            if stored > 0 and abs(recomputed - stored) / stored <= 0.25:
                res.trades_verified += 1
            else:
                res.details.append(
                    f"R2 mismatch stored={stored:.2f}x recomputed={recomputed:.2f}x"
                )

        if eth_ok and res.trades_checked > 0 and res.trades_verified >= 2 and not open_stale:
            res.verdict = "verified"
        entry.verification = {
            "verdict": res.verdict,
            "eth_oracle_ok": eth_ok,
            "trades_verified": f"{res.trades_verified}/{res.trades_checked}",
            "details": res.details[:5],
        }
        results[entry.wallet_address] = res

    dropped = sum(1 for r in results.values() if r.verdict != "verified")
    jlog(log, logging.INFO, "PnL verification done",
         checked=len(results), verified=len(results) - dropped, dropped=dropped)
    return results
