"""Feed event tests (docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md §6.2/§6.3/§6.9/§11).

Pure in-memory: aiosqlite :memory: DB, no network — mirrors
tests/test_wallet_classifier.py. Covers: deterministic ids, idempotent double
backfill, freshness bands, taxonomy typing (CALL/ENTRY/ADD/TRIM/EXIT/ROTATION),
block-range emission, honest nulls in the payload, and no-proof-no-row.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from config.settings import settings
from src.db.models import (
    Base,
    FeedEvent,
    Pool,
    PricePoint,
    SwapEvent,
    Token,
    Wallet,
)
from src.feed.events import backfill, freshness_band, make_event_id

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def ts(block: int) -> datetime:
    """Deterministic mapping block → timestamp (1 block = 1 second)."""
    return T0 + timedelta(seconds=block)


def ev(wallet, token, side, block, tx, amount=100.0):
    return SwapEvent(wallet_address=wallet, token_address=token, side=side,
                     block_num=block, ts=ts(block), token_amount=amount, tx_hash=tx)


# token 0xt3 has NO price series on purpose (honest-null checks)
POOLS = [("0xp1", "0xt1"), ("0xp2", "0xt2"), ("0xp3", "0xt3")]
POINTS = [("0xp1", 100, 1.0), ("0xp2", 100, 2.0)]


def scenario_events():
    """One token lifecycle for 0xb plus two genuine first calls by 0xa.

      0xa  BUY 0xt1 @200 tx=0xtxa   → CALL   (first activity on 0xt1 anywhere)
      0xa  BUY 0xt2 @150 tx=0xtxb   → CALL   (first activity on 0xt2 anywhere)
      0xb  BUY 0xt1 @300 tx=0xtxc   → ENTRY  (0xa already held)
      0xb  BUY 0xt1 @400 tx=0xtxd   → ADD    (25/50 = 50% ≥ 25%)
      0xb  SELL 0xt1 @500 tx=0xtxe  → TRIM   (37.5/75 = 50%)
      0xb  SELL 0xt1 @600 tx=0xtxf  → EXIT   (40/37.5 > 80%)
      0xb  BUY 0xt2 @610 tx=0xtxg   → ROTATION (exit 10 blocks ago, other token)
    """
    return [
        ev("0xa", "0xt2", "BUY", 150, "0xtxb", 50),
        ev("0xa", "0xt1", "BUY", 200, "0xtxa", 100),
        ev("0xb", "0xt1", "BUY", 300, "0xtxc", 50),
        ev("0xb", "0xt1", "BUY", 400, "0xtxd", 25),
        ev("0xb", "0xt1", "SELL", 500, "0xtxe", 37.5),
        ev("0xb", "0xt1", "SELL", 600, "0xtxf", 40),
        ev("0xb", "0xt2", "BUY", 610, "0xtxg", 30),
    ]


async def make_feed_db(pools, points, events):
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        for t in sorted({tok for _p, tok in pools}):
            s.add(Token(address=t, symbol=t.upper(), name=f"Token {t}"))
        for w in sorted({e.wallet_address for e in events}):
            s.add(Wallet(address=w))
        for pool, tok in pools:
            s.add(Pool(address=pool, token_address=tok, dex="test"))
        for pool, block, price in points:
            s.add(PricePoint(pool_address=pool, block_num=block,
                             ts=ts(block), price_usd=price))
        for e in events:
            s.add(e)
        await s.commit()
    return factory, engine


async def run_backfill(pools, points, events, ranked_lookup=None,
                       start_block=None, end_block=None):
    factory, engine = await make_feed_db(pools, points, events)
    try:
        async with factory() as s:
            count = await backfill(s, ranked_lookup=ranked_lookup,
                                   start_block=start_block, end_block=end_block)
            rows = (await s.execute(
                select(FeedEvent).order_by(FeedEvent.ts, FeedEvent.id))).scalars().all()
        return count, rows
    finally:
        await engine.dispose()


# ---------------- deterministic ids ----------------

def test_make_event_id_deterministic():
    a = make_event_id(54418923, "0xABC", 3)
    assert a == make_event_id(54418923, "0xabc", 3)  # case-normalized
    assert a == f"evt_{settings.chain_id}_54418923_0xabc_3"
    assert make_event_id(1, "0xa", 0) != make_event_id(2, "0xa", 0)
    assert make_event_id(1, "0xa", 0) != make_event_id(1, "0xb", 0)
    assert make_event_id(1, "0xa", 0) != make_event_id(1, "0xa", 1)


# ---------------- freshness bands (§6.9, spec §11: 30s/10min/3h/40h) --------

@pytest.mark.parametrize("age,band", [
    (0, "just_now"), (30, "just_now"), (59.9, "just_now"),
    (60, "minutes"), (600, "minutes"), (899, "minutes"),
    (900, "hours"), (7199, "hours"),
    (7200, "stale_today"), (86399, "stale_today"),
    (86400, "stale"), (200_000, "stale"),
])
def test_freshness_band(age, band):
    assert freshness_band(age) == band


# ---------------- taxonomy typing (§6.3) ----------------

@pytest.mark.asyncio
async def test_event_typing_taxonomy():
    count, rows = await run_backfill(POOLS, POINTS, scenario_events())
    assert count == 7
    got = {(r.wallet_address, r.block): r.type for r in rows}
    assert got == {
        ("0xa", 150): "CALL",
        ("0xa", 200): "CALL",
        ("0xb", 300): "ENTRY",
        ("0xb", 400): "ADD",
        ("0xb", 500): "TRIM",
        ("0xb", 600): "EXIT",
        ("0xb", 610): "ROTATION",
    }


@pytest.mark.asyncio
async def test_small_trims_and_tops_emit_nothing():
    # +10% top-up and a 10% trim are below the §6.3 thresholds → no events
    events = [
        ev("0xa", "0xt1", "BUY", 200, "0xtxa", 100),
        ev("0xa", "0xt1", "BUY", 300, "0xtxb", 10),    # 10% < ADD 25%
        ev("0xa", "0xt1", "SELL", 400, "0xtxc", 11),   # 10% < TRIM 20%
    ]
    count, rows = await run_backfill(POOLS, POINTS, events)
    assert count == 1
    assert rows[0].type == "CALL" and rows[0].block == 200


# ---------------- idempotency + determinism across replays ----------------

@pytest.mark.asyncio
async def test_double_backfill_is_idempotent():
    factory, engine = await make_feed_db(POOLS, POINTS, scenario_events())
    try:
        async with factory() as s:
            count1 = await backfill(s)
            rows1 = (await s.execute(
                select(FeedEvent).order_by(FeedEvent.ts, FeedEvent.id))).scalars().all()
            count2 = await backfill(s)
            rows2 = (await s.execute(
                select(FeedEvent).order_by(FeedEvent.ts, FeedEvent.id))).scalars().all()
    finally:
        await engine.dispose()
    assert count1 == 7
    assert count2 == 0  # replay adds zero duplicates
    assert len(rows2) == 7
    assert {r.id for r in rows1} == {r.id for r in rows2}
    for r in rows2:  # deterministic format evt_{chain}_{block}_{tx}_{idx}
        assert r.id.startswith(f"evt_{settings.chain_id}_{r.block}_{r.tx_hash}_")


@pytest.mark.asyncio
async def test_backfill_block_range_only_emits_inside_window():
    # replay still sees FULL history → TRIM at 500 keeps its type
    count, rows = await run_backfill(POOLS, POINTS, scenario_events(), start_block=500)
    assert count == 3
    assert {r.block: r.type for r in rows} == {500: "TRIM", 600: "EXIT", 610: "ROTATION"}


# ---------------- payload honesty (§6.2: null stays null, proof mandatory) --

@pytest.mark.asyncio
async def test_payload_shape_and_honest_nulls():
    count, rows = await run_backfill(POOLS, POINTS, scenario_events())
    assert count == 7
    by_key = {(r.wallet_address, r.block): r for r in rows}

    entry = by_key[("0xb", 300)]
    p = json.loads(entry.payload)
    assert p["id"] == entry.id and p["type"] == "ENTRY"
    assert p["action"]["side"] == "buy" and p["action"]["is_first_touch"] is True
    assert p["action"]["amount_usd"] == 50.0          # 50 tokens × series price 1.0
    assert p["action"]["position_after"]["avg_entry_usd"] == 1.0
    assert p["proof"]["tx_url"].endswith("/tx/0xtxc")  # proof mandatory
    assert "price_points" in p["proof"]["derivation"]
    assert p["token"]["market_cap_usd"] is None        # never a guess
    assert p["token"]["age_hours"] is None             # discovery time ≠ age
    assert p["wallet"]["rank"] is None                 # no ranked lookup passed
    assert p["wallet"]["tier"] is None                 # tiering ships in M6
    assert p["lag_seconds"] >= 0

    add = json.loads(by_key[("0xb", 400)].payload)
    assert add["confidence"] == {"score": None, "reasons": []}  # nothing known → null

    rot = json.loads(by_key[("0xb", 610)].payload)
    assert rot["context"]["rotation"]["blocks_after_exit"] == 10
    assert rot["context"]["rotation"]["exit_tx_hash"] == "0xtxf"


@pytest.mark.asyncio
async def test_unpriced_swap_stays_null():
    events = scenario_events() + [ev("0xc", "0xt3", "BUY", 700, "0xtxh", 10)]
    count, rows = await run_backfill(POOLS, POINTS, events)
    assert count == 8
    row = next(r for r in rows if r.wallet_address == "0xc")
    p = json.loads(row.payload)
    assert p["action"]["price_usd"] is None
    assert p["action"]["amount_usd"] is None
    assert p["action"]["position_after"]["size_usd"] is None


@pytest.mark.asyncio
async def test_ranked_lookup_flows_into_payload_and_confidence():
    ranked = {"0xa": {"rank": 1, "composite_score": 35.49, "tier": None,
                      "verdict": "verified", "style": "scalper",
                      "risk_flags": ["SINGLE_TOKEN_SAMPLE"],
                      "cluster_id": None, "label": None}}
    count, rows = await run_backfill(POOLS, POINTS, scenario_events(),
                                     ranked_lookup=ranked)
    row = next(r for r in rows if r.wallet_address == "0xa")
    p = json.loads(row.payload)
    assert p["wallet"]["rank"] == 1
    assert p["wallet"]["verdict"] == "verified"
    assert p["wallet"]["risk_flags"] == ["SINGLE_TOKEN_SAMPLE"]
    # verified +0.40, CALL +0.15, first touch +0.10 → 0.65 with reasons
    assert p["confidence"]["score"] == 0.65
    assert p["confidence"]["reasons"] == ["verified_wallet", "first_call", "first_touch"]


@pytest.mark.asyncio
async def test_no_proof_no_row():
    count, rows = await run_backfill(
        POOLS, POINTS, [ev("0xa", "0xt1", "BUY", 200, "", 10)])
    assert count == 0 and rows == []
