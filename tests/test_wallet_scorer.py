"""Unit tests for wallet metrics + composite scoring.

Key thesis check: a consistent multi-token winner must outrank a one-hit
wonder with the same max multiple.
"""
from datetime import datetime, timezone

from config.settings import settings
from src.analyze.position_calculator import CalcPosition
from src.analyze.wallet_scorer import composite_score, compute_metrics, trading_style

WEIGHTS = settings.load_weights()
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def pos(token, mult, size=100.0, closed=True, entry_pctile=0.5, exit_pctile=0.5, hours=24.0,
        entry_day=1):
    entry = datetime(2026, 6, entry_day, tzinfo=timezone.utc)
    return CalcPosition(
        wallet="0xw", token=token,
        status="closed" if closed else "open",
        entry_ts=entry, exit_ts=entry if not closed else datetime(2026, 6, entry_day + 1, tzinfo=timezone.utc),
        entry_block=entry_day * 100, exit_block=(entry_day + 1) * 100 if closed else None,
        entry_price_usd=1.0, exit_price_usd=mult if closed else 2.0,
        size_usd=size, pnl_usd=(mult - 1) * size if closed else None,
        return_multiple=mult if closed else (mult if mult else None),
        hold_hours=hours, entry_pctile=entry_pctile, exit_pctile=exit_pctile,
    )


def test_metrics_basic():
    positions = [
        pos("0xa", 10.0, entry_pctile=0.1, exit_pctile=0.9),
        pos("0xb", 2.0, entry_pctile=0.2, exit_pctile=0.8),
        pos("0xc", 0.5, entry_pctile=0.9, exit_pctile=0.1),  # loser
        pos("0xd", 3.0),
        pos("0xe", 1.5),
    ]
    m = compute_metrics(positions, WEIGHTS, now=NOW)
    assert m is not None
    assert m.total_positions == 5
    assert m.winning_positions == 4
    assert m.win_rate == 0.8
    assert m.median_return_multiple == 2.0
    assert m.max_return_multiple == 10.0
    assert m.distinct_tokens == 5
    assert m.dip_buying_accuracy == 0.4  # 0.1, 0.2 qualify ≤0.2; 0.9, 0.5, 0.5 do not
    assert m.top_selling_accuracy == 0.4  # 0.9, 0.8 qualify ≥0.8; the rest do not


def test_low_data_wallet_returns_none():
    assert compute_metrics([pos("0xa", 10.0), pos("0xb", 2.0)], WEIGHTS, now=NOW) is None
    # 6 positions but only 2 distinct tokens → still insufficient
    many = [pos("0xa", 1.5) for _ in range(6)]
    assert compute_metrics(many, WEIGHTS, now=NOW) is None


def test_consistent_winner_beats_one_hit_wonder():
    consistent = [
        pos(f"0x{i}", 12.0, entry_pctile=0.1, exit_pctile=0.9) for i in range(6)
    ]
    one_hit = [pos("0xonly", 500.0)] + [pos(f"0xj{i}", 0.6) for i in range(6)]
    m1 = compute_metrics(consistent, WEIGHTS, now=NOW)
    m2 = compute_metrics(one_hit, WEIGHTS, now=NOW)
    s1 = composite_score(m1, WEIGHTS)
    s2 = composite_score(m2, WEIGHTS)
    assert s1 > s2, f"consistent {s1} should beat one-hit {s2}"


def test_dip_buyer_style():
    positions = [pos(f"0x{i}", 5.0, entry_pctile=0.05, exit_pctile=0.85) for i in range(6)]
    m = compute_metrics(positions, WEIGHTS, now=NOW)
    style = trading_style(m, WEIGHTS)
    assert "dip_buyer" in style
