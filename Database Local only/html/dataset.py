"""Dataset builder for the local TopWallet explorer.

Robinhood Chain (4663) ONLY. Reads the LOCAL snapshot — never the VPS:
  - data/topwallet.db                   tokens, pools, price_points, swap_events, wallet_scores, checkpoints
  - results/wallet_labels.json          12,880 classified wallets + evidence
  - results/top_wallets_latest.json     verified ranked list
  - results/wallet_scenario_groups.json scenario verdicts
  - results/funder_clusters.json        funder metadata

BSC research files (wallet_data.json, diamond_*.json, cross_token_traders.json)
are deliberately NOT used.

swap_events.usd_value is NULL in the snapshot, so USD per swap is ESTIMATED as
token_amount x nearest pool price_point at-or-before the swap block (fallback:
first point after). Pools whose price_points sit >30x away from the token's
snapshot price (a scale bug seen on USDG-quoted pools) are rescaled onto the
snapshot price. A swap valued above the token's pool liquidity is treated as a
bad price point and left unpriced. The UI labels these figures "est.".
"""
from __future__ import annotations

import bisect
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXPLORER = "https://robinhoodchain.blockscout.com"
SPARK_POINTS = 90


def _load(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _epoch(ts: str) -> int:
    return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=timezone.utc).timestamp())


