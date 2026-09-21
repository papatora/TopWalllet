"""One-shot premise check for the explorer dataset (audit B-E P1).

Reports whether the local DB actually satisfies the explorer premise
(price_points & wallet_scores filled) and where every USD "est." comes from
(historical price series vs static snapshot fallback). Consolidates the facts
each audit round re-derived by hand: DB mtime/size/counts, pipeline
checkpoints, verified-PnL coverage, live /api/dataset meta, VPS reachability.

Usage:
  python scripts/check_premise.py          # local + live API
  python scripts/check_premise.py --vps    # + probe the VPS (SSH paramiko)

Exit 0 = premise met (price_points > 0 AND wallet_scores > 0 locally),
exit 1 = premise NOT met (sparkline / Price chart / USDG calibration are dead
paths; every USD "est." is snapshot-valued). Runbook when exit 1:
  python scripts/fetch_dump.py        # dump + split + MD5-verified download
  python scripts/rebuild_local_db.py  # validated rebuild (warns if points=0)
"""
import gzip
import json
import os
import socket
import sqlite3
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "topwallet.db"
TW = REPO / "results" / "top_wallets_latest.json"


def main() -> int:
    ok = True
    st = DB.stat()
    print(f"[local] {DB.name}: mtime {datetime.fromtimestamp(st.st_mtime)} | "
          f"size {st.st_size:,} byte")

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    tables = ("price_points", "wallet_scores", "swap_events", "wallets", "tokens")
    counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in tables}
    cps = {k: str(v)[:19] for k, v in con.execute("select stage,cursor from pipeline_checkpoints")}
    con.close()
    print(f"[local] counts: {counts}")
    print(f"[local] checkpoints: {cps}")
    if counts["price_points"] == 0 or counts["wallet_scores"] == 0:
        ok = False
        print("[local] PREMIS TIDAK TERPENUHI: sparkline / Price trend / Price chart /")
        print("        kalibrasi USDG adalah dead path; semua USD est. = harga snapshot")
        print("        statis (pricing_mode=snapshot_fallback).")

    if TW.exists():
        tw = json.loads(TW.read_text(encoding="utf-8"))
        print(f"[local] top_wallets_latest.json: generated {str(tw.get('generated_at', '?'))[:10]} | "
              f"total_ranked {tw.get('total_ranked')}")

    try:
        req = urllib.request.urlopen("http://127.0.0.1:8787/api/dataset", timeout=120)
        body = req.read()
        if req.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        d = json.loads(body)
        m = d["meta"]
        realized = sum(1 for e in d.get("ev", {}).values()
                       if (e.get("_score") or {}).get("realized") is not None)
        print(f"[api] pricing_mode={m.get('pricing_mode')} | price_points={m.get('price_points')} | "
              f"priced series/fallback={m.get('priced_series')}/{m.get('priced_fallback')} | "
              f"spark={len(d.get('spark', {}))} token | calibrated={len(m.get('calibrated', []))} | "
              f"ev.realized!=null={realized} wallet")
        if m.get("pricing_mode") in ("snapshot_fallback", "none"):
            ok = False
    except OSError as e:
        print(f"[api] explorer 8787 tidak jalan ({e}) - meta live tidak dicek")

    if "--vps" in sys.argv:
        try:
            s = socket.create_connection((os.getenv("VPS_HOST"),
                                          int(os.getenv("VPS_PORT", "22"))), timeout=10)
            s.close()
            print("[vps] TCP 22 terbuka - mengambil counts...")
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import _vps
            ssh = _vps.connect()
            _, out, _ = ssh.exec_command(
                "cd /opt/topwallet && .venv/bin/python -c \"import sqlite3;"
                "c=sqlite3.connect('file:data/topwallet.db?mode=ro',uri=True);"
                "print(c.execute('select count(*) from price_points').fetchone()[0],"
                "c.execute('select count(*) from wallet_scores').fetchone()[0])\"", timeout=60)
            pp, ws = (out.read().decode().split() + ["?", "?"])[:2]
            print(f"[vps] price_points={pp} wallet_scores={ws}")
            ssh.close()
        except Exception as e:
            print(f"[vps] TIDAK terjangkau: {type(e).__name__}: {str(e)[:90]}")

    print("PREMIS:", "OK" if ok else "BELUM TERPENUHI (exit 1)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
