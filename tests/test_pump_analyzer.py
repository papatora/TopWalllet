"""Tests for the PUMP wallet analyzer (directive TASK 1 + TASK 4).

All classification logic is exercised with synthetic trader dicts and a fake
GMGN client — no network. Mirrors the label-coexistence pattern of
test_wallet_classifier (a wallet can be SNIPER + BUNDLER at once).
"""
import asyncio

from src.analyze.pump_analyzer import (
    cross_analyze,
    analyze_pump_token,
    classify_trader,
    cluster_bundles,
    find_pump_start,
    parse_klines,
)

CA = "0xa6b53819f5bf521945fceb1f9bbb3a7a7b4effff"
BASE = 1_700_000_000  # epoch s
FUNDERS = {"0xw1": "0xfunderX"}  # bundler 0xw1 was funded by 0xfunderX


# ------------------------------------------------------------------ fakes --

class FakeClient:
    """Same method surface as GmgnClient — canned payloads, zero network."""

    def __init__(self, traders=(), klines_5m=None, klines_30s=None,
                 stats=None, created=None):
        self._traders = list(traders)
        self._k5 = {"klines": klines_5m if klines_5m is not None else []}
        self._k30 = {"klines": klines_30s if klines_30s is not None else []}
        self._stats = stats or {}
        self._created = created or {}

    def token_security(self, chain, ca):
        return {"bundler_rate": "24.2%", "dev_percentage": "39.3%"}

    def token_info(self, chain, ca):
        return {"symbol": "VAPE", "price": "0.000885", "holder_count": 1211}

    def token_top_traders(self, chain, ca, order_by="profit", limit=100):
        return list(self._traders)

    def token_kline(self, chain, ca, interval="5m", limit=100):
        return self._k5 if interval == "5m" else self._k30

    def wallet_stats(self, chain, wallet, period="30d"):
        return self._stats.get(wallet.lower())

    def created_tokens(self, chain, wallet):
        return list(self._created.get(wallet.lower(), []))


def klines_5m(n=30, pump_idx=12):
    """Flat 1000-volume candles, 6000 (=5×median) at pump_idx, then 2000."""
    rows = []
    for i in range(n):
        vol = 1000.0 if i < pump_idx else (6000.0 if i == pump_idx else 2000.0)
        rows.append([(BASE + i * 300) * 1000, 1.0, 1.1, 0.9, 1.05, vol])
    return rows


def fine_klines(n=40):
    return [[(BASE + i * 30) * 1000, 1.0, 1.0, 1.0, 1.0, 10.0] for i in range(n)]


def trader(addr, ts=None, tags=(), profit=0.0, buy_usd=100.0, block=None,
           funder=None):
    t = {"address": addr, "tags": list(tags), "realized_profit": profit,
         "buy_volume_usd": buy_usd}
    if ts is not None:
        t["first_tx_timestamp"] = ts * 1000  # ms, like GMGN
    if block is not None:
        t["first_block"] = block
    if funder is not None:
        t["funding_source"] = funder
    return t


def run(client, ca=CA):
    return asyncio.run(analyze_pump_token(client, "bsc", ca))


# ------------------------------------------------------------- kline math --

def test_find_pump_start_detects_5x_volume_spike():
    k = parse_klines(klines_5m(pump_idx=12))
    idx, ts = find_pump_start(k)
    assert idx == 12
    assert ts == BASE + 12 * 300


def test_find_pump_start_none_in_flat_series():
    rows = [[(BASE + i * 300) * 1000, 1.0, 1.0, 1.0, 1.0, 1000.0]
            for i in range(30)]
    assert find_pump_start(parse_klines(rows)) == (None, None)


def test_parse_klines_dict_and_list_forms():
    rows = [{"time": (BASE + 5000) * 1000, "open": 1, "high": 2, "low": 0.5,
             "close": 1.5, "volume": 42},
            [(BASE + 5300) * 1000, 1, 2, 0.5, 1.5, 7]]
    k = parse_klines(rows)
    assert [x["ts"] for x in k] == [BASE + 5000, BASE + 5300]
    assert k[0]["volume"] == 42 and k[1]["close"] == 1.5


