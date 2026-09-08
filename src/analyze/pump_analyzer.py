"""PUMP WALLET ANALYZER + CROSS-ANALYSIS — directive TASK 1 + TASK 4.

docs/DIRECTIVE_PUMP_ANALYZER_SCANNER.md: analyze dead-to-pump tokens (VAPE,
Life K-line) and classify every top trader into DEV / BUNDLER / SNIPER /
SMART_MONEY, split PRE_PUMP vs POST_PUMP, then cross-analyze 2+ tokens for
shared wallets / funders / bundler clusters.

Data comes exclusively from the existing GMGN OpenAPI client
(src/discover/gmgn_client.py) — no new HTTP layer.

Detection criteria (docs/GMGN_PANDUAN_LENGKAP.md §2, §3, §6, §7):
  * DEV      — trader tag contains "dev" OR the wallet's created_tokens
               includes this CA (deployer trading under an untagged wallet).
  * BUNDLER  — tag "bundler" OR block clustering: bought within the first 3
               blocks/buckets of kline start with ≥5 other wallets in the
               same/adjacent block (atomic bundle, guide §7 — atomicity is
               approximated by same/adjacent-block co-landing).
  * SNIPER   — first trade within the first 10 kline periods of the finest
               kline series (30s).
  * SMART_MONEY — wallet_stats(30d): win_rate ≥60% AND realized_profit ≥$1000
               AND NOT dev/bundler (guide §2: never read one metric alone, so
               both thresholds must hold).
  * Pump start — first candle with volume ≥5× the median volume of all prior
               candles (dead→pump split; trades before = PRE_PUMP).

Rate-limit friendliness (public test key): wallet_stats is fetched only for
non-dev/bundler candidates (cap SMART_STATS_CAP, pre-pump buyers first);
created_tokens only for untagged PRE_PUMP buyers (cap DEV_CREATED_CAP); all
calls retry once on HTTP 429.

CLI:
  python -m src.analyze.pump_analyzer --chain bsc --ca 0xa6b5...ffff \
      [--chain2 bsc --ca2 0x1a1e...4444]
Writes results/pump_analysis_{ca[:8]}.json and, for two tokens,
results/cross_analysis.json (directive TASK 4 format).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from src.discover.gmgn_client import GmgnClient

# --- thresholds (directive TASK 1 Step 2/3 + GMGN guide §2/§6/§7) ---
PUMP_VOLUME_MULT = 5.0        # pump candle = ≥5× median volume of prior candles
MIN_PRIOR_CANDLES = 5         # need ≥5 prior candles before median is trusted
SNIPER_FIRST_PERIODS = 10     # SNIPER: first trade within first 10 kline periods
BUNDLER_FIRST_BUCKETS = 3     # BUNDLER: within first 3 blocks/buckets of kline start
BUNDLER_ADJACENT = 1          # ...same or ±1 adjacent block
BUNDLER_MIN_OTHERS = 5        # ...with ≥5 OTHER wallets in same/adjacent block
SMART_MIN_WIN_RATE = 0.60     # SMART_MONEY: wallet_stats 30d win_rate ≥60%
SMART_MIN_PROFIT_USD = 1000.0 # ...and realized_profit ≥$1000
SMART_STATS_CAP = 60          # max wallet_stats calls per token (rate limits)
DEV_CREATED_CAP = 30          # max created_tokens calls per token (rate limits)
FINE_INTERVAL = "30s"         # finest kline: bundler buckets + sniper window
PUMP_INTERVAL = "5m"          # pump detection kline (directive uses 5m volume)

INTERVAL_SECONDS = {"30s": 30, "1m": 60, "5m": 300, "15m": 900, "1h": 3600,
                    "4h": 14400, "1d": 86400}

CORRELATION_HIGH = 0.3
CORRELATION_MODERATE = 0.1


# ---------------------------------------------------------------- helpers --

def _num(v, default=0.0) -> float:
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return default


def _ts_to_s(ts) -> float | None:
    """Normalize epoch ts (s or ms, int/float/str) to seconds."""
    if ts in (None, "", 0):
        return None
    f = _num(ts, 0.0)
    if f <= 0:
        return None
    return f / 1000.0 if f > 1e12 else f


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _pick(d: dict | None, keys: tuple[str, ...]) -> dict:
    """Copy only present, non-null keys — security/info payloads vary per chain."""
    out = {}
    for k in keys:
        v = (d or {}).get(k)
        if v not in (None, ""):
            out[k] = v
    return out


def _retry(fn, *args, retries: int = 2, **kwargs):
    """Client wrapper: GMGN returns {'_http_status': 429, ...} when throttled."""
    res = fn(*args, **kwargs)
    for attempt in range(retries - 1):
        if not (isinstance(res, dict) and res.get("_http_status") == 429):
            return res
        time.sleep(1.5 * (attempt + 1))
        res = fn(*args, **kwargs)
    return res


# ------------------------------------------------------------- kline math --

def _klines_payload(res) -> list:
    """token_kline returns a list (client unwraps); tolerate {'klines': [...]}."""
    if isinstance(res, dict):
        return res.get("klines") or []
    return res if isinstance(res, list) else []


def parse_klines(raw, interval: str = PUMP_INTERVAL) -> list[dict]:
    """Normalize GMGN kline rows (dict or [ts,o,h,l,c,v,...] lists) to
    [{'ts': epoch_s, 'open', 'high', 'low', 'close', 'volume'}]."""
    out: list[dict] = []
    for row in raw or []:
        if isinstance(row, dict):
            ts = _ts_to_s(row.get("time") or row.get("timestamp") or row.get("t")
                          or row.get("ts") or row.get("unixTime"))
            vol = _num(row.get("volume", row.get("v")), 0.0)
            o = _num(row.get("open", row.get("o")), 0.0)
            h = _num(row.get("high", row.get("h")), 0.0)
            low = _num(row.get("low", row.get("l")), 0.0)
            c = _num(row.get("close", row.get("c")), 0.0)
        elif isinstance(row, (list, tuple)) and len(row) >= 6:
            ts = _ts_to_s(row[0])
            o, h, low, c, vol = (_num(row[1]), _num(row[2]), _num(row[3]),
                                 _num(row[4]), _num(row[5]))
        else:
            continue
        if ts is None:
            continue
        out.append({"ts": ts, "open": o, "high": h, "low": low,
                    "close": c, "volume": vol})
    out.sort(key=lambda k: k["ts"])
    return out


def find_pump_start(klines: list[dict]) -> tuple[int | None, float | None]:
    """First candle with volume ≥5× the median volume of prior candles.
    Returns (index, ts) or (None, None) when no pump in the window."""
    for i in range(MIN_PRIOR_CANDLES, len(klines)):
        prior = [k["volume"] for k in klines[:i]]
        med = statistics.median(prior)
        vol = klines[i]["volume"]
        if vol > 0 and (med <= 0 or vol >= PUMP_VOLUME_MULT * med):
            return i, klines[i]["ts"]
    return None, None


# ------------------------------------------------------- trader extraction --

def _trader_addr(t: dict) -> str | None:
    for k in ("address", "wallet", "wallet_address", "trader"):
        v = t.get(k)
        if isinstance(v, str) and v:
            return v.lower()
    return None


def _trader_tags(t: dict) -> list[str]:
    """Lowercased GMGN tags — `tags` (taxonomy: dev/bundler/sniper/fresh_wallet/
    smart_degen/...) plus `maker_token_tags` (per-token maker labels)."""
    tags: list[str] = []
    for field in ("tags", "maker_token_tags"):
        v = t.get(field) or []
        if isinstance(v, str):
            v = [x.strip() for x in v.split(",") if x.strip()]
        tags.extend(str(x).lower() for x in v)
    return tags


def _trader_rank_tag(t: dict) -> str | None:
    v = t.get("wallet_tag_v2")
    return str(v).lower() if v else None


def _trader_first_ts(t: dict) -> float | None:
    for k in ("first_tx_timestamp", "first_tx_unixTime", "first_trade_time",
              "first_trade_at", "first_time", "first_active_at", "first_buy_at",
              "first_tx_time", "start_holding_at"):
        if k in t:
            ts = _ts_to_s(t.get(k))
            if ts is not None:
                return ts
    return None


def _trader_block(t: dict) -> int | None:
    for k in ("first_block", "first_tx_block", "block", "buy_block", "block_num"):
        v = t.get(k)
        if v not in (None, ""):
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
    return None


def _trader_profit(t: dict) -> float:
    for k in ("realized_profit", "profit", "pnl", "total_profit"):
        if k in t:
            return _num(t.get(k), 0.0)
    return 0.0


def _trader_buy_usd(t: dict) -> float:
    for k in ("buy_volume_usd", "accu_cost", "total_cost", "total_buy_volume",
              "buy_volume", "volume_usd"):
        if k in t:
            return _num(t.get(k), 0.0)
    return 0.0


def _trader_funder(t: dict) -> str | None:
    for k in ("funding_source", "funder", "funding_wallet"):
        v = t.get(k)
        if isinstance(v, str) and v.startswith("0x"):
            return v.lower()
    return None


# -------------------------------------------------------- wallet stats api --

def _stats_metrics(stats: dict | None) -> tuple[float | None, float | None]:
    """(win_rate 0..1, realized_profit_usd) from a wallet_stats 30d payload.
    Real GMGN shape: realized_profit top-level (decimal string), win rate at
    pnl_stat.winrate (0-1 fraction; tolerate 0-100 percent too)."""
    if not isinstance(stats, dict):
        return None, None
    sub_dicts = [stats] + [stats[k] for k in ("data", "stats", "pnl_stat")
                           if isinstance(stats.get(k), dict)]

    def _find(keys: tuple[str, ...]):
        for src in sub_dicts:
            for k in keys:
                if k in src and isinstance(src[k], (int, float, str)):
                    return src[k]
        return None

    wr_raw = _find(("win_rate", "winrate", "pnl_win_rate", "buy_win_rate"))
    win_rate = None
    if wr_raw is not None:
        v = _num(wr_raw, -1.0)
        if v >= 0:
            win_rate = v / 100.0 if v > 1.0 else v
    rp = _find(("realized_profit", "total_realized_profit", "realized_profit_30d",
                "realized_pnl", "pnl"))
    realized = _num(rp, 0.0) if rp is not None else None
    return win_rate, realized


# ---------------------------------------------------------- classification --

def cluster_bundles(records: list[dict], anchor_ts: float | None,
                    bucket_sec: int) -> dict[str, dict]:
    """BUNDLER block clustering (guide §7): wallets landing within the first
    BUNDLER_FIRST_BUCKETS buckets of kline start, with ≥BUNDLER_MIN_OTHERS
    other wallets in the same/adjacent bucket.

    `records` need 'address' plus 'block' (preferred) or 'first_trade_ts'.
    Returns address -> {'cluster_id': 'BUNDLE_00n', 'bucket': int,
                        'peers': n, 'mode': 'block'|'time'}.
    """
    buckets: dict[int, list[dict]] = defaultdict(list)
    min_block = min((r["block"] for r in records if r.get("block") is not None),
                    default=None)
    for r in records:
        if r.get("block") is not None and min_block is not None:
            r["_bucket"], r["_mode"] = r["block"] - min_block, "block"
        elif r.get("first_trade_ts") is not None and anchor_ts is not None:
            r["_bucket"] = int((r["first_trade_ts"] - anchor_ts) // bucket_sec)
            r["_mode"] = "time"
        else:
            continue
        if r["_bucket"] <= BUNDLER_FIRST_BUCKETS:
            buckets[r["_bucket"]].append(r)

    hits: dict[str, dict] = {}
    for bucket, members in sorted(buckets.items()):
        for r in members:
            near = [o for b in (bucket - BUNDLER_ADJACENT, bucket,
                                bucket + BUNDLER_ADJACENT)
                    for o in buckets.get(b, []) if o is not r]
            if len(near) >= BUNDLER_MIN_OTHERS:
                hits[r["address"]] = {"cluster_id": None,  # assigned below
                                      "bucket": bucket, "peers": len(near),
                                      "mode": r["_mode"]}

    # connected buckets within adjacency → one cluster id per component
    comp: dict[int, str] = {}
    cid_idx = 0
    for bucket in sorted(buckets):
        if bucket not in comp and any(h["bucket"] == bucket for h in hits.values()):
            cid_idx += 1
            cid = f"BUNDLE_{cid_idx:03d}"
            stack = [bucket]
            while stack:
                b = stack.pop()
                if b in comp:
                    continue
                comp[b] = cid
                stack += [b + d for d in (-1, 1)
                          if b + d in buckets and b + d not in comp]
    for h in hits.values():
        h["cluster_id"] = comp.get(h["bucket"], "BUNDLE_000")
    return hits


def classify_trader(record: dict, *, pump_start_ts: float | None,
                    fine_anchor_ts: float | None, fine_bucket_sec: int,
                    bundle_hits: dict[str, dict]) -> dict:
    """Tag + timing classes for one trader record (no network calls here)."""
    addr = record["address"]
    tags = record["tags"]
    classes: list[str] = []
    evidence: dict[str, Any] = {"tags": tags}

    if any("dev" in t for t in tags):
        classes.append("DEV")
        evidence["dev"] = "tag contains 'dev'"
    if addr in bundle_hits:
        classes.append("BUNDLER")
        evidence["bundler"] = bundle_hits[addr]
    if any("bundler" in t for t in tags) and "BUNDLER" not in classes:
        classes.append("BUNDLER")
        evidence["bundler"] = {"cluster_id": "TAGGED", "source": "gmgn tag"}

    phase = None
    ts = record.get("first_trade_ts")
    if ts is not None:
        if pump_start_ts is None or ts < pump_start_ts:
            phase = "PRE_PUMP"
        else:
            phase = "POST_PUMP"
        if (fine_anchor_ts is not None
                and ts <= fine_anchor_ts + SNIPER_FIRST_PERIODS * fine_bucket_sec
                and "SNIPER" not in classes):
            classes.append("SNIPER")
            evidence["sniper"] = {
                "first_trade_ts": ts,
                "within_periods": round((ts - fine_anchor_ts) / fine_bucket_sec, 1)}
    record["phase"] = phase

    if any("sniper" in t for t in tags) and "SNIPER" not in classes:
        classes.append("SNIPER")
        evidence["sniper"] = {"source": "gmgn tag"}
    record["classes"] = classes
    record["evidence"] = evidence
    return record


# ------------------------------------------------------------ token analysis --

async def analyze_pump_token(client: GmgnClient, chain: str, ca: str) -> dict:
    """Full per-token analysis (directive TASK 1). Network calls:
    security + info + top traders(100) + 2 klines + ≤DEV_CREATED_CAP
    created_tokens + ≤SMART_STATS_CAP wallet_stats."""
    ca_l = ca.lower()
    security = _retry(client.token_security, chain, ca) or {}
    info = _retry(client.token_info, chain, ca) or {}
    # token/info nests a rich `price` object — flatten it (scalar price wins).
    if isinstance(info.get("price"), dict):
        nested = info["price"]
        info = {**nested, **{k: v for k, v in info.items()
                             if k != "price" and v not in (None, "")}}
        info["price"] = nested.get("price")
    traders = _retry(client.token_top_traders, chain, ca, limit=100) or []
    klines = parse_klines(
        _klines_payload(_retry(client.token_kline, chain, ca,
                               interval=PUMP_INTERVAL, limit=100)), PUMP_INTERVAL)
    fine_klines = parse_klines(
        _klines_payload(_retry(client.token_kline, chain, ca,
                               interval=FINE_INTERVAL, limit=100)), FINE_INTERVAL)

    pump_idx, pump_start_ts = find_pump_start(klines)
    window_start_ts = klines[0]["ts"] if klines else None
    window_end_ts = klines[-1]["ts"] if klines else None
    peak = max(klines, key=lambda k: k["high"], default=None)

    fine_anchor_ts = fine_klines[0]["ts"] if fine_klines else window_start_ts
    fine_bucket_sec = INTERVAL_SECONDS[FINE_INTERVAL]

    # --- build trader records ---
    records: list[dict] = []
    for t in traders:
        if not isinstance(t, dict):
            continue
        addr = _trader_addr(t)
        if not addr:
            continue
        records.append({
            "address": addr,
            "tags": _trader_tags(t),
            "rank_tag": _trader_rank_tag(t),
            "first_trade_ts": _trader_first_ts(t),
            "block": _trader_block(t),
            "buy_usd": _trader_buy_usd(t),
            "realized_profit_this_token": _trader_profit(t),
            "funding_source": _trader_funder(t),
            "is_new": bool(t.get("is_new")),
            "is_suspicious": bool(t.get("is_suspicious")),
            "transfer_in": bool(t.get("transfer_in")),
            "raw_first": t,  # kept in-memory only; not serialized
        })

    bundle_hits = cluster_bundles(records, fine_anchor_ts, fine_bucket_sec)
    records = [classify_trader(r, pump_start_ts=pump_start_ts,
                               fine_anchor_ts=fine_anchor_ts,
                               fine_bucket_sec=fine_bucket_sec,
                               bundle_hits=bundle_hits)
               for r in records]

    # --- DEV via created_tokens for untagged PRE_PUMP buyers (cap for rate) ---
    dev_candidates = sorted(
        (r for r in records if "DEV" not in r["classes"] and r["phase"] == "PRE_PUMP"),
        key=lambda r: r["first_trade_ts"] or 0.0)
    checked = 0
    for r in dev_candidates:
        if checked >= DEV_CREATED_CAP:
            r["evidence"]["dev_check"] = "skipped (rate cap)"
            continue
        checked += 1
        created = _retry(client.created_tokens, chain, r["address"]) or []
        addrs = {str(t.get("address", "")).lower() for t in created
                 if isinstance(t, dict)}
        if ca_l in addrs:
            r["classes"].append("DEV")
            r["evidence"]["dev"] = "created_tokens includes this CA"

    # --- SMART_MONEY via wallet_stats 30d (pre-pump buyers first) ---
    smart_candidates = [r for r in records
                        if "DEV" not in r["classes"] and "BUNDLER" not in r["classes"]]
    smart_candidates.sort(key=lambda r: (r["phase"] != "PRE_PUMP",
                                         -(r["realized_profit_this_token"])))
    stats_checked = 0
    for r in smart_candidates:
        if stats_checked >= SMART_STATS_CAP:
            r["evidence"]["stats_check"] = "skipped (rate cap)"
            continue
        stats_checked += 1
        stats = _retry(client.wallet_stats, chain, r["address"], period="30d")
        win_rate, realized = _stats_metrics(stats if isinstance(stats, dict) else None)
        r["wallet_stats_30d"] = {"win_rate": win_rate, "realized_profit": realized}
        if (win_rate is not None and win_rate >= SMART_MIN_WIN_RATE
                and realized is not None and realized >= SMART_MIN_PROFIT_USD):
            r["classes"].append("SMART_MONEY")
            r["evidence"]["smart_money"] = {
                "win_rate": win_rate, "realized_profit_30d": realized,
                "source": "wallet_stats 30d"}

    # --- assemble directive-format output ---
    def _entry(r: dict, extra: dict) -> dict:
        e = {"address": r["address"],
             "phase": r["phase"],
             "first_trade_ts": _iso(r["first_trade_ts"]),
             "tags": r["tags"],
             "rank_tag": r.get("rank_tag")}
        e.update(extra)
        return e

    dev_wallets, bundler_wallets, smart_money = [], [], []
    pre_pump_buyers: list[str] = []
    for r in records:
        if "DEV" in r["classes"]:
            dev_wallets.append(_entry(r, {
                "label": "dev",
                "tokens_created_this_ca": ca_l,
                "evidence": r["evidence"],
            }))
        if "BUNDLER" in r["classes"]:
            bh = r["evidence"].get("bundler") or {}
            bundler_wallets.append(_entry(r, {
                "cluster_id": bh.get("cluster_id", "TAGGED"),
                "buy_block": r["block"],
                "buy_bucket": bh.get("bucket"),
                "peers_same_adjacent_block": bh.get("peers"),
                "buy_amount_usd": r["buy_usd"],
                "funding_source": r["funding_source"],
                "bundler_type": "tagged" if bh.get("cluster_id") == "TAGGED"
                                else bh.get("mode", "cluster"),
                "is_new_wallet": r.get("is_new"),
                "received_transfer": r.get("transfer_in"),
                "risk_score": 7.5 if bh.get("cluster_id") == "TAGGED" else 9.0,
            }))
        if "SMART_MONEY" in r["classes"]:
            ws = r.get("wallet_stats_30d") or {}
            smart_money.append(_entry(r, {
                "buy_time_before_pump_hours":
                    (round((pump_start_ts - r["first_trade_ts"]) / 3600.0, 2)
                     if pump_start_ts and r["first_trade_ts"] else None),
                "pnl_this_token": r["realized_profit_this_token"],
                "pnl_other_tokens_30d": ws.get("realized_profit"),
                "win_rate": ws.get("win_rate"),
                "other_early_buys": [],   # needs per-wallet activity sweep (later)
                "follow_worthy": bool((ws.get("win_rate") or 0) >= 0.70),
                "funding_source": r["funding_source"],
            }))
        if r["phase"] == "PRE_PUMP":
            pre_pump_buyers.append(r["address"])

    # cluster ids for the summary (block clusters only; TAGGED is not a cluster)
    cluster_ids = sorted({(w["cluster_id"]) for w in bundler_wallets
                          if w["cluster_id"] != "TAGGED"})
    bundler_rate = _pick(security, ("bundler_rate", "bundler_percentage"))
    dev_rate = _pick(security, ("dev_percentage", "dev_rate", "dev_token_percentage"))

    token_block = {
        "address": ca_l,
        "chain": chain,
        **_pick(info, ("symbol", "name", "price", "market_cap", "total_supply",
                       "created_timestamp", "holder_count")),
        "security": _pick(security, (
            "top_10_holder_rate", "is_honeypot", "honeypot", "is_open_source",
            "is_renounced", "renounced_mint", "is_blacklist", "buy_tax",
            "sell_tax", "burn_ratio", "lock_summary", "high_tax", "can_not_sell",
            "dev_percentage", "insider_rate", "bundler_rate", "phishing_rate",
            "holder_count", "rug_risk_level", "burned_percentage")),
        "kline_window": {"interval": PUMP_INTERVAL,
                         "start": _iso(window_start_ts),
                         "end": _iso(window_end_ts)},
        "dead_period": {"start": _iso(window_start_ts),
                        "end": _iso(pump_start_ts or window_end_ts)},
        "pump_start": _iso(pump_start_ts),
        "pump_start_index": pump_idx,
        "pump_peak": ({"ts": _iso(peak["ts"]), "price": peak["high"]}
                      if peak else None),
        "pump_detected": pump_start_ts is not None,
    }

    return {
        "token": token_block,
        "wallets": {"dev_wallets": dev_wallets,
                    "bundler_wallets": bundler_wallets,
                    "smart_money": smart_money},
        "pre_pump_buyers": pre_pump_buyers,
        "classifications": [{"address": r["address"], "classes": r["classes"],
                             "phase": r["phase"], "tags": r["tags"]}
                            for r in records],
        "summary": {
            "total_wallets_analyzed": len(records),
            "dev_wallets_count": len(dev_wallets),
            "bundler_clusters_count": len(cluster_ids),
            "bundler_wallets_count": len(bundler_wallets),
            "smart_money_count": len(smart_money),
            "pre_pump_buyers_count": len(pre_pump_buyers),
            "post_pump_traders_count": sum(1 for r in records
                                           if r["phase"] == "POST_PUMP"),
            **({"bundler_percentage": bundler_rate["bundler_rate"]}
               if bundler_rate else {}),
            **({"dev_token_percentage": dev_rate["dev_percentage"]}
               if dev_rate else {}),
        },
    }


# ------------------------------------------------------------ cross-analysis --

def _interest_set(a: dict) -> set[str]:
    """smart_money ∪ pre-pump buyers — the directive's overlap universe."""
    smart = {w["address"] for w in a.get("wallets", {}).get("smart_money", [])
             if w.get("address")}
    pre = {w for w in a.get("pre_pump_buyers", []) if w}
    return smart | pre


