"""Historical price reconstruction from on-chain DEX Swap events.

Robinhood Chain has no third-party historical price API (GeckoTerminal not
supported, Birdeye is Solana-centric), so TopWallet derives prices itself:

  * Uniswap v4 pools  — Swap logs from the PoolManager singleton, filtered by
    the pool's poolId topic. The log data carries sqrtPriceX96 after each swap.
  * Uniswap v3 pools  — Swap logs from the pool contract itself.

  price_raw      = (sqrtPriceX96 / 2^96)^2        # token1 per token0
  token0/token1  = ordered by numeric address     # EVM convention
  price_usd      = price_in_quote * quote_usd     # USDG≈$1; ETH via its USDG pool

Every point is persisted (price_points) so re-runs are incremental and the
analysis stage can compute local-window percentiles (dip/top timing).
"""
from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings, STABLE_SYMBOLS
from src.db.models import BlockTimestamp, Pool, PricePoint, Token
from src.utils.logger import jlog
from src.utils.rpc_client import EvmRpcClient, V3_SWAP_TOPIC0, v4_swap_topic0

log = logging.getLogger(__name__)
Q96 = 2 ** 96


@dataclass
class SeriesPoint:
    block: int
    ts: datetime
    price_usd: float


def _word(data_hex: str, index: int) -> int:
    raw = bytes.fromhex(data_hex[2:] if data_hex.startswith("0x") else data_hex)
    chunk = raw[index * 32:(index + 1) * 32]
    return int.from_bytes(chunk, "big") if len(chunk) == 32 else 0


def _sqrt_to_raw_price(sqrt_x96: int) -> float:
    if sqrt_x96 <= 0:
        return 0.0
    return (sqrt_x96 / Q96) ** 2


