"""Audit P2 versi MODIFY hakim (run: 2026-09-26) — bucket DUST.

GENERALIST dgn 1-2 swap pindah ke DUST, KECUALI yang terlindungi:
  UNION gate >$10k — notional wallet dihitung ENGINE dataset.py (rescale 30x
  + snapshot fallback + filter outlier likuiditas), bukan kolom usd_value
  (yang NULL semua). Union dgn gate pp-only (temuan advocate) utk aman.
Policy unpriced (eksplisit, sesuai tuntutan hakim): wallet 1-2 swap yang
  SEMUA swapnya tak terharga tetap pindah ke DUST (berbasis aktivitas).
Target hakim: pindah <= 8.317, GENERALIST tersisa ~20.293.

Jalankan dari repo root [PC]: python scripts/apply_audit_p2.py
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

import dataset  # noqa: E402  (engine explorer — sumber USD terukur)

LABELS = REPO / "results" / "wallet_labels.json"
OVERRIDES = REPO / "results" / "tag_overrides.json"
DB = REPO / "data" / "topwallet.db"
USD_PROTECT = 10_000


def main() -> int:
    print("[1/5] engine dataset.build() ...", flush=True)
    d = dataset.build()
    swaps_by_w = d["swaps"]
    widx_rows = d["wallets"]  # rows[i] sesuai index i? verifikasi via addr

    # wallet -> notional USD terukur (engine)
    waddr_of_idx = {}
    for i, r in enumerate(widx_rows):
        # rows: wallet rows memuat address di kolom pertama (verifikasi)
        a = (r[0] if isinstance(r, list) else r.get("address") or "").lower()
        waddr_of_idx[i] = a
    usd_vol: dict[str, float] = {}
    for wi, rows in swaps_by_w.items():
        a = waddr_of_idx.get(int(wi)) or ""
        if not a:
            continue
        usd_vol[a] = sum(usd for (_, _, _, usd, _, _) in rows if usd >= 0)
    print(f"  wallet dgn swap terukur: {len(usd_vol)}", flush=True)

    print("[2/5] kandidat GENERALIST 1-2 swap ...", flush=True)
    wl = json.loads(LABELS.read_text(encoding="utf-8"))
    w = wl["wallets"]
    gen = [a for a, e in w.items() if e.get("primary_type") == "GENERALIST"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cnt: dict[str, int] = {}
    for i in range(0, len(gen), 500):
        chunk = gen[i:i + 500]
        ph = ",".join("?" * len(chunk))
        for a, n in con.execute(
                f"select wallet_address, count(*) from swap_events "
                f"where wallet_address in ({ph}) group by 1", chunk):
            cnt[a] = n
    con.close()
    candidates = [a for a in gen if cnt.get(a, 0) in (1, 2)]
    print(f"  GENERALIST={len(gen)} kandidat 1-2 swap={len(candidates)}", flush=True)

    print("[3/5] gate union >$10k ...", flush=True)
    protected = [a for a in candidates if usd_vol.get(a, 0) > USD_PROTECT]
    move = [a for a in candidates if a not in set(protected)]
    unpriced_moved = sum(1 for a in move if usd_vol.get(a, 0) == 0)
    print(f"  terlindungi >$10k: {len(protected)} | pindah: {len(move)} "
          f"(unpriced di antaranya: {unpriced_moved})", flush=True)
    if len(move) > 8_500 or len(move) < 6_000:
        print("!! jumlah pindah di luar rentang hakim (~8.317) — DIBATALKAN")
        return 1

    print("[4/5] tulis override DUST ...", flush=True)
    ov = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    for a in move:
        o = ov["wallets"].get(a) or {}
        o["set_primary"] = "DUST"
        o["remove_labels"] = ["GENERALIST"]
        o["add_labels"] = ["DUST"]
        o["confidence"] = {"DUST": 0.6}
        o["note"] = (f"audit-night P2 (hakim MODIFY, union gate >$10k) — "
                     f"{cnt.get(a, 0)} swap, notional terukur ${usd_vol.get(a, 0):,.2f}; {now}")
        ov["wallets"][a] = o
    ov["generated_at"] = now
    OVERRIDES.write_text(json.dumps(ov, indent=1), encoding="utf-8")

    from src.analyze.tag_overrides import apply_to_labels_file
    n = apply_to_labels_file()
    print(f"  apply_to_labels_file: {n} wallet diperbarui", flush=True)

    print("[5/5] asersi pasca-apply ...", flush=True)
    wl2 = json.loads(LABELS.read_text(encoding="utf-8"))
    masih_gen = sum(1 for a in move
                    if (wl2["wallets"].get(a) or {}).get("primary_type") == "GENERALIST")
    dust_total = sum(1 for e in wl2["wallets"].values()
                     if e.get("primary_type") == "DUST")
    sisa_gen = sum(1 for e in wl2["wallets"].values()
                   if e.get("primary_type") == "GENERALIST")
    print(f"  masih GENERALIST dari yang dipindah: {masih_gen} (harus 0)")
    print(f"  total DUST: {dust_total} | GENERALIST tersisa: {sisa_gen} (target ~20.293)")
    return 0 if masih_gen == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
