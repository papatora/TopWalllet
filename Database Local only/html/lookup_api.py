"""Goal #4 — paste-CA lookup engine for the local explorer.

Input apa pun yang mengandung alamat 0x…  (CA mentah, link GMGN
gmgn.ai/robinhood/token/<ca>, link DexScreener, link Arkham) → laporan
token: rating 0-10 dengan rincian komponen, cluster/label wallet kita,
deployer + funder, sosial, status di-DB.

Sumber (mesin lokal, sama seperti dataset.py):
  - data/topwallet.db                       snapshot (in-DB?)
  - results/tag_overrides.json              cluster/label wallet kita
  - results/bubblemaps/<ca>.json            capture Goal #5 (ghost supply)
  - html/data/known_entities.json           entitas Arkham (108)
  - results/arkham_entities.json            arkham mentah (652)
  - DexScreener API langsung (chainId robinhood)   harga/likuiditas/sosial
  - Etherscan V2 (chainid=4663)             deployer + funder pertama

Tidak ada VPS di jalur ini. Rating JUJUR: tiap komponen dikembalikan
utk ditampilkan, bukan angka hitam.
"""
from __future__ import annotations

import json
import re
import ssl
import sqlite3
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DB = REPO / "data" / "topwallet.db"
OVERRIDES = REPO / "results" / "tag_overrides.json"
ARKHAM = REPO / "results" / "arkham_entities.json"
BUBBLE_DIR = REPO / "results" / "bubblemaps"
KNOWN = Path(__file__).resolve().parent / "data" / "known_entities.json"

CA_RE = re.compile(r"0x[0-9a-fA-F]{40}")
DEXSCREENER = "https://api.dexscreener.com/latest/dex/tokens/{ca}"
ETH_V2 = ("https://api.etherscan.io/v2/api?chainid=4663&module={mod}&action={act}"
          "&apikey={key}")
ETHERSCAN_KEYS = ["X475JYM3UEN2PXK67RXEVPFM8EN3PJ43YZ", "JMTCYFQQXKU8KDH5K8PC477D2MNUJZMP2"]
_key_i = 0

_cache: dict[str, tuple[float, dict]] = {}
TTL_S = 600


def parse_input(raw: str) -> str | None:
    m = CA_RE.search(raw or "")
    return m.group(0).lower() if m else None


def _get(url: str, timeout: int = 15) -> dict | list | None:
    req = urllib.request.Request(url, headers={"accept": "application/json",
                                               "user-agent": "TopWallet-lookup/1.0"})
    # Python sistem kadang membawa CA bundle kadaluarsa → coba certifi,
    # lalu default, terakhir tanpa verifikasi (endpoint publik baca-saja).
    ctxs = []
    try:
        import certifi
        ctxs.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        pass
    ctxs.append(ssl.create_default_context())
    ctxs.append(ssl._create_unverified_context())  # noqa: SLF001 — fallback terakhir
    last: Exception | None = None
    for ctx in ctxs:
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
    print(f"[lookup] fetch gagal {url[:80]}: {type(last).__name__}: {str(last)[:120]}")
    return None


def _eth_key() -> str:
    global _key_i
    k = ETHERSCAN_KEYS[_key_i]
    _key_i = (_key_i + 1) % len(ETHERSCAN_KEYS)
    return k


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _known_entity(addr: str) -> str | None:
    for src, shape in ((KNOWN, "known"), (ARKHAM, "arkham")):
        d = _load(src)
        if not d:
            continue
        if shape == "known":
            if addr in d:
                ent = d[addr]
                return ent.get("entity") or ent.get("label") if isinstance(ent, dict) else str(ent)
        else:
            v = d.get(addr)
            if v and isinstance(v, dict) and v.get("entity"):
                return v["entity"]
    return None


def _db_side(ca: str) -> dict:
    out: dict = {"in_db": False}
    if not DB.exists():
        return out
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        t = con.execute("select symbol,name,price_usd,liquidity_usd,volume_24h_usd,"
                        "first_seen from tokens where address=?", (ca,)).fetchone()
        if t is None:
            return out
        out["in_db"] = True
        out["symbol"] = t["symbol"]
        out["name"] = t["name"]
        out["first_seen"] = t["first_seen"]
        agg = con.execute(
            "select count(distinct wallet_address) traders, count(*) swaps,"
            " sum(case when side='BUY' then 1 else 0 end) buys,"
            " min(ts) first_swap, max(ts) last_swap,"
            " sum(coalesce(usd_value,0)) usd_est"
            " from swap_events where token_address=?", (ca,)).fetchone()
        out["traders"] = agg["traders"]
        out["swaps"] = agg["swaps"]
        out["buys"] = agg["buys"]
        out["usd_est"] = agg["usd_est"]
        # sqlite memberi string mentah → epoch detik (kontrak date() frontend)
        from datetime import datetime
        for k in ("first_swap", "last_swap"):
            v = agg[k]
            if isinstance(v, str) and v:
                try:
                    out[k] = datetime.fromisoformat(v.replace(" ", "T")).timestamp()
                except ValueError:
                    out[k] = None
            else:
                out[k] = None
        out["scored_wallets"] = con.execute(
            "select count(*) from wallet_scores").fetchone()[0]
        pools = con.execute(
            "select dex,version,quote_symbol,liquidity_usd,price_usd from pools"
            " where token_address=? order by coalesce(liquidity_usd,0) desc limit 3",
            (ca,)).fetchall()
        out["pools"] = [dict(p) for p in pools]
    finally:
        con.close()
    return out


