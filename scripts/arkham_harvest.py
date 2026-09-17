"""Arkham entity harvester — drives the user's logged-in Brave session via CDP.

Flow (user-defined, LOCAL, his account): arkm.com/explorer/address/<addr>
shows the owning entity IN THE PAGE TITLE when one exists:
    "Binance: Hot Wallet (0x28C) | Arkham"      → labeled
    "0x28C6...1d60 | Arkham"                    → unlabeled
    "Just a moment..."                          → Cloudflare challenge

Output: results/arkham_entities.json — {addr: {entity, label, category,
raw_title, checked_at}}, checkpointed atomically after EVERY address so the
run is resumable and a crash loses nothing.

Usage:
  python scripts/arkham_harvest.py --queue results/arkham_queue.json --max 120
  (queue = JSON array of addresses, lowercase)
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "arkham_entities.json"
CDP = "http://127.0.0.1:9222"

TITLE_RE = re.compile(r"^(.*?)\s*\((0x[0-9a-fA-F]{3,6})\)\s*\|\s*Arkham$")
TITLE_PLAIN_RE = re.compile(r"^(0x[0-9a-fA-F]{6,})\s*\|\s*Arkham$")
CATEGORIES = [
    "Centralized Exchange", "Decentralized Exchange", "Market Maker",
    "Smart Money", "Venture Capital", "Deposit Address", "Withdrawal Address",
    "Public Portfolio", "Token Lockup", "Foundation", ".DAO", "DAO",
    " Bridge", "Mining", "Bot", "Scam", "Fraud", "Pig Butchery",
    "Sanctioned", "Stolen Funds", "Mixing", "Service", "Contract Op",
]


def load_out() -> dict:
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_out(data: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(OUT)


def parse_title(title: str, addr: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    m = TITLE_RE.match(title or "")
    if m:
        entity = m.group(1).strip()
        label = ""
        if " : " in entity or ": " in entity:
            parts = re.split(r"\s*:\s+", entity, maxsplit=1)
            entity, label = parts[0].strip(), parts[1].strip()
        return {"entity": entity, "label": label, "raw_title": title,
                "checked_at": now}
    if TITLE_PLAIN_RE.match(title or ""):
        return {"entity": "", "label": "", "raw_title": title,
                "checked_at": now}
    if "just a moment" in (title or "").lower():
        return {"cf": True, "raw_title": title, "checked_at": now}
    # bentuk tak dikenal — simpan mentah supaya bisa dianalisis nanti
    return {"entity": "", "label": "", "raw_title": title, "unknown": True,
            "checked_at": now}


def detect_category(body_head: str) -> str:
    for c in CATEGORIES:
        if c.strip() in body_head:
            return c.strip()
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(REPO / "results" / "arkham_queue.json"))
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--pause-min", type=float, default=2.2)
    ap.add_argument("--pause-max", type=float, default=4.2)
    args = ap.parse_args()

    queue = [a.lower() for a in json.loads(Path(args.queue).read_text())]
    done = load_out()
    todo = [a for a in queue if a not in done][: args.max]
    print(f"queue={len(queue)} done={len(done)} todo={len(todo)}")

    if not todo:
        return 0
    cf_streak = 0
    labeled = 0
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for i, addr in enumerate(todo, 1):
            try:
                page.goto(f"https://arkm.com/explorer/address/{addr}",
                          timeout=40000)
                page.wait_for_load_state("domcontentloaded", timeout=20000)
                page.wait_for_timeout(2500 + random.random() * 1500)
                rec = parse_title(page.title(), addr)
                if rec.get("cf"):
                    # CF "just a moment" sering lolos sendiri — reload 1x
                    time.sleep(9)
                    page.reload(timeout=40000)
                    page.wait_for_load_state("domcontentloaded", timeout=20000)
                    page.wait_for_timeout(4000)
                    rec = parse_title(page.title(), addr)
                if rec.get("cf"):
                    cf_streak += 1
                    print(f"[{i}/{len(todo)}] {addr[:12]} CF-CHALLENGE "
                          f"(streak {cf_streak})", flush=True)
                    if cf_streak >= 5:
                        print("CF 5x beruntun — berhenti, coba lagi nanti")
                        break
                    time.sleep(8)
                    continue
                cf_streak = 0
                if rec.get("entity"):
                    labeled += 1
                    body = page.inner_text("body")[:2500]
                    rec["category"] = detect_category(body)
                    print(f"[{i}/{len(todo)}] {addr[:12]} → {rec['entity']} "
                          f"/ {rec['label'] or '-'} ({rec.get('category', '-')})",
                          flush=True)
                else:
                    print(f"[{i}/{len(todo)}] {addr[:12]} unlabeled", flush=True)
                done[addr] = rec
                save_out(done)
            except Exception as e:
                print(f"[{i}/{len(todo)}] {addr[:12]} ERR {str(e)[:90]}",
                      flush=True)
                time.sleep(5)
            time.sleep(random.uniform(args.pause_min, args.pause_max))

    print(f"SELESAI sesi ini: +{len(todo)} dicek, {labeled} labeled, "
          f"total {len(done)} di {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
