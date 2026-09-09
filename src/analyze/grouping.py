"""Generate deployer registry + funding sources grouping from existing data.

Reads: wallet_labels.json, funding_forensics.json, funder_clusters.json,
top_wallets_latest.json (all in results/).

Outputs:
  results/deployer_registry.md   — wallet grouped by "is this a deployer?"
  results/funding_sources.md     — funder → funded wallets → clusters
  results/deployer_registry.json — machine-readable
  results/funding_sources.json

Run:  python -m src.analyze.grouping  (or on VPS via cron)
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from config.settings import settings


def load(name):
    p = os.path.join(settings.results_dir, name)
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def build_deployer_registry(labels: dict, forensics: dict, top: dict) -> dict:
    """Group wallets by dev-related signals."""
    registry = {"serial_ruggers": [], "devs": [], "insiders": [], "snipers": [], "clean_traders": []}
    for w in labels.get("wallets", {}).values() if isinstance(labels, dict) else []:
        pass  # wallet_labels.json format: {wallet: {primary_type, labels[], evidence}}
    for addr, info in (labels.get("wallets") or {}).items():
        ptype = info.get("primary_type", "")
        entry = {"wallet": addr, "type": ptype, "labels": info.get("labels", []),
                 "confidence": info.get("confidence")}
        if ptype == "DEV_SERIAL_RUGGER":
            registry["serial_ruggers"].append(entry)
        elif ptype == "DEV":
            registry["devs"].append(entry)
        elif "INSIDER" in " ".join(info.get("labels", [])):
            registry["insiders"].append(entry)
        elif "SNIPER" in info.get("labels", []):
            registry["snipers"].append(entry)
    return registry


def build_funding_sources(forensics: dict, clusters: dict) -> dict:
    """Group wallets by their first funder."""
    funders: dict[str, list] = {}
    for w in (forensics or {}).get("wallets", []):
        f = w.get("funding", {})
        funder = f.get("funder")
        if not funder:
            continue
        funders.setdefault(funder, []).append({
            "wallet": w["wallet"], "rank": w.get("rank"),
            "amount_eth": f.get("amount_eth"), "class": w.get("funding_class"),
        })
    # annotate with cluster info
    result = {"funders": {}}
    for funder, wallets in sorted(funders.items(), key=lambda kv: -len(kv[1])):
        cluster_ids = set()
        for c_id, c_data in (clusters or {}).items():
            if funder in str(c_data):
                cluster_ids.add(c_id)
        result["funders"][funder] = {
            "funded_count": len(wallets),
            "cluster": list(cluster_ids) if cluster_ids else None,
            "wallets": wallets,
        }
    return result


def render_deployer_md(registry: dict) -> str:
    lines = ["# Deployer Registry", ""]
    for key, title in [("serial_ruggers", "🔴 SERIAL RUGGERS"), ("devs", "🟡 DEVS"),
                       ("insiders", "🟠 INSIDERS"), ("snipers", "🔵 SNIPERS"),
                       ("clean_traders", "🟢 CLEAN TRADERS")]:
        entries = registry.get(key, [])
        lines.append(f"\n## {title} ({len(entries)})\n")
        for e in entries:
            lines.append(f"- `{e['wallet']}` — {e['type']} — confidence {e.get('confidence', 'N/A')}")
    return "\n".join(lines)


def render_funding_md(funding: dict) -> str:
    lines = ["# Funding Sources", ""]
    for funder, info in sorted(funding.get("funders", {}).items(),
                               key=lambda kv: -kv[1]["funded_count"]):
        lines.append(f"\n## Funder `{funder[:16]}…` — {info['funded_count']} wallets")
        if info.get("cluster"):
            lines.append(f"   **Clusters:** {', '.join(info['cluster'])}")
        for w in info["wallets"][:5]:
            lines.append(f"   - {w['wallet'][:16]}… rank #{w.get('rank', '?')} {w.get('class', '')}")
    return "\n".join(lines)


def main():
    labels = load("wallet_labels.json") or {"wallets": {}}
    forensics = load("funding_forensics.json")
    clusters = load("funder_clusters.json")

    registry = build_deployer_registry(labels, forensics, clusters)
    funding = build_funding_sources(forensics, clusters)

    (os.path.join(settings.results_dir, "deployer_registry.json")
     and open(os.path.join(settings.results_dir, "deployer_registry.json"), "w").write(json.dumps(registry, indent=1)))
    (os.path.join(settings.results_dir, "funding_sources.json")
     and open(os.path.join(settings.results_dir, "funding_sources.json"), "w").write(json.dumps(funding, indent=1)))

    with open(os.path.join(settings.results_dir, "deployer_registry.md"), "w", encoding="utf-8") as f:
        f.write(render_deployer_md(registry))
    with open(os.path.join(settings.results_dir, "funding_sources.md"), "w", encoding="utf-8") as f:
        f.write(render_funding_md(funding))

    print(f"deployer registry: {sum(len(registry.get(k, [])) for k in registry)} entries")
    print(f"funding sources: {len(funding.get('funders', {}))} funders")


if __name__ == "__main__":
    main()
