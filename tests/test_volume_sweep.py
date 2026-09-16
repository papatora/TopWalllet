"""Volume sweep unit tests — tagging state machine (bot.js port),
symbol dedupe, and on-chain transfer classification. No network."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.volume_sweep import (TagState, classify_transfers,
                                  dedupe_by_symbol_keep_highest_volume,
                                  token_key)

FLOOR = 100_000.0
TROUGH = 350_000.0
SUSTAIN_MS = 45 * 60_000


def st():
    return TagState()


# ---------------- tag gate: FIRST ----------------

def test_first_below_floor_no_tag():
    t = st()
    assert t.evaluate("k", 99_999, 1000) is None
    assert "k" not in t.tags


def test_first_at_floor_fires():
    t = st()
    assert t.evaluate("k", FLOOR, 1000) == "first"
    t.commit("k", FLOOR, 1000)
    assert t.tags["k"] == FLOOR


# ---------------- DOUBLE ----------------

def test_double_requires_2x_anchor():
    t = st()
    t.commit("k", 500_000, 0)
    assert t.evaluate("k", 900_000, 1) is None      # < 2x
    assert t.evaluate("k", 1_000_000, 2) == "double"  # >= 2x


def test_double_above_floor_only():
    t = st()
    t.commit("k", 500_000, 0)
    assert t.evaluate("k", 2_000_000, 1) == "double"


# ---------------- TROUGH ----------------

def test_trough_fires_when_dip_reaches_reset_zone():
    t = st()
    t.commit("k", 500_000, 0)
    # dip to 120k (above floor, <= trough reset, below anchor) = genuine drop
    assert t.evaluate("k", 120_000, 1) == "trough"


def test_trough_no_fire_when_dip_stays_above_reset():
    t = st()
    t.commit("k", 500_000, 0)
    assert t.evaluate("k", 400_000, 1) is None
    assert t.troughs["k"] == 400_000


def test_fresh_tag_between_floor_and_trough_does_not_refire():
    # floor(100K) < trough(350K): a token tagged at 150K must NOT instantly
    # re-fire 'trough' — nothing dropped below its anchor yet
    t = st()
    t.commit("k", 150_000, 0)
    assert t.evaluate("k", 150_000, 1) is None
    assert t.evaluate("k", 250_000, 2) is None       # < 2x anchor, no drop


def test_trough_below_floor_does_not_refire_until_back():
    t = st()
    t.commit("k", 500_000, 0)
    assert t.evaluate("k", 80_000, 1) is None        # below floor → hot reset, no fire
    assert t.evaluate("k", 120_000, 2) == "trough"   # trough 80k <= 350k, back >= floor


def test_no_trough_when_volume_never_drops():
    t = st()
    t.commit("k", 500_000, 0)
    assert t.evaluate("k", 600_000, 1) is None
    assert t.evaluate("k", 700_000, 2) is None
    assert t.troughs["k"] == 500_000


# ---------------- SUSTAIN ----------------

def test_sustain_after_continuous_hot_window():
    t = st()
    t.commit("k", 1_000_000, 0)
    assert t.evaluate("k", 1_000_000, 44 * 60_000) is None
    assert t.evaluate("k", 1_000_000, SUSTAIN_MS) == "sustain"


def test_sustain_window_restarts_after_fire_commit():
    t = st()
    t.commit("k", 1_000_000, 0)
    assert t.evaluate("k", 1_000_000, SUSTAIN_MS) == "sustain"
    t.commit("k", 1_000_000, SUSTAIN_MS)             # caller commits on fire
    assert t.evaluate("k", 1_000_000, SUSTAIN_MS + 60_000) is None
    assert t.evaluate("k", 1_000_000, 2 * SUSTAIN_MS) == "sustain"


def test_dip_below_floor_deletes_hot_timer():
    t = st()
    t.commit("k", 1_000_000, 0)
    assert t.evaluate("k", 90_000, 1000) is None
    assert "k" not in t.hot                          # hot streak reset


def test_commit_resets_anchor_trough_and_hot():
    t = st()
    t.commit("k", 500_000, 0)
    t.evaluate("k", 120_000, 1)                      # trough dips
    t.commit("k", 400_000, 2)                        # fires double? no — manual commit
    assert t.tags["k"] == 400_000
    assert t.troughs["k"] == 400_000                 # trough reset (bot.js semantics)
    assert t.hot["k"] == 2
    assert t.evaluate("k", 500_000, 3) is None       # old trough must not refire


# ---------------- symbol dedupe ----------------

def test_dedupe_keeps_highest_volume_per_symbol():
    items = [
        {"symbol": "DOGE", "address": "0x" + "a" * 40, "volume": 100},
        {"symbol": "DOGE", "address": "0x" + "b" * 40, "volume": 900},
        {"symbol": "PEPE", "address": "0x" + "c" * 40, "volume": 500},
    ]
    out = dedupe_by_symbol_keep_highest_volume(items)
    addrs = {i["address"] for i in out}
    assert addrs == {"0x" + "b" * 40, "0x" + "c" * 40}


# ---------------- transfer classification ----------------

def _tx(blocks, n_recipients=1, tx=None):
    """Build ascending Blockscout-shaped transfers: mint->dev at b0 then
    n_recipients buyers per block."""
    rows = []
    txn = tx
    for b in blocks:
        for i in range(n_recipients):
            if txn is None:
                txn = f"0x{b:064x}"
            rows.append({
                "from": {"hash": "0x" + "1" * 40},
                "to": {"hash": f"0x{b:02x}{i:02x}" + "2" * 36},
                "block_number": b,
                "transaction_hash": txn,
            })
    return rows


def test_classify_sniper_early_late():
    rows = _tx([100], n_recipients=1)            # mint/dev seeding at b0=100
    rows += _tx([102], n_recipients=3)           # <= b0+10 → sniper
    rows += _tx([250], n_recipients=3)           # <= b0+300 → early
    rows += _tx([1000, 1010, 1011, 1012], n_recipients=3)  # late zone
    cls = classify_transfers(rows)
    assert cls["b0"] == 100 and cls["b1"] == 1012
    sniper_expected = {f"0x66{i:02x}" + "2" * 36 for i in range(3)}
    assert sniper_expected <= set(cls["sniper"])
    early_expected = {f"0xfa{i:02x}" + "2" * 36 for i in range(3)}
    assert early_expected <= set(cls["early"])
    late_expected = {f"0x{b:02x}{i:02x}" + "2" * 36
                     for b in (1000, 1010, 1011, 1012) for i in range(3)}
    assert late_expected <= set(cls["late"])


def test_classify_bundle_same_tx():
    same = "0x" + "f" * 64
    rows = _tx([100], n_recipients=1)
    rows += [{"from": {"hash": "0x" + "1" * 40},
              "to": {"hash": f"0x{100 + i:02x}aa" + "2" * 36},
              "block_number": 105, "transaction_hash": same}
             for i in range(5)]                  # 5 wallets, one tx, early
    cls = classify_transfers(rows)
    assert cls["bundles"] == [same]


def test_classify_excludes_pool_like_recipient():
    pool = "0x" + "9" * 40
    rows = []
    for b in range(100, 140):
        rows.append({"from": {"hash": "0x" + "1" * 40},
                     "to": {"hash": pool},
                     "block_number": b,
                     "transaction_hash": f"0x{b:064x}"})
    rows += _tx([150], n_recipients=5)
    cls = classify_transfers(rows)
    assert pool in cls["excluded"]
    assert all(a != pool for a in cls["sniper"] + cls["early"])


def test_classify_empty():
    cls = classify_transfers([])
    assert cls["b0"] == 0 and cls["sniper"] == []


def test_key_format():
    assert token_key("robinhood", "0xABC") == "robinhood:0xabc"
