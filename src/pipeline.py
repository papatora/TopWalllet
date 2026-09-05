"""Pipeline orchestrator — discover → prices → enrich → analyze(+rank/export).

Checkpoint/resume model:
  * discovery is idempotent (tokens/pools/wallets upserted, unique keys)
  * wallet enrichment state lives in wallets.status (pending → in_progress →
    enriched/failed/skipped) — an interrupted run simply resumes on `pending`
    and `in_progress` rows
  * price points and swap events are keyed so re-runs replace, not duplicate
"""
from __future__ import annotations

import asyncio
import bisect
import logging
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings, STABLE_SYMBOLS
from src.analyze.anti_gaming import apply_filters, cluster_wallets
from src.analyze.position_calculator import (
    CalcPosition,
    PricedEvent,
    PriceWindowLookup,
    build_positions,
)
from src.analyze.wallet_scorer import composite_score, compute_metrics
from src.db.database import get_session_factory, init_db
from src.db.models import (
    PipelineCheckpoint,
    Pool,
    PricePoint,
    SwapEvent,
    Token,
    Wallet,
    WalletScore,
    WalletTokenInterest,
)
from src.discover.dex_scraper import TokenDiscovery
from src.discover.holder_scraper import (
    BlockscoutClient,
    WalletHit,
    extract_wallet_hits,
)
from src.discover.leaderboard_scraper import fetch_leaderboard_wallets
from src.enrich.price_fetcher import PriceService
from src.enrich.tx_fetcher import TxFetcher, TradeEvent
from src.rank.export import export_results, eip55
from src.rank.ranker import rank_wallets
from src.utils.logger import jlog, setup_logging
from src.utils.rpc_client import EvmRpcClient

log = logging.getLogger(__name__)

ALL_STAGES = ["discover", "enrich", "prices", "analyze"]


