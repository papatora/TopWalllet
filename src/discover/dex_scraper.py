"""Stage 1a — Token + pool universe from DexScreener (free, no key).

DexScreener fully indexes Robinhood Chain (chainId "robinhood", Uniswap v4
dominant). We harvest trending/searched tokens, then pull full pair data in
batches of 30 to filter by liquidity/volume and record the main pool per
token (poolId for v4, pool contract for v3) — the pool is what pricing and
trade classification hang off later.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx
from aiolimiter import AsyncLimiter

from config.settings import settings, STABLE_SYMBOLS
from src.utils.logger import jlog

log = logging.getLogger(__name__)
BASE = "https://api.dexscreener.com"
UA = {"User-Agent": "TopWallet/0.1"}


@dataclass
class PoolData:
    address: str
    dex: str
    version: int
    quote_token: str
    quote_symbol: str
    liquidity_usd: float | None
    price_usd: float | None


@dataclass
class TokenData:
    address: str
    symbol: str
    name: str
    price_usd: float | None
    liquidity_usd: float | None
    volume_24h_usd: float | None
    pool: PoolData | None = None


class DexScreenerClient:
    def __init__(self):
        self._search_limiter = AsyncLimiter(settings.dexscreener_search_rpm, 60)
        self._profiles_limiter = AsyncLimiter(settings.dexscreener_profiles_rpm, 60)
        self._client: httpx.AsyncClient | None = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            proxy = settings.proxy_urls[0] if settings.proxy_urls else None
            self._client = httpx.AsyncClient(timeout=20.0, headers=UA, proxy=proxy)
        return self._client

    async def _get(self, path: str, limiter: AsyncLimiter) -> AnyJson:
        client = await self._http()
        for attempt in range(4):
            await limiter.acquire()
            resp = await client.get(f"{BASE}{path}")
            if resp.status_code == 429:
                await asyncio.sleep(2 ** attempt * 2)
                continue
            if resp.status_code >= 500:
                await asyncio.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        return None

    async def token_profiles(self) -> list[dict]:
        data = await self._get("/token-profiles/latest/v1", self._profiles_limiter)
        return data or []

    async def token_boosts(self) -> list[dict]:
        data = await self._get("/token-boosts/latest/v1", self._profiles_limiter)
        return data or []

    async def search(self, query: str) -> list[dict]:
        data = await self._get(f"/latest/dex/search?q={query}", self._search_limiter)
        return (data or {}).get("pairs", [])

    async def token_pairs(self, chain: str, addresses: list[str]) -> list[dict]:
        data = await self._get(f"/tokens/v1/{chain}/{{}}".format(",".join(addresses)), self._search_limiter)
        return data or []

    async def close(self):
        if self._client:
            await self._client.aclose()


AnyJson = object  # typed as any JSON payload


def _pool_from_pair(pair: dict) -> PoolData | None:
    labels = pair.get("labels") or []
    version = 4 if "v4" in labels else 3
    quote = pair.get("quoteToken") or {}
    quote_addr = (quote.get("address") or "").lower()
    if not quote_addr:
        return None
    return PoolData(
        address=(pair.get("pairAddress") or "").lower(),
        dex=pair.get("dexId", ""),
        version=version,
        quote_token=quote_addr,
        quote_symbol=quote.get("symbol", ""),
        liquidity_usd=(pair.get("liquidity") or {}).get("usd"),
        price_usd=_to_float(pair.get("priceUsd")),
    )


def _to_float(x) -> float | None:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


class TokenDiscovery:
    """Builds the filtered token universe for the target chain."""

    def __init__(self, client: DexScreenerClient | None = None):
        self.client = client or DexScreenerClient()

    async def _candidate_addresses(self) -> set[str]:
        chain = settings.chain
        candidates: set[str] = set()
        for coro in (self.client.token_profiles(), self.client.token_boosts()):
            for entry in await coro:
                if entry.get("chainId") == chain:
                    addr = (entry.get("tokenAddress") or "").lower()
                    if addr.startswith("0x"):
                        candidates.add(addr)
        for q in settings.discovery_queries:
            try:
                for pair in await self.client.search(q):
                    if pair.get("chainId") != chain:
                        continue
                    base = pair.get("baseToken") or {}
                    addr = (base.get("address") or "").lower()
                    if addr.startswith("0x") and addr not in (settings.usdg_address, settings.weth_address):
                        candidates.add(addr)
            except Exception as e:  # keep discovery going on single-query failure
                jlog(log, logging.WARNING, "search query failed", query=q, error=str(e)[:150])
        return candidates

    async def discover(self) -> list[TokenData]:
        candidates = await self._candidate_addresses()
        jlog(log, logging.INFO, "dex discovery candidates", count=len(candidates))

        results: dict[str, TokenData] = {}
        addr_list = sorted(candidates)
        quote_infra = {settings.usdg_address, settings.weth_address}
        for i in range(0, len(addr_list), 30):
            batch = addr_list[i:i + 30]
            try:
                pairs = await self.client.token_pairs(settings.chain, batch)
            except Exception as e:
                jlog(log, logging.WARNING, "token_pairs batch failed", error=str(e)[:150])
                continue
            for addr in batch:
                token_pairs = [p for p in pairs if ((p.get("baseToken") or {}).get("address") or "").lower() == addr]
                if not token_pairs:
                    continue
                best = max(
                    token_pairs,
                    key=lambda p: ((p.get("liquidity") or {}).get("usd") or 0),
                )
                liq = _to_float((best.get("liquidity") or {}).get("usd")) or 0
                vol = _to_float((best.get("volume") or {}).get("h24")) or 0
                if liq < settings.min_liquidity_usd or vol < settings.min_volume_24h_usd:
                    continue
                base = best.get("baseToken") or {}
                pool = _pool_from_pair(best)
                if pool is None or not pool.address:
                    continue
                results[addr] = TokenData(
                    address=addr,
                    symbol=base.get("symbol", ""),
                    name=base.get("name", ""),
                    price_usd=_to_float(best.get("priceUsd")),
                    liquidity_usd=liq,
                    volume_24h_usd=vol,
                    pool=pool,
                )
            if len(results) >= settings.max_tokens:
                break

        # trim to configured universe size by liquidity, drop quote infra
        ordered = sorted(results.values(), key=lambda t: t.liquidity_usd or 0, reverse=True)
        final = [t for t in ordered if t.address not in quote_infra][: settings.max_tokens]

        # ETH pricing pool: register the largest stable/WETH pool so the price
        # service can value ETH-quoted trades on-chain (WETH itself is never a
        # tracked position — it is quote infrastructure).
        try:
            weth_pairs = await self.client.token_pairs(settings.chain, [settings.weth_address])
            stable_quotes = [p for p in weth_pairs
                             if ((p.get("quoteToken") or {}).get("symbol") or "").upper() in STABLE_SYMBOLS]
            if stable_quotes:
                best = max(stable_quotes, key=lambda p: ((p.get("liquidity") or {}).get("usd") or 0))
                pool = _pool_from_pair(best)
                if pool:
                    final.append(TokenData(
                        address=settings.weth_address, symbol="WETH", name="Wrapped Ether",
                        price_usd=_to_float(best.get("priceUsd")),
                        liquidity_usd=_to_float((best.get("liquidity") or {}).get("usd")),
                        volume_24h_usd=_to_float((best.get("volume") or {}).get("h24")),
                        pool=pool,
                    ))
        except Exception as e:
            jlog(log, logging.WARNING, "weth pricing pool unavailable", error=str(e)[:120])

        jlog(log, logging.INFO, "dex discovery done", tokens=len(final),
             symbols=[t.symbol for t in final[:15]])
        await self.client.close()
        return final
