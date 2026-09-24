"""Goal #5 — Bubblemaps re-verify harvester (sesi login user, mesin lokal).

Buka bubble tiap token Robinhood chain di v2.bubblemaps.io/map?address=<ca>&chain=robinhood
via Brave CDP (sesi login = data subgraph penuh), capture SEMUA response
api.bubblemaps.io (subgraph relasi antar top-holder, token-top-holders,
market), lalu ekstrak grup cluster dari panel Address List (grup resmi
Bubblemaps). Output per token: results/bubblemaps/<ca>.json.

Pemakaian:
  python scripts/bubblemaps_capture.py --tokens results/bubblemaps_token_queue.json --max 12
  (queue = JSON array alamat token lowercase; file sudah ada = skip kecuali --force)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "results" / "bubblemaps"
CDP = "http://127.0.0.1:9222"
MAP_URL = "https://v2.bubblemaps.io/map?address={ca}&chain=robinhood"

PANEL_JS = """
() => {
  const norm = (e) => String(e.innerText || '').split('\\n').join(' | ');
  const all = [...document.querySelectorAll('*')];
  const clusters = all
    .filter((e) => e.children.length < 8 && /Cluster \\d+/.test(e.innerText || '')
                   && String(e.innerText).length < 150)
    .map(norm);
  const holders = all
    .filter((e) => { const t = String(e.innerText || '').trim();
                     return /^#\\d+/.test(t) && t.includes('0x') && t.length < 80; })
    .map(norm);
  return { clusters: [...new Set(clusters)], holders: [...new Set(holders)] };
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", default=str(REPO / "results" / "bubblemaps_token_queue.json"))
    ap.add_argument("--max", type=int, default=12)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--wait-s", type=int, default=16)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    queue = json.load(open(args.tokens))[: args.max]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"queue: {len(queue)} token")

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = next((c for c in ctx.pages if "bubblemaps" in c.url), ctx.new_page())

        for i, ca in enumerate(queue, 1):
            ca = str(ca).lower()
            out = OUT_DIR / f"{ca}.json"
            if out.exists() and not args.force:
                print(f"[{i}/{len(queue)}] {ca[:10]} skip (sudah ada)")
                continue

            cap: dict[str, dict] = {}

            def on_resp(r, _cap=cap):
                u = r.url
                if "api.bubblemaps.io" in u:
                    try:
                        body = r.text()
                    except Exception:
                        body = ""
                    _cap[u] = {"status": r.status, "len": len(body), "body": body}

            pg.on("response", on_resp)
            try:
                pg.goto(MAP_URL.format(ca=ca), wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(args.wait_s * 1000)
                panel = pg.evaluate(PANEL_JS)
            except Exception as e:
                print(f"[{i}/{len(queue)}] {ca[:10]} GAGAL: {str(e)[:120]}")
                pg.remove_listener("response", on_resp)
                continue
            pg.remove_listener("response", on_resp)

            subgraph = next((v for u, v in cap.items() if "subgraph" in u), None)
            holders = next((v for u, v in cap.items() if "token-top-holders" in u), None)
            rec = {
                "token": ca,
                "chain": "robinhood",
                "url": MAP_URL.format(ca=ca),
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "subgraph_len": subgraph["len"] if subgraph else 0,
                "subgraph": json.loads(subgraph["body"]) if subgraph else None,
                "top_holders": json.loads(holders["body"]) if holders else None,
                "api_calls": {u: v["len"] for u, v in cap.items()},
                "panel_clusters": panel.get("clusters", []),
                "panel_holders": panel.get("holders", []),
            }
            out.write_text(json.dumps(rec, indent=1))
            n_rel = len(rec["subgraph"] or [])
            print(f"[{i}/{len(queue)}] {ca[:10]} OK — relasi={n_rel}, "
                  f"panel cluster={len(rec['panel_clusters'])}, holder panel={len(rec['panel_holders'])}")

    print("SELESAI — hasil di results/bubblemaps/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
