"""Tests for the Whale Entry Map (conviction rule)."""
from src.analyze.whale_map import Entrant, compute_whale_entry_map


def ent(wallet, vwap, size):
    return Entrant(wallet=wallet, vwap_entry_price=vwap, cost_basis_usd=size)


def test_strong_conviction_whales_above_us():
    # 8 whales all entered ABOVE current price → we are early with underwater whales
    entrants = [ent(f"0x{i}", vwap=2.0, size=10_000) for i in range(8)]
    m = compute_whale_entry_map("0xtok", entrants, current_price_usd=1.0)
    assert m.verdict in ("STRONG", "MIXED")
    assert m.pct_whales_at_or_above_current == 1.0
    assert m.whale_avg_entry_price == 2.0
    assert m.conviction_score > 60


def test_danger_whales_far_below_us():
    # all whales entered at 1/10th of current → we are the exit liquidity
    entrants = [ent(f"0x{i}", vwap=0.1, size=10_000) for i in range(8)]
    m = compute_whale_entry_map("0xtok", entrants, current_price_usd=1.0)
    assert m.verdict == "DANGER"
    assert m.pct_whales_at_or_above_current == 0.0
    assert m.conviction_score == 0.0


def test_jumbo_above_amplifies():
    mixed = [ent("0xa", 2.0, 50_000)] + [ent(f"0x{i}", 0.5, 1_000) for i in range(9)]
    m = compute_whale_entry_map("0xtok", mixed, current_price_usd=1.0)
    # one jumbo (50k vs median 1k = 50x) underwater whale → jumbo_above_current = 1
    assert m.jumbo_above_current == 1
    assert m.verdict in ("MIXED", "STRONG")


def test_insufficient_data():
    entrants = [ent("0xa", 2.0, 10_000), ent("0xb", 2.0, 10_000)]
    m = compute_whale_entry_map("0xtok", entrants, current_price_usd=1.0)
    assert m.verdict == "INSUFFICIENT_DATA"
    assert compute_whale_entry_map("0xtok", entrants, None) is None
