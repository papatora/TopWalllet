"""Discover Arkham web app internal API endpoints from its JS bundles."""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"}

def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

try:
    html = get("https://arkm.com/visualizer").decode("utf-8", "replace")
    chunks = sorted(set(re.findall(r'src="(/_next/static/[^"]+\.js)"', html)))
    print("chunks:", len(chunks))
    hits = set()
    for c in chunks[:12]:
        try:
            js = get("https://arkm.com" + c).decode("utf-8", "replace")
        except Exception:
            continue
        hits |= set(re.findall(r'["\'](https?://[^"\']*api[^"\']{0,60}|/api/[^"\']{3,60})["\']', js))
    for h in sorted(hits)[:40]:
        print(" ", h)
except Exception as e:
    print("ERR:", e)
