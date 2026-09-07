"""Unit tests for the wallet classifier (docs/WALLET_TAXONOMY.md).

Pure in-memory: aiosqlite :memory: DB + tmp_path fixture files. No network.
"""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.analyze.wallet_classifier import classify_all_wallets, primary_type
from src.db.models import (
    Base,
    Pool,
    PricePoint,
    SwapEvent,
    Token,
    Wallet,
    WalletLabel,
    WalletScore,
)

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def ts(block: int) -> datetime:
    """Deterministic mapping block → timestamp (1 block = 1 second)."""
    return T0 + timedelta(seconds=block)


def ev(wallet, token, side, block, tx, amount=100.0):
    return SwapEvent(wallet_address=wallet, token_address=token, side=side,
                     block_num=block, ts=ts(block), token_amount=amount, tx_hash=tx)


async def make_db(pools, points, events, scores=()):
    """pools: [(pool_addr, token)], points: [(pool_addr, first_block)],
    events: [SwapEvent], scores: [(wallet, cluster_id)]."""
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        tokens = {t for _p, t in pools}
        for t in sorted(tokens):
            s.add(Token(address=t, symbol=t.upper()))
        for w in sorted({e.wallet_address for e in events} |
                        {w for w, _c in scores}):
            s.add(Wallet(address=w))
        for pool, token in pools:
            s.add(Pool(address=pool, token_address=token, dex="test"))
        for pool, block in points:
            s.add(PricePoint(pool_address=pool, block_num=block,
                             ts=ts(block), price_usd=1.0))
        for e in events:
            s.add(e)
        for w, cid in scores:
            s.add(WalletScore(wallet_address=w, cluster_id=cid))
        await s.commit()
    return factory, engine


async def run(tmp_path, pools, points, events, ranked=None, scores=(), files=None):
    for name, payload in (files or {}).items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    factory, engine = await make_db(pools, points, events, scores)
    try:
        async with factory() as session:
            counts = await classify_all_wallets(session, ranked=ranked,
                                                results_dir=tmp_path)
            rows = {
                w: sorted(r.label for r in (await session.execute(
                    select(WalletLabel).where(WalletLabel.wallet_address == w)))
                    .scalars().all())
                for w in {e.wallet_address for e in events}
            }
        out = json.loads((tmp_path / "wallet_labels.json").read_text(encoding="utf-8"))
        return counts, rows, out
    finally:
        await engine.dispose()


# ---------------- DEV_SERIAL_RUGGER (#1) ----------------

@pytest.mark.asyncio
async def test_dev_serial_rugger(tmp_path):
    events = []
    pools, points = [], []
    for i in range(1, 6):  # 5 tokens: first buyer at +1 block, full flip in 19 s
        token, pool = f"0xtok{i}", f"0xpool{i}"
        pools.append((pool, token))
        points.append((pool, 1000 * i))
        events += [
            ev("0xdev", token, "BUY", 1000 * i + 1, f"0xbuy{i}"),
            ev("0xdev", token, "SELL", 1000 * i + 20, f"0xsell{i}"),
        ]
    counts, rows, out = await run(tmp_path, pools, points, events)
    assert "DEV_SERIAL_RUGGER" in rows["0xdev"]
    assert "SNIPER" in rows["0xdev"]  # +1 block also sniped — labels coexist
    assert out["wallets"]["0xdev"]["primary_type"] == "DEV_SERIAL_RUGGER"
    evd = out["wallets"]["0xdev"]["evidence"]["DEV_SERIAL_RUGGER"]
    assert evd["first_buyer_tokens_le_50_blocks"] == 5
    assert evd["sample"][0]["pool_first_block"] == 1000  # real block cited
    assert counts["primary_types"]["DEV_SERIAL_RUGGER"] == 1


# ---------------- DEV (#2) ----------------