def build() -> dict:
    labels_doc = _load("results/wallet_labels.json")
    W = {a.lower(): v for a, v in labels_doc["wallets"].items()}
    con = sqlite3.connect(REPO / "data" / "topwallet.db")

    # ---- tokens -----------------------------------------------------------
    tok_idx: dict[str, int] = {}
    tokens: list[list] = []  # [addr, symbol, name, price, liquidity, vol24h, first_seen, dex, quote]

    def tk(addr: str) -> int:
        a = addr.lower()
        if a not in tok_idx:
            tok_idx[a] = len(tokens)
            tokens.append([a, None, None, None, None, None, None, None, None])
        return tok_idx[a]

    liquidity: dict[str, float] = {}
    snap: dict[str, float] = {}
    for addr, sym, name, price, liq, vol, first in con.execute(
        "select address,symbol,name,price_usd,liquidity_usd,volume_24h_usd,first_seen from tokens"
    ):
        tokens[tk(addr)][1:7] = [sym, name, price, liq, vol, _epoch(first)]
        liquidity[addr.lower()] = liq
        if price:
            snap[addr.lower()] = price

    # ---- price series per token (pool with most points) --------------------
    pool_for: dict[str, tuple] = {}
    for tok, pool, dex, ver, quote, n in con.execute(
        "select lower(p.token_address), p.address, p.dex, p.version, p.quote_symbol, count(pp.id) from pools p "
        "left join price_points pp on pp.pool_address=p.address group by p.address order by 6"
    ):
        pool_for[tok] = (pool, f"{dex} v{ver}", quote)  # asc order -> last write has most points
    series: dict[str, tuple[list[int], list[float]]] = {}
    spark: dict[int, list] = {}
    calibrated: list[list] = []
    for tok, (pool, dex, quote) in pool_for.items():
        i = tk(tok)
        tokens[i][7:9] = [dex, quote]
        rows = con.execute(
            "select block_num, price_usd, ts from price_points where pool_address=? order by block_num", (pool,)
        ).fetchall()
        if not rows:
            continue
        # Some pools (notably USDG-quoted) store price_points on the wrong scale (~1e-12x).
        # When the latest point is >30x away from the token's snapshot price, rescale the
        # whole series onto the snapshot price and record it as calibrated.
        scale, snap, last = 1.0, tokens[i][3], rows[-1][1]
        if snap and last and not (1 / 30 <= last / snap <= 30):
            scale = snap / last
            calibrated.append([i, round(scale, 6) if scale >= 1e-6 else scale])
        elif not last:
            continue
        series[tok] = ([r[0] for r in rows], [r[1] * scale for r in rows])
        step = max(1, len(rows) // SPARK_POINTS)
        pick = rows[::step] + ([rows[-1]] if (len(rows) - 1) % step else [])
        spark[i] = [[_epoch(r[2]), r[1] * scale] for r in pick]

    def price_at(tok: str, block: int):
        s = series.get(tok)
        if not s:
            return None
        j = bisect.bisect_right(s[0], block) - 1
        return s[1][j] if j >= 0 else s[1][0]

    # ---- swaps ------------------------------------------------------------
    order = sorted(W)
    widx = {a: i for i, a in enumerate(order)}
    swaps_by_w: dict[int, list] = defaultdict(list)
    priced = unpriced = outliers = 0
    ts_min = ts_max = None
    for wa, ta, ts, block, side, amt, tx in con.execute(
        "select lower(wallet_address), lower(token_address), ts, block_num, side, token_amount, tx_hash "
        "from swap_events order by ts"
    ):
        if wa not in widx:
            continue
        p = price_at(ta, block)
        if p is None:
            sp = snap.get(ta)
            p = sp  # fallback: harga snapshot terakhir token (kasar, tetap "est.")
        usd = round(amt * p, 2) if p is not None else -1
        if usd > (liquidity.get(ta) or 1_000_000):  # bigger than the whole pool = bad price point
            usd = -1
            outliers += 1
        priced += usd >= 0
        unpriced += usd < 0
        t = _epoch(ts)
        ts_min = t if ts_min is None else min(ts_min, t)
        ts_max = t if ts_max is None else max(ts_max, t)
        swaps_by_w[widx[wa]].append([tk(ta), t, 1 if side.upper() == "SELL" else 0, usd, tx])

    # ---- scores / verification ---------------------------------------------
    scores: dict[str, dict] = {}
    for wa, score, metrics, style, flags, cluster in con.execute(
        "select lower(wallet_address), composite_score, metrics, trading_style, risk_flags, cluster_id from wallet_scores"
    ):
        m = json.loads(metrics)
        scores[wa] = {
            "score": score, "style": style, "flags": json.loads(flags), "cluster": cluster,
            "realized": m.get("total_realized_pnl_usd"), "unrealized": m.get("total_unrealized_pnl_usd"),
            "win_rate": m.get("win_rate"), "positions": m.get("total_positions"),
        }
    # on-chain tag verification (scripts/reverify_tags.py): wallet -> status
    try:
        _tv = _load("results/tag_verification.json").get("insider", {})
        _best = {}
        for _k, _v in _tv.items():
            _w, _verdict = _k.split(":", 1)[0], _v.get("verdict")
            _st = {"CONFIRMED_INSIDER": "insider PROVEN", "MINT_ALLOCATION": "insider PROVEN (mint)",
                   "TRADER_MISREAD": "insider OVERTURNED (coverage gap)", "AIRDROP_SPAM": "airdrop spam target",
                   "UNRESOLVED": "insider unproven"}.get(_verdict)
            if _st and (_w not in _best or _st.startswith("insider PROVEN")):
                _best[_w] = _st
        for _w, _st in _best.items():
            scores.setdefault(_w, {}).update(tag=_st)
    except Exception:
        pass
    for grp, rows in _load("results/wallet_scenario_groups.json").items():
        for r in rows:
            scores.setdefault(r["wallet"].lower(), {}).update(group=grp, verified=r.get("verified"), rank=r.get("rank"))
    for r in _load("results/top_wallets_latest.json")["wallets"]:
        scores.setdefault(r["wallet_address"].lower(), {}).update(
            top_rank=r["rank"], score=r["composite_score"],
            realized=r["metrics"]["total_realized_pnl_usd"], win_rate=r["metrics"]["win_rate"])

    # ---- derived behavioural labels (dari pola swap, bukan tag eksternal) ---
    import statistics as _stats

    first_ts: dict[int, int] = {}
    for wl in swaps_by_w.values():
        for e in wl:
            ta, tsv = e[0], e[1]
            if ta not in first_ts or tsv < first_ts[ta]:
                first_ts[ta] = tsv

    LINKAGE = {"AIRDROP_FARMER", "PHISHING_TARGET", "INSIDER"}
    derived: dict[int, list[str]] = {}
    for wi, wl in swaps_by_w.items():
        if len(wl) < 20:
            continue
        tss = sorted(e[1] for e in wl)
        gaps = [b - a for a, b in zip(tss, tss[1:]) if b >= a]
        med_gap = _stats.median(gaps) if gaps else 10 ** 9
        toks = {e[0] for e in wl}
        net = sum(e[3] if e[2] == 1 else -e[3] for e in wl if e[3] >= 0)
        early_buys = sum(1 for e in wl if e[2] == 0 and e[1] - first_ts.get(e[0], e[1]) <= 120)
        botlike = med_gap <= 20 and len(wl) >= 150
        labs = []
        if botlike:
            labs.append("BOT")
            if early_buys >= 6 and len(toks) >= 8:
                labs.append("SNIPER_BOT")
        addr = order[wi]
        wlabs = set(W[addr]["labels"]) if addr in W else set()
        linked = bool(wlabs & LINKAGE) or any(l.startswith("CLUSTER_MEMBER") for l in wlabs)
        if net >= 100_000 and len(wl) >= 20:
            labs.append("WHALE_SUS" if linked else "WHALE")
        if labs:
            derived[wi] = labs

    # ---- wallets, labels, evidence -------------------------------------------
    types = sorted({v["primary_type"] for v in W.values()})
    label_names = sorted({l for v in W.values() for l in v["labels"]}
                         | {l for ls in derived.values() for l in ls})
    t_i = {t: i for i, t in enumerate(types)}
    l_i = {l: i for i, l in enumerate(label_names)}

    rows, ev, bundles, clusters = [], {}, {}, {}
    for i, a in enumerate(order):
        v = W[a]
        name = ""
        e_out = {}
        for lab, e in v["evidence"].items():
            if lab == "GENERALIST" or not isinstance(e, dict):
                continue
            e = json.loads(json.dumps(e))
            if lab == "BUNDLER_SUSPECT":
                b = bundles.setdefault(e["tx_hash"], {"tx": e["tx_hash"], "token": tk(e["token"]), "block": e["block"],
                                                      "distinct": e["distinct_wallets"], "members": []})
                b["members"].append(i)
                e.pop("wallet_sample", None)
                e["token"] = tk(e["token"])
            elif lab.startswith("CLUSTER_MEMBER"):
                c = clusters.setdefault(e["cluster_id"], {"id": e["cluster_id"], "funder": e["funder"],
                                                          "member_count": e.get("member_count"), "members": []})
                c["members"].append(i)
                e.pop("members", None)
            elif lab == "CT_ATTRIBUTED":
                name = e.get("name") or e.get("twitter_username") or ""
            for key in ("snipes", "sample"):
                for s in e.get(key) or []:
                    if isinstance(s, dict) and "token" in s:
                        s["token"] = tk(s["token"])
            if isinstance(e.get("tokens"), list):
                e["tokens"] = [tk(x) for x in e["tokens"]]
            e_out[lab] = e
        if a in scores:
            e_out["_score"] = scores[a]
        if e_out:
            ev[i] = e_out
        dl = derived.get(i, [])
        rows.append([a, t_i[v["primary_type"]], [l_i[l] for l in v["labels"] + dl],
                     [round(v["confidence"].get(l, 0), 2) for l in v["labels"]] + [0.8] * len(dl),
                     name])

    fc = _load("results/funder_clusters.json")
    if fc.get("cluster_id") in clusters:
        clusters[fc["cluster_id"]].update(funded_wallets=fc.get("funded_wallets"),
                                          funder_eth=fc["funder"].get("eth_balance"), note=fc.get("note"))

    reg_path = Path(__file__).resolve().parent / "data" / "known_entities.json"
    known = {}
    if reg_path.exists():
        known = {a.lower(): v for a, v in json.loads(reg_path.read_text(encoding="utf-8")).get("entities", {}).items()}

    checkpoints = {s: u for s, _c, u in con.execute("select stage,cursor,updated_at from pipeline_checkpoints")}
    con.close()

    # ---- lineage / "indukan": dari mana wallet insider dapat token ----------
    funders: dict[str, set] = {}
    for a, v in W.items():
        for lab in v.get("labels", []):
            if lab.startswith("CLUSTER_MEMBER"):
                f = ((v.get("evidence") or {}).get(lab) or {}).get("funder") or ""
                if f:
                    funders.setdefault(f.lower(), set()).add(a)
    origins: dict[str, dict] = {}
    for a, v in W.items():
        evd = v.get("evidence") or {}
        ins = evd.get("INSIDER") or {}
        senders = ins.get("senders") or {}
        o = None
        if ins.get("mint"):
            o = {"kind": "MINT", "label": "Mint dev (dari 0x0)",
                 "senders": [], "tokens": ins.get("tokens", [])}
        elif senders:
            slist = []
            for sa, si in senders.items():
                si = si or {}
                sp = si.get("spread") or {}
                kind = si.get("kind") or (
                    "MASS_SPREAD" if (sp.get("max_recipients") or 0) >= 20 else "TRANSFER")
                slist.append({"addr": sa, "kind": kind, "spread": sp})
            if any(s["addr"] in funders for s in slist):
                o = {"kind": "CLUSTER", "label": "Cluster / fleet operator",
                     "senders": slist, "tokens": ins.get("tokens", [])}
            else:
                o = {"kind": "TRANSFER", "label": "Transfer personal (OTC/hibah?)",
                     "senders": slist, "tokens": ins.get("tokens", [])}
        if o is None:
            for lab in v.get("labels", []):
                if lab.startswith("CLUSTER_MEMBER"):
                    f = ((evd.get(lab) or {}).get("funder") or "").lower()
                    if f:
                        o = {"kind": "CLUSTER", "label": "Funding cluster",
                             "senders": [{"addr": f, "kind": "FUNDER"}],
                             "tokens": [], "cluster": lab.split(":", 1)[1]}
                    break
        if o:
            origins[a] = o

    return {
        "meta": {
            "chain": "Robinhood Chain", "chain_id": 4663, "explorer": EXPLORER,
            "labels_generated": labels_doc["generated_at"],
            "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "swap_from": ts_min, "swap_to": ts_max,
            "swaps_total": priced + unpriced, "priced": priced, "unpriced": unpriced, "outliers": outliers,
            "type_counts": Counter(v["primary_type"] for v in W.values()),
            "label_counts": Counter(l for v in W.values() for l in v["labels"]),
            "checkpoints": checkpoints, "calibrated": calibrated,
        },
        "types": types, "labels": label_names, "tokens": tokens, "spark": {str(k): v for k, v in spark.items()},
        "wallets": rows,
        "swaps": {str(k): v for k, v in swaps_by_w.items()}, "ev": {str(k): v for k, v in ev.items()}, "origins": origins,
        "bundles": sorted(bundles.values(), key=lambda b: -len(b["members"])),
        "clusters": list(clusters.values()),
        "known": known,
    }


if __name__ == "__main__":
    d = build()
    m = d["meta"]
    print(f"wallets={len(d['wallets'])} active={len(d['swaps'])} tokens={len(d['tokens'])} "
          f"swaps={m['swaps_total']} priced={m['priced']} outliers={m['outliers']} "
          f"bundles={len(d['bundles'])} clusters={len(d['clusters'])}")
