"""Arkham label extraction — tag CEX/bridge/fund untuk wallet kita.

Kebutuhan: ARKHAM_API_KEY dari arkham.io (endpoint resmi api.arkhamintelligence.com,
header x-api-key). Cookie web TIDAK cukup — backend Arkham ada di balik Cloudflare
dan kebijakan TopWallet melarang bypass CF (lihat SECURITY_POLICY.md).

Cara kerja (setelah key terpasang di .env):
  1. Ambil daftar wallet prioritas (top swaps + top ranked) dari DB lokal.
  2. Untuk tiap wallet, minta data transfer/entity Arkham, kumpulkan label
     entity (CEX / bridge / fund / dls.).
  3. Merge ke Database Local only/html/data/known_entities.json — visualizer
     langsung menampilkan ikon & nama entitas di node yang menyebar ke sana.

Jalankan: python scripts/arkham_labels.py --top 500
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KNOWN = REPO / "Database Local only" / "html" / "data" / "known_entities.json"
API = "https://api.arkhamintelligence.com"


def top_wallets(db_path: Path, limit: int) -> list[str]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = con.execute(
        "select wallet_address, count(*) n from swap_events "
        "group by wallet_address order by n desc limit ?", (limit,)).fetchall()
    con.close()
    return [r[0] for r in rows]


def fetch_labels(wallet: str, key: str, session) -> dict | None:
    # endpoint resmi: transfers wallet -> dari sana Arkham expose entity counterparty
    try:
        r = _get(
            f"{API}/transfers",
            {"x-api-key": key}, {"base": wallet, "chains": "robinhood", "limit": 50})
        if r.status_code == 429:
            time.sleep(3)
            return None
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=500)
    args = ap.parse_args()
    key = os.getenv("ARKHAM_API_KEY", "").strip()
    if not key:
        print("ARKHAM_API_KEY belum di-set di .env.")
        print("Daftar akses API Arkham (gratis berbasis review) lalu isi key.")
        print("Sementara: tambah manual alamat CEX/bridge ke known_entities.json — visualizer langsung render.")
        return 1

    import httpx

    session = httpx.Client(timeout=25.0)

    def _get(url: str, headers: dict, params: dict):
        return session.get(url, headers=headers, params=params)
    known = json.loads(KNOWN.read_text(encoding="utf-8"))
    known.setdefault("entities", {})
    wallets = top_wallets(REPO / "data" / "topwallet.db", args.top)
    found = 0
    for i, w in enumerate(wallets, 1):
        data = fetch_labels(w, key, session)
        if not data:
            continue
        # struktur respons Arkham berisi counterparty + entity name/type
        for tx in data if isinstance(data, list) else data.get("transfers", []):
            for side in ("fromEntity", "toEntity"):
                ent = tx.get(side) or {}
                name, typ = ent.get("name"), (ent.get("type") or "").upper()
                addr = (tx.get(side.replace("Entity", "Address")) or {}).get("address")
                if name and typ and addr and typ in ("CEX", "BRIDGE", "FUND", "DEX"):
                    known["entities"][addr.lower()] = {"name": name, "type": typ}
                    found += 1
        if i % 25 == 0:
            print(f"{i}/{len(wallets)} wallets scanned, entities found: {found}", flush=True)
        time.sleep(0.4)  # sopan terhadap rate limit
    KNOWN.write_text(json.dumps(known, indent=2), encoding="utf-8")
    print(f"selesai: {found} entity labels disimpan ke known_entities.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