class PriceService:
    def __init__(self, rpc: EvmRpcClient, session: AsyncSession):
        self.rpc = rpc
        self.session = session
        self._series_cache: dict[str, list[SeriesPoint]] = {}  # pool_address → sorted points
        self._token_pool: dict[str, str] = {}                  # token → main pool address
        self._eth_pool: str | None = None
        self._eth_const: float | None = None
        self._v4_topic = v4_swap_topic0()
        self.head_hint: int | None = None
        self._eth_spot: float | None = None

    # ---------------- setup ----------------

    async def load_pools(self) -> None:
        pools = (await self.session.execute(select(Pool))).scalars().all()
        by_liq = sorted(pools, key=lambda p: p.liquidity_usd or 0, reverse=True)
        for p in by_liq:
            self._token_pool.setdefault(p.token_address, p.address)
        # ETH price pool: most liquid pool whose base is WETH/native and quote is a stable
        for p in by_liq:
            if p.quote_symbol.upper() in STABLE_SYMBOLS and p.token_address in (
                settings.weth_address, "0x0000000000000000000000000000000000000000"
            ):
                self._eth_pool = p.address
                break
        jlog(log, logging.INFO, "price service pools loaded", pools=len(pools),
             eth_price_pool=self._eth_pool)

    # ---------------- series building ----------------

    async def build_all_series(self, from_block: int, to_block: int) -> int:
        pools = (await self.session.execute(select(Pool))).scalars().all()
        if self._eth_pool:
            pools = sorted(pools, key=lambda p: p.address != self._eth_pool)  # ETH pool first
        total = 0
        for pool in pools:
            try:
                total += await self.build_series_for_pool(pool, from_block, to_block)
            except Exception as e:
                jlog(log, logging.WARNING, "series build failed", pool=pool.address, error=str(e)[:160])
        await self.session.commit()
        jlog(log, logging.INFO, "price series built", points=total, pools=len(pools))
        return total

    async def build_series_for_pool(self, pool: Pool, from_block: int, to_block: int,
                                    max_calls: int | None = None) -> int:
        if pool.version == 4:
            logs = await self.rpc.get_logs_adaptive(
                from_block, to_block,
                address=settings.pool_manager,
                topics=[self._v4_topic, pool.address],
                max_calls=max_calls,
            )
        else:
            logs = await self.rpc.get_logs_adaptive(
                from_block, to_block, address=pool.address, topics=[V3_SWAP_TOPIC0],
                max_calls=max_calls,
            )
        if not logs:
            return 0

        # (block, sqrtPriceX96) — last sqrt price per block wins; skip blocks
        # already stored so re-runs are idempotent
        existing = set((await self.session.execute(
            select(PricePoint.block_num).where(PricePoint.pool_address == pool.address)
        )).scalars().all())
        raw_points: dict[int, int] = {}
        for entry in logs:
            block = int(entry["blockNumber"], 16)
            if block in existing:
                continue
            data = entry.get("data") or "0x"
            try:
                sqrt = _word(data, 2)
                if sqrt > 0:
                    raw_points[block] = sqrt
            except (ValueError, IndexError):
                continue
        if not raw_points:
            return 0

        # timestamps (cached in DB across pools)
        blocks = sorted(raw_points)
        ts_map = await self._timestamps(blocks)

        token = await self.session.get(Token, pool.token_address)
        token_addr = pool.token_address.lower()
        quote_addr = pool.quote_token.lower()

        # quote USD per block (stables = $1, ETH via its own pool)
        quote_usd_by_block: dict[int, float] = {}
        for block in blocks:
            q = await self._quote_usd(pool, block)
            if q:
                quote_usd_by_block[block] = q
        if not quote_usd_by_block:
            return 0

        # raw = sqrtPriceX96² = token1-per-token0 (token0 = lower address).
        # Address-ordering surprises happen (quote-token metadata mismatches),
        # so pick the orientation whose median best matches the token's known
        # spot price from DexScreener; fall back to the ordering rule.
        token_is_token0 = token_addr < quote_addr
        spot = token.price_usd if token and token.price_usd else None

        def build(invert: bool) -> list[tuple[int, datetime, float]]:
            out = []
            for block in blocks:
                q = quote_usd_by_block.get(block)
                if not q:
                    continue
                raw = _sqrt_to_raw_price(raw_points[block])
                if raw <= 0:
                    continue
                p = (1.0 / raw if invert else raw) * q
                if 0 < p < 10 ** 9:
                    out.append((block, ts_map[block], p))
            return out

        import math

        def med_log_dist(series: list) -> float:
            if not series:
                return float("inf")
            logs_sorted = sorted(math.log10(p) for _, _, p in series)
            return abs(logs_sorted[len(logs_sorted) // 2] - math.log10(spot))

        normal = build(False)     # price = raw × quote_usd
        inverted = build(True)    # price = (1/raw) × quote_usd
        if spot:
            pick_inverted = med_log_dist(inverted) < med_log_dist(normal)
        else:
            pick_inverted = not token_is_token0
        candidates = inverted if pick_inverted else normal

        for block, ts, price_usd in candidates:
            self.session.add(PricePoint(
                pool_address=pool.address, block_num=block, ts=ts, price_usd=price_usd,
            ))
        return len(candidates)

    async def _timestamps(self, blocks: list[int]) -> dict[int, datetime]:
        """Timestamps via anchor blocks + linear interpolation.

        A busy pool can produce tens of thousands of swap blocks; fetching
        real timestamps per block would cost an RPC call each. Instead we
        fetch exact timestamps on a coarse grid (every ANCHOR_SPACING blocks
        plus the head region) and interpolate — on a 0.1s-block L2 the error
        is ~1s, irrelevant for price series.
        """
        ts_map: dict[int, datetime] = {}
        missing = []
        for b in blocks:
            row = await self.session.get(BlockTimestamp, b)
            if row:
                ts_map[b] = row.ts
            else:
                missing.append(b)
        if not missing:
            return ts_map

        spacing = 1_000_000
        lo, hi = min(missing), max(missing)
        anchors = sorted(set(
            list(range(max(lo // spacing * spacing, 1), hi + spacing, spacing))
            + [max(hi, hi + 1), hi + spacing, self.head_hint or hi]
        ))
        anchors = [a for a in anchors if a > 0]
        fetched = await self.rpc.block_timestamps(anchors)
        # block_timestamps returns unix seconds; normalize to aware datetimes
        known = sorted(
            (b, datetime.fromtimestamp(t, tz=timezone.utc)) for b, t in fetched.items()
        )

        def interp(b: int) -> datetime | None:
            if not known:
                return None
            if b <= known[0][0]:
                return known[0][1]
            if b >= known[-1][0]:
                return known[-1][1]
            j = bisect.bisect_right([k[0] for k in known], b) - 1
            b0, t0 = known[j]
            b1, t1 = known[j + 1]
            if b1 == b0:
                return t0
            frac = (b - b0) / (b1 - b0)
            seconds = (t1 - t0).total_seconds() * frac
            return t0 + timedelta(seconds=seconds)

        for b in missing:
            ts = interp(b)
            if ts is None:
                continue
            ts_map[b] = ts
            self.session.add(BlockTimestamp(block_num=b, ts=ts))
        await self.session.flush()
        return ts_map

    async def _quote_usd(self, pool: Pool, block: int) -> float | None:
        symbol = pool.quote_symbol.upper()
        if symbol in STABLE_SYMBOLS:
            return 1.0
        if pool.quote_token.lower() in (settings.weth_address, "0x0000000000000000000000000000000000000000"):
            return await self.eth_price_at(block)
        return None

    async def eth_price_at(self, block: int) -> float | None:
        """ETH USD: series from the ETH/stable pool when available, else the
        verified DexScreener on-chain oracle (WETH most-liquid pool)."""
        if self._eth_pool is not None:
            series = await self.get_series(self._eth_pool)
            if series:
                prices = [p.block for p in series]
                idx = bisect.bisect_right(prices, block) - 1
                if idx < 0:
                    idx = 0
                return series[idx].price_usd
        if self._eth_spot is None:
            from src.analyze.pnl_verifier import eth_oracle_usd

            self._eth_spot = await eth_oracle_usd()
            jlog(log, logging.INFO, "eth spot oracle fallback", usd=self._eth_spot)
        return self._eth_spot

    async def _blockscout_coin_price(self) -> float | None:
        from src.discover.holder_scraper import BlockscoutClient

        stats = await BlockscoutClient().stats()
        try:
            return float(stats.get("coin_price"))
        except (TypeError, ValueError):
            return None

    # ---------------- lookups ----------------

    async def get_series(self, pool_address: str) -> list[SeriesPoint]:
        if pool_address in self._series_cache:
            return self._series_cache[pool_address]
        rows = (await self.session.execute(
            select(PricePoint).where(PricePoint.pool_address == pool_address).order_by(PricePoint.block_num)
        )).scalars().all()
        series = [SeriesPoint(block=r.block_num, ts=r.ts, price_usd=r.price_usd) for r in rows]
        self._series_cache[pool_address] = series
        return series

    async def price_at(self, token_address: str, block: int) -> float | None:
        pool = self._token_pool.get(token_address.lower())
        if pool is None:
            return None
        series = await self.get_series(pool)
        if not series:
            return None
        blocks = [p.block for p in series]
        idx = bisect.bisect_right(blocks, block) - 1
        if idx < 0:
            idx = 0
        return series[idx].price_usd

    async def window_prices(self, token_address: str, block: int, window_blocks: int) -> list[float]:
        """Prices of the token's pool within ±window around `block` (for percentiles)."""
        pool = self._token_pool.get(token_address.lower())
        if pool is None:
            return []
        series = await self.get_series(pool)
        blocks = [p.block for p in series]
        lo = bisect.bisect_left(blocks, block - window_blocks)
        hi = bisect.bisect_right(blocks, block + window_blocks)
        return [p.price_usd for p in series[lo:hi]]

    def last_point_ts(self, token: str) -> datetime | None:
        """Timestamp of the most recent known price point for a token."""
        pool = self._token_pool.get(token)
        if pool is None or pool not in self._series_cache:
            return None
        series = self._series_cache[pool]
        return series[-1].ts if series else None

    def percentile(self, value: float, window: list[float]) -> float | None:
        """Fraction of window prices strictly below `value` (0 = bought the dip, 1 = the top)."""
        if not window:
            return None
        below = sum(1 for p in window if p < value)
        return below / len(window)