def _verdict(score: float) -> str:
    if score >= CORRELATION_HIGH:
        return "HIGH_CORRELATION"
    if score >= CORRELATION_MODERATE:
        return "MODERATE_CORRELATION"
    return "LOW_CORRELATION"


def cross_analyze(analyses: list[dict]) -> dict:
    """Directive TASK 4: wallet overlap, shared funders, shared bundler
    clusters, correlation score = overlap / min(smart_money_counts)."""
    tokens: list[dict] = []
    per: list[dict] = []
    for a in analyses:
        tok = (a.get("token") or {})
        tid = tok.get("address") or a.get("address") or "?"
        smart = {w["address"] for w in a.get("wallets", {}).get("smart_money", [])
                 if w.get("address")}
        interest = _interest_set(a)
        bundlers = {w["address"] for w in a.get("wallets", {}).get("bundler_wallets", [])
                    if w.get("address")}
        funders = {w["funding_source"] for w in
                   a.get("wallets", {}).get("smart_money", [])
                   + a.get("wallets", {}).get("bundler_wallets", [])
                   if w.get("funding_source")}
        clusters: dict[str, set[str]] = defaultdict(set)
        for w in a.get("wallets", {}).get("bundler_wallets", []):
            if w.get("cluster_id") and w["cluster_id"] != "TAGGED" and w.get("address"):
                clusters[w["cluster_id"]].add(w["address"])
        per.append({"id": tid, "smart": smart, "interest": interest,
                    "bundler": bundlers, "funders": funders, "clusters": clusters})
        tokens.append({"address": tid, "chain": tok.get("chain"),
                       "smart_money_count": a.get("summary", {}).get(
                           "smart_money_count", len(smart)),
                       "pre_pump_buyers_count": a.get("summary", {}).get(
                           "pre_pump_buyers_count",
                           len(a.get("pre_pump_buyers", [])))})

    overlap_counter: Counter[str] = Counter()
    for p in per:
        overlap_counter.update(p["interest"])
    shared_wallets = sorted(a for a, n in overlap_counter.items() if n >= 2)

    funder_counter: Counter[str] = Counter()
    for p in per:
        funder_counter.update(p["funders"])
    shared_funders = sorted(f for f, n in funder_counter.items() if n >= 2)

    shared_clusters = []
    for i in range(len(per)):
        for j in range(i + 1, len(per)):
            for cid_a, members_a in per[i]["clusters"].items():
                for cid_b, members_b in per[j]["clusters"].items():
                    shared = members_a & members_b
                    if len(shared) >= 2:
                        shared_clusters.append({
                            "clusters": [f"{per[i]['id'][:10]}:{cid_a}",
                                         f"{per[j]['id'][:10]}:{cid_b}"],
                            "shared_members": sorted(shared)})

    pairwise = []
    for i in range(len(per)):
        for j in range(i + 1, len(per)):
            a, b = per[i], per[j]
            overlap = a["interest"] & b["interest"]
            smart_a = a["smart"] or a["interest"]
            smart_b = b["smart"] or b["interest"]
            denom = min(len(smart_a), len(smart_b))
            score = (len(overlap) / denom) if denom else 0.0
            pairwise.append({
                "pair": [a["id"], b["id"]],
                "overlap_wallets": sorted(overlap),
                "overlap_count": len(overlap),
                "correlation_score": round(score, 4),
                "verdict": _verdict(score),
            })

    overall = max((p["correlation_score"] for p in pairwise), default=0.0)
    verdict = _verdict(overall)
    rec = {
        "HIGH_CORRELATION":
            "HIGH_CORRELATION — same group likely operating both pumps. "
            "Monitor these wallets for next token purchase.",
        "MODERATE_CORRELATION":
            "MODERATE_CORRELATION — partial overlap; watch the shared wallets "
            "for coordinated entries.",
        "LOW_CORRELATION":
            "LOW_CORRELATION — no significant wallet overlap detected.",
    }[verdict]

    return {"cross_analysis": {
        "tokens": tokens,
        "shared_wallets": shared_wallets,
        "shared_funding_sources": shared_funders,
        "shared_bundler_clusters": shared_clusters,
        "pairwise": pairwise,
        "correlation_score": overall,
        "verdict": verdict,
        "recommendation": rec,
    }}