class Pipeline:
    def __init__(self, overrides: dict | None = None):
        self.overrides = overrides or {}
        self.rpc = EvmRpcClient()
        self.blockscout = BlockscoutClient()
        self.tx_fetcher = TxFetcher(self.blockscout)
        self.weights_cfg = settings.load_weights()
        self.session_factory = get_session_factory()
        self.block_time_s: float = 0.25
        self.head_block: int = 0

    def _apply_overrides(self) -> None:
        if "max_tokens" in self.overrides:
            settings.max_tokens = int(self.overrides["max_tokens"])
        if "enrich_limit" in self.overrides:
            settings.enrich_limit_per_run = int(self.overrides["enrich_limit"])
        if "lookback_days" in self.overrides:
            settings.lookback_days = int(self.overrides["lookback_days"])
            settings.price_lookback_days = int(self.overrides["lookback_days"])

    async def run(self, stages: list[str] | None = None) -> dict:
        setup_logging()
        self._apply_overrides()
        await init_db()
        stages = stages or ALL_STAGES
        started = datetime.now(timezone.utc)
        counts: dict = {}
        async with self.session_factory() as session:
            for stage in stages:
                jlog(log, logging.INFO, f"=== stage: {stage} ===")
                if stage == "discover":
                    counts.update(await self.stage_discover(session))
                elif stage == "enrich":
                    counts.update(await self.stage_enrich(session))
                elif stage == "prices":
                    counts.update(await self.stage_prices(session))
                elif stage == "analyze":
                    counts.update(await self.stage_analyze(session, started))
                await self._checkpoint(session, stage)
        await self.blockscout.close()
        await self.rpc.close()
        return counts

    async def _checkpoint(self, session: AsyncSession, stage: str) -> None:
        row = await session.get(PipelineCheckpoint, stage)
        if row is None:
            row = PipelineCheckpoint(stage=stage)
            session.add(row)
        row.cursor = datetime.now(timezone.utc).isoformat()
        await session.commit()

    # ---------------- Stage 1: DISCOVER ----------------

    async def stage_discover(self, session: AsyncSession) -> dict:
        tokens = await TokenDiscovery().discover()
        jlog(log, logging.INFO, "discovered tokens", count=len(tokens))

        symbols: dict[str, str] = {}
        for t in tokens:
            decimals = await self._token_decimals(t.address)
            await self._upsert_token(session, t, decimals)
            if t.pool:
                await self._upsert_pool(session, t)
            symbols[t.address] = t.symbol
        await session.commit()

        # wallet discovery per token (holders + recent traders); zero-address
        # mints/burns must never become "wallets"
        exclude = {
            settings.pool_manager, settings.weth_address, settings.usdg_address,
            "0x0000000000000000000000000000000000000000",
        }
        wallets_seen: set[str] = set()
        hits_total = 0
        for t in tokens:
            holders = await self.blockscout.token_holders(t.address, settings.holders_per_token)
            transfers = await self.blockscout.token_transfers(t.address, settings.trader_pages_per_token)
            hits: list[WalletHit] = extract_wallet_hits(t.address, holders, transfers, exclude)
            for hit in hits:
                await self._upsert_wallet_interest(session, hit)
                wallets_seen.add(hit.address)
                hits_total += 1

        # optional leaderboard source (no-op unless enabled)
        for entry in await fetch_leaderboard_wallets():
            addr = (entry.get("wallet") or "").lower()
            if addr.startswith("0x"):
                hit = WalletHit(address=addr, token_address="", source="leaderboard")
                await self._upsert_wallet_interest(session, hit)
                wallets_seen.add(addr)

        # cap the universe (keep wallets active across the most tokens)
        if len(wallets_seen) > settings.max_wallets:
            stmt = (
                select(WalletTokenInterest.wallet_address, func.count().label("n"))
                .group_by(WalletTokenInterest.wallet_address)
                .order_by(func.count().desc())
                .limit(settings.max_wallets)
            )
            keep = {row[0] for row in (await session.execute(stmt)).all()}
            drop = wallets_seen - keep
            if drop:
                await session.execute(
                    delete(Wallet).where(Wallet.address.in_(drop), Wallet.status == "pending")
                )
                wallets_seen = keep

        await session.commit()
        counts = {
            "tokens": len(tokens),
            "wallet_candidates": len(wallets_seen),
            "interest_edges": hits_total,
        }
        jlog(log, logging.INFO, "discover complete", **counts)
        return counts

    async def _token_decimals(self, address: str) -> int:
        data = await self.blockscout.get_json(f"/api/v2/tokens/{address}")
        try:
            return int((data or {}).get("decimals") or 18)
        except (TypeError, ValueError):
            return 18

    async def _upsert_token(self, session: AsyncSession, t, decimals: int) -> None:
        row = await session.get(Token, t.address)
        if row is None:
            row = Token(address=t.address)
            session.add(row)
        row.symbol = t.symbol
        row.name = t.name
        row.decimals = decimals
        row.price_usd = t.price_usd
        row.liquidity_usd = t.liquidity_usd
        row.volume_24h_usd = t.volume_24h_usd

    async def _upsert_pool(self, session: AsyncSession, t) -> None:
        p = t.pool
        row = await session.get(Pool, p.address)
        if row is None:
            row = Pool(address=p.address, token_address=t.address)
            session.add(row)
        row.dex = p.dex
        row.version = p.version
        row.quote_token = p.quote_token
        row.quote_symbol = p.quote_symbol
        row.liquidity_usd = p.liquidity_usd
        row.price_usd = p.price_usd

    async def _upsert_wallet_interest(self, session: AsyncSession, hit: WalletHit) -> None:
        wallet = await session.get(Wallet, hit.address)
        if wallet is None:
            wallet = Wallet(address=hit.address)
            session.add(wallet)
        if hit.source:
            exists = await session.execute(
                select(WalletTokenInterest.id).where(
                    WalletTokenInterest.wallet_address == hit.address,
                    WalletTokenInterest.token_address == hit.token_address,
                    WalletTokenInterest.source == hit.source,
                )
            )
            if exists.first() is None:
                session.add(WalletTokenInterest(
                    wallet_address=hit.address,
                    token_address=hit.token_address,
                    source=hit.source,
                ))

    # ---------------- Stage 2b: PRICES (targeted) ----------------

    async def stage_prices(self, session: AsyncSession) -> dict:
        """Build price series ONLY for tokens candidate wallets actually traded,
        starting from their earliest observed trade — this bounds getLogs work
        to what scoring needs instead of the whole DEX universe."""
        self.head_block = await self.rpc.block_number()
        self.block_time_s = await self._estimate_block_time()

        service = PriceService(self.rpc, session)
        await service.load_pools()
        service.head_hint = self.head_block

        # the public RPC's log index lags the tip — never scan the last
        # SAFE_LOG_LAG blocks (they come back silently empty)
        to_block = max(self.head_block - settings.safe_log_lag_blocks, 1)

        # drop deaf indexers from getLogs rotation before the heavy scans
        from src.utils.rpc_client import v4_swap_topic0

        await self.rpc.probe_log_endpoints(settings.pool_manager, v4_swap_topic0(), to_block)

        lookback_blocks = min(
            int(settings.price_lookback_days * 86400 / max(self.block_time_s, 0.01)),
            self.head_block,
        )
        window_blocks = int(settings.dip_window_days * 86400 / max(self.block_time_s, 0.01))

        pools = (await session.execute(select(Pool))).scalars().all()
        pool_by_token: dict[str, Pool] = {}
        for p in sorted(pools, key=lambda p: p.liquidity_usd or 0, reverse=True):
            pool_by_token.setdefault(p.token_address, p)

        # scan only AROUND the blocks where trades actually happened: merge
        # each token's event blocks into clusters (gaps < CLUSTER_GAP) and
        # price each cluster with a small margin. Full-history scans of active
        # pools cost hundreds of getLogs calls; cluster scans cost 1-3 each
        # and cover exactly the blocks the scorer needs prices for.
        cluster_gap = 30_000
        margin = 5_000
        max_clusters_per_pool = settings.price_max_clusters_per_pool

        built_points = 0
        priced_pools: set[str] = set()
        quotes_needed: set[str] = set()
        tokens_rows = (await session.execute(
            select(SwapEvent.token_address,
                   func.min(SwapEvent.block_num),
                   func.max(SwapEvent.block_num))
            .group_by(SwapEvent.token_address)
        )).all()
        cutoff_block = self.head_block - min(
            int(settings.price_lookback_days * 86400 / max(self.block_time_s, 0.01)),
            self.head_block,
        )

        # ETH-quoted pools need the ETH price series FIRST (they fail otherwise);
        # the WETH/stable pool has no swap events of its own, so cluster scanning
        # never reaches it — build it explicitly over the lookback window.
        eth_needed = any(
            (pool_by_token.get(t).quote_token.lower() in
             (settings.weth_address, "0x0000000000000000000000000000000000000000"))
            for t, _mn, _mx in tokens_rows if pool_by_token.get(t)
        )
        if eth_needed and service._eth_pool:
            eth_pool_row = await session.get(Pool, service._eth_pool)
            if eth_pool_row:
                from_block = max(to_block - lookback_blocks, 1)
                built_points += await service.build_series_for_pool(
                    eth_pool_row, from_block, to_block,
                    max_calls=settings.price_max_calls_per_pool,
                )
                priced_pools.add(service._eth_pool)
        for token, min_block, max_block in tokens_rows:
            pool = pool_by_token.get(token)
            if pool is None or max_block < cutoff_block:
                continue  # no pool, or all events older than the price window
            blocks = sorted((await session.execute(
                select(SwapEvent.block_num).where(SwapEvent.token_address == token)
            )).scalars().all())
            # merge into clusters
            clusters: list[list[int]] = []
            for b in blocks:
                if clusters and b - clusters[-1][1] <= cluster_gap:
                    clusters[-1][1] = b
                else:
                    clusters.append([b, b])
            clusters = clusters[-max_clusters_per_pool:]  # keep the most recent
            for c0, c1 in clusters:
                f = max(c0 - margin, 1)
                t = min(c1 + margin, to_block)
                if f > t:
                    continue
                try:
                    built_points += await service.build_series_for_pool(
                        pool, f, t,
                        max_calls=settings.price_max_calls_per_pool,
                    )
                    priced_pools.add(pool.address)
                    quotes_needed.add(pool.quote_token.lower())
                    quotes_needed.add(pool.quote_symbol.upper())
                except Exception as e:
                    jlog(log, logging.WARNING, "series build failed",
                         pool=pool.address, error=str(e)[:160])
                    break

        await session.commit()
        jlog(log, logging.INFO, "targeted price series built", points=built_points, pools=len(priced_pools))
        return {"price_points": built_points, "pools_priced": len(priced_pools)}

    async def _estimate_block_time(self) -> float:
        """Empirical: timestamps of head and head-1M blocks (no unit guessing)."""
        try:
            span = min(1_000_000, self.head_block - 1)
            ts = await self.rpc.block_timestamps([self.head_block, self.head_block - span])
            head_ts = ts.get(self.head_block)
            old_ts = ts.get(self.head_block - span)
            if head_ts and old_ts and head_ts > old_ts:
                return (head_ts - old_ts) / span
        except Exception as e:
            jlog(log, logging.WARNING, "block time estimate failed", error=str(e)[:120])
        return 0.25

    # ---------------- Stage 2b: ENRICH ----------------

    async def stage_enrich(self, session: AsyncSession) -> dict:
        query = (
            select(Wallet)
            .where(Wallet.status.in_(["pending", "in_progress"]))
            .order_by(Wallet.first_seen.asc())
        )
        wallets = (await session.execute(query)).scalars().all()
        if settings.enrich_limit_per_run > 0:
            wallets = wallets[: settings.enrich_limit_per_run]
        return await self.enrich_wallets(session, wallets)

    async def enrich_wallets(self, session: AsyncSession, wallets: list[Wallet]) -> dict:
        """Enrich an explicit wallet list (used by the pipeline stage AND track-by-CA).

        Blockscout-only (cheap, no RPC): classifies trades and persists them
        WITHOUT prices — the targeted prices stage attaches those later."""
        tokens = (await session.execute(select(Token))).scalars().all()
        pools = (await session.execute(select(Pool))).scalars().all()
        decimals = {t.address: t.decimals for t in tokens}
        # counterparty set per token: its pools + the v4 PoolManager singleton
        counterparties: dict[str, set[str]] = {}
        for p in pools:
            counterparties.setdefault(p.token_address, set()).add(p.address)
        for tok in list(counterparties):
            counterparties[tok].add(settings.pool_manager)
        tracked = set(counterparties)
        tracked -= {settings.usdg_address, settings.weth_address}
        counterparties = {t: cps for t, cps in counterparties.items() if t in tracked}

        # which tracked tokens each wallet was discovered through — enrichment
        # fetches per (wallet, token) via Blockscout's token-filtered endpoint
        interest_rows = (await session.execute(
            select(WalletTokenInterest.wallet_address, WalletTokenInterest.token_address)
            .where(WalletTokenInterest.token_address.in_(tracked))
        )).all()
        interest_map: dict[str, list[str]] = {}
        for wallet_addr, token_addr in interest_rows:
            interest_map.setdefault(wallet_addr, []).append(token_addr)

        jlog(log, logging.INFO, "enrich starting", wallets=len(wallets))
        enriched = failed = 0
        for i in range(0, len(wallets), settings.enrich_concurrency):
            batch = wallets[i:i + settings.enrich_concurrency]
            results = await asyncio.gather(
                *[self._fetch_one(w.address, interest_map.get(w.address, []),
                                  counterparties, decimals) for w in batch],
                return_exceptions=True,
            )
            for wallet, result in zip(batch, results):
                if isinstance(result, Exception):
                    wallet.status = "failed"
                    wallet.error = str(result)[:300]
                    failed += 1
                    jlog(log, logging.WARNING, "wallet enrich failed",
                         wallet=wallet.address, error=str(result)[:160])
                    continue
                await self._persist_events(session, wallet, result)
                enriched += 1
            await session.commit()
            jlog(log, logging.INFO, "enrich progress", done=min(i + len(batch), len(wallets)),
                 total=len(wallets), enriched=enriched, failed=failed)
        return {"wallets_enriched": enriched, "wallets_failed": failed}

    async def _fetch_one(self, address: str, interest_tokens: list[str],
                         counterparties: dict[str, set[str]],
                         decimals: dict[str, int]) -> list[TradeEvent]:
        """Network-only part (safe to run concurrently): per interested token,
        pull the wallet's full transfer history for that token and classify
        swaps by NET flow per transaction.

        v4 routes often move tokens PoolManager → router → user, so per-leg
        classification fails; instead we group a tx's legs and use
        (received − sent) as the wallet's net trade, requiring only that the
        tx touched the token's pool or the v4 PoolManager singleton.
        """
        address = address.lower()
        events: list[TradeEvent] = []
        from src.enrich.tx_fetcher import _parse_amount, _parse_ts

        for token in interest_tokens:
            cps = counterparties.get(token)
            if not cps:
                continue
            items = await self.blockscout.address_token_transfers(
                address, settings.enrich_max_pages_per_wallet, token_filter=token,
            )
            by_tx: dict[str, list[dict]] = {}
            for it in items:
                tx = (it.get("transaction_hash") or "").lower()
                if tx:
                    by_tx.setdefault(tx, []).append(it)

            for tx, legs in by_tx.items():
                # a swap tx touches the pool somewhere even when the wallet's
                # leg goes through a router (PoolManager→router→wallet), so
                # test ANY leg of the tx against the pool counterparties —
                # not just the wallet-adjacent legs (subagent-audit fix)
                touched_pool = any(
                    ((leg.get("from") or {}).get("hash") or "").lower() in cps
                    or ((leg.get("to") or {}).get("hash") or "").lower() in cps
                    for leg in legs
                )
                received = sent = 0.0
                block_num = 0
                ts = None
                for leg in legs:
                    src = ((leg.get("from") or {}).get("hash") or "").lower()
                    dst = ((leg.get("to") or {}).get("hash") or "").lower()
                    amount = _parse_amount((leg.get("total") or {}).get("value") or leg.get("value")) or 0.0
                    if dst == address:
                        received += amount
                    elif src == address:
                        sent += amount
                    block_num = block_num or int(leg.get("block_number") or 0)
                    if ts is None:
                        ts = _parse_ts(leg.get("block_timestamp") or leg.get("timestamp"))
                if not touched_pool or block_num == 0:
                    continue  # pure wallet-to-wallet transfer / airdrop
                dec = decimals.get(token, 18)
                net_units = received - sent
                if abs(net_units) <= 0:
                    continue
                side = "BUY" if net_units > 0 else "SELL"
                token_amount = abs(net_units) / (10 ** dec)
                if token_amount <= 0:
                    continue
                events.append(TradeEvent(
                    wallet=address, token=token, side=side, token_amount=token_amount,
                    block_num=block_num, ts=ts, tx_hash=tx,
                ))
        events.sort(key=lambda e: e.block_num)
        return events

    async def _persist_events(self, session: AsyncSession, wallet: Wallet,
                              events: list[TradeEvent]) -> None:
        """Main-loop part: fill missing timestamps and persist unpriced swaps
        (prices are attached by the targeted prices stage + analyze lookup)."""
        if not events:
            wallet.status = "enriched"
            wallet.enriched_at = datetime.now(timezone.utc)
            return
        missing_ts_blocks = [e.block_num for e in events if e.ts is None]
        ts_map = await self.rpc.block_timestamps(missing_ts_blocks) if missing_ts_blocks else {}

        # full refresh per wallet keeps re-runs idempotent
        await session.execute(delete(SwapEvent).where(SwapEvent.wallet_address == wallet.address))
        seen: set[tuple] = set()
        kept = 0
        for ev in events:
            key = (ev.token, ev.side, ev.block_num, round(ev.token_amount, 12))
            if key in seen:
                continue
            seen.add(key)
            ts = ev.ts or (
                datetime.fromtimestamp(ts_map[ev.block_num], tz=timezone.utc)
                if ev.block_num in ts_map else None
            )
            if ts is None:
                continue
            session.add(SwapEvent(
                wallet_address=wallet.address, token_address=ev.token, ts=ts,
                block_num=ev.block_num, side=ev.side, token_amount=ev.token_amount,
                price_usd=None, usd_value=None, tx_hash=ev.tx_hash,
            ))
            kept += 1
        if kept:
            wallet.last_active = max(ev.ts for ev in events if ev.ts) or wallet.last_active
        wallet.status = "enriched"
        wallet.enriched_at = datetime.now(timezone.utc)
        jlog(log, logging.DEBUG, "wallet events persisted", wallet=wallet.address[:10], kept=kept)

    # ---------------- Stage 3: ANALYZE (+rank+export) ----------------

    async def stage_analyze(self, session: AsyncSession, started: datetime) -> dict:
        ranked = await self.analyze_wallets(session, started=started)
        counts = await self._db_counts(session)
        return counts | {"wallets_ranked": len(ranked)}

    async def analyze_wallets(
        self,
        session: AsyncSession,
        restrict_to: set[str] | None = None,
        started: datetime | None = None,
        do_export: bool = True,
        do_push: bool = True,
    ) -> list:
        """Score enriched wallets; optionally export/push (full pipeline only).

        Returns the ranked wallet list so track-by-CA can render its own output.
        """
        started = started or datetime.now(timezone.utc)
        service = PriceService(self.rpc, session)
        await service.load_pools()
        self._verify_service = service  # used by the hard PnL verifier

        tokens = (await session.execute(select(Token))).scalars().all()
        symbols = {t.address: t.symbol or t.address[:8] for t in tokens}
        current_prices = {t.address: t.price_usd for t in tokens if t.price_usd}
        self._decimals = {t.address: t.decimals for t in tokens}

        # in-memory sync lookup over the stored price series (shared cache with
        # the verifier so it sees identical prices)
        pools = (await session.execute(select(Pool))).scalars().all()
        series_by_pool: dict[str, tuple[list[int], list[float]]] = {}
        for p in pools:
            pts = await service.get_series(p.address)
            if pts:
                series_by_pool[p.address] = (
                    [q.block for q in pts], [q.price_usd for q in pts],
                )
        token_pool = {p.token_address: p.address for p in pools}
        first_block_by_token: dict[str, int] = {}
        for tok, pool in token_pool.items():
            if pool in series_by_pool:
                first_block_by_token[tok] = series_by_pool[pool][0][0]

        lookup = _SeriesLookup(series_by_pool, token_pool)
        window_blocks = int(settings.dip_window_days * 86400 / max(self.block_time_s, 0.01))

        query = select(Wallet).where(Wallet.status == "enriched")
        if restrict_to:
            query = query.where(Wallet.address.in_(restrict_to))
        wallets = (await session.execute(query)).scalars().all()
        jlog(log, logging.INFO, "analyzing wallets", wallets=len(wallets))

        scored: list[tuple] = []
        excluded = 0
        wallet_tokens: dict[str, set[str]] = {}
        buys_at: dict[tuple, set] = defaultdict(set)
        sells_at: dict[tuple, set] = defaultdict(set)
        for wallet in wallets:
            events = (await session.execute(
                select(SwapEvent).where(SwapEvent.wallet_address == wallet.address).order_by(SwapEvent.block_num)
            )).scalars().all()
            if not events:
                wallet.status = "skipped"
                continue
            by_token: dict[str, list[PricedEvent]] = {}
            for ev in events:
                price = ev.price_usd or lookup.price_at(ev.token_address, ev.block_num)
                if not price:
                    continue  # trade outside any price series — cannot be valued
                by_token.setdefault(ev.token_address, []).append(PricedEvent(
                    token=ev.token_address, side=ev.side, token_amount=ev.token_amount,
                    price_usd=price, ts=ev.ts, block_num=ev.block_num,
                ))
                # counterparty-coincidence index (same token, same block)
                key = (ev.token_address, ev.block_num)
                (buys_at if ev.side == "BUY" else sells_at)[key].add(wallet.address)
            if not by_token:
                wallet.status = "skipped"
                continue
            positions: list[CalcPosition] = []
            for token, evs in by_token.items():
                # DexScreener snapshot is fresher than the (lagged) series tip
                cur_price = current_prices.get(token) or lookup.last_price(token)
                positions.extend(build_positions(
                    wallet.address, token, evs,
                    current_price_usd=cur_price,
                    price_lookup=lookup, dip_window_blocks=window_blocks,
                ))
            metrics = compute_metrics(positions, self.weights_cfg)
            filters = apply_filters(metrics, positions, [e for evs in by_token.values() for e in evs],
                                    self.weights_cfg, first_block_by_token)
            if filters.excluded:
                excluded += 1
                wallet.status = "skipped"
                continue
            wallet_tokens[wallet.address] = set(by_token.keys())
            score = composite_score(metrics, self.weights_cfg) if metrics else 0.0
            scored.append((wallet.address, metrics, positions, score, filters.flags, None))

        # wash-pair detection (subagent-audit finding): two wallets repeatedly
        # on opposite sides of the same token in the same block
        pair_counts: dict[tuple, int] = defaultdict(int)
        for key, buyers in buys_at.items():
            for b in buyers:
                for sll in sells_at.get(key, ()):  # noqa: B007
                    if b != sll:
                        pair_counts[tuple(sorted((b, sll)))] += 1
        wash_wallets = {w for pair, n in pair_counts.items() if n >= 3 for w in pair}

        clusters = cluster_wallets(wallet_tokens)
        scored = [(w, m, p, s, f + (["WASH_PAIR"] if w in wash_wallets else []), clusters.get(w))
                  for (w, m, p, s, f, _) in scored]

        ranked = rank_wallets(scored, self.weights_cfg)

        # --- hard PnL verification: unverified wallets do not ship ---
        if settings.verify_pnl and ranked:
            from src.analyze.pnl_verifier import verify_top_wallets

            counterparties: dict[str, set[str]] = {}
            for p in pools:
                counterparties.setdefault(p.token_address, set()).add(p.address)
            for tok in list(counterparties):
                counterparties[tok].add(settings.pool_manager)
            self._counterparties = counterparties

            await verify_top_wallets(ranked, service, self._rederive_trade)
            before = len(ranked)
            ranked = [e for e in ranked
                      if (e.verification or {}).get("verdict") == "verified"]
            for i, e in enumerate(ranked, start=1):
                e.rank = i
            jlog(log, logging.INFO, "strict verification filter",
                 before=before, shipped=len(ranked))

        await self._persist_scores(session, ranked)
        await session.commit()

        if do_export:
            counts = await self._db_counts(session)
            counts.update({"wallets_scored": len(scored), "wallets_excluded": excluded})
            export_results(ranked, symbols, counts, started)
            if do_push and settings.auto_push_results and settings.github_token:
                from src.utils.github_pusher import push_results

                push_results()
        return ranked

    async def _rederive_trade(self, wallet: str, pos) -> float | None:
        """R2 re-derivation: recompute a position's return multiple from RAW
        Blockscout legs (fresh request, not our DB) + series prices."""
        from src.enrich.tx_fetcher import _parse_amount

        wallet = wallet.lower()
        cps = (self._counterparties or {}).get(pos.token)
        if not cps:
            return None
        items = await self.blockscout.address_token_transfers(wallet, 12, token_filter=pos.token)
        dec = (self._decimals or {}).get(pos.token, 18)

        def net_units_at(block: int, tol: int = 10) -> float:
            units = 0.0
            for it in items:
                bn = int(it.get("block_number") or 0)
                if abs(bn - block) > tol:
                    continue
                src = ((it.get("from") or {}).get("hash") or "").lower()
                dst = ((it.get("to") or {}).get("hash") or "").lower()
                amt = _parse_amount((it.get("total") or {}).get("value") or it.get("value")) or 0.0
                if dst == wallet and src in cps:
                    units += amt
                elif src == wallet and dst in cps:
                    units -= amt
            return abs(units) / (10 ** dec) if units else 0.0

        entry_amt = net_units_at(pos.entry_block)
        exit_amt = net_units_at(pos.exit_block) if pos.exit_block else 0.0
        if entry_amt <= 0 or exit_amt <= 0:
            return None
        svc = self._verify_service
        pe = await svc.price_at(pos.token, pos.entry_block)
        px = await svc.price_at(pos.token, pos.exit_block)
        if not pe or not px:
            return None
        return (exit_amt * px) / (entry_amt * pe)

    async def _persist_scores(self, session: AsyncSession, ranked) -> None:
        await session.execute(delete(WalletScore))
        for entry in ranked:
            session.add(WalletScore(
                wallet_address=entry.wallet_address,
                composite_score=entry.composite_score,
                metrics=json_dumps(entry.metrics),
                trading_style=entry.trading_style,
                risk_flags=json_dumps_list(entry.risk_flags),
                cluster_id=entry.cluster_id,
            ))

    async def _db_counts(self, session: AsyncSession) -> dict:
        async def count(model):
            return (await session.execute(select(func.count()).select_from(model))).scalar() or 0

        return {
            "tokens_in_db": await count(Token),
            "pools_in_db": await count(Pool),
            "wallets_in_db": await count(Wallet),
            "swap_events": await count(SwapEvent),
        }


