"""Audit P3 versi MODIFY hakim (run: 2026-09-26) — relabel TERBATAS.

Relabel wallet platform-funded: INSIDER -> GENERALIST, HANYA untuk
single-entity GMGN / PonsV2BondingCurve. Exclude ketat sesuai putusan:
  - wallet dengan >=2 entitas arkham berbeda di evidence (multi-entity)
  - wallet berbukti MINT_ALLOCATION (alokasi dev, bukan funding platform)
  - primary AIRDROP_FARMER (sudah benar)
  - proxy-family & entitas ambigu ("up", "0x", "Proxy", Uniswap, MEXC, dst)
Gate on-chain: transfer sender->wallet diverifikasi ulang via Etherscan
sebelum batch. Angka target: TEPAT 133 (GMGN 129 + PonsV2 4) sesuai
crosstab hakim. Bukti TIDAK dihapus; note + confidence 0.4.

Jalankan dari repo (VPS): TOPWALLET_RUN_ENV=vps python scripts/apply_audit_p3.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

ALLOWED = {"GMGN", "PonsV2BondingCurve"}
OVERRIDES = REPO / "results" / "tag_overrides.json"
LABELS = REPO / "results" / "wallet_labels.json"


def entities_of(entry: dict) -> tuple[set[str], bool]:
    """Kembalikan (himpunan entitas sender, ada MINT_ALLOCATION?)."""
    ents: set[str] = set()
    mint = False
    ev = entry.get("evidence")
    if not isinstance(ev, dict):
        return ents, mint
    for g, e in ev.items():
        if not isinstance(e, dict):
            continue
        if str(e.get("kind") or "").upper().startswith("MINT"):
            mint = True
        for s, sinfo in (e.get("senders") or {}).items():
            if isinstance(sinfo, dict) and sinfo.get("arkham_entity"):
                ents.add(sinfo["arkham_entity"])
    return ents, mint


async def onchain_gate(wallet: str, token: str, sender: str, client) -> bool:
    """True bila ada transfer sender -> wallet utk token tsb (Etherscan)."""
    items = await client.address_token_transfers(wallet, 4, token_filter=token)
    for it in items:
        src = ((it.get("from") or {}).get("hash") or "").lower()
        dst = ((it.get("to") or {}).get("hash") or "").lower()
        if src == sender and dst == wallet:
            return True
    return False


def sender_of(entry: dict, wallet_addr: str) -> tuple[str, str] | None:
    """(sender, token) pertama yang entitasnya di ALLOWED."""
    ev = entry.get("evidence")
    if not isinstance(ev, dict):
        return None
    for g, e in ev.items():
        if not isinstance(e, dict):
            continue
        for s, sinfo in (e.get("senders") or {}).items():
            if isinstance(sinfo, dict) and sinfo.get("arkham_entity") in ALLOWED:
                toks = e.get("tokens") or []
                tok = str(toks[0]).lower() if toks else ""
                return str(s).lower(), tok
    return None


async def main() -> int:
    ov = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    wl = json.loads(LABELS.read_text(encoding="utf-8"))
    wallets_ov = ov.get("wallets", {})
    labels_w = wl.get("wallets", {})

    stats = {"insider_primary": 0, "multi_entity": 0, "mint": 0,
             "airdrop_primary": 0, "entity_lain": 0, "kandidat": 0}
    candidates: dict[str, dict] = {}
    for addr, o in wallets_ov.items():
        ev = o.get("evidence")
        if not isinstance(ev, dict):
            continue
        pr = (labels_w.get(addr) or {}).get("primary_type")
        if pr == "AIRDROP_FARMER":
            stats["airdrop_primary"] += 1
            continue
        if pr != "INSIDER":
            continue
        stats["insider_primary"] += 1
        ents, mint = entities_of(o)
        if mint:
            stats["mint"] += 1
            continue
        if len(ents) >= 2:
            stats["multi_entity"] += 1
            continue
        if len(ents) == 1 and next(iter(ents)) in ALLOWED:
            candidates[addr] = o
        else:
            stats["entity_lain"] += 1

    stats["kandidat"] = len(candidates)
    print("statistik seleksi:", json.dumps(stats))
    g = sum(1 for a, o in candidates.items()
            if entities_of(o)[0] == {"GMGN"})
    p = len(candidates) - g
    print(f"kandidat: GMGN={g} PonsV2={p} (target hakim: 129+4=133)")
    if len(candidates) != 133:
        print("!! JUMLAH TIDAK 133 — DIBATALKAN (tanpa perubahan)")
        return 1

    # gate on-chain
    from src.utils.etherscan_client import make_explorer_client
    client = make_explorer_client()
    passed: list[str] = []
    failed: list[str] = []
    for i, (addr, o) in enumerate(candidates.items(), 1):
        pair = sender_of(o, addr)
        if not pair:
            failed.append(addr)
            continue
        sender, tok = pair
        ok = await onchain_gate(addr, tok, sender, client) if tok else False
        (passed if ok else failed).append(addr)
        if i % 25 == 0:
            print(f"  gate {i}/{len(candidates)}: pass={len(passed)} fail={len(failed)}", flush=True)
    try:
        await client.close()
    except Exception:
        pass
    print(f"gate on-chain: pass={len(passed)} fail={len(failed)}")
    if failed:
        print("  gagal gate (dikecualikan):", failed[:5], "..." if len(failed) > 5 else "")
    if len(passed) < 120:
        print("!! TERLALU SEDIKIT lolos gate — DIBATALKAN (aman)")
        return 1

    # tulis entri override
    now = datetime.now(timezone.utc).isoformat()
    written = 0
    for addr in passed:
        o = candidates[addr]
        o["set_primary"] = "GENERALIST"
        o["remove_labels"] = ["INSIDER"]
        o["add_labels"] = ["GENERALIST"]
        o["confidence"] = {"GENERALIST": 0.4}
        o["note"] = f"audit-night P3 (hakim MODIFY) — didanai platform {sorted(entities_of(o)[0])}; bukti asli dipertahankan; {now}"
        wallets_ov[addr] = o
        written += 1
    ov["generated_at"] = now
    OVERRIDES.write_text(json.dumps(ov, indent=1), encoding="utf-8")
    print(f"override ditulis: {written}")

    # merge ke wallet_labels.json
    from src.analyze.tag_overrides import apply_to_labels_file
    n = apply_to_labels_file()
    print(f"apply_to_labels_file: {n} wallet diperbarui")

    # asersi pasca-apply
    wl2 = json.loads(LABELS.read_text(encoding="utf-8"))
    masih_insider = [a for a in passed
                     if (wl2["wallets"].get(a) or {}).get("primary_type") == "INSIDER"]
    print(f"asersi: {len(masih_insider)} dari {len(passed)} masih INSIDER (harus 0)")
    return 0 if not masih_insider else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