@pytest.mark.asyncio
async def test_dev_first_buyer_with_fast_flip(tmp_path):
    pools, points, events = [], [], []
    for i in (1, 2):  # first buyer at +100 blocks (early, not sniper) + flip
        token, pool = f"0xtok{i}", f"0xpool{i}"
        pools.append((pool, token))
        points.append((pool, 1000))
        events += [
            ev("0xdev", token, "BUY", 1000 + 100, f"0xbuy{i}"),
            ev("0xdev", token, "SELL", 1100 + 60, f"0xsell{i}"),
        ]
    _c, rows, out = await run(tmp_path, pools, points, events)
    assert rows["0xdev"] == ["DEV"]  # +100 blocks is early but no sniper window
    assert out["wallets"]["0xdev"]["primary_type"] == "DEV"
    assert "DEV_SERIAL_RUGGER" not in rows["0xdev"]


# ---------------- BUNDLER_SUSPECT (#3) + SNIPER priority ----------------

@pytest.mark.asyncio
async def test_bundler_same_tx_five_wallets(tmp_path):
    pools = [("0xp1", "0xt1")]
    points = [("0xp1", 1000)]
    events = [ev(f"0xb{i}", "0xt1", "BUY", 1000, "0xbundletx", amount=10)
              for i in range(5)]
    events.append(ev("0xsolo", "0xt1", "BUY", 1002, "0xsolotx", amount=10))
    _c, rows, out = await run(tmp_path, pools, points, events)
    for i in range(5):
        w = f"0xb{i}"
        assert "BUNDLER_SUSPECT" in rows[w]
        assert "SNIPER" in rows[w]  # bundle landed at pool creation block 0
        assert out["wallets"][w]["primary_type"] == "BUNDLER_SUSPECT"
    evd = out["wallets"]["0xb0"]["evidence"]["BUNDLER_SUSPECT"]
    assert evd["tx_hash"] == "0xbundletx" and evd["distinct_wallets"] == 5
    assert evd["block"] == 1000
    assert rows["0xsolo"] == ["SNIPER"]
    assert out["wallets"]["0xsolo"]["primary_type"] == "SNIPER"


# ---------------- SNIPER (#4) ----------------

@pytest.mark.asyncio
async def test_sniper_within_10_blocks(tmp_path):
    pools = [("0xp1", "0xt1")]
    points = [("0xp1", 5000)]
    events = [
        ev("0xsniper", "0xt1", "BUY", 5005, "0xs1"),   # delta 5 ≤ 10
        ev("0xlate", "0xt1", "BUY", 5200, "0xs2"),     # delta 200
    ]
    _c, rows, out = await run(tmp_path, pools, points, events)
    assert "SNIPER" in rows["0xsniper"]
    assert "SNIPER" not in rows["0xlate"]
    snipe = out["wallets"]["0xsniper"]["evidence"]["SNIPER"]["snipes"][0]
    assert snipe["delta_blocks"] == 5


# ---------------- INSIDER (#5) ----------------

@pytest.mark.asyncio
async def test_insider_sells_token_never_bought(tmp_path):
    pools = [("0xpA", "0xtA"), ("0xpB", "0xtB")]
    points = [("0xpA", 4500), ("0xpB", 4500)]
    events = [
        ev("0xins", "0xtA", "BUY", 5000, "0xi1"),    # has a real buy elsewhere
        ev("0xins", "0xtB", "SELL", 5001, "0xi2"),   # sells a token never bought
        ev("0xpure", "0xtA", "SELL", 5002, "0xi3"),  # pure receiver-dumper
    ]
    _c, rows, out = await run(tmp_path, pools, points, events)
    assert "INSIDER" in rows["0xins"]
    assert "AIRDROP_FARMER" not in rows["0xins"]
    assert out["wallets"]["0xins"]["evidence"]["INSIDER"]["tokens"] == ["0xtB"]
    # pure receiver: AIRDROP_FARMER port + INSIDER both stick (primary = INSIDER,
    # priority 5 beats 9)
    assert "AIRDROP_FARMER" in rows["0xpure"]
    assert "INSIDER" in rows["0xpure"]
    assert out["wallets"]["0xpure"]["primary_type"] == "INSIDER"


# ---------------- AIRDROP_FARMER (#9, anti_gaming port) ----------------

