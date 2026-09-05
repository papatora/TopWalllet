"""Track-by-CA: rank the smartest wallets that traded a specific token.

CLI:      python -m src.track_by_ca --ca <CONTRACT_ADDRESS>
API:      GET /api/v1/track-by-ca?ca=<CONTRACT_ADDRESS>

Flow: DexScreener resolves the token's main pool → Blockscout pulls the
token's transfer history (all wallets that ever touched it) → every wallet's
full history is enriched and scored by the same engine as the global
pipeline → output is the global track record of wallets that entered THIS
token, ranked by composite score.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from config.settings import settings
from src.db.database import get_session_factory, init_db
from src.db.models import Pool, Token, Wallet
from src.discover.dex_scraper import DexScreenerClient, TokenData, _pool_from_pair, _to_float
from src.enrich.price_fetcher import PriceService
from src.utils.logger import jlog, setup_logging
from src.utils.rpc_client import EvmRpcClient

log = logging.getLogger(__name__)


async def _resolve_token(client: DexScreenerClient, ca: str) -> TokenData | None:
    pairs = await client.token_pairs(settings.chain, [ca])
    if not pairs:
        return None
    best = max(pairs, key=lambda p: ((p.get("liquidity") or {}).get("usd") or 0))
    base = best.get("baseToken") or {}
    pool = _pool_from_pair(best)
    if pool is None:
        return None
    return TokenData(
        address=ca.lower(), symbol=base.get("symbol", ""), name=base.get("name", ""),
        price_usd=_to_float(best.get("priceUsd")),
        liquidity_usd=_to_float((best.get("liquidity") or {}).get("usd")),
        volume_24h_usd=_to_float((best.get("volume") or {}).get("h24")),
        pool=pool,
    )


async def run_track_by_ca(ca: str, top_n: int = 50) -> dict | None:
    setup_logging()
    await init_db()
    ca = ca.lower()
    rpc = EvmRpcClient()
    from src.discover.holder_scraper import BlockscoutClient, WalletHit, extract_wallet_hits

    blockscout = BlockscoutClient()
    session_factory = get_session_factory()
    started = datetime.now(timezone.utc)

    async with session_factory() as session:
        token_row = await session.get(Token, ca)
        pool_rows = (await session.execute(select(Pool).where(Pool.token_address == ca))).scalars().all()

        client = DexScreenerClient()
        token_data = await _resolve_token(client, ca)
        await client.close()
        if token_data is None and (token_row is None or not pool_rows):
            return None

        from src.pipeline import Pipeline as _P

        helper = _P()
        if token_data is not None:
            await helper._upsert_token(session, token_data, await helper._token_decimals(ca))
            await helper._upsert_pool(session, token_data)
            await session.commit()
            token_row = await session.get(Token, ca)
            pool_rows = (await session.execute(select(Pool).where(Pool.token_address == ca))).scalars().all()

        # discover every wallet that touched this token
        exclude = {settings.pool_manager, settings.weth_address, settings.usdg_address}
        exclude |= {p.address for p in pool_rows}
        transfers = await blockscout.token_transfers(ca, max(8, settings.trader_pages_per_token * 3))
        hits = extract_wallet_hits(ca, [], transfers, exclude)
        holder_items = await blockscout.token_holders(ca, settings.holders_per_token)
        hits += extract_wallet_hits(ca, holder_items, [], exclude)

        helper = _P()
        for hit in hits:
            await helper._upsert_wallet_interest(session, hit)
        await session.commit()
        jlog(log, logging.INFO, "track-ca wallets discovered", ca=ca, wallets=len(hits))

        # targeted price series (covers the CA pool + every other token the
        # discovered wallets traded — the same engine as the global pipeline)
        from src.utils.rpc_client import v4_swap_topic0

        head = await rpc.block_number()
        await rpc.probe_log_endpoints(
            settings.pool_manager, v4_swap_topic0(),
            head - settings.safe_log_lag_blocks,
        )
        await helper.stage_prices(session)
        await session.commit()

        # enrich all candidate wallets (pending ones only — resume-safe)
        addresses = {h.address for h in hits}
        wallets = (await session.execute(
            select(Wallet).where(Wallet.address.in_(addresses), Wallet.status.in_(["pending", "in_progress"]))
        )).scalars().all()
        await helper.stage_enrich_for(session, wallets)
        await session.commit()

        # analyze restricted to this wallet set
        ranked = await helper.analyze_wallets(session, restrict_to=addresses, started=started)
        ranked = ranked[:top_n]

        symbols = {ca: (token_row.symbol if token_row else ca[:8])}
        from src.rank.export import eip55

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "token": {
                "ca": eip55(ca),
                "symbol": token_row.symbol if token_row else "",
                "name": token_row.name if token_row else "",
            },
            "total_wallets_analyzed": len(addresses),
            "ranked_wallets": [
                {
                    "rank": e.rank,
                    "wallet_address": eip55(e.wallet_address),
                    "composite_score": e.composite_score,
                    "win_rate": e.metrics.win_rate,
                    "median_return_multiple": e.metrics.median_return_multiple,
                    "max_return_multiple": e.metrics.max_return_multiple,
                    "distinct_tokens": e.metrics.distinct_tokens,
                    "trading_style": e.trading_style,
                    "risk_flags": e.risk_flags,
                    "entry_timing_pctiles": [
                        round(p.entry_pctile, 3) for p in e.positions
                        if p.token == ca and p.entry_pctile is not None
                    ],
                }
                for e in ranked
            ],
        }
        out_dir = settings.results_dir / "by_ca"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{ca}.json").write_text(json.dumps(payload, indent=2))

        await blockscout.close()
        await rpc.close()
        return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Track smart wallets by token CA")
    parser.add_argument("--ca", required=True, help="token contract address (0x...)")
    parser.add_argument("--top", type=int, default=50)
    args = parser.parse_args()
    setup_logging()
    result = asyncio.run(run_track_by_ca(args.ca, args.top))
    if result is None:
        print(f"No pair/transfers found for CA {args.ca} on {settings.chain}")
        sys.exit(1)
    print(json.dumps(result, indent=2))