# ------------------------------------------------------------------- CLI --

def _save(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"[saved] {path}")


async def _run(chain: str, ca: str, chain2: str | None, ca2: str | None,
               out_dir: str) -> None:
    client = GmgnClient()
    try:
        a1 = await analyze_pump_token(client, chain, ca)
        _save(os.path.join(out_dir, f"pump_analysis_{ca[:8]}.json"), a1)
        s = a1["summary"]
        print(f"[token] {ca} dev={s['dev_wallets_count']} "
              f"bundler={s['bundler_wallets_count']} "
              f"smart={s['smart_money_count']} "
              f"pre_pump={s['pre_pump_buyers_count']} "
              f"pump_detected={a1['token']['pump_detected']}")
        if ca2:
            a2 = await analyze_pump_token(client, chain2 or chain, ca2)
            _save(os.path.join(out_dir, f"pump_analysis_{ca2[:8]}.json"), a2)
            cross = cross_analyze([a1, a2])
            _save(os.path.join(out_dir, "cross_analysis.json"), cross)
            cx = cross["cross_analysis"]
            print(f"[cross] shared_wallets={len(cx['shared_wallets'])} "
                  f"score={cx['correlation_score']} verdict={cx['verdict']}")
    finally:
        client.close()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m src.analyze.pump_analyzer",
        description="PUMP wallet analyzer + cross-analysis (GMGN OpenAPI)")
    ap.add_argument("--chain", required=True, help="bsc | robinhood | sol | ...")
    ap.add_argument("--ca", required=True, help="token contract address")
    ap.add_argument("--chain2", help="second token chain (cross-analysis)")
    ap.add_argument("--ca2", help="second token CA (cross-analysis)")
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args(argv)
    asyncio.run(_run(args.chain, args.ca, args.chain2, args.ca2, args.out_dir))


if __name__ == "__main__":
    main()