# ------------------------------------------------- per-token classification --

def test_dev_detection_by_tag():
    client = FakeClient(
        traders=[trader("0xdev", ts=BASE + 330, tags=("dev",))],
        klines_5m=klines_5m(), klines_30s=fine_klines())
    out = run(client)
    classes = {c["address"]: c["classes"] for c in out["classifications"]}
    assert classes["0xdev"] == ["DEV"]
    assert [w["address"] for w in out["wallets"]["dev_wallets"]] == ["0xdev"]


def test_dev_detection_via_created_tokens():
    client = FakeClient(
        traders=[trader("0xcreator", ts=BASE + 330)],
        klines_5m=klines_5m(), klines_30s=fine_klines(),
        created={"0xcreator": [{"address": CA}, {"address": "0xother"}]})
    out = run(client)
    classes = {c["address"]: c["classes"] for c in out["classifications"]}
    assert classes["0xcreator"] == ["DEV"]
    assert out["summary"]["dev_wallets_count"] == 1


def test_bundler_block_clustering_same_adjacent_blocks():
    # 4 wallets in block 5000 + 3 in adjacent block 5001 → every wallet sees
    # ≥5 others within ±1 block → whole set is one BUNDLE cluster.
    traders = ([trader(f"0xa{i}", ts=BASE, block=5000) for i in range(4)]
               + [trader(f"0xb{i}", ts=BASE + 3, block=5001) for i in range(3)]
               + [trader("0xloner", ts=BASE + 7200, block=99999)])
    client = FakeClient(traders=traders, klines_5m=klines_5m(),
                        klines_30s=fine_klines())
    out = run(client)
    bundlers = {w["address"]: w for w in out["wallets"]["bundler_wallets"]}
    assert set(bundlers) == {f"0xa{i}" for i in range(4)} | {
        f"0xb{i}" for i in range(3)}
    assert all(w["cluster_id"] == "BUNDLE_001" for w in bundlers.values())
    assert "0xloner" not in bundlers          # far outside first 3 blocks
    assert out["summary"]["bundler_clusters_count"] == 1


def test_bundler_time_clustering_needs_five_others():
    # 6 wallets in bucket 0 (30s buckets, kline start = BASE): each sees
    # exactly 5 others in the same bucket → ≥5 → all bundled.
    traders = [trader(f"0xc{i}", ts=BASE + i * 5) for i in range(6)]
    # 2 wallets alone in bucket 2: only 1 other nearby → NOT bundled.
    traders += [trader("0xpair0", ts=BASE + 60), trader("0xpair1", ts=BASE + 75)]
    traders.append(trader("0xlate", ts=BASE + 3600))   # bucket 120 — outside
    hits = cluster_bundles(
        [{"address": t["address"], "block": None,
          "first_trade_ts": t["first_tx_timestamp"] / 1000} for t in traders],
        anchor_ts=BASE, bucket_sec=30)
    assert set(hits) == {f"0xc{i}" for i in range(6)}
    assert all(h["cluster_id"] == "BUNDLE_001" for h in hits.values())


def test_sniper_first_trade_within_10_periods():
    traders = [trader("0xsniper", ts=BASE + 150),    # bucket 5 ≤ 10 → SNIPER
               trader("0xchaser", ts=BASE + 900)]    # bucket 30 → not
    client = FakeClient(traders=traders, klines_5m=klines_5m(),
                        klines_30s=fine_klines())
    out = run(client)
    classes = {c["address"]: c["classes"] for c in out["classifications"]}
    assert classes["0xsniper"] == ["SNIPER"]
    assert "SNIPER" not in classes["0xchaser"]


