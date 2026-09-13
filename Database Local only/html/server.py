"""Local-only web server for the TopWallet explorer.

    python server.py            -> http://127.0.0.1:8787
    python server.py --port 9000 --open

Binds to 127.0.0.1 only. Serves this folder as static files plus:
    GET  /api/dataset   full dataset JSON (built from the local DB at startup, cached)
    POST /api/rebuild   rebuild the dataset from data/topwallet.db + results/*.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import dataset

ROOT = Path(__file__).resolve().parent
_lock = threading.Lock()
_cache: dict = {"gz": b"", "built": 0.0}


def rebuild() -> dict:
    t0 = time.time()
    data = dataset.build()
    raw = json.dumps(data, separators=(",", ":")).encode()
    with _lock:
        _cache["gz"] = gzip.compress(raw, 6)
        _cache["built"] = time.time()
    m = data["meta"]
    print(f"[dataset] {len(data['wallets'])} wallets · {m['swaps_total']} swaps · "
          f"{len(raw)/1e6:.1f} MB json ({len(_cache['gz'])/1e6:.2f} MB gz) · {time.time()-t0:.1f}s")
    return m


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".mjs": "text/javascript",
                      ".svg": "image/svg+xml", ".md": "text/markdown; charset=utf-8"}

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/api/dataset":
            with _lock:
                body = _cache["gz"]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/rebuild":
            try:
                meta = rebuild()
                payload, code = {"ok": True, "built": meta["built"]}, 200
            except Exception as exc:  # surface the reason to the UI
                payload, code = {"ok": False, "error": str(exc)}, 500
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--open", action="store_true", help="open the browser after start")
    args = ap.parse_args()
    rebuild()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(ROOT)))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"[server] TopWallet explorer running at {url}  (Ctrl+C to stop)")
    if args.open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
