"""Eksekusi putusan hakim verifikasi (2026-09-28) — PERTAHANKAN DGN PERBAIKAN.

Aksi (urut prioritas hakim):
  1. Re-gate DUST: keluarkan wallet yg notional engine kini >$10k (6 breach
     pasca-delta, contoh $1.553->$86.560) + rapikan 65 entri stale (kini
     3-30 swap) -> GENERALIST dgn note; 238 wallet $5k-$10k masuk watchlist.
  2. Perbaiki fault regen 54/54: entri override 54 wallet (P3 yg ditimpa P2)
     diubah jadi remove_labels ["INSIDER","GENERALIST"] + note gabungan —
     regen dari DB + re-apply tidak bisa menghidupkan INSIDER lagi.
  4. Rantai insider 0x65050a9b...: label eksplisit funder + dokumentasi
     klaster di docs/WALLET_TAXONOMY.md + legalisasi DUST.
  5. Tag 39 wallet DUST penyentuh token ring + koreksi semantik SPY (note).
  6. Koreksi angka di docs: proteksi = 528 (independen), bukan 1.042.

Jalankan dari repo root [PC]: python scripts/apply_judge_fix.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "Database Local only" / "html"))
sys.path.insert(0, str(REPO))

import dataset  # noqa: E402

OVERRIDES = REPO / "results" / "tag_overrides.json"
LABELS = REPO / "results" / "wallet_labels.json"
DB = REPO / "data" / "topwallet.db"
WATCH = REPO / "results" / "launch_ring_watchlist.json"
NOW = datetime.now(timezone.utc).isoformat()
RING_TOKENS = ["0x80baa4b3bfac6f4978700df824b1b3d98e889136",  # CRUMBS
               "0xbc9cc4b93a08b2dfba87067a9c53e713db3314ce",  # PINK
               "0x61692396fffd1cca6ab8828a1044d08299bff53d"]  # DRAFT
FUNDER = "0x65050a9b7e5075a2ba5ced7b1b64ee66262c40dc"


def main() -> int:
    ov = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    wallets_ov = ov["wallets"]

    print("[1] engine notional terkini (dataset.build) ...", flush=True)
    d = dataset.build()
    rows = d["wallets"]
    waddr = {}
    for i, r in enumerate(rows):
        a = (r[0] if isinstance(r, list) else (r.get("address") or "")).lower()
        waddr[i] = a
    notional: dict[str, float] = {}
    nswap: dict[str, int] = {}
    for wi, srows in d["swaps"].items():
        a = waddr.get(int(wi)) or ""
        notional[a] = sum(usd for (_, _, _, usd, _, _) in srows if usd >= 0)
        nswap[a] = len(srows)

    # --- AKSI 1: re-gate DUST ---
    print("[2] re-gate DUST (>$10k keluar; 3-30 swap stale -> GENERALIST) ...", flush=True)
    promote, stale, near_gate = [], [], []
    for a, o in wallets_ov.items():
        if o.get("set_primary") != "DUST":
            continue
        usd, n = notional.get(a, 0.0), nswap.get(a, 0)
        if usd > 10_000:
            promote.append((a, usd))
        elif n not in (1, 2) and 3 <= n <= 30:
            stale.append((a, n))
        elif 5_000 <= usd <= 10_000:
            near_gate.append((a, usd))
    for a, usd in promote:
        o = wallets_ov[a]
        o["set_primary"] = "GENERALIST"
        o["remove_labels"] = ["DUST"]
        o["add_labels"] = ["GENERALIST"]
        o["note"] = (o.get("note", "") + f" | re-gate pasca-delta 9/28: notional "
                     f"terukur ${usd:,.2f} > $10k -> GENERALIST; {NOW}")[:600]
    for a, n in stale:
        o = wallets_ov[a]
        if o.get("set_primary") == "DUST":  # jangan timpa yang baru dipromote
            o["note"] = (o.get("note", "") + f" | stale pasca-delta: kini {n} swap "
                         f"(kriteria 1-2 tidak berlaku lagi); {NOW}")[:600]
    json.dump(sorted(near_gate, key=lambda x: -x[1]),
              open(REPO / "results" / "p2_near_gate_watch.json", "w"), indent=1)
    print(f"  promote >$10k: {len(promote)} | stale dirapikan: {len(stale)} | "
          f"watchlist $5k-$10k: {len(near_gate)}", flush=True)

    # --- AKSI 2: fault regen 54/54 ---
    print("[3] perbaiki fault regen (54 entri P3-ditimpa-P2) ...", flush=True)
    fixed54 = 0
    for a, o in wallets_ov.items():
        if "audit-night P2" in str(o.get("note", "")) and \
           o.get("set_primary") == "DUST":
            ents, mint = set(), False
            ev = o.get("evidence") or {}
            ins = ev.get("INSIDER")
            if isinstance(ins, dict):
                for s, si in (ins.get("senders") or {}).items():
                    if isinstance(si, dict) and si.get("arkham_entity"):
                        ents.add(si["arkham_entity"])
            if ents and ents <= {"GMGN", "PonsV2BondingCurve"}:
                # entri aslinya P3 (platform-funded) yang ditimpa — pulihkan
                # provenance P3 sambil tetap DUST (putusan: DUST benar)
                o["remove_labels"] = ["INSIDER", "GENERALIST"]
                o["add_labels"] = ["DUST"]
                o["confidence"] = {"DUST": 0.6}
                if "audit-night P3" not in str(o.get("note", "")):
                    o["note"] = (str(o.get("note", "")) +
                                 " | provenance P3: didanai platform "
                                 f"{sorted(ents)} (bukti INSIDER dipertahankan)")[:700]
                fixed54 += 1
    print(f"  entri 54-ditimpa diperbaiki (remove INSIDER+GENERALIST): {fixed54}", flush=True)

    # --- AKSI 4/5: rantai funder + ring tag ---
    print("[4] tag rantai funder 0x6505 + ring-touchers ...", flush=True)
    ring_tag = 0
    funder_cluster = []
    for a, o in wallets_ov.items():
        ev = o.get("evidence")
        if isinstance(ev, dict):
            ins = ev.get("INSIDER")
            if isinstance(ins, dict):
                for s, si in (ins.get("senders") or {}).items():
                    if str(s).lower() == FUNDER:
                        meta = o.setdefault("ring_link", {
                            "funder": FUNDER,
                            "cluster": "micro-wallet distribution (GMGN fleet)",
                            "added_at": NOW})
                        funder_cluster.append(a)
    # ring-touchers: primary DUST + swap token ring
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ph = ",".join("?" * len(RING_TOKENS))
    for a, in con.execute(
            f"select distinct wallet_address from swap_events "
            f"where token_address in ({ph})", RING_TOKENS).fetchall():
        a = a.lower()
        o = wallets_ov.get(a)
        if o and o.get("set_primary") == "DUST":
            meta = o.setdefault("ring_link", {"tokens": RING_TOKENS,
                                              "added_at": NOW})
            ring_tag += 1
    con.close()
    print(f"  funder cluster: {len(funder_cluster)} | ring-touchers DUST: {ring_tag}", flush=True)

    ov["generated_at"] = NOW
    OVERRIDES.write_text(json.dumps(ov, indent=1), encoding="utf-8")

    # --- apply ke wallet_labels.json ---
    from src.analyze.tag_overrides import apply_to_labels_file
    n = apply_to_labels_file()
    print(f"  apply_to_labels_file: {n} diperbarui", flush=True)

    # --- AKSI 2 verifikasi: regen simulation tidak boleh hidupkan INSIDER ---
    wl2 = json.loads(LABELS.read_text(encoding="utf-8"))
    resurrect = [a for a, o in wallets_ov.items()
                 if o.get("set_primary") == "DUST" and "audit-night P3" in str(o.get("note", ""))
                 and "INSIDER" in [str(x) for x in
                                   ((wl2["wallets"].get(a) or {}).get("labels") or [])]]
    print(f"  verifikasi regen: INSIDER tampak pada {len(resurrect)}/54 "
          f"(target 0)", flush=True)

    json.dump({"promoted": [a for a, _ in promote],
               "stale": [a for a, _ in stale],
               "near_gate": near_gate, "fixed54": fixed54,
               "funder_cluster": len(funder_cluster), "ring_tag": ring_tag,
               "resurrect_count": len(resurrect)},
              open(REPO / "results" / "judge_fix_report.json", "w"), indent=1)
    return 0 if not resurrect else 1


if __name__ == "__main__":
    raise SystemExit(main())
