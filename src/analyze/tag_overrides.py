"""Apply on-chain verification verdicts on top of classifier output.

The classifier (wallet_classifier.py) derives labels from LOCAL swap_events
only — a coverage hole makes a trader look like an INSIDER ("sells a token
it never bought"). scripts/reverify_tags.py re-checks every such wallet
against raw on-chain transfers + Swap logs and writes
results/tag_overrides.json. This module merges those verdicts back into
results/wallet_labels.json so every consumer (explorer dataset, grouping,
scoring exports) sees the corrected category.

Override file format:
{
  "generated_at": ...,
  "wallets": {
    "<address>": {
      "set_primary": "AIRDROP_FARMER",       # new primary type
      "remove_labels": ["INSIDER"],
      "add_labels": ["AIRDROP_FARMER", "PHISHING_TARGET"],
      "confidence": {"<label>": 0.9},
      "evidence": {"<label>": {...on-chain proof...}},
      "note": "..."
    }, ...
  }
}
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def load_overrides(results_dir: Path) -> dict:
    path = results_dir / "tag_overrides.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("wallets", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def apply_overrides(labels_payload: dict, overrides: dict) -> tuple[dict, int]:
    """Mutate-and-return the labels payload with on-chain verdicts applied.

    Returns (payload, wallets_changed). Wallets in the override file that are
    absent from the labels payload are ignored (they will re-surface after the
    next classification pass if the classifier still flags them).
    """
    if not overrides:
        return labels_payload, 0
    wallets = labels_payload.setdefault("wallets", {})
    changed = 0
    for addr, ov in overrides.items():
        entry = wallets.get(addr)
        if not entry or not isinstance(ov, dict):
            continue
        labels = [l for l in entry.get("labels", []) if l not in set(ov.get("remove_labels", []))]
        for add in ov.get("add_labels", []):
            if add not in labels:
                labels.append(add)
        entry["labels"] = labels
        if ov.get("set_primary"):
            entry["primary_type"] = ov["set_primary"]
        elif entry.get("primary_type") in set(ov.get("remove_labels", [])):
            entry["primary_type"] = labels[0] if labels else "GENERALIST"
        ev = entry.setdefault("evidence", {})
        for label, proof in (ov.get("evidence") or {}).items():
            merged = dict(proof)
            merged["onchain_verified"] = True
            merged["verified_at"] = ov.get("verified_at") or datetime.now(timezone.utc).isoformat()
            ev[label] = merged
        conf = entry.setdefault("confidence", {})
        for label, c in (ov.get("confidence") or {}).items():
            conf[label] = c
        if ov.get("note"):
            entry["override_note"] = ov["note"]
        changed += 1
    labels_payload["tag_overrides_applied"] = {
        "wallets": changed,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }
    return labels_payload, changed


def apply_to_labels_file(results_dir: Path | None = None) -> int:
    """Rewrite results/wallet_labels.json with overrides merged in.

    Called by the pipeline right after classification so every cycle keeps
    the on-chain-verified positions. Returns wallets changed (0 = no-op).
    """
    from config.settings import settings

    rd = Path(results_dir) if results_dir else Path(settings.results_dir)
    labels_path = rd / "wallet_labels.json"
    if not labels_path.exists():
        return 0
    overrides = load_overrides(rd)
    if not overrides:
        return 0
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    payload, changed = apply_overrides(payload, overrides)
    if changed:
        labels_path.write_text(
            json.dumps(payload, indent=1, sort_keys=False) + "\n", encoding="utf-8"
        )
    return changed