def test_smart_money_thresholds_and_exclusions():
    traders = [
        trader("0xgood", ts=BASE + 600, profit=400),    # 65% WR, $5k → SMART
        trader("0xlowwr", ts=BASE + 660, profit=9000),  # WR 50% → no
        trader("0xlowpf", ts=BASE + 720, profit=10),    # $999 → no
        trader("0xdevrich", ts=BASE + 780, tags=("dev",), profit=9000),
        trader("0xbund", ts=BASE + 840, tags=("bundler",), profit=9000),
        trader("0xcreator", ts=BASE + 330),             # untagged, pre-pump
        trader("0xnostats", ts=BASE + 900),
    ]
    stats = {"0xgood": {"win_rate": 0.65, "realized_profit": 5000},
             "0xlowwr": {"win_rate": 0.50, "realized_profit": 9000},
             "0xlowpf": {"win_rate": 0.65, "realized_profit": 999},
             # percent-format win_rate must normalize: 90 → 0.9
             "0xdevrich": {"win_rate": 90, "realized_profit": 9999},
             "0xbund": {"win_rate": 0.9, "realized_profit": 9000}}
    client = FakeClient(traders=traders, klines_5m=klines_5m(),
                        klines_30s=fine_klines(), stats=stats,
                        created={"0xcreator": [{"address": CA}]})
    out = run(client)
    classes = {c["address"]: c["classes"] for c in out["classifications"]}
    assert classes["0xgood"] == ["SMART_MONEY"]
    assert "SMART_MONEY" not in classes["0xlowwr"]
    assert "SMART_MONEY" not in classes["0xlowpf"]
    assert classes["0xdevrich"] == ["DEV"]           # dev never smart money
    assert classes["0xbund"] == ["BUNDLER"]          # bundler never smart money
    assert classes["0xcreator"] == ["DEV"]           # via created_tokens
    sm = {w["address"]: w for w in out["wallets"]["smart_money"]}
    assert list(sm) == ["0xgood"]
    assert sm["0xgood"]["win_rate"] == 0.65
    assert sm["0xgood"]["pnl_other_tokens_30d"] == 5000
    assert sm["0xgood"]["follow_worthy"] is False    # WR < 70%


def test_pre_post_pump_split():
    pump_ts = BASE + 12 * 300
    traders = [trader("0xearly", ts=pump_ts - 600),
               trader("0xaftpump", ts=pump_ts + 300)]
    client = FakeClient(traders=traders, klines_5m=klines_5m(),
                        klines_30s=fine_klines())
    out = run(client)
    phase = {c["address"]: c["phase"] for c in out["classifications"]}
    assert phase == {"0xearly": "PRE_PUMP", "0xaftpump": "POST_PUMP"}
    assert out["pre_pump_buyers"] == ["0xearly"]
    assert out["summary"]["pre_pump_buyers_count"] == 1
    assert out["token"]["pump_start"] is not None
    assert out["token"]["dead_period"]["end"] is not None


def test_analyze_output_directive_format_and_summary():
    traders = [trader("0xdev", ts=BASE, tags=("dev",)),
               trader("0xearly", ts=BASE + 60)]
    client = FakeClient(traders=traders, klines_5m=klines_5m(),
                        klines_30s=fine_klines())
    out = run(client)
    assert set(out) >= {"token", "wallets", "pre_pump_buyers", "summary"}
    assert set(out["wallets"]) == {"dev_wallets", "bundler_wallets",
                                   "smart_money"}
    tok = out["token"]
    assert tok["address"] == CA and tok["chain"] == "bsc"
    assert tok["security"]["bundler_rate"] == "24.2%"
    assert tok["pump_detected"] is True and tok["pump_peak"]["price"] == 1.1
    assert out["summary"]["total_wallets_analyzed"] == 2
    assert out["summary"]["bundler_percentage"] == "24.2%"
    assert out["summary"]["dev_token_percentage"] == "39.3%"


