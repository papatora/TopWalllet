"""Unit tests for the FIFO position calculator (no network)."""
from datetime import datetime, timezone

from src.analyze.position_calculator import PricedEvent, build_positions


class StaticLookup:
    """Always reports the trade price at the 10th percentile of its window."""

    def window_prices(self, token, block, window_blocks):
        return [block / 100 + i for i in range(10)]

    def percentile(self, value, window):
        if not window:
            return None
        below = sum(1 for p in window if p < value)
        return below / len(window)


def ev(side, amount, price, block, token="0xtoken"):
    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return PricedEvent(token=token, side=side, token_amount=amount, price_usd=price,
                       ts=base, block_num=block)


def test_closed_position_multiple():
    # buy 100 @ 1.0 → sell 100 @ 10.0 → 10x closed position
    positions = build_positions("0xw", "0xtoken", [ev("BUY", 100, 1.0, 100), ev("SELL", 100, 10.0, 200)])
    assert len(positions) == 1
    p = positions[0]
    assert p.status == "closed"
    assert p.return_multiple == 10.0
    assert p.size_usd == 100.0
    assert p.pnl_usd == 900.0


def test_partial_sell_realizes_proportionally():
    # buy 100 @ 1.0, sell 50 @ 3.0 → realized 3x on 50 units, 50 left open
    positions = build_positions("0xw", "0xtoken", [ev("BUY", 100, 1.0, 100), ev("SELL", 50, 3.0, 200)])
    closed = [p for p in positions if p.status == "closed"]
    open_pos = [p for p in positions if p.status == "open"]
    assert len(closed) == 1 and closed[0].return_multiple == 3.0
    assert len(open_pos) == 1
    assert open_pos[0].size_usd == 50.0  # remaining cost basis


def test_open_position_uses_current_price():
    positions = build_positions("0xw", "0xtoken", [ev("BUY", 10, 1.0, 100)], current_price_usd=5.0)
    assert len(positions) == 1
    p = positions[0]
    assert p.status == "open"
    assert p.return_multiple == 5.0


def test_sell_without_buy_is_ignored():
    # selling tokens bought before the lookback window must not crash or fabricate
    positions = build_positions("0xw", "0xtoken", [ev("SELL", 100, 2.0, 100)])
    assert positions == []


def test_multi_roundtrip_accumulates():
    events = [
        ev("BUY", 10, 1.0, 100),
        ev("SELL", 10, 2.0, 150),   # 2x
        ev("BUY", 20, 4.0, 300),
        ev("SELL", 20, 12.0, 400),  # 3x
    ]
    positions = build_positions("0xw", "0xtoken", events)
    assert len(positions) == 2
    mults = sorted(p.return_multiple for p in positions)
    assert mults == [2.0, 3.0]


def test_timing_percentiles_attached():
    positions = build_positions(
        "0xw", "0xtoken", [ev("BUY", 10, 1.0, 100), ev("SELL", 10, 2.0, 150)],
        price_lookup=StaticLookup(),
    )
    assert positions[0].entry_pctile is not None
    assert positions[0].exit_pctile is not None