def _cluster_side(ca: str) -> dict:
    ov = _load(OVERRIDES) or {}
    wallets = ov.get("wallets", ov)
    groups: dict[str, int] = {}
    members: list[str] = []
    for addr, entry in wallets.items():
        ev = entry.get("evidence")
        if not isinstance(ev, dict):
            continue
        hit = False
        for group, e in ev.items():
            if isinstance(e, dict) and any(
                    str(t).lower() == ca for t in (e.get("tokens") or [])):
                hit = True
                prim = entry.get("set_primary") or group
                groups[prim] = groups.get(prim, 0) + 1
        if hit:
            members.append(addr)
    return {"groups": groups, "members": members[:50], "members_total": len(members)}


def _bubble_side(ca: str) -> dict:
    f = BUBBLE_DIR / f"{ca}.json"
    if not f.exists():
        return {"captured": False}
    r = _load(f) or {}
    th = r.get("top_holders") or []
    shares = sorted(
        (((h.get("holder_data") or {}).get("share") or 0), h.get("address"))
        for h in th)
    top1 = (shares[-1][0] * 100) if shares else None
    clusters = []
    for line in (r.get("panel_clusters") or []):
        m = re.search(r"Cluster (\d+).*?\((\d+)\).*?([\d.]+)%", line)
        if m:
            clusters.append({"n": int(m.group(2)), "pct": float(m.group(3))})
    return {"captured": True, "holders": len(th), "top1_pct": top1,
            "clusters": clusters}


def _dex_side(ca: str) -> dict:
    d = _get(DEXSCREENER.format(ca=ca))
    pairs = (d or {}).get("pairs") or []
    rp = [p for p in pairs if str(p.get("chainId", "")).lower() == "robinhood"]
    if not rp:
        rp = pairs
    if not rp:
        return {"found": False}
    best = max(rp, key=lambda p: ((p.get("liquidity") or {}).get("usd") or 0))
    info = best.get("info") or {}
    socials = []
    for s in (info.get("socials") or []):
        if s.get("url"):
            socials.append({"type": s.get("type") or "link", "url": s["url"]})
    for w in (info.get("websites") or []):
        if w.get("url"):
            socials.append({"type": "website", "url": w["url"]})
    liq = ((best.get("liquidity") or {}).get("usd")) or 0
    vol = ((best.get("volume") or {}).get("h24")) or 0
    return {
        "found": True,
        "symbol": ((best.get("baseToken") or {}).get("symbol")) or "",
        "name": ((best.get("baseToken") or {}).get("name")) or "",
        "price_usd": _f(best.get("priceUsd")),
        "liquidity_usd": liq,
        "volume_24h_usd": vol,
        "pair_created_at": best.get("pairCreatedAt"),
        "socials": socials,
        "dex_id": best.get("dexId"),
        "pair_url": best.get("url"),
    }


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _chain_side(ca: str) -> dict:
    out: dict = {"deployer": None, "deploy_tx": None, "deploy_age_days": None,
                 "funder": None, "funder_entity": None}
    d = _get(ETH_V2.format(mod="contract", act="getcontractcreation",
                           key=_eth_key()) + f"&contractaddresses={ca}")
    try:
        res = ((d or {}).get("result") or None)
        # Etherscan mengembalikan result berupa STRING pesan error saat gagal
        if isinstance(res, list) and res and isinstance(res[0], dict):
            res = res[0]
            out["deployer"] = (res.get("contractCreator") or "").lower() or None
            out["deploy_tx"] = res.get("txHash")
            ts = res.get("timestamp")
            if ts:
                out["deploy_age_days"] = round(max(0, time.time() - int(ts)) / 86400, 1)
    except Exception:
        pass
    if out["deployer"]:
        f = _get(ETH_V2.format(mod="account", act="txlist", key=_eth_key())
                 + f"&address={out['deployer']}&page=1&offset=10&sort=asc")
        try:
            rows = (f or {}).get("result") or []
            if isinstance(rows, list):
                for r0 in rows:
                    if str(r0.get("from", "")).lower() not in ("", out["deployer"]):
                        out["funder"] = str(r0["from"]).lower()
                        break
        except Exception:
            pass
        if out["funder"]:
            out["funder_entity"] = _known_entity(out["funder"])
    return out


