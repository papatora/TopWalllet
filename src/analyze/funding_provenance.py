"""Funding provenance + dev fingerprinting for verified Top wallets.

For every wallet in results/top_wallets_latest.json, answer the user's questions:
  1. Where did its capital come from?  → first ETH funding source, classified:
     CEX hot wallet / bridge-contract / another known wallet in our DB /
     unknown EOA / contract.
  2. Is the PnL real skill or insider advantage? → dev fingerprint: how many
     tracked tokens did the wallet buy within EARLY_BLOCKS of the pool's first
     observed swap (≈ pool creation), and did it flip them fast.

Output: results/funding_forensics.json (merged keys documented below).

Run ON THE VPS:  python -m src.analyze.funding_provenance --top 40
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from config.settings import settings
from src.db.database import get_session_factory, init_db
from src.db.models import Pool, PricePoint, SwapEvent, Wallet
from src.discover.holder_scraper import BlockscoutClient
from src.utils.logger import setup_logging

log = logging.getLogger(__name__)

EARLY_BLOCKS = 300          # buy within N blocks of pool's first observed swap = "early"
FAST_FLIP_HOURS = 24        # and fully closed within 24h
DEV_SUSPECT_MIN_TOKENS = 3  # early+fast on >= N distinct tokens → DEV_SUSPECT

CEX_KEYWORDS = ("binance", "bybit", "okx", "gate", "mexc", "bitget", "kucoin",
                "coinbase", "kraken", "htx", "huobi", "upbit", "bitfinex",
                "crypto.com", "stargate", "bridge", "router", "across", "socket")


def _short(addr: str | None) -> str:
    return (addr or "").lower()


async def first_funding(bc: BlockscoutClient, wallet: str, max_pages: int = 4) -> dict:
    """Oldest incoming native-ETH transfer that is NOT the wallet itself.
    Blockscout lists newest-first; RH chain is young so a few pages usually
    cover a wallet's whole life."""
    url: str | None = f"/api/v2/addresses/{wallet}/transactions?filter=to"
    oldest_incoming = None
    for _ in range(max_pages):
        if not url:
            break
        data = await bc.get_json(url)
        if not isinstance(data, dict):
            break
        items = data.get("items", [])
        for tx in items:
            to_a = _short(tx.get("to", {}))
            from_a = _short(tx.get("from", {}))
            if to_a == wallet.lower() and from_a != wallet.lower() and tx.get("value"):
                oldest_incoming = tx  # list is newest-first: keep the last seen
        url = data.get("next_page_url")
        if url:
            url = url.replace(bc.base, "")
    if oldest_incoming is None:
        return {}
    frm = oldest_incoming.get("from") or {}
    return {
        "funder": frm.get("hash", "").lower(),
        "funder_label": frm.get("name") or "",
        "funder_is_contract": bool(frm.get("is_contract")),
        "amount_eth": float(oldest_incoming.get("value", 0)) / 1e18,
        "block": oldest_incoming.get("block_number"),
        "ts": oldest_incoming.get("timestamp"),
    }


def classify_funding(f: dict) -> str:
    if not f:
        return "UNKNOWN"
    label = (f.get("funder_label") or "").lower()
    if any(k in label for k in CEX_KEYWORDS):
        return "CEX_FUNDED"
    if f.get("funder_is_contract"):
        return "CONTRACT_FUNDED"  # bridge/router/multisig
    return "WALLET_FUNDED"


async def dev_fingerprint(session, wallet: str) -> dict:
    """Early-entry + fast-flip statistics across the wallet's tracked tokens."""
    evs = (await session.execute(
        select(SwapEvent).where(SwapEvent.wallet_address == wallet)
        .order_by(SwapEvent.block_num)
    )).scalars().all()
    if not evs:
        return {"early_entries": 0, "fast_flips": 0, "dev_suspect": False}
    pools = (await session.execute(select(Pool))).scalars().all()
    token_pool = {p.token_address: p.address for p in pools}
    first_block = dict((await session.execute(
        select(PricePoint.pool_address, func.min(PricePoint.block_num))
        .group_by(PricePoint.pool_address))).all())

    by_token: dict[str, list] = {}
    for ev in evs:
        by_token.setdefault(ev.token_address, []).append(ev)

    early = 0
    fast_flip = 0
    for token, evs_t in by_token.items():
        pool = token_pool.get(token)
        if pool is None:
            continue
        fb = first_block.get(pool)
        first_buy = next((e for e in evs_t if e.side == "BUY"), None)
        if first_buy is None or fb is None:
            continue
        is_early = (first_buy.block_num - fb) <= EARLY_BLOCKS
        sells = [e for e in evs_t if e.side == "SELL"]
        bought = sum(e.token_amount for e in evs_t if e.side == "BUY")
        sold = sum(e.token_amount for e in sells)
        fully_flipped = bought > 0 and sold / bought >= 0.95
        hold_h = None
        if first_buy.ts and sells:
            hold_h = (max(s.ts for s in sells) - first_buy.ts).total_seconds() / 3600
        if is_early:
            early += 1
            if fully_flipped and (hold_h or 0) <= FAST_FLIP_HOURS:
                fast_flip += 1
    return {
        "early_entries": early,
        "fast_flips": fast_flip,
        "dev_suspect": early >= DEV_SUSPECT_MIN_TOKENS and fast_flip >= DEV_SUSPECT_MIN_TOKENS,
    }


async def main(top_n: int) -> int:
    setup_logging()
    await init_db()
    bc = BlockscoutClient()
    session_factory = get_session_factory()

    data = json.loads((settings.results_dir / "top_wallets_latest.json").read_text())
    wallets = data.get("wallets", [])[:top_n]
    out = []
    async with session_factory() as session:
        for i, w in enumerate(wallets, 1):
            addr = w["wallet_address"].lower()
            funding = await first_funding(bc, addr)
            fp = await dev_fingerprint(session, addr)
            in_db = await session.get(Wallet, addr) is not None
            entry = {
                "wallet": w["wallet_address"],
                "rank": w["rank"],
                "composite_score": w["composite_score"],
                "realized_pnl_usd": w["metrics"]["total_realized_pnl_usd"],
                "funding": funding,
                "funding_class": classify_funding(funding),
                "dev_fingerprint": fp,
                "classification": (
                    "DEV_SUSPECT" if fp["dev_suspect"]
                    else classify_funding(funding).replace("_FUNDED", "_BACKED")
                ),
            }
            # is the funder itself one of the wallets we track?
            if funding.get("funder"):
                row = await session.get(Wallet, funding["funder"])
                entry["funder_in_our_db"] = row is not None
            out.append(entry)
            if i % 10 == 1:
                log.info("forensics progress %d/%d", i, len(wallets))

    (settings.results_dir / "funding_forensics.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "wallets": out}, indent=2))
    summary: dict[str, int] = {}
    for e in out:
        summary[e["classification"]] = summary.get(e["classification"], 0) + 1
    (settings.results_dir / "funding_forensics.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "summary": summary, "wallets": out}, indent=2))
    log.info("funding forensics done: %s", summary)
    await bc.close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args()
    asyncio.run(main(args.top))
