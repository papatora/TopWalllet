"""EVM JSON-RPC client with endpoint rotation, rate limiting and backoff.

Implemented on raw JSON-RPC (httpx) instead of web3.py: zero heavy deps,
works on any EVM chain, and batch calls keep getLogs-based pricing cheap.
"""
from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import httpx

from config.settings import settings
from src.enrich.rate_limiter import RateLimiter
from src.utils.logger import jlog
import logging

log = logging.getLogger(__name__)


class RpcError(Exception):
    pass


class AllEndpointsDown(Exception):
    pass


class EvmRpcClient:
    def __init__(self, endpoints: list[str] | None = None, rps: float | None = None):
        self.endpoints = [e.rstrip("/") for e in (endpoints or settings.evm_rpc_endpoints)]
        if not self.endpoints:
            raise ValueError("No EVM_RPC_ENDPOINTS configured")
        self._limiter = RateLimiter(rps or settings.rpc_rps, period=1.0)
        self._cool_until: dict[int, float] = {}
        self._log_blocked_until: dict[int, float] = {}
        self._idx = random.randrange(len(self.endpoints))
        self._client: httpx.AsyncClient | None = None
        self._block_ts_cache: dict[int, int] = {}
        self._ts_lock = asyncio.Lock()
        self._request_id = 0

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            proxies = settings.proxy_urls or None
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"User-Agent": "TopWallet/0.1"},
                proxy=proxies[0] if proxies else None,
            )
        return self._client

    def _next_endpoint(self, skip_for_logs: bool = False) -> tuple[int, str]:
        now = time.time()

        def usable(i: int) -> bool:
            if self._cool_until.get(i, 0) > now:
                return False
            if skip_for_logs and self._log_blocked_until.get(i, 0) > now:
                return False
            return True

        for _ in range(len(self.endpoints)):
            self._idx = (self._idx + 1) % len(self.endpoints)
            if usable(self._idx):
                return self._idx, self.endpoints[self._idx]
        # nothing fully usable: fall back to the least-restricted endpoint
        if skip_for_logs:
            idx = min(range(len(self.endpoints)),
                      key=lambda i: max(self._log_blocked_until.get(i, 0), self._cool_until.get(i, 0)))
        else:
            idx = min(range(len(self.endpoints)), key=lambda i: self._cool_until.get(i, 0))
        return idx, self.endpoints[idx]

    async def call(self, method: str, params: list[Any]) -> Any:
        """Single JSON-RPC call with endpoint rotation on 429/5xx/transport errors."""
        client = await self._http()
        last_err: Exception | None = None
        for attempt in range(len(self.endpoints) * 2):
            await self._limiter.acquire()
            idx, url = self._next_endpoint()
            self._request_id += 1
            payload = {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params}
            try:
                resp = await client.post(url, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                self._cool_until[idx] = time.time() + 15
                last_err = e
                await asyncio.sleep(0.5)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                self._cool_until[idx] = time.time() + (20 if resp.status_code == 429 else 10)
                jlog(log, logging.WARNING, "rpc endpoint cooled", endpoint=self._mask(url), status=resp.status_code)
                last_err = RpcError(f"{resp.status_code} from endpoint {idx}")
                await asyncio.sleep(0.5)
                continue
            if resp.status_code >= 400:
                body = (resp.text or "")[:200]
                raise RpcError(f"http {resp.status_code} from endpoint {idx}: {body}")
            try:
                data = resp.json()
            except ValueError as e:
                last_err = e
                continue
            if "error" in data:
                err = data["error"]
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                code = err.get("code") if isinstance(err, dict) else None
                # request-level error (e.g. getLogs range too large): caller decides
                raise RpcError(f"rpc error {code}: {msg}")
            return data.get("result")
        raise AllEndpointsDown(str(last_err))

    async def batch_call(self, calls: list[tuple[str, list[Any]]]) -> list[Any]:
        """JSON-RPC batch. Falls back to sequential on batch-unfriendly errors."""
        await self._limiter.acquire()
        idx, url = self._next_endpoint()
        client = await self._http()
        payload = [
            {"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)
        ]
        try:
            resp = await client.post(url, json=payload)
            if resp.status_code == 429:
                self._cool_until[idx] = time.time() + 20
                raise RpcError("429 batch")
            resp.raise_for_status()
            data = resp.json()
        except (RpcError, httpx.HTTPError, ValueError):
            # fallback: sequential calls (some endpoints reject batches)
            out = []
            for m, p in calls:
                try:
                    out.append(await self.call(m, p))
                except RpcError:
                    out.append(None)
            return out
        results: list[Any] = [None] * len(calls)
        for item in data if isinstance(data, list) else []:
            i = item.get("id")
            if isinstance(i, int) and 0 <= i < len(results):
                results[i] = item.get("result") if "error" not in item else None
        return results

    async def block_number(self) -> int:
        res = await self.call("eth_blockNumber", [])
        return int(res, 16)

    async def chain_id(self) -> int:
        res = await self.call("eth_chainId", [])
        return int(res, 16)

    async def probe_log_endpoints(self, probe_address: str, probe_topic: str,
                                  head: int, span: int = 1500) -> None:
        """One-shot sanity check: some indexers return `result: []` silently for
        log queries they can't serve. Probe every endpoint directly with a
        recent-range query and block the deaf ones from getLogs rotation."""
        client = await self._http()
        counts: dict[int, int] = {}
        for i, url in enumerate(self.endpoints):
            body = {"fromBlock": hex(max(head - span, 1)), "toBlock": hex(head),
                    "address": probe_address, "topics": [probe_topic]}
            try:
                resp = await client.post(
                    url, json={"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [body]},
                    timeout=httpx.Timeout(20.0),
                )
                data = resp.json() if resp.status_code == 200 else {}
                res = data.get("result")
                counts[i] = len(res) if isinstance(res, list) else -1
            except Exception:
                counts[i] = -1
        best = max(counts.values(), default=0)
        for i, n in counts.items():
            if n < 0 or best <= 0 or n < best * 0.1:
                # deaf or erroring indexer — park it for log queries only
                self._log_blocked_until[i] = time.time() + 3600
                jlog(log, logging.INFO, "endpoint failed log probe; blocked for getLogs",
                     endpoint=self._mask(self.endpoints[i]), count=n)
            else:
                jlog(log, logging.INFO, "endpoint log probe ok",
                     endpoint=self._mask(self.endpoints[i]), count=n)

    async def get_logs(
        self,
        from_block: int,
        to_block: int,
        address: str | None = None,
        topics: list[Any] | None = None,
    ) -> list[dict]:
        """eth_getLogs with endpoint rotation that remembers which endpoints
        reject wide ranges (e.g. Alchemy free tier caps at 10 blocks)."""
        skip_for_logs = True
        params: dict[str, Any] = {"fromBlock": hex(from_block), "toBlock": hex(to_block)}
        if address:
            params["address"] = address
        if topics is not None:
            params["topics"] = topics

        client = await self._http()
        last_err: Exception | None = None
        consecutive_fail = 0
        for _ in range(len(self.endpoints) * 3):
            # when every usable endpoint is cooling, back off instead of hammering
            now = time.time()
            usable = [
                i for i in range(len(self.endpoints))
                if self._cool_until.get(i, 0) <= now
                and (not skip_for_logs or self._log_blocked_until.get(i, 0) <= now)
            ]
            if not usable:
                await asyncio.sleep(min(2 ** consecutive_fail, 15))
                consecutive_fail += 1
            else:
                consecutive_fail = 0
            await self._limiter.acquire()
            idx, url = self._next_endpoint(skip_for_logs=skip_for_logs)
            self._request_id += 1
            payload = {"jsonrpc": "2.0", "id": self._request_id,
                       "method": "eth_getLogs", "params": [params]}
            try:
                resp = await client.post(url, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                self._cool_until[idx] = time.time() + 15
                last_err = e
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                self._cool_until[idx] = time.time() + (20 if resp.status_code == 429 else 10)
                consecutive_fail = 0
                last_err = RpcError(f"{resp.status_code} from endpoint {idx}")
                continue
            body = resp.text or ""
            if resp.status_code >= 400:
                low = body.lower()
                if "block range" in low or "free tier" in low or "upgrade" in low:
                    # endpoint cannot serve wide getLogs ranges — park it for log queries
                    self._log_blocked_until[idx] = time.time() + 3600
                    jlog(log, logging.INFO, "endpoint blocked for wide getLogs", endpoint=self._mask(url))
                    last_err = RpcError(body[:160])
                    continue
                raise RpcError(f"http {resp.status_code}: {body[:200]}")
            data = resp.json()
            if "error" in data:
                err = data["error"]
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                low = msg.lower()
                if "exceeds limit" in low or "more than" in low or "too many" in low:
                    # response-size problem: caller should shrink the window
                    raise RpcError(f"RESPONSE_SIZE_EXCEEDED: {msg}")
                if "block range" in low or "free tier" in low:
                    self._log_blocked_until[idx] = time.time() + 3600
                    last_err = RpcError(msg)
                    continue
                raise RpcError(f"rpc error: {msg}")
            return data.get("result")
        raise AllEndpointsDown(str(last_err))

    async def get_logs_adaptive(
        self,
        from_block: int,
        to_block: int,
        address: str | None,
        topics: list[Any] | None,
        start_window: int | None = None,
        max_calls: int | None = None,
    ) -> list[dict]:
        """Fetch logs over a large range. Shrinks the window only on
        response-size limits; endpoint-specific range rejections are routed
        around instead. `max_calls` bounds the worst-case RPC spend (oldest
        ranges are dropped first, newest data always wins)."""
        window = start_window or settings.getlogs_start_window
        budget = max_calls or 10 ** 9
        logs: list[dict] = []
        end = to_block
        retries_left = 3
        calls = 0
        while end >= from_block:
            if calls >= budget:
                jlog(log, logging.WARNING, "getlogs call budget exhausted; oldest ranges dropped",
                     fetched=len(logs), calls=calls, oldest_reached=end)
                break
            start = max(end - window + 1, from_block)
            calls += 1
            try:
                chunk = await self.get_logs(start, end, address, topics)
                logs.extend(chunk)
                end = start - 1
                retries_left = 3
                if len(logs) > settings.price_max_logs_per_pool:
                    jlog(log, logging.WARNING, "price series capped", fetched=len(logs))
                    break
            except AllEndpointsDown:
                retries_left -= 1
                if retries_left <= 0:
                    jlog(log, logging.WARNING, "getlogs range skipped after retries",
                         start=start, end=end)
                    end = start - 1
                    retries_left = 3
                else:
                    await asyncio.sleep(15)
            except RpcError as e:
                msg = str(e)
                if "RESPONSE_SIZE_EXCEEDED" in msg and window > 2000:
                    window = window // 2
                    jlog(log, logging.INFO, "shrinking getlogs window", window=window)
                else:
                    jlog(log, logging.WARNING, "getlogs range skipped",
                         start=start, end=end, error=msg[:140])
                    end = start - 1
        return logs

    async def block_timestamps(self, blocks: list[int]) -> dict[int, int]:
        """Batch eth_getBlockByNumber for timestamps, with memory caching."""
        async with self._ts_lock:
            missing = sorted({b for b in blocks if b not in self._block_ts_cache})
        if missing:
            fetched: dict[int, int] = {}
            for i in range(0, len(missing), 40):
                chunk = missing[i:i + 40]
                calls = [("eth_getBlockByNumber", [hex(b), False]) for b in chunk]
                results = await self.batch_call(calls)
                for b, res in zip(chunk, results):
                    if res and res.get("timestamp"):
                        fetched[b] = int(res["timestamp"], 16)
            async with self._ts_lock:
                self._block_ts_cache.update(fetched)
        async with self._ts_lock:
            return {b: self._block_ts_cache[b] for b in set(blocks) if b in self._block_ts_cache}

    @staticmethod
    def _mask(url: str) -> str:
        return url.split("/v2/")[0] + "/v2/***" if "/v2/" in url else url

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()


# --- Event topic constants (keccak256 of event signatures) ---
TRANSFER_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
V3_SWAP_TOPIC0 = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"


def v4_swap_topic0() -> str:
    """keccak256 of the canonical Uniswap v4 Swap signature (verified on-chain:
    logs exist under this topic on Robinhood Chain's PoolManager). User-defined
    value types map to their underlying type: PoolId → bytes32, Contract → address."""
    from Crypto.Hash import keccak

    sig = "Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)"
    k = keccak.new(digest_bits=256)
    k.update(sig.encode())
    return "0x" + k.hexdigest()
