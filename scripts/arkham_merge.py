"""Merge Arkham harvest results into the explorer's known_entities.json.

arkham_entities.json (harvester output) → filter labeled → map Arkham
category → our entity type → merge into
"Database Local only/html/data/known_entities.json" (existing entries win).
After merging: rebuild the explorer dataset (launcher refresh / start).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "results" / "arkham_entities.json"
DST = REPO / "Database Local only" / "html" / "data" / "known_entities.json"

TYPE_MAP = {
    "Centralized Exchange": "CEX",
    "Decentralized Exchange": "DEX",
    "Bridge": "BRIDGE",
    "Venture Capital": "FUND",
    "Market Maker": "FUND",
    "Smart Money": "OTHER",
    "Deposit Address": "CEX",
    "Withdrawal Address": "CEX",
}


def main() -> int:
    src = json.loads(SRC.read_text(encoding="utf-8")) if SRC.exists() else {}
    doc = json.loads(DST.read_text(encoding="utf-8"))
    entities = doc.setdefault("entities", {})
    added, skipped = 0, 0
    for addr, rec in src.items():
        name = (rec.get("entity") or "").strip()
        if not name or addr in entities:
            if addr in entities:
                skipped += 1
            continue
        label = (rec.get("label") or "").strip()
        display = f"{name}: {label}" if label and label.lower() != name.lower() else name
        etype = TYPE_MAP.get(rec.get("category", ""), "OTHER")
        entities[addr.lower()] = {
            "name": display,
            "type": etype,
            "source": "arkham",
            "verified_at": rec.get("checked_at")
            or datetime.now(timezone.utc).isoformat(),
        }
        added += 1
    doc["_updated"] = datetime.now(timezone.utc).isoformat()
    DST.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"added={added} skipped_existing={skipped} total={len(entities)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
