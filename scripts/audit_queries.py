"""Ekstraktor bukti audit P1-P3 (read-only) — output JSON ke stdout.

Dipakai subagent workflow debat via:
  python scripts/audit_queries.py p1|p2|p3|all

ANTI-HALU: hanya angka dari data lokal nyata (DB + wallet_labels.json +
tag_overrides.json). Tanpa perkiraan.
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "topwallet.db"
LABELS = REPO / "results" / "wallet_labels.json"
OVERRIDES = REPO / "results" / "tag_overrides.json"


def q(sql: str, args: tuple = ()) -> list:
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = c.execute(sql, args).fetchall()
    c.close()
    return rows


def p1() -> dict:
    """Facet (label sekunder) vs primary — kandidat promosi."""
    wl = json.loads(LABELS.read_text(encoding="utf-8"))["wallets"]
    prim = Counter(e.get("primary_type") for e in wl.values())
    facet = Counter()
    promoted_examples = {}
    for addr, e in wl.items():
        p = e.get("primary_type")
        for l in (e.get("labels") or []):
            l = str(l)
            if l != p:
                facet[l] += 1
                promoted_examples.setdefault(l, []).append(addr)
    return {
        "primary_counts": dict(prim.most_common()),
        "facet_vs_primary_gap": {k: v for k, v in facet.most_common(15)},
        "contoh_addr": {k: v[:3] for k, v in promoted_examples.items()
                        if k in ("SNIPER", "AIRDROP_FARMER", "MEV_BOT", "PHISHING_TARGET")},
        "total_wallets": len(wl),
    }


def p2() -> dict:
    """GENERALIST dgn 1-2 swap — profil dpt jadi DUST."""
    wl = json.loads(LABELS.read_text(encoding="utf-8"))["wallets"]
    gen = [a for a, e in wl.items() if e.get("primary_type") == "GENERALIST"]
    dist = Counter()
    dust_addrs = []
    for i in range(0, len(gen), 500):
        chunk = gen[i:i + 500]
        ph = ",".join("?" * len(chunk))
        for a, n in q(f"select wallet_address, count(*) from swap_events "
                      f"where wallet_address in ({ph}) group by 1", tuple(chunk)):
            dist[n] += 1
            if n <= 2 and len(dust_addrs) < 5:
                dust_addrs.append(a)
    one_two = sum(v for k, v in dist.items() if k <= 2)
    usd = q("select count(*) from (select wallet_address, sum(coalesce(usd_value,0)) s "
            "from swap_events group by 1 having count(*) <= 2 and s > 10000)")
    return {
        "generalist_total": len(gen),
        "swap_dist_1_2_3_5_6_10_lebih": {
            "1-2": one_two, "3-5": sum(v for k, v in dist.items() if 3 <= k <= 5),
            "6-10": sum(v for k, v in dist.items() if 6 <= k <= 10),
            ">10": sum(v for k, v in dist.items() if k > 10)},
        "dust_tapi_usd_diatas_10k": usd[0][0] if usd else 0,
        "contoh_dust": dust_addrs,
    }


def p3() -> dict:
    """294 wallet platform-funded (bukti arkham_entity) — sebaran label."""
    ov = json.loads(OVERRIDES.read_text(encoding="utf-8"))["wallets"]
    wl = json.loads(LABELS.read_text(encoding="utf-8"))["wallets"]
    by_entity = Counter()
    by_primary = Counter()
    sample = {}
    for addr, o in ov.items():
        ev = o.get("evidence")
        if not isinstance(ev, dict):
            continue
        ent = None
        for g, e in ev.items():
            if isinstance(e, dict):
                for s, sinfo in (e.get("senders") or {}).items():
                    if isinstance(sinfo, dict) and sinfo.get("arkham_entity"):
                        ent = sinfo["arkham_entity"]
        if not ent:
            continue
        by_entity[ent] += 1
        pr = wl.get(addr, {}).get("primary_type", "?")
        by_primary[pr] += 1
        sample.setdefault(ent, []).append(addr)
    return {
        "total_platform_funded": sum(by_entity.values()),
        "by_arkham_entity": dict(by_entity.most_common()),
        "by_primary_type": dict(by_primary.most_common()),
        "contoh_per_entity": {k: v[:2] for k, v in sample.items()},
    }


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    out = {}
    if which in ("p1", "all"):
        out["P1"] = p1()
    if which in ("p2", "all"):
        out["P2"] = p2()
    if which in ("p3", "all"):
        out["P3"] = p3()
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    main()
