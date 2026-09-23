"""Build the verification base for WF-1 — deterministic, read-only.

Output results/verification_base.json:
  groups:   per label-group: stats + sample wallets (max 60/group)
  golden:   deterministic golden-wallet candidates (rules from 07 criteria)
  noise:    deterministic noise candidates (no swaps / dust / unlabeled)
  clusters: be41 + f70d member facts
"""
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "topwallet.db"
SAMPLE = 60

BAD_LABELS = {"INSIDER", "AIRDROP_FARMER", "PHISHING_TARGET", "BUNDLER_SUSPECT",
              "MEV_BOT", "DEV", "SNIPER_BOT", "TRADER_COVERAGE_GAP"}

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

labels = defaultdict(dict)   # addr -> {label: conf}
for r in con.execute("SELECT wallet_address, label, confidence FROM wallet_labels"):
    labels[r["wallet_address"].lower()][r["label"]] = round(r["confidence"] or 0, 2)

stats = {}
for r in con.execute("""SELECT wallet_address,
        COUNT(*) n, SUM(side='BUY') buys, SUM(side='SELL') sells,
        COUNT(DISTINCT token_address) toks,
        ROUND(SUM(CASE WHEN side='BUY' THEN usd_value ELSE -usd_value END), 0) net,
        MIN(block_num) b0, MAX(block_num) b1
        FROM swap_events GROUP BY wallet_address"""):
    stats[r["wallet_address"].lower()] = dict(r)

groups: dict[str, list] = defaultdict(list)
for addr, lab in labels.items():
    primary = sorted(lab.items(), key=lambda x: -x[1])[0][0] if lab else "GENERALIST"
    for l in lab:
        groups[l.split(":")[0]].append(addr)

out = {"groups": {}, "golden": [], "noise_count": 0, "noise_sample": [],
       "clusters": {}}
seen_golden = set()

for gname, addrs in sorted(groups.items()):
    entries = []
    for a in addrs:
        s = stats.get(a, {})
        lab = labels.get(a, {})
        entries.append({
            "addr": a, "labels": sorted(lab), "conf": lab,
            "swaps": s.get("n", 0), "buys": s.get("buys", 0) or 0,
            "sells": s.get("sells", 0) or 0, "toks": s.get("toks", 0) or 0,
            "net_usd": s.get("net", 0) or 0,
            "span_days": round(((s.get("b1") or 0) - (s.get("b0") or 0)) * 2 / 86400, 1),
        })
    entries.sort(key=lambda e: -e["swaps"])
    bad = sum(1 for e in entries if BAD_LABELS & set(e["labels"]))
    balanced = sum(1 for e in entries
                   if e["swaps"] >= 20 and abs(e["buys"] - e["sells"]) <= max(2, e["swaps"] * 0.05))
    out["groups"][gname] = {
        "count": len(entries),
        "bad_labels_inside": bad,
        "balanced_traders": balanced,
        "sample": entries[:SAMPLE],
    }

# golden candidates: aturan 07_COPYTRADE (versi lokal, tanpa skor VPS)
for addr, s in stats.items():
    lab = labels.get(addr, {})
    if BAD_LABELS & set(lab):
        continue
    if (s["n"] or 0) < 20 or (s["toks"] or 0) < 3:
        continue
    if (s["net"] or 0) < 1000:
        continue
    span = ((s["b1"] or 0) - (s["b0"] or 0)) * 2 / 86400
    if span < 14:
        continue
    if addr in seen_golden:
        continue
    seen_golden.add(addr)
    out["golden"].append({
        "addr": addr, "labels": sorted(lab), "swaps": s["n"],
        "toks": s["toks"], "net_usd": s["net"], "span_days": round(span, 1),
    })
out["golden"].sort(key=lambda g: -g["net_usd"])
out["golden"] = out["golden"][:150]

# noise: wallet TANPA swap sama sekali (top-up tak terklasifikasi)
total_wallets = con.execute("SELECT COUNT(*) FROM wallets").fetchone()[0]
no_swap = con.execute("""SELECT COUNT(*) FROM wallets w
                         WHERE NOT EXISTS (SELECT 1 FROM swap_events s
                                           WHERE s.wallet_address = w.address)""").fetchone()[0]
out["noise_count"] = no_swap
out["total_wallets"] = total_wallets
out["noise_sample"] = [r[0] for r in con.execute(
    """SELECT address FROM wallets w WHERE NOT EXISTS
       (SELECT 1 FROM swap_events s WHERE s.wallet_address = w.address) LIMIT 25""")]

# clusters
for cid in ("cluster_be41", "cluster_f70d"):
    mem = [r[0] for r in con.execute(
        "SELECT wallet_address FROM wallet_labels WHERE label=?", (f"CLUSTER_MEMBER:{cid}",))]
    det = []
    for a in mem:
        s = stats.get(a, {})
        det.append({"addr": a, "swaps": s.get("n", 0),
                    "buys": s.get("buys", 0) or 0, "sells": s.get("sells", 0) or 0,
                    "toks": s.get("toks", 0) or 0})
    out["clusters"][cid] = det

(OUT := REPO / "results" / "verification_base.json").write_text(
    json.dumps(out, indent=1), encoding="utf-8")
print(f"groups={len(out['groups'])} golden={len(out['golden'])} "
      f"noise={out['noise_count']} total_wallets={total_wallets}")
