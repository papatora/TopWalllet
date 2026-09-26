"""Goal #3 DIAMOND — atribusi wallet <- CT (X/Twitter) via sesi login.

Metode: playwright headless + cookie auth_token/ct0 (dari .env VPS, hasil
xlogin) -> buka x.com/search?q=<alamat wallet> (tab live) -> kumpulkan
penulis tweet yang menyebut alamat itu -> results/x_attribution.json.

Labeler: wallet teratribusi + rekam jejak terverifikasi (top_wallets_latest
atau skor) -> CT_ATTRIBUTED + DIAMOND via tag_overrides (bukti = link tweet).

Jalankan di VPS: TOPWALLET_RUN_ENV=vps python scripts/x_attribution.py --max 50
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "x_attribution.json"
SEARCH = "https://x.com/search?q={q}&f=live"


def load_env() -> dict:
    env = {}
    for line in open("/opt/topwallet/.env", encoding="utf-8", errors="replace"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def targets(max_n: int) -> list[str]:
    """Wallet target: terverifikasi bagus (top_wallets_latest) + skor tinggi."""
    out: list[str] = []
    tw = REPO / "results" / "top_wallets_latest.json"
    if tw.exists():
        try:
            rows = json.loads(tw.read_text(encoding="utf-8")).get("wallets") or []
            for r in rows:
                a = (r.get("wallet_address") or "").lower()
                if a and r.get("verified", True):
                    out.append(a)
        except Exception:
            pass
    if len(out) < max_n:
        ws = REPO / "results" / "wallet_scores.json"
        if ws.exists():
            try:
                scored = json.loads(ws.read_text(encoding="utf-8"))
                rows = scored.get("wallets") or scored if isinstance(scored, list) else []
                for r in rows[:200]:
                    a = (r.get("wallet_address") or "").lower()
                    sc = r.get("composite_score") or 0
                    if a and sc >= 60 and a not in out:
                        out.append(a)
            except Exception:
                pass
    return out[:max_n]


async def search_wallet(page, wallet: str) -> list[dict]:
    """Kembalikan tweet yang menyebut wallet: [{handle, url, text}]."""
    found: list[dict] = []
    for q in (f'"{wallet}"', f'"{wallet[:12]}"'):
        try:
            await page.goto(SEARCH.format(q=q), wait_until="domcontentloaded",
                            timeout=45_000)
            await page.wait_for_timeout(4_000 + random.randint(0, 2_000))
            items = await page.evaluate("""
() => [...document.querySelectorAll('article')].slice(0, 12).map(a => {
  const links = [...a.querySelectorAll('a[href^="/"]')];
  const status = links.find(l => /\\/status\\/\\d+/.test(l.getAttribute('href') || ''));
  const user = links.find(l => /^\\/[^/]+$/.test(l.getAttribute('href') || ''));
  const text = (a.querySelector('article [data-testid=\"tweetText\"]') || {}).innerText || '';
  return { user: user ? user.getAttribute('href') : null,
           url: status ? status.getAttribute('href') : null, text: text.slice(0, 300) };
}).filter(t => t.user && t.url)
""")
            for t in items:
                t["user"] = (t["user"] or "").lstrip("/")
                t["url"] = "https://x.com" + (t["url"] or "")
                if t["user"] and not any(f["user"] == t["user"] for f in found):
                    found.append(t)
            if found:
                break  # query pertama cukup
        except Exception as e:
            print(f"  search {q[:20]} gagal: {str(e)[:80]}", flush=True)
    return found


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=50)
    args = ap.parse_args()

    env = load_env()
    auth, ct0 = env.get("X_AUTH_TOKEN", ""), env.get("X_CT0", "")
    if not auth:
        print("X_AUTH_TOKEN tidak ada di .env — jalankan x_seed_env.py dulu")
        return 1
    targets_list = targets(args.max)
    print(f"target: {len(targets_list)} wallet", flush=True)

    from playwright.async_api import async_playwright

    results: dict[str, dict] = {}
    try:
        results = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        results = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900})
        await ctx.add_cookies([
            {"name": "auth_token", "value": auth, "domain": ".x.com", "path": "/",
             "httpOnly": True, "secure": True},
            {"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/",
             "secure": True},
        ])
        page = await ctx.new_page()
        # verifikasi sesi
        await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(3_000)
        if "/login" in page.url:
            print("SESI MATI — auth_token ditolak X. Jalankan ulang xlogin.")
            await browser.close()
            return 1
        print("sesi X hidup ✓", flush=True)

        done = 0
        for w in targets_list:
            if w in results and results[w].get("tweets"):
                continue  # resume-safe
            found = await search_wallet(page, w)
            results[w] = {
                "tweets": found[:5],
                "accounts": sorted({t["user"] for t in found}),
                "searched_at": datetime.now(timezone.utc).isoformat(),
            }
            done += 1
            if found:
                print(f"  {w[:12]} → {results[w]['accounts']}", flush=True)
            if done % 10 == 0:
                OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False))
                print(f"  ...{done}/{len(targets_list)} (checkpoint)", flush=True)
            await page.wait_for_timeout(1_500 + random.randint(0, 2_500))
        await browser.close()

    OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False))
    hit = sum(1 for v in results.values() if v.get("tweets"))
    print(f"SELESAI: {hit}/{len(results)} wallet teratribusi → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
