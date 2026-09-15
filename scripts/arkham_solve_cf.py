"""Solve Cloudflare untuk arkm.com via 2captcha + Webshare proxy (VPS).

Alur:
  1. Ambil 1 proxy Webshare dari PROXY_URLS_FILE (sticky utk sesi ini).
  2. createTask AntiCloudflareTask (2captcha) -> poll getTaskResult.
  3. Dapat cf_clearance + user_agent -> request arkm.com LEWAT PROXY YANG SAMA
     dengan UA yang sama (clearance terikat IP proxy).
  4. Kalau 200 -> simpan clearance (results/arkham_clearance.json) utk dipakai
     scraper label, lalu grep bundle JS utk endpoint internal API.

Jalankan di VPS:  .venv/bin/python scripts/arkham_solve_cf.py
Env: TWOCAPTCHA_KEY, PROXY_URLS_FILE, (opsional ARKHAM_SESSION cookie)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

BASE = "https://arkm.com/visualizer"
OUT = Path("results/arkham_clearance.json")


def load_proxy() -> str | None:
    f = os.getenv("PROXY_URLS_FILE", "")
    if not f or not Path(f).exists():
        return None
    lines = [l.strip() for l in Path(f).read_text().splitlines() if l.strip()]
    return lines[0] if lines else None


def parse_proxy(url: str) -> dict:
    u = urlparse(url if "://" in url else "http://" + url)
    host, port = u.hostname, u.port or 80
    user, pwd = (u.username or ""), (u.password or "")
    # 2captcha butuh host:port tanpa skema + user/pass terpisah
    return {"proxyType": "http", "proxyAddress": host, "proxyPort": port,
            "proxyLogin": user, "proxyPassword": pwd}


def main() -> int:
    key = os.getenv("TWOCAPTCHA_KEY", "").strip()
    if not key:
        print("TWOCAPTCHA_KEY belum di-set di .env")
        return 1
    proxy_url = load_proxy()
    if not proxy_url:
        print("PROXY_URLS_FILE kosong/tidak ada — AntiCloudflareTask wajib proxy")
        return 1
    p = parse_proxy(proxy_url)
    print("proxy:", p["proxyAddress"], p["proxyPort"])

    api = "https://api.2captcha.com"
    task = {"type": "AntiCloudflareTask", "websiteURL": BASE,
            **p}
    r = httpx.post(f"{api}/createTask", json={"clientKey": key, "task": task}, timeout=30)
    j = r.json()
    if j.get("errorId") != 0:
        print("createTask error:", json.dumps(j)[:300])
        return 1
    task_id = j["task"]["taskId"] if isinstance(j.get("task"), dict) else j.get("taskId")
    print("taskId:", task_id)

    ua = None
    cookies = {}
    for _ in range(40):
        time.sleep(5)
        rr = httpx.post(f"{api}/getTaskResult", json={"clientKey": key, "taskId": task_id}, timeout=30)
        rj = rr.json()
        st = rj.get("status")
        if st == "ready":
            sol = rj.get("solution", {})
            cookies = sol.get("cookies", {})
            ua = sol.get("userAgent") or sol.get("user_agent")
            print("solved. cookies:", list(cookies.keys()), "ua:", (ua or "")[:60])
            break
        if rj.get("errorId"):
            print("solve error:", json.dumps(rj)[:300])
            return 1
        print("waiting...", flush=True)
    if not cookies:
        print("timeout menunggu solve")
        return 1

    clearance = cookies.get("cf_clearance", "")
    jar = "; ".join(f"{k}={v}" for k, v in cookies.items())
    sess = os.getenv("ARKHAM_SESSION", "")
    if sess:
        jar += f"; arkham_session={sess}"
    headers = {"User-Agent": ua or "Mozilla/5.0", "Cookie": jar,
               "Accept": "text/html,application/json"}

    with httpx.Client(proxy=proxy_url, headers=headers, timeout=30, follow_redirects=True) as c:
        page = c.get(BASE)
        print("page status:", page.status_code, "len:", len(page.text))
        if page.status_code != 200:
            OUT.write_text(json.dumps({"clearance": clearance, "ua": ua,
                                       "proxy": proxy_url, "cookies": cookies}, indent=1))
            print("clearance disimpan tapi page belum 200 — coba lagi nanti")
            return 1
        chunks = sorted(set(re.findall(r'src="(/_next/static/[^"]+\.js)"', page.text)))
        print("chunks:", len(chunks))
        hits = set()
        for cpath in chunks[:14]:
            try:
                js = c.get("https://arkm.com" + cpath, timeout=30).text
            except Exception:
                continue
            hits |= set(re.findall(
                r'["\'](https?://[^"\']*api[^"\']{0,70}|/api/[^"\']{3,70})["\']', js))
        OUT.write_text(json.dumps({"clearance": clearance, "ua": ua, "proxy": proxy_url,
                                   "cookies": cookies, "endpoints": sorted(hits)}, indent=1))
        print("== kandidat endpoint ==")
        for h in sorted(hits)[:40]:
            print(" ", h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
