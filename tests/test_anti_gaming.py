"""Unit tests for anti-gaming filters and clustering."""
from src.analyze.anti_gaming import apply_filters, cluster_wallets
from src.analyze.position_calculator import CalcPosition, PricedEvent
from src.analyze.wallet_scorer import compute_metrics
from config.settings import settings

WEIGHTS = settings.load_weights()
from datetime import datetime, timezone

NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def pos(token, mult, size=100.0, closed=True, entry_block=1000, exit_block=2000, hours=24.0):
    entry = datetime(2026, 6, 1, tzinfo=timezone.utc)
    return CalcPosition(
        wallet="0xw", token=token, status="closed" if closed else "open",
        entry_ts=entry, exit_ts=entry, entry_block=entry_block, exit_block=exit_block,
        entry_price_usd=1.0, exit_price_usd=mult, size_usd=size,
        pnl_usd=(mult - 1) * size, return_multiple=mult, hold_hours=hours,
        entry_pctile=0.5, exit_pctile=0.5,
    )


def buy_ev(token, block):
    return PricedEvent(token=token, side="BUY", token_amount=1.0, price_usd=1.0,
                       ts=NOW, block_num=block)


def test_low_data_excluded():
    positions = [pos("0xa", 2.0), pos("0xb", 1.5)]
    m = compute_metrics(positions, WEIGHTS, now=NOW)
    res = apply_filters(m, positions, [buy_ev("0xa", 1)], WEIGHTS)
    assert res.excluded and "LOW_DATA" in res.flags


def test_airdrop_farmer_excluded():
    positions = [pos(f"0x{i}", 1.2) for i in range(6)]
    m = compute_metrics(positions, WEIGHTS, now=NOW)
    res = apply_filters(m, positions, [], WEIGHTS)  # zero BUY events
    assert res.excluded and "AIRDROP_FARMER" in res.flags


def test_mev_bot_flagged():
    # 40 machine-gun round trips
    positions = [pos(f"0x{i % 4}", 1.05, hours=0.05, entry_block=i * 10,
                     exit_block=i * 10 + 1) for i in range(40)]
    m = compute_metrics(positions, WEIGHTS, now=NOW)
    res = apply_filters(m, positions, [buy_ev("0x1", 1)], WEIGHTS)
    assert "MEV_BOT" in res.flags
    assert not res.excluded  # flagged, scoring punishes via hold/recency


def test_wash_suspect_roundtrips():
    # 6 round trips of the same token within 30 blocks
    positions = [pos("0xsame", 1.1, entry_block=1000 + i * 100,
                     exit_block=1000 + i * 100 + 10, hours=0.2) for i in range(6)]
    positions += [pos(f"0xfiller{i}", 1.2) for i in range(4)]
    m = compute_metrics(positions, WEIGHTS, now=NOW)
    res = apply_filters(m, positions, [buy_ev("0x1", 1)], WEIGHTS)
    assert "WASH_SUSPECT" in res.flags


def test_clustering_tags_fleets():
    wallet_tokens = {
        "0xaaa": {"0xt1", "0xt2", "0xt3", "0xt4"},
        "0xaab": {"0xt1", "0xt2", "0xt3", "0xt4"},  # identical → cluster
        "0xaac": {"0xt1", "0xt2", "0xt3", "0xt5"},  # 80% overlap (>= 0.85? 4/5=0.8 <0.85 → no)
        "0xloner": {"0xzz1", "0xzz2"},
    }
    out = cluster_wallets(wallet_tokens, similarity=0.75)
    assert out.get("0xaaa") == out.get("0xaab") and out.get("0xaaa")
    assert "0xloner" not in out