@pytest.mark.asyncio
async def test_airdrop_farmer_zero_buys(tmp_path):
    pools = [("0xp1", "0xt1"), ("0xp2", "0xt2")]
    points = [("0xp1", 100), ("0xp2", 100)]
    events = [
        ev("0xfarm", "0xt1", "SELL", 200, "0xf1"),
        ev("0xfarm", "0xt2", "SELL", 300, "0xf2"),
    ]
    _c, rows, _out = await run(tmp_path, pools, points, events)
    assert "AIRDROP_FARMER" in rows["0xfarm"]


# ---------------- CLUSTER_MEMBER (#8) ----------------

@pytest.mark.asyncio
async def test_cluster_member_from_capture_and_forensics(tmp_path):
    pools = [("0xp1", "0xt1")]
    points = [("0xp1", 100)]
    trio = [f"0xfunded{i}" for i in (1, 2, 3)]
    events = [ev(w, "0xt1", "BUY", 200 + i, f"0xc{i}") for i, w in enumerate(trio)]
    events += [ev("0xcluster1111111111111111111111111111111111", "0xt1", "BUY", 210, "0xc9"),
               ev("0xtrunc0000000000000000000000000000000099", "0xt1", "BUY", 211, "0xc10")]

    files = {
        "funder_clusters.json": {
            "cluster_id": "cluster_f70d",
            "funder": {"address": "0xf70da97812cb96acdf810712aa562db8dfa3dbef"},
            "funded_wallets": 26,
            "top38_members_funded_by_cluster": [
                "0xcluster1111111111111111111111111111111111",   # full match
                "0xtrunc00000000000000000000000000000000…",      # truncated capture
            ],
        },
        "funding_forensics.json": {
            "wallets": [
                {"wallet": w.upper(), "funding": {"funder": "0xfeedaabbccddeeff001122334455667788990011"},
                 "dev_fingerprint": {}}
                for w in trio
            ],
        },
    }
    _c, rows, out = await run(tmp_path, pools, points, events, files=files)

    # capture file: exact + prefix-truncated matches → cluster_f70d
    assert "CLUSTER_MEMBER:cluster_f70d" in rows["0xcluster1111111111111111111111111111111111"]
    assert "CLUSTER_MEMBER:cluster_f70d" in rows["0xtrunc0000000000000000000000000000000099"]
    # forensics file: 3 wallets sharing one funder → derived funding cluster
    for w in trio:
        assert "CLUSTER_MEMBER:cluster_feed" in rows[w], rows[w]
    assert out["wallets"][trio[0]]["primary_type"].startswith("CLUSTER_MEMBER:")
    evd = out["wallets"][trio[0]]["evidence"]["CLUSTER_MEMBER:cluster_feed"]
    assert evd["funder"] == "0xfeedaabbccddeeff001122334455667788990011"
    assert evd["member_count"] == 3


@pytest.mark.asyncio
async def test_cluster_member_from_token_overlap_score(tmp_path):
    pools = [("0xp1", "0xt1")]
    points = [("0xp1", 100)]
    events = [ev("0xsyb", "0xt1", "BUY", 150, "0xs1")]
    _c, rows, _out = await run(tmp_path, pools, points, events,
                               scores=[("0xsyb", "cluster_0xsyb11")])
    assert "CLUSTER_MEMBER:cluster_0xsyb11" in rows["0xsyb"]


# ---------------- SMART_TRACKER (#10, via ranked verifier verdict) ---------

@pytest.mark.asyncio
async def test_smart_tracker_requires_verified_verdict(tmp_path):
    pools = [("0xp1", "0xt1")]
    points = [("0xp1", 100)]
    events = [ev("0xsmart", "0xt1", "BUY", 9000, "0xs1")]
    ranked = [
        SimpleNamespace(wallet_address="0xsmart", verification={"verdict": "verified"},
                        composite_score=42.0, rank=3),
        SimpleNamespace(wallet_address="0xfail", verification={"verdict": "unverified"},
                        composite_score=99.0, rank=1),
    ]
    _c, rows, out = await run(tmp_path, pools, points, events, ranked=ranked)
    assert "SMART_TRACKER" in rows["0xsmart"]
    assert out["wallets"]["0xsmart"]["primary_type"] == "SMART_TRACKER"
    assert "0xfail" not in out["wallets"]


# ---------------- CT_ATTRIBUTED (#7, interim leaderboard capture) ----------

