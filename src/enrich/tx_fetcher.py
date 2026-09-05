"""Stage 2 — Wallet enrichment: full token transfer history → classified swaps.

For each wallet we pull the complete ERC-20 transfer history from Blockscout
(newest first, paginated), then classify each transfer of a tracked token:

  wallet → pool/poolmanager : SELL
  pool/poolmanager → wallet : BUY
  anything else             : wallet-to-wallet transfer (ignored in v1)

USD value is attached by the pipeline using the per-pool price series
(price_fetcher). Tokens that are pure quote infra (USDG/WETH) are skipped —
they are the measuring stick, not positions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from src.discover.holder_scraper import BlockscoutClient
from src.utils.logger import jlog

log = logging.getLogger(__name__)


@dataclass
class TradeEvent:
    wallet: str
    token: str
    side: str            # BUY | SELL
    token_amount: float
    block_num: int
    ts: datetime | None
    tx_hash: str = ""


def _parse_amount(value) -> float | None:
    """Blockscout amounts arrive as decimal strings (rarely hex); be liberal."""
    if value is None:
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        pass
    try:
        if str(value).startswith("0x"):
            return float(int(str(value), 16))
    except ValueError:
        return None
    return None


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class TxFetcher:
    def __init__(self, blockscout: BlockscoutClient | None = None):
        self.blockscout = blockscout or BlockscoutClient()

    async def fetch_wallet_events(
        self,
        wallet: str,
        counterparties: dict[str, set[str]],
        decimals: dict[str, int],
        max_pages: int,
    ) -> list[TradeEvent]:
        """`counterparties` maps tracked token CA → set of pool/poolmanager addresses."""
        items = await self.blockscout.address_token_transfers(wallet.lower(), max_pages)
        events: list[TradeEvent] = []
        wallet = wallet.lower()
        for item in items:
            token = ((item.get("token") or {}).get("address") or "").lower()
            if token not in counterparties:
                continue  # untracked token or quote infra
            src = (item.get("from") or {}).get("hash") or ""
            dst = (item.get("to") or {}).get("hash") or ""
            src, dst = src.lower(), dst.lower()
            cps = counterparties[token]
            if wallet == src.lower() and dst in cps:
                side = "SELL"
            elif wallet == dst and src in cps:
                side = "BUY"
            else:
                continue  # plain transfer between wallets / self
            amount = _parse_amount((item.get("total") or {}).get("value") or item.get("value"))
            if not amount or amount <= 0:
                continue
            dec = decimals.get(token, 18)
            token_amount = amount / (10 ** dec) if dec is not None else amount
            if token_amount <= 0:
                continue
            block_num = int(item.get("block_number") or 0)
            events.append(TradeEvent(
                wallet=wallet,
                token=token,
                side=side,
                token_amount=token_amount,
                block_num=block_num,
                ts=_parse_ts(item.get("block_timestamp") or item.get("timestamp")),
                tx_hash=(item.get("transaction_hash") or "").lower(),
            ))
        events.sort(key=lambda e: e.block_num)
        jlog(log, logging.DEBUG, "wallet events fetched", wallet=wallet[:10], events=len(events))
        return events

    async def close(self):
        await self.blockscout.close()
