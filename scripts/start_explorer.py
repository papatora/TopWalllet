"""Start the local explorer (8787) detached if not running, rebuild dataset,
print a one-line summary. Used by the dynamic workflow via world.run."""
import gzip
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HTML = REPO / "Database Local only" / "html"


def get(url: str, timeout: int = 10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":  # /api/dataset dikirim gzip
            body = gzip.decompress(body)
        return r.status, body


def post(url: str, timeout: int = 300):
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def main() -> int:
    try:
        get("http://127.0.0.1:8787/", timeout=5)
        print("server sudah jalan")
    except OSError:
        py = sys.executable
        subprocess.Popen(
            [py, "server.py", "--port", "8787"],
            cwd=str(HTML),
            creationflags=0x00000008 | 0x00000200,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            time.sleep(2)
            try:
                get("http://127.0.0.1:8787/", timeout=5)
                break
            except OSError:
                pass
        print("server start (hidden)")

    st, body = post("http://127.0.0.1:8787/api/rebuild", timeout=600)
    print("rebuild:", body.decode()[:80])

    st, body = get("http://127.0.0.1:8787/api/dataset", timeout=120)
    d = json.loads(body)
    m = d["meta"]
    print(f"wallets={len(d['wallets'])} tokens={len(d['tokens'])} "
          f"swaps={m['swaps_total']} priced={m.get('priced')} built={m['built'][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