def test_classify_trader_labels_coexist_like_taxonomy():
    # Sniper + bundler at once (wallet_classifier coexistence pattern).
    rec = {"address": "0xmulti", "tags": [], "first_trade_ts": BASE + 30,
           "block": 100, "buy_usd": 0.0,
           "realized_profit_this_token": 0.0, "funding_source": None}
    bundle = cluster_bundles([rec], anchor_ts=BASE, bucket_sec=30)
    assert bundle == {}   # 1 wallet — no peers, not a bundle
    out = classify_trader(dict(rec), pump_start_ts=BASE + 3600,
                          fine_anchor_ts=BASE, fine_bucket_sec=30,
                          bundle_hits={"0xmulti": {"cluster_id": "BUNDLE_001",
                                                   "bucket": 1, "peers": 6,
                                                   "mode": "time"}})
    assert out["classes"] == ["BUNDLER", "SNIPER"]
    assert out["phase"] == "PRE_PUMP"


# ------------------------------------------------------------ cross-analysis --

def _analysis(ca, smart=(), pre=(), bundlers=(), chain="bsc"):
    def bundler_entry(addr):
        e = {"address": addr, "cluster_id": "BUNDLE_001"}
        if addr in FUNDERS:
            e["funding_source"] = FUNDERS[addr]
        return e
    return {
        "token": {"address": ca, "chain": chain},
        "wallets": {
            "dev_wallets": [],
            "bundler_wallets": [bundler_entry(b) for b in bundlers],
            "smart_money": [{"address": s} for s in smart],
        },
        "pre_pump_buyers": list(pre),
        "summary": {"smart_money_count": len(smart),
                    "pre_pump_buyers_count": len(pre)},
    }


def test_cross_analyze_high_correlation():
    a1 = _analysis("0xaaaa1111", smart=("0xw1", "0xw2", "0xw3"), pre=("0xw4",))
    a2 = _analysis("0xbbbb2222", smart=("0xw1", "0xw2"), pre=("0xw9",))
    cx = cross_analyze([a1, a2])["cross_analysis"]
    assert cx["shared_wallets"] == ["0xw1", "0xw2"]
    assert cx["pairwise"][0]["overlap_count"] == 2
    # score = overlap 2 / min(smart 3, smart 2) = 1.0
    assert cx["correlation_score"] == 1.0
    assert cx["verdict"] == "HIGH_CORRELATION"
    assert "same group" in cx["recommendation"]


def test_cross_analyze_low_and_moderate_verdicts():
    low = cross_analyze([
        _analysis("0xaaaa1111", smart=("0xw1",)),
        _analysis("0xbbbb2222", smart=("0xw2",))])["cross_analysis"]
    assert low["shared_wallets"] == []
    assert low["verdict"] == "LOW_CORRELATION"

    # 1 shared of min(smart)=10 → exactly 0.1 → MODERATE
    mod = cross_analyze([
        _analysis("0xaaaa1111",
                  smart=tuple(f"0xs{i}" for i in range(10))),
        _analysis("0xbbbb2222",
                  smart=("0xs0",) + tuple(f"0xo{i}" for i in range(9)))])[
        "cross_analysis"]
    assert mod["correlation_score"] == 0.1
    assert mod["verdict"] == "MODERATE_CORRELATION"


def test_cross_analyze_shared_funder_and_bundler_cluster():
    # Same two bundler wallets appear in both tokens (also counted as early
    # interest via smart_money) → shared funder + shared cluster + high score.
    a1 = _analysis("0xaaaa1111", smart=("0xw1", "0xw2"),
                   bundlers=("0xw1", "0xw2"))
    a2 = _analysis("0xbbbb2222", smart=("0xw1", "0xw2"),
                   bundlers=("0xw1", "0xw2"))
    cx = cross_analyze([a1, a2])["cross_analysis"]
    assert cx["shared_funding_sources"] == ["0xfunderX"]
    assert len(cx["shared_bundler_clusters"]) == 1
    assert cx["shared_bundler_clusters"][0]["shared_members"] == ["0xw1", "0xw2"]
    assert cx["verdict"] == "HIGH_CORRELATION"   # overlap 2 / min(smart) 2