class _SeriesLookup(PriceWindowLookup):
    """Sync view over per-pool price series for percentile + valuation math."""

    def __init__(self, series_by_pool, token_pool):
        self.series = series_by_pool
        self.token_pool = token_pool

    def _blocks_prices(self, token: str) -> tuple[list[int], list[float]] | None:
        pool = self.token_pool.get(token)
        return self.series.get(pool) if pool else None

    def window_prices(self, token: str, block: int, window_blocks: int) -> list[float]:
        bp = self._blocks_prices(token)
        if not bp:
            return []
        blocks, prices = bp
        lo = bisect.bisect_left(blocks, block - window_blocks)
        hi = bisect.bisect_right(blocks, block + window_blocks)
        return prices[lo:hi]

    def price_at(self, token: str, block: int) -> float | None:
        """Nearest series price at or before `block` (None if series starts later)."""
        bp = self._blocks_prices(token)
        if not bp:
            return None
        blocks, prices = bp
        idx = bisect.bisect_right(blocks, block) - 1
        if idx < 0:
            return None
        return prices[idx]

    def last_price(self, token: str) -> float | None:
        bp = self._blocks_prices(token)
        return bp[1][-1] if bp else None

    def percentile(self, value: float, window: list[float]) -> float | None:
        if not window:
            return None
        below = sum(1 for p in window if p < value)
        return below / len(window)


def json_dumps(metrics) -> str:
    import json

    d = metrics.__dict__.copy()
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return json.dumps(d, default=str)


def json_dumps_list(items: list[str]) -> str:
    import json

    return json.dumps(items)
