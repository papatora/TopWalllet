"""Extract & tidy ALL wallets from the DB — runs on the VPS, read-only.

Produces:
  results/wallet_labels.json          REGENERATED from wallet_labels table
                                      (fresher than the last analyze export;
                                      primary type re-derived via taxonomy
                                      priority; tag_overrides then merged)
  results/wallet_extract.csv          one row per wallet (94K+): kategori,
                                      aktivitas, skor, cluster, verification
  results/wallet_extract_summary.json rollup per kategori + verification

Safe beside a running pipeline: DB opened read-only (WAL allows concurrent
readers), no DB writes anywhere.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import settings  # noqa: E402
from src.analyze.wallet_classifier import PRIMARY_PRIORITY  # noqa: E402

RESULTS = Path(settings.results_dir)
NOW = datetime.now(timezone.utc).isoformat()


def sqlite_path() -> Path:
    url = settings.database_url
    tail = url.split("///", 1)[1] if "///" in url else url
    p = Path(tail)
    return p if p.is_absolute() else Path.cwd() / p


def derive_primary(labels: list[str]) -> str:
    for prio in PRIMARY_PRIORITY:
        for lab in labels:
            if lab == prio or lab.startswith(prio + ":"):
                return lab if ":" in lab and lab.startswith("CLUSTER") else prio
    return "GENERALIST"


def main() -> int:
    db = sqlite3.connect(f"file:{sqlite_path()}?mode=ro", uri=True)
    db.execute("PRAGMA busy_timeout=30000")
    db.row_factory = sqlite3.Row

    # ---------------- labels dari DB ----------------
    labels_by_wallet: dict[str, dict] = defaultdict(dict)  # wallet -> {label: (conf, evidence)}
    for row in db.execute("SELECT wallet_address, label, confidence, evidence FROM wallet_labels"):
        try:
            ev = json.loads(row["evidence"] or "{}")
        except (ValueError, TypeError):
            ev = {}
        labels_by_wallet[row["wallet_address"]][row["label"]] = (row["confidence"] or 0.0, ev)

    wallets_meta = {r["address"]: r for r in db.execute(
        "SELECT address, status, first_seen, last_active FROM wallets")}

    # ---------------- swap aggregates ----------------
    agg: dict[str, tuple] = {}
    for r in db.execute(
        "SELECT wallet_address, COUNT(*) n, "
        "SUM(CASE WHEN side='BUY' THEN 1 ELSE 0 END) buys, "
        "SUM(CASE WHEN side='SELL' THEN 1 ELSE 0 END) sells, "
        "COUNT(DISTINCT token_address) toks, "
        "MIN(block_num) b0, MAX(block_num) b1 "
        "FROM swap_events GROUP BY wallet_address"
    ):
        agg[r["wallet_address"]] = (r["n"], r["buys"] or 0, r["sells"] or 0,
                                    r["toks"], r["b0"] or 0, r["b1"] or 0)

    # ---------------- scores ----------------
    scores: dict[str, tuple] = {}
    for r in db.execute(
        "SELECT wallet_address, composite_score, trading_style, cluster_id, metrics "
        "FROM wallet_scores"
    ):
        try:
            m = json.loads(r["metrics"] or "{}")
        except (ValueError, TypeError):
            m = {}
        pnl = m.get("realized_pnl_usd") or m.get("realized_pnl") or None
        scores[r["wallet_address"]] = (r["composite_score"], r["trading_style"],
                                       r["cluster_id"] or "", pnl)

    # ---------------- verification status ----------------
    vfile = RESULTS / "tag_verification.json"
    verdict_by_wallet: dict[str, list[str]] = defaultdict(list)
    if vfile.exists():
        try:
            tv = json.loads(vfile.read_text(encoding="utf-8"))
            for key, v in (tv.get("insider") or {}).items():
                w = key.split(":", 1)[0]
                verdict_by_wallet[w].append(str(v.get("verdict")))
        except (ValueError, OSError):
            pass

    def verified_status(w: str) -> str:
        vs = set(verdict_by_wallet.get(w, []))
        if vs & {"CONFIRMED_INSIDER", "MINT_ALLOCATION"}:
            return "insider_proven"
        if "TRADER_MISREAD" in vs:
            return "insider_overturned"
        if "AIRDROP_SPAM" in vs:
            return "airdrop_spam"
        if "UNRESOLVED" in vs:
            return "unproven"
        return ""

    # ---------------- wallet_labels.json (regenerated) ----------------
    wallets_out: dict[str, dict] = {}
    for w, lab_map in labels_by_wallet.items():
        labels = sorted(lab_map)
        evidence = {lab: info[1] for lab, info in lab_map.items() if info[1]}
        confidence = {lab: round(info[0], 2) for lab, info in lab_map.items()}
        wallets_out[w] = {
            "primary_type": derive_primary(labels),
            "labels": labels,
            "evidence": evidence,
            "confidence": confidence,
        }

    # tag_overrides merge (jika ada hasil verification)
    try:
        from src.analyze.tag_overrides import apply_overrides, load_overrides

        payload = {
            "generated_at": NOW,
            "taxonomy": "docs/WALLET_TAXONOMY.md (14 types; primary = priority 1→14)",
            "source": "scripts/extract_wallets.py (regenerated from wallet_labels table)",
            "summary": {},
            "wallets": wallets_out,
        }
        payload, changed = apply_overrides(payload, load_overrides(RESULTS))
        wallets_out = payload["wallets"]
    except Exception as e:  # jangan gagalkan extract karena overrides
        changed = 0
        print("overrides merge skipped:", e)

    labels_doc = {
        "generated_at": NOW,
        "taxonomy": "docs/WALLET_TAXONOMY.md (14 types; primary = priority 1→14)",
        "source": "regenerated from wallet_labels table by scripts/extract_wallets.py",
        "summary": {
            "wallets_classified": len(wallets_out),
            "labels_assigned": sum(len(v["labels"]) for v in wallets_out.values()),
            "primary_types": dict(sorted(Counter(
                v["primary_type"] for v in wallets_out.values()).items())),
            "overrides_applied": changed,
        },
        "wallets": wallets_out,
    }
    (RESULTS / "wallet_labels.json").write_text(
        json.dumps(labels_doc, indent=1, default=str), encoding="utf-8")

    # ---------------- wallet_extract.csv ----------------
    csv_path = RESULTS / "wallet_extract.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["wallet", "status", "primary_type", "labels", "swaps", "buys",
                     "sells", "tokens", "first_block", "last_block", "first_seen",
                     "last_active", "score", "style", "cluster_id", "est_pnl_usd",
                     "verified"])
        for addr, meta in wallets_meta.items():
            n, buys, sells, toks, b0, b1 = agg.get(addr, ("", "", "", "", "", ""))
            score, style, cluster, pnl = scores.get(addr, ("", "", "", ""))
            entry = wallets_out.get(addr)
            primary = entry["primary_type"] if entry else "UNCLASSIFIED"
            labels = ";".join(entry["labels"]) if entry else ""
            wr.writerow([
                addr, meta["status"], primary, labels, n, buys, sells, toks,
                b0, b1, meta["first_seen"], meta["last_active"],
                score, style, cluster, pnl, verified_status(addr),
            ])

    # ---------------- summary ----------------
    with_swaps = len(agg)
    types = Counter(v["primary_type"] for v in wallets_out.values())
    unclassified = len(wallets_meta) - len(wallets_out)
    clusters: dict[str, dict] = defaultdict(lambda: {"members": 0, "funder": ""})
    for w, lab_map in labels_by_wallet.items():
        for lab in lab_map:
            if lab.startswith("CLUSTER_MEMBER:"):
                cid = lab.split(":", 1)[1]
                clusters[cid]["members"] += 1
                clusters[cid]["funder"] = (lab_map[lab][1] or {}).get("funder", "")

    verdict_counts = Counter(v for ws in verdict_by_wallet.values() for v in ws)
    summary = {
        "generated_at": NOW,
        "universe": {
            "wallets_total": len(wallets_meta),
            "wallets_with_swaps": with_swaps,
            "wallets_classified": len(wallets_out),
            "wallets_unclassified": unclassified,
            "swap_events": sum(a[0] for a in agg.values()),
            "tokens_in_db": db.execute("SELECT COUNT(*) FROM tokens").fetchone()[0],
        },
        "primary_types": dict(types.most_common()),
        "verification": dict(verdict_counts.most_common()),
        "clusters": dict(clusters),
        "top_by_swaps": [
            {"wallet": w, "swaps": a[0], "tokens": a[3],
             "primary_type": wallets_out[w]["primary_type"] if w in wallets_out else "UNCLASSIFIED"}
            for w, a in sorted(agg.items(), key=lambda kv: -kv[1][0])[:50]
        ],
        "files": {
            "csv": "results/wallet_extract.csv",
            "labels": "results/wallet_labels.json",
        },
    }
    (RESULTS / "wallet_extract_summary.json").write_text(
        json.dumps(summary, indent=1, default=str), encoding="utf-8")

    print(json.dumps(summary["universe"], indent=1))
    print("primary_types:", dict(types.most_common()))
    print("csv rows:", len(wallets_meta))
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
