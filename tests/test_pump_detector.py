"""Tests for pump-first discovery (detect pumps, classify participants, find hunters)."""
from src.analyze.pump_detector import (
    Pump, classify_pump_participants, detect_pumps, multi_pump_hunters,
)


def series():
    # flat base (6 pts), 10x pump (7 pts), cool-down (3 pts) — 16 aligned points
    blocks = [1000 + i * 100 for i in range(16)]
    prices = [1.0, 1.05, 0.95, 1.0, 1.1, 0.98,
              1.5, 2.5, 4.0, 5.5, 7.0, 8.5, 10.0, 9.0, 8.0, 7.5]
    return blocks, prices


def test_detect_pumps_finds_10x():
    blocks, prices = series()
    pumps = detect_pumps(blocks, prices, min_gain_pct=50)
    assert len(pumps) >= 1
    p = pumps[0]
    assert p.peak_price / p.start_price >= 5
    assert p.peak_block > p.start_block


def test_no_pump_in_flat_series():
    blocks = list(range(100, 100 + 50, 10))
    prices = [1.0] * 50
    assert detect_pumps(blocks, prices, min_gain_pct=50) == []


def _buy(w, block, usd):
    return {"wallet": w, "block": block, "usd": usd}


def test_participant_categories():
    pump = Pump(start_block=1000, start_price=1.0, peak_block=2000, peak_price=10.0,
                gain_pct=900, duration_blocks=1000)
    buys = [
        _buy("0xaccum", 900, 500),          # before pump = ACCUMULATOR
        _buy("0xearly", 1050, 300),         # first 10% = EARLY_HUNTER
        _buy("0xmid", 1500, 200),           # MID_RIDER
        _buy("0xlate", 1950, 400),          # last 25% = LATE_CHASER
    ]
    parts = classify_pump_participants(pump, buys, [])
    cats = {p.wallet: p.category for p in parts}
    assert cats == {"0xaccum": "ACCUMULATOR", "0xearly": "EARLY_HUNTER",
                    "0xmid": "MID_RIDER", "0xlate": "LATE_CHASER"}


def test_multi_pump_hunter_ranking():
    by_pump = {
        "tokenA": [_mk("0xgold", "ACCUMULATOR", 100), _mk("0xlucky", "EARLY_HUNTER", 50)],
        "tokenB": [_mk("0xgold", "EARLY_HUNTER", 200)],
    }
    hunters = multi_pump_hunters(by_pump, min_pumps=2)
    assert hunters[0]["wallet"] == "0xgold" and hunters[0]["pumps_caught"] == 2
    assert all(h["wallet"] != "0xlucky" for h in hunters)  # 1 pump only


def _mk(wallet, cat, usd):
    from src.analyze.pump_detector import PumpParticipant
    return PumpParticipant(wallet, cat, 1000, usd, 0.0, 0.0)
