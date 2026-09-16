"""Volume sweep unit tests — tagging state machine (bot.js port incl. the
genuine-drop trough guard) and the CA queue. No network."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.volume_sweep import (TagState, dedupe_by_symbol_keep_highest_volume,
                                  queue_push, token_key)

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
    assert t.evaluate("k", 900_000, 1) is None        # < 2x
    assert t.evaluate("k", 1_000_000, 2) == "double"  # >= 2x


# ---------------- TROUGH ----------------

def test_trough_fires_when_dip_reaches_reset_zone():
    t = st()
    t.commit("k", 500_000, 0)
    # dip to 120k (above floor, <= trough reset, well below anchor)
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
    assert t.evaluate("k", 250_000, 2) is None        # < 2x anchor, no drop


def test_bleeding_rug_fires_trough_at_most_once():
    """THE pin for the genuine-drop guard: a rug bleeding -1%/poll must not
    re-fire 'trough' every 5 minutes (anchor ratchets down each commit)."""
    t = st()
    t.commit("k", 340_000, 0)
    fires = 0
    vol = 340_000.0
    for i in range(12):
        vol *= 0.99
        if t.evaluate("k", vol, i + 1) is not None:
            fires += 1
            t.commit("k", vol, i + 1)
    assert fires <= 1, f"bleeding rug fired {fires}x"


def test_oscillating_token_does_not_spam_trough():
    t = st()
    t.commit("k", 300_000, 0)
    vols = [295_000, 300_000, 290_000, 298_000, 291_000, 299_000]
    fires = [v for v in vols if t.evaluate("k", v, 1) is not None]
    assert fires == []  # dips of <10% are not a genuine collapse


def test_dead_token_revive_still_fires_trough():
    # anchor 100K -> dead at 10K (below floor, hot reset) -> revive 150K
    t = st()
    t.commit("k", 100_000, 0)
    assert t.evaluate("k", 10_000, 1) is None          # cold, trough tracked
    assert t.evaluate("k", 150_000, 2) == "trough"     # 10K <= 70K(=100K*0.7)


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
    t.commit("k", 1_000_000, SUSTAIN_MS)              # caller commits on fire
    assert t.evaluate("k", 1_000_000, SUSTAIN_MS + 60_000) is None
    assert t.evaluate("k", 1_000_000, 2 * SUSTAIN_MS) == "sustain"


def test_dip_below_floor_deletes_hot_timer():
    t = st()
    t.commit("k", 1_000_000, 0)
    assert t.evaluate("k", 90_000, 1000) is None
    assert "k" not in t.hot                           # hot streak reset


def test_commit_resets_anchor_trough_and_hot():
    t = st()
    t.commit("k", 500_000, 0)
    t.evaluate("k", 120_000, 1)                       # trough dips
    t.commit("k", 400_000, 2)
    assert t.tags["k"] == 400_000
    assert t.troughs["k"] == 400_000                  # trough reset (bot.js)
    assert t.hot["k"] == 2
    assert t.evaluate("k", 500_000, 3) is None        # old trough must not refire


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


# ---------------- CA queue ----------------

def test_queue_push_dedupes_by_ca():
    q = []
    assert queue_push(q, "0xabc", "first", 120_000, "t1") is True
    assert queue_push(q, "0xabc", "double", 300_000, "t2") is False
    assert len(q) == 1 and q[0]["reason"] == "first"


def test_queue_push_caps_length_dropping_oldest():
    q = []
    for i in range(150):
        queue_push(q, f"0x{i:040x}", "first", 100_000, "t")
    assert len(q) <= 100
    assert q[0]["ca"] == f"0x{50:040x}"               # oldest 50 dropped
    assert q[-1]["ca"] == f"0x{149:040x}"


def test_key_format():
    assert token_key("robinhood", "0xABC") == "robinhood:0xabc"
