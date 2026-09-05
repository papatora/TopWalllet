"""Stage 1b — Wallet discovery via the Blockscout explorer API (free).

Two complementary sources per token:
  * token holders  — /tokens/{ca}/holders (top holders at current snapshot)
  * token traders  — /tokens/{ca}/transfers (recent transfer parties)

Contract addresses are excluded from wallet discovery: on a Uniswap-v4 chain
the counterparty in transfers is the PoolManager singleton and aggregation
routers — wallets we extract must be EOAs, not infrastructure.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from config.settings import settings
from src.utils.logger import jlog

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (compatible; TopWallet/0.1)"}


@dataclass
class WalletHit:
    address: str
    token_address: str
    source: str  # holder | trader
    is_contract: bool = False


class BlockscoutClient:
    def __init__(self, base_url: str | None = None, rps: float | None = None):
        self.base = (base_url or settings.blockscout_url).rstrip("/")
        self._limiter_rate = rps or settings.blockscout_rps
        from aiolimiter import AsyncLimiter

        self._limiter = AsyncLimiter(max(self._limiter_rate, 0.1), 1.0)
        self._client: httpx.AsyncClient | None = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            proxy = settings.proxy_urls[0] if settings.proxy_urls else None
            self._client = httpx.AsyncClient(timeout=30.0, headers=UA, proxy=proxy)
        return self._client

    async def get_json(self, path: str, params: dict | None = None, retries: int = 5) -> dict | list | None:
        client = await self._http()
        for attempt in range(retries):
            try:
                await self._limiter.acquire()
                resp = await client.get(f"{self.base}{path}", params=params)
                if resp.status_code == 429:
                    await asyncio.sleep(1.5 * (2 ** attempt))
                    continue
                if resp.status_code >= 500:
                    await asyncio.sleep(1.0 * (2 ** attempt))
                    continue
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as e:
                if attempt == retries - 1:
                    jlog(log, logging.WARNING, "blockscout request failed", path=path, error=str(e)[:150])
                    return None
                await asyncio.sleep(1.5 * (2 ** attempt))
        return None

    async def token_holders(self, ca: str, max_items: int) -> list[dict]:
        items: list[dict] = []
        url: str | None = f"/api/v2/tokens/{ca}/holders"
        while url and len(items) < max_items:
            data = await self.get_json(url)
            if not isinstance(data, dict):
                break
            items.extend(data.get("items", []))
            url = data.get("next_page_url")
            if url:
                url = url.replace(self.base, "")
        return items[:max_items]

    async def token_transfers(self, ca: str, max_pages: int) -> list[dict]:
        items: list[dict] = []
        url: str | None = f"/api/v2/tokens/{ca}/transfers"
        for _ in range(max_pages):
            if not url:
                break
            data = await self.get_json(url)
            if not isinstance(data, dict):
                break
            items.extend(data.get("items", []))
            url = data.get("next_page_url")
            if url:
                url = url.replace(self.base, "")
        return items

    async def address_token_transfers(self, wallet: str, max_pages: int,
                                      token_filter: str | None = None) -> list[dict]:
        """ERC-20 transfer history for a wallet (newest first, paginated).

        With `token_filter`, Blockscout returns ONLY transfers of that one
        token — the full history of the wallet's relationship with it, which
        is exactly what per-token position building needs."""
        items: list[dict] = []
        url: str | None = f"/api/v2/addresses/{wallet}/token-transfers"
        for _ in range(max_pages):
            if not url:
                break
            params = {"type": "ERC-20"}
            if token_filter:
                params["token"] = token_filter
            data = await self.get_json(url, params=params)
            if not isinstance(data, dict):
                break
            items.extend(data.get("items", []))
            url = data.get("next_page_url")
            if url:
                url = url.replace(self.base, "")
        return items

    async def stats(self) -> dict:
        data = await self.get_json("/api/v2/stats")
        return data if isinstance(data, dict) else {}

    async def close(self):
        if self._client:
            await self._client.aclose()


def _addr(x: dict | None) -> str:
    return ((x or {}).get("hash") or "").lower()


def _is_contract(x: dict | None) -> bool:
    return bool((x or {}).get("is_contract"))


def extract_wallet_hits(token_ca: str, holders: list[dict], transfers: list[dict],
                        exclude: set[str]) -> list[WalletHit]:
    hits: list[WalletHit] = []
    seen: set[tuple[str, str]] = set()

    def add(address: str, source: str, is_contract: bool):
        if not address or address in exclude or is_contract:
            return
        key = (address, source)
        if key not in seen:
            seen.add(key)
            hits.append(WalletHit(address=address, token_address=token_ca, source=source,
                                  is_contract=is_contract))

    for item in holders:
        addr = item.get("address") or {}
        add(_addr(addr), "holder", _is_contract(addr))
    for item in transfers:
        add(_addr(item.get("from")), "trader", _is_contract(item.get("from")))
        add(_addr(item.get("to")), "trader", _is_contract(item.get("to")))
    return hits