def _rating(db: dict, dex: dict, bub: dict, clu: dict) -> tuple[float, list]:
    comps = []

    def add(name: str, score: float, max: float, note: str):
        comps.append({"component": name, "score": round(score, 2), "max": max,
                      "note": note})

    liq = dex.get("liquidity_usd") or 0
    add("Likuiditas", min(2.5, (liq / 1_000_000) ** 0.5 * 2.5) if liq > 0 else 0,
        2.5, f"liquidity ${liq:,.0f}")
    vol = dex.get("volume_24h_usd") or 0
    ratio = (vol / liq) if liq > 0 else 0
    add("Volume/Liq", min(2.0, ratio * 2.0) if ratio >= 0.05 else (ratio / 0.05 * 1.0),
        2.0, f"vol24 ${vol:,.0f} · rasio {ratio:.2f}")
    age = dex.get("pair_created_at")
    age_d = (time.time() * 1000 - age) / 86_400_000 if age else None
    add("Usia", 1.0 if age_d and age_d >= 30 else (age_d / 30 if age_d else 0.2),
        1.0, f"usia pair {age_d:.1f} hari" if age_d else "usia tak diketahui")
    soc = dex.get("socials") or []
    add("Sosial", min(1.0, 0.5 * len(soc)), 1.0,
        ", ".join(s["type"] for s in soc) or "tidak ada link sosial")
    traders = db.get("traders") or 0
    pts = 0.0
    if db.get("in_db"):
        pts = min(1.0, traders / 50)
        bad = sum(n for g, n in (clu.get("groups") or {}).items()
                  if g in ("INSIDER", "MEV_BOT", "AIRDROP_FARMER"))
        good = sum(n for g, n in (clu.get("groups") or {}).items()
                   if g in ("DIAMOND", "SNIPER", "GENERALIST", "TRADER"))
        pts += min(1.0, good / 20) - min(0.8, bad / 100)
    grp_note = " · ".join(f"{g} ×{n}" for g, n in
                          sorted((clu.get("groups") or {}).items(), key=lambda kv: -kv[1]))
    add("Data & cluster lokal", max(0.0, pts), 2.0,
        f"{traders} trader di snapshot" + (f" · {grp_note}" if grp_note else ""))
    pen = 0.0
    top1 = bub.get("top1_pct") if bub.get("captured") else None
    if top1 is not None and top1 >= 50:
        pen = -min(2.5, (top1 - 50) / 20)
    add("Konsentrasi supply", pen, 2.5,
        f"top1 holder {top1:.1f}%" if top1 is not None else "belum ada capture bubblemaps (tanpa penalti)")
    total = max(0.0, min(10.0, sum(c["score"] for c in comps)))
    return total, comps


def lookup(raw: str) -> dict:
    ca = parse_input(raw)
    if not ca:
        return {"ok": False, "error": "tidak ada alamat 0x… yang valid di input"}
    hit = _cache.get(ca)
    if hit and time.time() - hit[0] < TTL_S:
        return hit[1]

    db = _db_side(ca)
    clu = _cluster_side(ca)
    bub = _bubble_side(ca)
    dex = _dex_side(ca)
    chain = _chain_side(ca) if dex.get("found") or db.get("in_db") else {"deployer": None}
    ent = {}
    for who in ("deployer", "funder"):
        a = chain.get(who)
        if a:
            ent[who] = _known_entity(a)
    chain["deployer_entity"] = ent.get("deployer")
    chain["funder_entity"] = ent.get("funder")
    rating, comps = _rating(db, dex, bub, clu)
    result = {
        "ok": True,
        "ca": ca,
        "links": {
            "gmgn": f"https://gmgn.ai/robinhood/token/{ca}",
            "dexscreener": f"https://dexscreener.com/robinhood/{ca}",
            "arkham": f"https://www.arkm.com/explorer/address/{ca}",
            "bubblemaps": f"https://v2.bubblemaps.io/map?address={ca}&chain=robinhood",
            "explorer": f"https://robin.etherscan.io/token/{ca}",
        },
        "db": db, "dex": dex, "chain": chain, "cluster": clu, "bubblemaps": bub,
        "rating": rating, "rating_components": comps,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }
    _cache[ca] = (time.time(), result)
    return result