@pytest.mark.asyncio
async def test_ct_attributed_from_leaderboard_capture(tmp_path):
    pools = [("0xp1", "0xt1")]
    points = [("0xp1", 100)]
    events = [ev("0xctwallet", "0xt1", "BUY", 8000, "0xs1")]
    files = {
        "external_leaderboards.json": {
            "sources": {"gmgn_smartmoney_30d": {"code": 0, "data": {"rank": [
                {"address": "0xctwallet", "twitter_username": "vali_eth", "name": "Vali"},
            ]}}},
        },
    }
    _c, rows, out = await run(tmp_path, pools, points, events, files=files)
    assert "CT_ATTRIBUTED" in rows["0xctwallet"]
    assert out["wallets"]["0xctwallet"]["evidence"]["CT_ATTRIBUTED"]["twitter_username"] == "vali_eth"


# ---------------- MEV_BOT (#13) ----------------

@pytest.mark.asyncio
async def test_mev_bot_machinegun_roundtrips(tmp_path):
    pools = [("0xp1", "0xt1")]
    points = [("0xp1", 1)]
    events = [ev("0xearlier", "0xt1", "BUY", 2, "0xe0")]  # eats the first-buyer slot
    for i in range(30):
        events += [
            ev("0xmev", "0xt1", "BUY", 100 + i * 10, f"0xm{i}", amount=10),
            ev("0xmev", "0xt1", "SELL", 100 + i * 10 + 1, f"0xn{i}", amount=10),
        ]
    _c, rows, out = await run(tmp_path, pools, points, events)
    assert "MEV_BOT" in rows["0xmev"]
    assert out["wallets"]["0xmev"]["evidence"]["MEV_BOT"]["round_trips"] == 30
    assert "DEV" not in rows["0xmev"]  # not the first buyer → no dev fingerprint


# ---------------- GENERALIST (#14) ----------------

@pytest.mark.asyncio
async def test_generalist_fallback(tmp_path):
    pools = [("0xp1", "0xt1")]
    points = [("0xp1", 100)]
    events = [
        ev("0xearly", "0xt1", "BUY", 101, "0xg0"),
        ev("0xnorm", "0xt1", "BUY", 90000, "0xg1"),
    ]
    _c, rows, out = await run(tmp_path, pools, points, events)
    assert rows["0xnorm"] == ["GENERALIST"]
    assert out["wallets"]["0xnorm"]["primary_type"] == "GENERALIST"


# ---------------- persistence + export shape ----------------

@pytest.mark.asyncio
async def test_labels_persisted_and_export_shape(tmp_path):
    pools = [("0xp1", "0xt1")]
    points = [("0xp1", 1000)]
    events = [
        ev("0xsniper", "0xt1", "BUY", 1003, "0xp0"),
        ev("0xwhale", "0xt1", "BUY", 70000, "0xp1"),
    ]
    counts, rows, out = await run(tmp_path, pools, points, events)
    assert counts["wallets_classified"] == 2
    assert counts["labels_assigned"] == len(rows["0xsniper"]) + len(rows["0xwhale"])
    for wallet, payload in out["wallets"].items():
        assert set(payload) >= {"primary_type", "labels", "evidence"}
        assert payload["primary_type"] == primary_type(payload["labels"])
        assert isinstance(payload["evidence"], dict)
    # evidence cites real on-chain blocks from the DB
    evd = out["wallets"]["0xsniper"]["evidence"]["SNIPER"]
    assert evd["snipes"][0]["buy_block"] == 1003
    assert evd["snipes"][0]["pool_first_block"] == 1000


def test_primary_type_priority_order():
    assert primary_type({"SNIPER", "BUNDLER_SUSPECT"}) == "BUNDLER_SUSPECT"
    assert primary_type({"AIRDROP_FARMER", "INSIDER"}) == "INSIDER"
    assert primary_type({"CLUSTER_MEMBER:cluster_f70d", "MEV_BOT"}) == \
        "CLUSTER_MEMBER:cluster_f70d"
    assert primary_type(set()) == "GENERALIST"
    assert primary_type({"SMART_TRACKER"}) == "SMART_TRACKER"
